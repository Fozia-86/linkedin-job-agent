"""Adzuna API — free tier, requires an App ID + App Key.

Get credentials from https://developer.adzuna.com/
Docs: https://developer.adzuna.com/docs/search
"""
from __future__ import annotations

import requests

from ..postings import Posting
from ..config import Settings

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"
TIMEOUT = 20
RESULTS_PER_COUNTRY = 20

# Adzuna's `what` param does an AND/phrase match, so a literal "OR" string
# matches nothing. `what_or` is the actual param for OR-of-terms search; each
# space-separated word is optional. This is intentionally broad — scoring.py
# does the real relevance filtering afterwards.
SEARCH_TERMS = "AI FastAPI agent LLM GCP Gemini Kubernetes"


def fetch(settings: Settings) -> list[Posting]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []

    postings: list[Posting] = []
    for country in settings.adzuna_countries:
        url = BASE_URL.format(country=country)
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": RESULTS_PER_COUNTRY,
            "what_or": SEARCH_TERMS,
            "content-type": "application/json",
        }
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])

        for item in results:
            job_id = str(item.get("id", ""))
            location = (item.get("location") or {}).get("display_name", "")
            postings.append(
                Posting(
                    id=f"adzuna:{job_id}",
                    source=f"Adzuna ({country})",
                    title=item.get("title", ""),
                    company=(item.get("company") or {}).get("display_name", ""),
                    location=location,
                    remote="remote" in (item.get("title", "") + location).lower(),
                    url=item.get("redirect_url", ""),
                    description=item.get("description", ""),
                    tags=[],
                    posted_at=item.get("created", ""),
                )
            )
    return postings
