"""RemoteOK public API — no API key required.

Docs: https://remoteok.com/api
"""
from __future__ import annotations

import requests

from ..postings import Posting

API_URL = "https://remoteok.com/api"
TIMEOUT = 20
HEADERS = {"User-Agent": "NAADVION-JobAgent/1.0 (personal job search tool)"}


def fetch() -> list[Posting]:
    resp = requests.get(API_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    raw = resp.json()

    postings: list[Posting] = []
    for item in raw:
        # The first element of RemoteOK's response is a legal notice, not a job.
        if not isinstance(item, dict) or "id" not in item or "position" not in item:
            continue

        postings.append(
            Posting(
                id=f"remoteok:{item['id']}",
                source="RemoteOK",
                title=item.get("position", ""),
                company=item.get("company", ""),
                location=item.get("location", "") or "Remote",
                remote=True,
                url=item.get("url") or f"https://remoteok.com/remote-jobs/{item['id']}",
                description=item.get("description", ""),
                tags=item.get("tags", []) or [],
                posted_at=item.get("date", ""),
            )
        )
    return postings
