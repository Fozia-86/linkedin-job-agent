"""Builds the twice-daily digest: fetch -> score -> draft -> send.

This module never applies to anything on Fozia's behalf. It only
produces draft messages and a summary for her to review; she applies
herself via each posting's own link.
"""
from __future__ import annotations

import logging

from . import cache
from .config import Settings
from .drafting import draft_application_message
from .gemini_client import GeminiNotConfigured, is_quota_exhausted
from .postings import Posting
from .scoring import ScoredPosting, score_and_rank
from .sources import fetch_all
from .whatsapp import get_backend

logger = logging.getLogger(__name__)


def _format_digest(scored: list[ScoredPosting], drafts: dict[str, str]) -> str:
    if not scored:
        return "NAADVION Job Agent: no new matching postings this run."

    lines = [f"NAADVION Job Agent — {len(scored)} new matching posting(s):", ""]
    for i, sp in enumerate(scored, start=1):
        p: Posting = sp.posting
        region = "Pakistan" if sp.is_pakistan else "International/Remote"
        lines.append(f"{i}. {p.title} @ {p.company} ({region}, score {sp.score})")
        lines.append(f"   {p.location}")
        lines.append(f"   Apply: {p.url}")
        draft = drafts.get(p.id)
        if draft:
            lines.append(f"   Draft message:\n   {draft}")
        lines.append("")

    lines.append("Reminder: review each draft and apply yourself via the link above. Nothing here auto-applies.")
    return "\n".join(lines)


def run_digest(settings: Settings, profile: dict) -> str:
    all_postings = fetch_all(settings)
    scored = score_and_rank(all_postings, profile, settings.min_match_score)

    # Skip postings already surfaced in a recent digest so the twice-daily
    # run doesn't spam the same jobs.
    fresh = [
        sp for sp in scored
        if not cache.is_recently_seen(sp.posting.id, settings.seen_posting_cooldown_days)
    ][: settings.max_results_per_digest]

    drafts: dict[str, str] = {}
    for sp in fresh:
        try:
            drafts[sp.posting.id] = draft_application_message(settings, profile, sp.posting)
        except GeminiNotConfigured as exc:
            logger.warning("Skipping draft generation: %s", exc)
            break
        except Exception as exc:  # noqa: BLE001 - one bad draft must not kill the run
            logger.warning("Failed to draft message for %s: %s", sp.posting.id, exc)
            if is_quota_exhausted(exc):
                logger.warning("Gemini quota exhausted — stopping further draft attempts for this run")
                break

    digest_text = _format_digest(fresh, drafts)

    backend = get_backend(settings)
    backend.send(digest_text)

    if fresh:
        cache.mark_seen([sp.posting.id for sp in fresh])

    return digest_text
