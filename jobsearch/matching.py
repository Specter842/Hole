"""Keyword / tag relevance matching between a job description and stored achievements.

Deliberately dependency-free and explainable. Every score traces back to the
specific terms that produced it, which matters because the tailoring step is
only allowed to write about achievements that are actually in the database --
and because the honest answer is sometimes "your profile does not cover this".

Phase 2 can swap this out for embeddings behind the same `score_achievements`
signature.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Sequence

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")
# Clause boundaries. A sentence-ending period splits, but a period inside a token
# does not, so "node.js" and "3.5" survive intact.
CLAUSE_SPLIT_RE = re.compile(r"[,;:!?()\[\]{}|\n\r\t]+|\.(?=\s|$)|\s+[-–—]\s+")
SECTION_HEADING_RE = re.compile(
    r"(requirement|qualification|what you.{0,15}(bring|have|need)|must have|"
    r"skills|experience with|you should|we.{0,5}re looking for|about you|nice to have)",
    re.IGNORECASE,
)

# Field weights: a tag the candidate explicitly claimed is stronger evidence
# than a word that happens to appear in a paragraph. Keys are the neutral field
# names of a MatchDoc, so the same scorer works on an experience, a project, a
# bullet, or a certification.
FIELD_WEIGHTS: dict[str, float] = {
    "tags": 3.0,
    "title": 2.0,
    "field": 2.0,
    "impact": 1.5,
    "organization": 1.0,
    "text": 1.0,
}

PHRASE_BONUS = 1.6  # a matched two-word phrase is worth more than two loose words

# Written out rather than pulled from a library so the behaviour is inspectable.
# These are the surface forms; the stemmed variants get folded in below, because
# tokens are stemmed before they are looked up here.
RAW_STOPWORDS = {
    "a", "about", "above", "across", "after", "again", "against", "all", "also",
    "am", "an", "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "cannot", "could",
    "did", "do", "does", "doing", "done", "down", "during", "each", "either",
    "else", "etc", "even", "ever", "every", "few", "for", "from", "further",
    "get", "had", "has", "have", "having", "he", "her", "here", "hers", "him",
    "his", "how", "however", "i", "if", "in", "into", "is", "it", "its", "just",
    "like", "make", "makes", "many", "may", "me", "might", "more", "most", "much",
    "must", "my", "no", "nor", "not", "now", "of", "off", "on", "once", "one",
    "only", "or", "other", "others", "ought", "our", "ours", "out", "over", "own",
    "per", "same", "shall", "she", "should", "since", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "upon", "us",
    "use", "used", "using", "very", "via", "was", "we", "well", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with",
    "within", "without", "would", "you", "your", "yours",
}

# Job-posting boilerplate. These words appear in every posting, so they carry no
# signal about whether a particular achievement is relevant.
RAW_BOILERPLATE = {
    "ability", "applicant", "application", "apply", "background", "based",
    "benefits", "candidate", "career", "company", "compensation", "culture",
    "day", "dental", "description", "diverse", "diversity", "employee",
    "employer", "employment", "equal", "excellent", "experience", "familiarity",
    "full", "great", "help", "hire", "hiring", "inclusion", "inclusive", "job",
    "join", "knowledge", "level", "life", "location", "looking", "medical",
    "member", "mission", "office", "opportunity", "org", "organization", "paid",
    "people", "plus", "position", "preferred", "proficiency", "qualification",
    "qualifications", "range", "remote", "requirement", "requirements", "role",
    "salary", "seeking", "senior", "skill", "skills", "solid", "strong",
    "successful", "team", "time", "top", "understanding", "vision", "want",
    "we", "work", "working", "world", "year", "years",
    # benefits / perks blocks
    "bonus", "competitive", "dental", "equity", "flexible", "holiday", "hybrid",
    "insurance", "onsite", "perk", "pto", "unlimited",
    # posting connective tissue
    "benefit", "bring", "build", "building", "comfortable", "duty", "end",
    "exposure", "ideally", "include", "including", "measurable", "modern",
    "nice", "overview", "own", "partner", "production", "raise", "record",
    "report", "responsibility", "track",
}

# Small, safe 1:1 normalisations so obvious variants match each other.
ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "psql": "postgresql",
    "gcp": "googlecloud",
    "node.js": "nodejs",
    "node": "nodejs",
    "react.js": "react",
    "reactjs": "react",
    "next.js": "nextjs",
    "vue.js": "vue",
    "ci/cd": "cicd",
    "restful": "rest",
    "a/b": "ab",
}


DOUBLED_CONSONANT_RE = re.compile(r"^(.*?)([bdfglmnprt])\2$")


def _undouble(stem: str) -> str:
    """'runn' -> 'run', 'shipp' -> 'ship'."""
    match = DOUBLED_CONSONANT_RE.match(stem)
    return match.group(1) + match.group(2) if match and len(stem) > 3 else stem


def _stem(word: str) -> str:
    """Light suffix stripping, applied to both sides so it stays symmetric.

    Not linguistically correct and not trying to be. It only has to make the
    posting's "Design and build" reach the profile's "Designed the idempotency
    layer" -- without a stemmer that pair silently reads as a missing skill.
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return _undouble(word[:-3])
    if len(word) > 4 and word.endswith("ed"):
        return _undouble(word[:-2])
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is", "as")):
        return word[:-1]
    return word


