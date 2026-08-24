"""CLI entrypoints — run each piece of the pipeline independently.

    python -m src.main fetch-jobs           # fetch + score only, no Gemini/WhatsApp calls
    python -m src.main run-digest           # full pipeline: fetch, score, draft, send
    python -m src.main test-whatsapp        # send a test message through the configured backend
    python -m src.main draft-project-post   # test the Tue project-spotlight post, any day
    python -m src.main draft-credential-post # test the Thu credential/skill post, any day
    python -m src.main draft-reflection-post # test the Sat reflection post, any day
    python -m src.main schedule             # start the twice-daily + 3x/week scheduler (long-running)

This CLI never auto-applies to a job and never auto-posts to LinkedIn.
"""
from __future__ import annotations

import argparse
import logging

from .config import get_settings, get_profile
from .digest import run_digest
from .post_drafter import TOPIC_CREDENTIAL, TOPIC_PROJECT, TOPIC_REFLECTION, draft_post
from .scoring import score_and_rank
from .sources import fetch_all
from .whatsapp import get_backend

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def cmd_fetch_jobs(_args) -> None:
    settings = get_settings()
    profile = get_profile()
    postings = fetch_all(settings)
    scored = score_and_rank(postings, profile, settings.min_match_score)

    print(f"\nFetched {len(postings)} postings total, {len(scored)} matched (score >= {settings.min_match_score}).\n")
    for sp in scored[: settings.max_results_per_digest]:
        region = "PK" if sp.is_pakistan else "non-PK"
        print(f"[{sp.score:>3}] ({region}) {sp.posting.title} @ {sp.posting.company} — {sp.posting.url}")


def cmd_run_digest(_args) -> None:
    settings = get_settings()
    profile = get_profile()
    text = run_digest(settings, profile)
    print("\n--- Digest sent/written. Contents: ---\n")
    print(text)


def cmd_test_whatsapp(_args) -> None:
    settings = get_settings()
    backend = get_backend(settings)
    ok = backend.send("NAADVION Job Agent: this is a test message. If you see this, delivery works.")
    print("Sent OK" if ok else "Send FAILED — check logs above and your .env values")


def _cmd_draft_post(topic: str) -> None:
    settings = get_settings()
    profile = get_profile()
    path = draft_post(settings, profile, topic)
    print(f"\nPost draft(s) written to: {path}")
    print("Nothing was posted — review the file and post manually if you approve it.")


def cmd_draft_project_post(_args) -> None:
    _cmd_draft_post(TOPIC_PROJECT)


def cmd_draft_credential_post(_args) -> None:
    _cmd_draft_post(TOPIC_CREDENTIAL)


def cmd_draft_reflection_post(_args) -> None:
    _cmd_draft_post(TOPIC_REFLECTION)


def cmd_schedule(_args) -> None:
    from .scheduler import run_scheduler
    run_scheduler()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NAADVION Job & Internship Finder Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch-jobs", help="Fetch + score postings only (no Gemini/WhatsApp calls)").set_defaults(func=cmd_fetch_jobs)
    sub.add_parser("run-digest", help="Full pipeline: fetch, score, draft, send").set_defaults(func=cmd_run_digest)
    sub.add_parser("test-whatsapp", help="Send a test message through the configured WhatsApp backend").set_defaults(func=cmd_test_whatsapp)
    sub.add_parser("draft-project-post", help="Test the Tuesday project-spotlight post (any day)").set_defaults(func=cmd_draft_project_post)
    sub.add_parser("draft-credential-post", help="Test the Thursday credential/skill post (any day)").set_defaults(func=cmd_draft_credential_post)
    sub.add_parser("draft-reflection-post", help="Test the Saturday reflection post (any day)").set_defaults(func=cmd_draft_reflection_post)
    sub.add_parser("schedule", help="Start the twice-daily + 3x/week scheduler (long-running process)").set_defaults(func=cmd_schedule)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
