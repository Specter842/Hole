# AI Job Search Platform

Your whole career history as a queryable graph, and resumes generated from it —
never from a document you have to keep rewriting.

**Status:** profile graph, ingestion, retrieval, and tailoring all work. The autonomous
pipeline (sourcing → policy → dispatch → scheduler) is next.

## The idea

A LinkedIn profile isn't a document, it's a structure: you hold positions at
organizations, accomplishments belong to a specific position, and skills point back at
where you used them. This stores your history that way, so generating a resume is a
*query* — pick the positions that matter for this posting, pick the strongest bullets
under each, list only the skills you can prove — rather than an exercise in rewriting a
page and hoping nothing drifted.

Two rules make it trustworthy:

**Selection is deterministic; only phrasing is generative.** Code decides which
positions appear, which bullets sit under them, and which skills may be claimed. The
model receives that plan and writes prose for it. It never chooses what is true.

**A skill with no evidence cannot reach a resume.** Every skill links to the experience,
project, accomplishment, or certification that demonstrates it. Import 40 skills from
LinkedIn and 12 will be unevidenced — those 12 stay off every resume until you attach a
real record, no matter how loudly a posting asks for them.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Get a free Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) —
no card required — and set it in the shell:

```bash
$env:GEMINI_API_KEY = "..."
```

or copy `.env.example` to `.env` and put it there (`.env` is gitignored).

Gemini is the default because the free tier costs nothing and one pipeline run can
tailor a dozen applications. It is **rate-limited**, not unlimited: there are per-minute
and per-day request caps. If you'd rather use Claude, set `provider = "anthropic"` under
`[llm]` in `config.toml` and supply `ANTHROPIC_API_KEY` instead — both paths are
maintained and tested.

```bash
python -m jobsearch config
```

confirms which provider is active and whether it can see a key. Then:

```bash
python -m jobsearch init
```

## Getting your history in

### LinkedIn export (best starting point)

In LinkedIn: **Settings → Data Privacy → Get a copy of your data → Download larger
data archive.** It arrives by email as a zip of CSVs. This is your own data delivered by
LinkedIn — no scraping, no automated access, nothing that puts your account at risk.

```bash
python -m jobsearch import linkedin ~/Downloads/Basic_LinkedInDataExport.zip
```

Reads Positions, Education, Skills, Projects, Certifications, Honors, Publications,
Languages, Volunteering, Recommendations, and your contact details. Bullet-formatted
position descriptions are split into individual accomplishments. Rows land **verified**,
because no model touched them.

### Documents — resume, reviews, notes, anything

```bash
python -m jobsearch import document ~/Documents/resume.pdf
```

```bash
python -m jobsearch import document ~/Documents/2024-review.docx --hint "my 2024 performance review"
```

PDF, DOCX, TXT, MD, CSV, JSON, HTML. A model extracts structured entities under an
extraction prompt as strict as the generation one — nothing inferred, nothing
"improved", null wherever the document is silent. These rows land **unverified** and
show up in `review` until you confirm them.

### Everything at once

Drop it all in a folder and:

```bash
python -m jobsearch import inbox inbox/
```

Zips are treated as LinkedIn exports, everything else as documents. One failure doesn't
stop the run.

### Then link and review

```bash
python -m jobsearch link
```

Scans your real records for literal mentions of each skill and attaches evidence where it
finds them. It will not guess: skills it can't ground stay unevidenced and get listed so
you can attach them yourself or add the accomplishment that proves them.

```bash
python -m jobsearch review
```

Lists everything a model extracted. `review confirm experiences` accepts a whole table,
`review confirm experiences 4` accepts one row, `rm experiences 4` throws one out.

Made a mess? `sources` lists every import and `sources undo <id>` deletes every row it
created.

## Using it

```bash
python -m jobsearch profile
```

Renders the graph — positions with their accomplishments and dates, projects, education,
certifications, and your skills sorted by how much evidence backs each one. Unevidenced
skills are called out separately.

```bash
python -m jobsearch match --job-file posting.txt --company "Meridian Systems"
```

No API call. Shows the fit score, which positions were selected and why, which bullets
were chosen under each, the skills it's allowed to claim, and — the useful part — what
the posting asks for that nothing in your history supports.

```bash
python -m jobsearch tailor --job-file posting.txt --company Acme --role "Backend Engineer"
```

| Flag | Effect |
| --- | --- |
| `--dry-run` | Print the plan and the exact prompt. No API call. |
| `--verified-only` | Use only rows you've confirmed. |
| `--max-experiences` / `--max-bullets` | Resume shape (defaults 4 and 4). |
| `--min-score` | Relevance floor, % of the best match (default 12). |
| `--print` | Echo the documents to the terminal. |
| `--no-record` | Don't log an `applications` row. |

