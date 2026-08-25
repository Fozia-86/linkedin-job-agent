"""Arbeitnow public job board API — no API key required.

Docs: https://arbeitnow.com/api/job-board-api
"""
from __future__ import annotations

import requests

from ..postings import Posting

API_URL = "https://arbeitnow.com/api/job-board-api"
TIMEOUT = 20


def _as_list(value) -> list:
    """Arbeitnow's API occasionally returns tags/job_types as a dict instead
    of a list for a malformed record (observed: {"1": "manager"} instead of
    ["manager"]) — coerce defensively instead of crashing the whole fetch
    over one bad record."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def fetch() -> list[Posting]:
    resp = requests.get(API_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    postings: list[Posting] = []
    for item in data:
        slug = item.get("slug", "")
        postings.append(
            Posting(
                id=f"arbeitnow:{slug}",
                source="Arbeitnow",
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                location=item.get("location", "") or ("Remote" if item.get("remote") else ""),
                remote=bool(item.get("remote", False)),
                url=item.get("url", ""),
                description=item.get("description", ""),
                tags=_as_list(item.get("tags")) + _as_list(item.get("job_types")),
                posted_at=str(item.get("created_at", "")),
            )
        )
    return postings
