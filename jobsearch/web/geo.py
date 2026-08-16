"""Turning a job posting's free-text location into a country -- carefully.

`jobs.location` is whatever a board's API returned: "Remote", "San Francisco, CA",
"Remote (US/UK)", "Berlin, Germany | Remote". None of it is normalized, and there
is no geocoding anywhere else in this project. Rather than guess a country from a
city name (wrong for anything ambiguous -- "Cambridge", "Portland", "Georgia") or
fall back to some default, this module only ever recognizes a country when its
name, official name, or a common abbreviation appears as a whole word. Everything
else is left unmatched. An unmatched location still shows up in the plain ranked
list elsewhere on the page -- it just never gets credited to a country it
doesn't actually name.
"""

from __future__ import annotations

import re

# Common name/abbreviation variants -> canonical country name. Deliberately
# limited to countries that actually turn up on tech job boards; this is not
# meant to be an exhaustive gazetteer.
COUNTRY_ALIASES: dict[str, str] = {
    "US": "United States", "U.S.": "United States", "U.S.A.": "United States",
    "USA": "United States", "United States": "United States",
    "United States of America": "United States",
    "UK": "United Kingdom", "U.K.": "United Kingdom",
    "United Kingdom": "United Kingdom", "Great Britain": "United Kingdom",
    "Canada": "Canada",
    "Germany": "Germany", "Deutschland": "Germany",
    "France": "France",
    "Netherlands": "Netherlands", "The Netherlands": "Netherlands",
    "Holland": "Netherlands",
    "Ireland": "Ireland",
    "Spain": "Spain",
    "Portugal": "Portugal",
    "Italy": "Italy",
    "Poland": "Poland",
    "Sweden": "Sweden",
    "Norway": "Norway",
    "Denmark": "Denmark",
    "Finland": "Finland",
    "Switzerland": "Switzerland",
    "Austria": "Austria",
    "Belgium": "Belgium",
    "Australia": "Australia",
    "New Zealand": "New Zealand",
    "India": "India",
    "Singapore": "Singapore",
    "Japan": "Japan",
    "South Korea": "South Korea", "Korea": "South Korea",
    "Israel": "Israel",
    "UAE": "United Arab Emirates", "U.A.E.": "United Arab Emirates",
    "United Arab Emirates": "United Arab Emirates",
    "Brazil": "Brazil",
    "Mexico": "Mexico",
    "South Africa": "South Africa",
    "Philippines": "Philippines",
}

# Longest alias first, so "United States of America" matches before "United
# States" or "US" have a chance to shadow it -- and each is still whole-word
# bounded, so "US" never fires inside "USABLE" or "House".
_ALIASES_BY_LENGTH = sorted(COUNTRY_ALIASES, key=len, reverse=True)
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in _ALIASES_BY_LENGTH) + r")\b",
    re.IGNORECASE,
)
_LOOKUP = {alias.lower(): canonical for alias, canonical in COUNTRY_ALIASES.items()}


# Approximate country centroids (lat, lon), for placing map pins. Only the
# countries this app's job data can actually name (see COUNTRY_ALIASES above)
# need an entry -- this is not a general-purpose gazetteer.
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "United States": (39.8, -98.6),
    "United Kingdom": (54.0, -2.5),
    "Canada": (56.1, -106.3),
    "Germany": (51.2, 10.5),
    "France": (46.6, 2.2),
    "Netherlands": (52.1, 5.3),
    "Ireland": (53.4, -8.2),
    "Spain": (40.5, -3.7),
    "Portugal": (39.4, -8.2),
    "Italy": (42.8, 12.6),
    "Poland": (51.9, 19.1),
    "Sweden": (62.0, 15.0),
    "Norway": (60.5, 8.5),
    "Denmark": (56.3, 9.5),
    "Finland": (64.0, 26.0),
    "Switzerland": (46.8, 8.2),
    "Austria": (47.5, 14.6),
    "Belgium": (50.5, 4.5),
    "Australia": (-25.3, 133.8),
    "New Zealand": (-41.0, 174.9),
    "India": (22.0, 79.0),
    "Singapore": (1.35, 103.8),
    "Japan": (36.2, 138.3),
    "South Korea": (35.9, 127.8),
    "Israel": (31.0, 34.8),
    "United Arab Emirates": (23.4, 53.8),
    "Brazil": (-14.2, -51.9),
    "Mexico": (23.6, -102.5),
    "South Africa": (-30.6, 22.9),
    "Philippines": (12.9, 121.8),
}

# ISO 3166-1 alpha-2, used only to build the flag emoji for a canonical name.
COUNTRY_ISO2: dict[str, str] = {
    "United States": "US", "United Kingdom": "GB", "Canada": "CA",
    "Germany": "DE", "France": "FR", "Netherlands": "NL", "Ireland": "IE",
    "Spain": "ES", "Portugal": "PT", "Italy": "IT", "Poland": "PL",
    "Sweden": "SE", "Norway": "NO", "Denmark": "DK", "Finland": "FI",
    "Switzerland": "CH", "Austria": "AT", "Belgium": "BE",
    "Australia": "AU", "New Zealand": "NZ", "India": "IN",
    "Singapore": "SG", "Japan": "JP", "South Korea": "KR", "Israel": "IL",
    "United Arab Emirates": "AE", "Brazil": "BR", "Mexico": "MX",
    "South Africa": "ZA", "Philippines": "PH",
}


def flag_emoji(country: str) -> str:
    """Regional-indicator flag for a canonical country name, or the globe
    emoji as a neutral fallback when there is no ISO2 entry for it."""
    iso2 = COUNTRY_ISO2.get(country)
    if not iso2:
        return "\U0001F310"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2)


def project_equirect(lat: float, lon: float) -> tuple[float, float]:
    """Plain equirectangular projection of (lat, lon) to (top%, left%) for a
    flat map image spanning the full lat range [-90, 90] and lon range
    [-180, 180]. No fancy map projection -- this matches a simple flat world
    silhouette, not a Mercator basemap."""
    left = (lon + 180.0) / 360.0 * 100.0
    top = (90.0 - lat) / 180.0 * 100.0
    return top, left


def extract_countries(location: str | None) -> list[str]:
    """Every country unambiguously named in `location`, in first-seen order.

    A compound posting like "Remote (US/UK)" genuinely reaches both countries,
    so both are returned rather than picking one. "Remote" alone, or a bare
    city name with no country attached, returns an empty list -- there is
    nothing here to guess from.
    """
    if not location:
        return []
    seen: list[str] = []
    for match in _PATTERN.finditer(location):
        canonical = _LOOKUP[match.group(1).lower()]
        if canonical not in seen:
            seen.append(canonical)
    return seen
