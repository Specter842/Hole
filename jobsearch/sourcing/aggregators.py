"""Adzuna and USAJobs -- broad aggregators, both with free official APIs.

Neither returns the full posting text. Adzuna gives a truncated snippet and
USAJobs gives a structured summary, so postings from here score against less
material than an ATS board posting. The pipeline compensates by fetching nothing
extra and simply treating a thin description as thin evidence: a job with 200
characters of text rarely clears the fit threshold, which is the correct outcome
rather than a bug to work around.
"""

from __future__ import annotations

from typing import Any

from .base import Posting, SourceError, SourceResult, fetch_json, html_to_text, iso_date

ADZUNA_SEARCH = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
USAJOBS_SEARCH = "https://data.usajobs.gov/api/search"


def fetch_adzuna(
    *,
    app_id: str,
    app_key: str,
    country: str = "us",
    what: str = "",
    where: str = "",
    results_per_page: int = 50,
    max_pages: int = 2,
    max_age_days: int = 30,
) -> SourceResult:
    result = SourceResult(source="adzuna")
    if not (app_id and app_key):
        result.errors.append("adzuna: app_id and app_key are required")
        return result

    for page in range(1, max(1, max_pages) + 1):
        params: dict[str, Any] = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": results_per_page,
            "content-type": "application/json",
            "max_days_old": max_age_days,
        }
        if what:
            params["what_or"] = what
        if where:
            params["where"] = where
        try:
            payload = fetch_json(
                ADZUNA_SEARCH.format(country=country.lower(), page=page), params=params
            )
        except SourceError as exc:
            result.errors.append(str(exc))
            break

        rows = (payload or {}).get("results") or []
        if not rows:
            break
        for job in rows:
            salary_min = job.get("salary_min")
            salary_max = job.get("salary_max")
            compensation = (
                f"{salary_min:.0f}-{salary_max:.0f}" if salary_min and salary_max else None
            )
            result.postings.append(
                Posting(
                    source="adzuna",
                    external_id=str(job.get("id", "")),
                    company=str((job.get("company") or {}).get("display_name") or "").strip(),
                    title=str(job.get("title") or "").strip(),
                    location=str((job.get("location") or {}).get("display_name") or "").strip(),
                    url=str(job.get("redirect_url") or ""),
                    description=html_to_text(job.get("description")),
                    compensation=compensation,
                    posted_at=iso_date(job.get("created")),
                )
            )
        if len(rows) < results_per_page:
            break
    return result


def _usajobs_description(descriptor: dict[str, Any]) -> str:
    details = (descriptor.get("UserArea") or {}).get("Details") or {}
    parts = [
        str(details.get("JobSummary") or ""),
        str(details.get("MajorDuties") or ""),
        str(details.get("Requirements") or ""),
        str(descriptor.get("QualificationSummary") or ""),
    ]
    return html_to_text("\n\n".join(p for p in parts if p))


def fetch_usajobs(
    *,
    email: str,
    api_key: str,
    keyword: str = "",
    location: str = "",
    results_per_page: int = 50,
) -> SourceResult:
    result = SourceResult(source="usajobs")
    if not (email and api_key):
        result.errors.append("usajobs: email and api_key are required")
        return result

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": api_key,
    }
    params: dict[str, Any] = {"ResultsPerPage": min(results_per_page, 500)}
    if keyword:
        params["Keyword"] = keyword
    if location:
        params["LocationName"] = location

    try:
        payload = fetch_json(USAJOBS_SEARCH, params=params, headers=headers)
    except SourceError as exc:
        result.errors.append(str(exc))
        return result

    items = ((payload or {}).get("SearchResult") or {}).get("SearchResultItems") or []
    for item in items:
        descriptor = item.get("MatchedObjectDescriptor") or {}
        apply_uris = descriptor.get("ApplyURI") or []
        remuneration = descriptor.get("PositionRemuneration") or []
        compensation = None
        if remuneration:
            first = remuneration[0]
            low, high = first.get("MinimumRange"), first.get("MaximumRange")
            if low and high:
                compensation = f"{low}-{high} {first.get('RateIntervalCode', '')}".strip()
        result.postings.append(
            Posting(
                source="usajobs",
                external_id=str(descriptor.get("PositionID") or item.get("MatchedObjectId") or ""),
                company=str(descriptor.get("OrganizationName") or "").strip(),
                title=str(descriptor.get("PositionTitle") or "").strip(),
                location=str(descriptor.get("PositionLocationDisplay") or "").strip(),
                url=str(descriptor.get("PositionURI") or ""),
                apply_url=str(apply_uris[0]) if apply_uris else str(descriptor.get("PositionURI") or ""),
                description=_usajobs_description(descriptor),
                compensation=compensation,
                posted_at=iso_date(descriptor.get("PublicationStartDate")),
            )
        )
    return result