Writes `resume.md`, `cover_letter.md`, `fit_notes.md`, the posting, the raw response, and
`sources.json` recording exactly which position and bullet IDs went in, at what score.

```bash
python -m jobsearch render output/2026-07-31_acme_engineer/resume.md --pdf
```

Print-ready HTML sized for one US Letter page; direct PDF if `weasyprint` or
`wkhtmltopdf` is installed, otherwise print to PDF from a browser.

## Review UI

Everything above has a browser front end:

```bash
python -m jobsearch web
```

Opens `http://127.0.0.1:8765`. Six pages: a dashboard that says plainly what is and
isn't wired up, sourced jobs ranked by fit, the application queue, the profile graph with
each skill's evidence, the review list for model-extracted rows, and run history. You can
tailor a posting, approve or reject a draft, and confirm extracted rows from there.

It is **loopback only and there is no login**, because it serves your full employment
history and drafts addressed to real employers. Passing a public bind address is refused
rather than warned about. Three things guard it:

- **127.0.0.1 only.** `serve()` raises on anything else.
- **CSRF token** on every mutating request, minted per process. Any web page you have open
  can POST to localhost; without the token it gets a 403. GET never changes state.
- **Host header check**, which blocks DNS rebinding — a hostile domain re-resolving to
  127.0.0.1 to read these pages from a tab you left open.

Sending is deliberately *not* wired to a button. Approving marks the row; the pipeline
sends. One irreversible action, one place it can happen.

## The grounding check

Every generated draft is scanned before you see it:

| Finding | Means |
| --- | --- |
| `unsourced-number` | A metric that appears in no record — the classic way a tailored resume becomes a lie. |
| `unknown-organization` | A company name that isn't a real employer, school, or the target. |
| `unevidenced-claim` | A technology or credential retrieval explicitly refused to claim, present anyway. |
| `placeholder` | `[Your Name]`, `TODO`, and friends. |

`unevidenced-claim` is the strongest of the four: the planner already worked out exactly
which named technologies your record can't support, so anything from that list turning up
in the draft is unambiguous — no heuristics involved. Ordinary words are filtered out of
that list first, so "backend" in a summary sentence doesn't drown the real findings.

A clean report isn't proof of accuracy. A dirty one is proof of a problem.

`fit_notes.md` is for you. It never goes to an employer.

## About the fit score

0–100, weighted toward what the posting emphasizes: terms under a requirements heading,
and terms it repeats. Benefits blurbs and company backstory are excluded.

It runs **conservative on purpose** — a strong-but-not-domain-matching candidate lands
around 35–45, not 80. Watch the numbers on a dozen real postings before picking a
threshold for autonomous sending; don't assume 80 means "good".

## Manual editing

```bash
python -m jobsearch add experience --title "Senior Engineer" --org "Acme" --start 2023-02 --skills "python,redis"
```

```bash
python -m jobsearch add achievement --experience 1 --title "Rebuilt checkout" --description "Event-driven Python service." --impact "cut p95 latency to 380ms"
```

Also `add project|education|certification`, `list <table>`, `show <table> <id>`,
`rm <table> <id>`, `skill add`, and `skill evidence <name> experience <id>`.

## Trying it on fake data

`examples/demo_linkedin_export/` is a fictional LinkedIn export. Point at a throwaway
database so it never mixes with yours:

```bash
python -m jobsearch import linkedin examples/demo_linkedin_export --db demo.db
```

```bash
python -m jobsearch link --db demo.db
```

```bash
python -m jobsearch match --job-file examples/sample_job.txt --company "Meridian Systems" --db demo.db
```

Pass `--db` *after* the final subcommand, or set `JOBSEARCH_DB`.

## Tests

```bash
python -m unittest discover -s tests -v
```

270 tests. No API key, no network — connectors run against captured response shapes, and
both model SDKs are replaced with fakes so the failure modes that matter (safety blocks,
a thinking budget eating the token ceiling, blocked prompts) are exercised without
spending a call.

## Layout