def _with_stems(words: set[str]) -> frozenset[str]:
    """Keep both surface and stemmed forms so lookups work whichever arrives."""
    return frozenset(words | {_stem(w) for w in words})


STOPWORDS = _with_stems(RAW_STOPWORDS)
BOILERPLATE = _with_stems(RAW_BOILERPLATE)


def normalize(word: str) -> str:
    word = word.strip(".-")
    word = ALIASES.get(word, word)
    return _stem(word)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, aliases applied, stopwords kept (bigrams need them dropped later)."""
    if not text:
        return []
    lowered = text.lower().replace("/", " ").replace("_", " ")
    return [normalize(t) for t in TOKEN_RE.findall(lowered) if normalize(t)]


def content_tokens(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]


def _phrase_pairs(text: str) -> list[tuple[str, str]]:
    """(normalized, as-written) two-word phrases from adjacent content words.

    Requiring raw adjacency and staying inside a clause is what keeps junk like
    "end end" (from "end to end") or "scale including" (across a comma) from
    being treated as a real requirement.
    """
    out: list[tuple[str, str]] = []
    for clause in CLAUSE_SPLIT_RE.split(text.lower().replace("/", " ").replace("_", " ")):
        if not clause.strip():
            continue
        raw = TOKEN_RE.findall(clause)
        norm = [normalize(t) for t in raw]
        for (first, second), (raw_first, raw_second) in zip(
            zip(norm, norm[1:]), zip(raw, raw[1:])
        ):
            if not first or not second:
                continue
            if first in STOPWORDS or second in STOPWORDS:
                continue
            if len(first) < 2 or len(second) < 2:
                continue
            out.append((f"{first} {second}", f"{raw_first} {raw_second}"))
    return out


def phrases(text: str) -> list[str]:
    return [normalized for normalized, _ in _phrase_pairs(text)]


def surface_forms(text: str) -> dict[str, str]:
    """Map each normalized term back to how it was actually written.

    Stemming turns "tuning" into "tun" and "Kubernetes" into "kubernete", which
    is fine for matching and unreadable in a report. Gap lists are rendered
    through this so the user sees the posting's own words.
    """
    surfaces: dict[str, str] = {}
    lowered = text.lower().replace("/", " ").replace("_", " ")
    for clause in CLAUSE_SPLIT_RE.split(lowered):
        for raw in TOKEN_RE.findall(clause):
            normalized = normalize(raw)
            if normalized and normalized not in surfaces:
                surfaces[normalized] = raw.strip(".-")
    for normalized, raw in _phrase_pairs(text):
        surfaces.setdefault(normalized, raw)
    return surfaces


def _terms_from(text: str) -> set[str]:
    """Unigrams + adjacent-content phrases, matching how the posting is tokenized."""
    return set(content_tokens(text)) | set(phrases(text))


@dataclass
class MatchDoc:
    """One scoreable thing from the profile graph.

    `fields` uses the neutral names in FIELD_WEIGHTS. `payload` carries the node
    itself back to the caller so retrieval can act on what matched.
    """

    key: tuple[str, int]
    label: str
    fields: dict[str, Any] = dc_field(default_factory=dict)
    payload: Any = None

    @property
    def kind(self) -> str:
        return self.key[0]

    @property
    def id(self) -> int:
        return self.key[1]


def record_terms(fields: dict[str, Any]) -> dict[str, float]:
    """Map every term in a record to the weight of the strongest field it appears in."""
    weighted: dict[str, float] = {}

    def absorb(text: str | None, weight: float) -> None:
        if not text:
            return
        for term in _terms_from(str(text)):
            if weighted.get(term, 0.0) < weight:
                weighted[term] = weight

    for name, weight in FIELD_WEIGHTS.items():
        value = fields.get(name)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = " . ".join(str(item) for item in value)
        absorb(str(value), weight)
    return weighted


def compute_idf(docs: Sequence[dict[str, float]]) -> dict[str, float]:
    """Terms that appear in every achievement say nothing about which one to pick."""
    n = max(len(docs), 1)
    df: dict[str, int] = {}
    for doc in docs:
        for term in doc:
            df[term] = df.get(term, 0) + 1
    return {term: math.log(1 + n / (1 + count)) + 0.25 for term, count in df.items()}


def job_description_terms(job_description: str) -> dict[str, float]:
    """Term -> importance within this posting.

    Importance combines how often the term appears with whether it appeared under
    a requirements-style heading.
    """
    weights: dict[str, float] = {}
    section_weight = 1.0
    for line in job_description.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < 90 and SECTION_HEADING_RE.search(stripped):
            section_weight = 1.5
        elif len(stripped) < 60 and stripped.endswith(":"):
            section_weight = 1.0

        for term in content_tokens(stripped):
            weights[term] = weights.get(term, 0.0) + section_weight
        for term in phrases(stripped):
            weights[term] = weights.get(term, 0.0) + section_weight * PHRASE_BONUS
    return weights


def _covers(term: str, covered: set[str]) -> bool:
    """A phrase counts as covered when it matches, or when both halves do.

    "high-throughput python services" should not read as a missing requirement
    just because the profile says "python service" in a different word order.
    """
    if term in covered:
        return True
    parts = term.split(" ")
    return len(parts) > 1 and all(part in covered for part in parts)


@dataclass
class Match:
    doc: MatchDoc
    score: float
    relative: float
    matched_terms: list[str] = dc_field(default_factory=list)

    @property
    def key(self) -> tuple[str, int]:
        return self.doc.key

    @property
    def id(self) -> int:
        return self.doc.id

    @property
    def kind(self) -> str:
        return self.doc.kind

    @property
    def label(self) -> str:
        return self.doc.label

    @property
    def payload(self) -> Any:
        return self.doc.payload


def score_records(job_description: str, docs: Sequence[MatchDoc]) -> list[Match]:
    """Rank profile records against a posting. Highest score first.

    Relative scores are normalised within the batch, so score experiences
    against experiences and bullets against bullets -- comparing across kinds
    would make a one-line certification look as important as a four-year job.
    """
    if not docs:
        return []

    term_maps = [record_terms(doc.fields) for doc in docs]
    idf = compute_idf(term_maps)
    jd_weights = job_description_terms(job_description)

    matches: list[Match] = []
    for doc, terms in zip(docs, term_maps):
        score = 0.0
        contributions: list[tuple[float, str]] = []
        for term, field_weight in terms.items():
            if term not in jd_weights:
                continue
            value = idf.get(term, 1.0) * field_weight * math.log(1 + jd_weights[term])
            if " " in term:
                value *= PHRASE_BONUS
            score += value
            contributions.append((value, term))
        contributions.sort(reverse=True)
        matches.append(
            Match(
                doc=doc,
                score=round(score, 4),
                relative=0.0,
                matched_terms=[term for _, term in contributions[:12]],
            )
        )

    best = max((m.score for m in matches), default=0.0)
    for m in matches:
        m.relative = round(100.0 * m.score / best, 1) if best > 0 else 0.0

    matches.sort(key=lambda m: (-m.score, m.id))
    return matches


def select_matches(
    matches: Sequence[Match],
    *,
    top: int = 8,
    min_relative: float = 15.0,
) -> list[Match]:
    """Keep the strongest matches, dropping anything that barely registered."""
    kept = [m for m in matches if m.score > 0 and m.relative >= min_relative]
    return list(kept[:top])


def coverage_gaps(
    job_description: str,
    docs: Sequence[MatchDoc],
    *,
    limit: int = 15,
    company: str | None = None,
) -> list[str]:
    """Posting terms with no supporting evidence anywhere in the profile.

    This is what lets the tool say "these requirements aren't covered" instead
    of letting the model paper over the gap.
    """
    jd_weights = job_description_terms(job_description)
    covered: set[str] = set()
    for doc in docs:
        covered |= set(record_terms(doc.fields))
    # The employer's own name is not a skill gap.
    ignored = set(content_tokens(company or ""))

    candidates: list[tuple[float, str]] = []
    for term, weight in jd_weights.items():
        if term in covered:
            continue
        parts = term.split(" ")
        if any(p in BOILERPLATE or p in STOPWORDS or p in ignored or len(p) < 3 for p in parts):
            continue
        # A phrase is only a gap if neither half is evidenced -- "comfortable with
        # Docker" is not missing when Docker is all over the profile.
        if len(parts) > 1 and any(p in covered for p in parts):
            continue
        if term.replace(".", "").isdigit():
            continue
        if weight < 1.4:  # mentioned once, in passing
            continue
        candidates.append((weight * (PHRASE_BONUS if " " in term else 1.0), term))

    candidates.sort(reverse=True)
    surfaces = surface_forms(job_description)
    seen_words: set[str] = set()
    gaps: list[str] = []
    for _, term in candidates:
        # Prefer the phrase over its component words, and don't repeat either.
        words = set(term.split(" "))
        if words & seen_words:
            continue
        seen_words |= words
        gaps.append(surfaces.get(term, term))
        if len(gaps) >= limit:
            break
    return gaps


def _is_heading_line(line: str) -> bool:
    """Title-cased headings capitalize everything, so they prove nothing."""
    stripped = line.strip()
    if not stripped or stripped[0] in "-*•":
        return False
    words = [w for w in re.findall(r"[A-Za-z][\w'&+#.-]*", stripped) if len(w) > 1]
    if not words or len(words) > 8:
        return False
    capitalized = sum(1 for w in words if w[0].isupper())
    return capitalized / len(words) >= 0.6


def claimlike_terms(job_description: str, terms: Sequence[str]) -> list[str]:
    """Narrow a gap list to things a resume could falsely *claim*.

    "PCI DSS", "Terraform", "CI/CD" are credentials and technologies -- writing
    one you cannot back up is a lie. "backend" and "platform" are ordinary words
    that belong in a summary sentence, and flagging them would bury the real
    findings in noise.

    The signal is how the posting itself writes the term: a name appears
    capitalized mid-sentence, an ordinary noun does not.
    """
    lines = job_description.splitlines()
    keep: list[str] = []
    for term in terms:
        if " " in term or any(not ch.isalpha() for ch in term):
            keep.append(term)  # phrases and things like ci/cd, c++, .net
            continue
        pattern = re.compile(r"\b" + re.escape(term) + r"\w*", re.IGNORECASE)
        for line in lines:
            if _is_heading_line(line):
                continue
            for match in pattern.finditer(line):
                if not match.group(0)[0].isupper():
                    continue
                prefix = line[: match.start()].rstrip()
                if not prefix or prefix[-1] in ".!?:;":
                    continue  # sentence start: capitalization is not informative
                keep.append(term)
                break
            else:
                continue
            break
    return keep


# How many of a posting's terms the fit score is measured against. Real postings
# carry 250-350 emphasized terms once the company backstory, team blurb, and
# benefits are counted -- scoring against all of them means posting length, not
# candidate suitability, dominates the number. Ranking by weight and keeping the
# top slice makes the score comparable between a terse 800-character posting and
# a 5,000-character one.
FIT_TERM_LIMIT = 40


def fit_score(job_description: str, docs: Sequence[MatchDoc]) -> float:
    """0-100: how much of what this posting most insists on the profile covers.

    Comparable across postings, so the autonomous policy can use it as a
    threshold for "apply without asking".
    """
    jd_weights = job_description_terms(job_description)
    covered: set[str] = set()
    for doc in docs:
        covered |= set(record_terms(doc.fields))

    ranked: list[tuple[float, str]] = []
    for term, weight in jd_weights.items():
        parts = term.split(" ")
        if any(p in BOILERPLATE or p in STOPWORDS or len(p) < 3 for p in parts):
            continue
        if term.replace(".", "").isdigit():
            continue
        # Mentioned once, in passing, outside any requirements section.
        if weight < 1.5:
            continue
        ranked.append((weight * (PHRASE_BONUS if " " in term else 1.0), term))

    ranked.sort(reverse=True)
    top = ranked[:FIT_TERM_LIMIT]
    if not top:
        return 0.0
    total = sum(weight for weight, _ in top)
    hit = sum(weight for weight, term in top if _covers(term, covered))
    return round(100.0 * hit / total, 1) if total > 0 else 0.0


def matched_term_summary(matches: Iterable[Match]) -> list[str]:
    seen: list[str] = []
    for m in matches:
        for term in m.matched_terms:
            if term not in seen:
                seen.append(term)
    return seen
