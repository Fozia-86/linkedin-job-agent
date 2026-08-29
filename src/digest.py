"""Builds the twice-daily digest: fetch -> score -> draft -> send.

This module never applies to anything on Fozia's behalf. It only
produces draft messages and a summary for her to review; she applies
herself via each posting's own link.
"""
from __future__ import annotations

import logging

from . import cache
from .config import Settings
from .connects import ConnectSuggestion, build_connect_suggestion
from .dashboard import render_dashboard
from .drafting import draft_application_message
from .gemini_client import GeminiNotConfigured, is_quota_exhausted
from .postings import Posting
from .scoring import ScoredPosting, score_and_rank, select_with_source_cap
from .sources import fetch_all
from .whatsapp import get_backend

logger = logging.getLogger(__name__)


def _format_digest(
    scored: list[ScoredPosting], drafts: dict[str, str], connects: dict[str, ConnectSuggestion]
) -> str:
    if not scored:
        return "NAADVION Job Agent: no new matching postings this run."

    lines = [f"NAADVION Job Agent — {len(scored)} new matching posting(s):", "", "=== JOBS ==="]
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

    connect_entries = [(i, sp) for i, sp in enumerate(scored, start=1) if sp.posting.id in connects]
    if connect_entries:
        lines.append("=== CONNECTS (LinkedIn) ===")
        for i, sp in connect_entries:
            c = connects[sp.posting.id]
            lines.append(f"{i}. {c.company}")
            lines.append(f"   Search: {c.search_url}")
            lines.append(f"   Note: {c.note}")
            lines.append("")

    lines.append(
        "Reminder: review each draft and apply/connect yourself via the links above. "
        "Nothing here auto-applies or auto-connects."
    )
    return "\n".join(lines)


def run_digest(settings: Settings, profile: dict) -> str:
    all_postings = fetch_all(settings)
    scored = score_and_rank(all_postings, profile, settings.min_match_score)

    # Skip postings already surfaced in a recent digest so the twice-daily
    # run doesn't spam the same jobs.
    fresh_candidates = [
        sp for sp in scored
        if not cache.is_recently_seen(sp.posting.id, settings.seen_posting_cooldown_days)
    ]
    fresh = select_with_source_cap(fresh_candidates, settings.max_results_per_digest)

    drafts: dict[str, str] = {}
    connects: dict[str, ConnectSuggestion] = {}
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
            continue

        # Connect suggestion only for postings that already got a job draft
        # — no point suggesting a LinkedIn connection without an application
        # message to go with it.
        try:
            connects[sp.posting.id] = build_connect_suggestion(settings, profile, sp.posting)
        except GeminiNotConfigured as exc:
            logger.warning("Skipping connect suggestion generation: %s", exc)
            break
        except Exception as exc:  # noqa: BLE001 - one bad connect suggestion must not kill the run
            logger.warning("Failed to build connect suggestion for %s: %s", sp.posting.id, exc)
            if is_quota_exhausted(exc):
                logger.warning("Gemini quota exhausted — stopping further connect suggestions for this run")
                break

    digest_text = _format_digest(fresh, drafts, connects)
    render_dashboard(fresh, drafts, connects)

    backend = get_backend(settings)
    sent_ok = backend.send(digest_text)
    # Explicit, unambiguous outcome in the logs — send() swallows delivery
    # errors internally (so one bad WhatsApp call can't crash the run), which
    # means without this line success and silent failure look identical in
    # the run's output.
    logger.info("WhatsApp send result: %s", "SUCCESS" if sent_ok else "FAILED — see error above")

    if fresh:
        cache.mark_seen([sp.posting.id for sp in fresh])

    return digest_text