```
jobsearch/
  schema.py        the graph DDL, with the CHECK constraints that enforce structure
  db.py            connection, CRUD, org/skill dedup, v1 -> v2 migration
  graph.py         in-memory read model, match documents
  matching.py      tokenizing, stemming, IDF scoring, coverage gaps, fit score
  retrieval.py     job description + graph -> ResumePlan
  llm.py           model access: Gemini or Claude behind one call()
  generate.py      prompt assembly, response parsing
  verify.py        post-generation grounding checks
  linking.py       attach skills to records that name them
  render.py        markdown -> print HTML -> PDF
  cli.py           argparse front end
  web/             local review UI: loopback-only http.server, no dependencies
  config.py        config.toml loading and validation
  policy.py        the two autonomy gates: screen, and decide_dispatch
  pipeline.py      the unattended run, end to end
  schedule.py      Windows Task Scheduler registration
  ingest/
    linkedin.py    LinkedIn data export (deterministic)
    documents.py   pdf/docx/text -> model extraction -> graph
  sourcing/
    base.py        Posting, HTML-to-text, polite HTTP
    ats_boards.py  Greenhouse, Lever, Ashby
    aggregators.py Adzuna, USAJobs
  dispatch/
    email_gmail.py Gmail API, gmail.send scope only
    ats_form.py    Playwright form filling, aborts rather than guessing
    linkedin.py    drafting only, permanently
examples/          fictional export and a sample posting
tests/
output/            generated applications (gitignored)
config.toml        your pipeline settings (gitignored; template is committed)
jobsearch.db       your profile (gitignored)
```

## Schema

`profile`, `organizations`, `experiences`, `achievements`, `education`, `projects`,
`skills`, `skill_evidence`, `certifications`, `awards`, `publications`, `languages`,
`volunteering`, `recommendations`, `applications`, `sources`.

Two constraints do real work. `achievements` requires **exactly one** parent — a position,
project, or degree — so an accomplishment can never float free of the context that dates
and places it. `skill_evidence` requires exactly one target, and its absence is what
disqualifies a skill.

Every row records the `source_id` it came from and whether a human has `verified` it, so
a bad import can be undone wholesale and autonomous sending can be restricted to
confirmed facts.

Opening a Phase 1 database migrates it automatically: each distinct employer becomes an
organization and a position, its bullets become attached accomplishments, and tagged
skills get evidence rows pointing at them.

## The autonomous pipeline

```bash
python -m jobsearch run
```

One pass: **source → score → screen → tailor → verify → decide → dispatch.** Everything
it does lands in the database — which postings it saw, the fit it computed, why it
skipped what it skipped, what the grounding check found, what the policy decided and on
what grounds, and whether dispatch succeeded.

Copy `config.example.toml` to `config.toml` first — it's annotated throughout.

```bash
python -m jobsearch config
```

Prints the effective settings and every problem that would stop a run doing useful work.

### The master switch

`autonomous` ships **false**. The pipeline sources, scores, tailors, verifies, and then
stops, leaving everything in the review queue. Set it `true` when you've watched a few
runs and trust the fit numbers. Sending reaches real employers under your name and can't
be undone, so it's one deliberate edit rather than a default.

`--dry-run` goes further: forms get filled but never submitted, emails composed but never
sent.

### What it takes to send

An application only leaves the machine when **all** of these hold:

| Gate | Blocks on |
| --- | --- |
| `autonomous` | Off means nothing sends, ever. |
| Grounding check | Any unsourced metric, unknown employer, unevidenced claim, or placeholder. |
| Profile completeness | Missing name or email. |
| Verified records | Optional: refuse drafts built on rows you haven't confirmed. |
| Per-run cap | `max_applications_per_run` |
| Per-day cap | `max_applications_per_day` |
| Per-company/week cap | `max_per_company_per_week` |
| Channel | A configured channel that can actually handle this posting. |

Fail any one and it queues with the reason recorded on the application row. Volume isn't
the goal — the caps exist so a bad scoring day can't become fifty identical applications
with your name on them.

Before tailoring there's a second, cheaper gate: excluded companies and keywords, title
match, location, posting age, duplicate detection, and the fit floor. Those skips cost no
API calls and their reasons show up in `jobs`.

### Where jobs come from

Greenhouse, Lever, and Ashby publish documented unauthenticated read APIs — one request
per company board, full posting text, no key. Adzuna and USAJobs are official developer
APIs with free keys and broader coverage, though both return thinner descriptions, which
correctly scores them lower.

There is no Indeed connector (no public read API, scraping blocked) and no LinkedIn
connector. Neither omission is a gap to be filled.

```bash
python -m jobsearch jobs
```

Lists what's been sourced, sorted by fit, with the most common skip reasons underneath.
`jobs show <id> --full` prints a whole posting. **`jobs rescore`** resets stored verdicts
after you change the config or thresholds — old skip decisions are only as good as the
rules that produced them.

### How to apply

`dispatch.channel_order` is tried in order.

**`ats_form`** drives application forms in a real browser (`pip install playwright &&
playwright install chromium`). Thirteen platforms are recognized by host — Greenhouse,
Lever, Ashby, Workable, SmartRecruiters, Recruitee, BreezyHR, JazzHR, BambooHR, Personio,
Teamtailor, Rippling, and Jobvite — and most of the filling is ATS-agnostic anyway:
required fields are found by their DOM properties and filled by the label a person reads,
so a board with no hand-written selectors is handled by the same generic path.

