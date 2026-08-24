"""Arbeitnow public job board API — no API key required.

Docs: https://arbeitnow.com/api/job-board-api
"""
from __future__ import annotations

import requests

from ..postings import Posting

API_URL = "https://arbeitnow.com/api/job-board-api"
TIMEOUT = 20


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
                tags=(item.get("tags", []) or []) + (item.get("job_types", []) or []),
                posted_at=str(item.get("created_at", "")),
            )
        )
    return postings
