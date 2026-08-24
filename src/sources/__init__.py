"""Job/internship sources.

IMPORTANT — do not add a LinkedIn source here. Scraping LinkedIn or
automating a LinkedIn login/browser session violates LinkedIn's Terms
of Service and risks an account ban. Any new source added to this
package must be a documented public API or RSS feed, never scraping
or automating an authenticated platform.
"""
from __future__ import annotations

import logging

from ..postings import Posting
from ..config import Settings
from . import remoteok, arbeitnow, adzuna

logger = logging.getLogger(__name__)


def fetch_all(settings: Settings) -> list[Posting]:
    """Fetch postings from every configured source.

    Each source is isolated: if one fails (network error, bad API key,
    rate limit) the others still run and the pipeline keeps working.
    """
    postings: list[Posting] = []

    for name, fetch_fn, enabled in (
        ("RemoteOK", remoteok.fetch, True),
        ("Arbeitnow", arbeitnow.fetch, True),
        ("Adzuna", lambda: adzuna.fetch(settings), bool(settings.adzuna_app_id and settings.adzuna_app_key)),
    ):
        if not enabled:
            logger.info("Skipping %s (not configured)", name)
            continue
        try:
            fetched = fetch_fn()
            logger.info("Fetched %d postings from %s", len(fetched), name)
            postings.extend(fetched)
        except Exception as exc:  # noqa: BLE001 - one bad source must not kill the run
            logger.warning("Failed to fetch from %s: %s", name, exc)

    return postings