It screenshots the completed form before submitting, and stops rather than guessing: an
unresolvable required field, a missing resume, an unrecognized host after a redirect, or
**a CAPTCHA** all abort and queue the application for you to finish. It never answers
demographic or voluntary self-identification questions — those are refused at both ends,
so you cannot even store one.

Three things it learned the hard way, all verified against live boards:

- **A board URL is not a promise about where you land.** `boards.greenhouse.io/stripe/...`
  redirects to `stripe.com/careers/...`, which has no form on it at all. The host is
  re-checked *after* navigation and anything unrecognized is refused, because the
  alternative is typing your name, email, and phone into an arbitrary page.
- **The form renders after `domcontentloaded`.** Greenhouse's current board is a React
  app; without waiting for a known field the fill pass runs against an empty page.
- **The resume is uploaded first, on purpose.** Greenhouse parses the file and writes its
  own guesses at your name and email into the form, discarding anything typed before.
  Upload first, then fill — your record beats a parser's guess at your PDF.

### Answering what a resume can't

Real postings ask things no resume covers: *"Do you require visa sponsorship?"*, *"What is
your notice period?"*, *"Why Anthropic?"*. The tool will not invent answers to those — an
invented "no" to a sponsorship question is a lie told to an employer under your name.

So you write them once instead:

```bash
python -m jobsearch answers add "visa sponsorship" "No"
```

Filling a form then becomes a lookup, which keeps auto-submit inside the same rule as
everything else: what gets sent traces to something you recorded. Patterns match
case-insensitively against the question after decoration (`*`, `?`, `:`) is stripped, the
most specific pattern wins, and `--company` scopes an answer to one employer so *"why do
you want to work here"* can differ per application. An answer scoped to one company is
never used for another.

Demographic and voluntary self-identification questions are refused at both ends — you
cannot store one and it will never fill one, whatever patterns exist.

Questions that block a run are recorded, so the list comes from real postings rather than
guesses about what forms ask:

```bash
python -m jobsearch answers gaps
```

### How a form gets filled

Every required field still empty after the first pass is stamped with a reference and
filled through that reference, never by searching for its label. Label text is not
identity: on Figma's live board `get_by_label("Country")` matches three widgets and the
first is the phone dial-code prefix. An element reference cannot be wrong about which
field it is.

Each widget kind is handled — text, textarea, native select, radio group, checkbox, and
the React comboboxes that Country and Location autocompletes are built from. Filling runs
up to three passes because answering one question reveals follow-ups that were hidden,
then **rescans** rather than trusting that each fill took; a combobox that silently
rejected a value is not counted as answered just because the click didn't raise.

Two refusals do the safety work:

- An answer matching **more than one** offered option fills nothing. `"Austin"` against
  `["Austin, Texas", "Austin, Indiana"]` is genuinely ambiguous, and guessing puts a city
  on your application that you never named.
- A checkbox is only ever ticked, never cleared. An answer of "No" leaves it alone.

Anything unresolved stops the run and gets recorded in `answers gaps`. An unfilled field
costs you a minute; a wrongly filled one gets submitted.

**Verified end to end**: a dry run against Figma's live Greenhouse posting reports
`unanswered: []` — resume attached, comboboxes resolved, every question answered from
stored values, demographic questions left untouched. It stops before submit only because
it is a dry run.

**`email`** sends from your own Gmail account over OAuth with the `gmail.send` scope —
it cannot read your mail. It only emails an address the posting *itself* invites
applications to; guessing `careers@company.com` would be spam, so a posting with no
address simply falls through to the next channel.

### Outreach

```bash
python -m jobsearch outreach draft 12 --channel linkedin_note
```

Drafts a connection note, DM, or cold email grounded in the same closed fact set as the
resume. Email drafts can be sent with `outreach send <id>`. LinkedIn drafts never can —
you get the text and a deep link, and you send it in your own browser.

### On a timer

```bash
python -m jobsearch schedule install --at 08:00
```

Writes a `.cmd` wrapper and registers a daily Windows scheduled task. `schedule remove`
undoes both. On Linux/macOS it prints the equivalent cron line.

```bash
python -m jobsearch runs
```

History of every pass: mode, counts, errors.

### On LinkedIn

The tool drafts connection notes and DMs and deep-links you to the right page. It will
never click, submit, or navigate LinkedIn programmatically, and `dispatch/linkedin.py`
deliberately exports no send function — there's a test asserting it stays that way.
LinkedIn's User Agreement bans automated access and enforces it with account
restrictions; losing the account you job-hunt from isn't worth a few saved clicks. Cold
email is automated end to end instead.

## Roadmap

- Feed employer responses back into scoring, so the fit metric learns from what actually
  gets replies.
- Interview-prep briefs generated from the graph plus the posting.
