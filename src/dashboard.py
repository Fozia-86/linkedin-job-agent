"""Renders a static HTML dashboard (docs/index.html) for GitHub Pages —
the same data as the WhatsApp digest (Jobs found, Connect suggestions),
just browsable. Read-only output: nothing here applies, connects, or
posts anything; it only mirrors what run_digest() already drafted.

A short history of past runs is kept in data/dashboard_history.json
(most recent first, capped at MAX_HISTORY_RUNS) so trends are visible
across a few days rather than the page only ever showing "right now".
Like data/seen_postings.json, this file is committed back to the repo
by the GitHub Actions workflow so history survives ephemeral runners.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import BASE_DIR, DATA_DIR
from .connects import ConnectSuggestion
from .scoring import ScoredPosting

DOCS_DIR = BASE_DIR / "docs"
DASHBOARD_PATH = DOCS_DIR / "index.html"
HISTORY_PATH = DATA_DIR / "dashboard_history.json"
MAX_HISTORY_RUNS = 7

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NAADVION Job Agent Dashboard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fafafa; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .tagline {{ color: #555; margin-top: 0; }}
  .run {{ border: 1px solid #ddd; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem; background: #fff; }}
  .run h2 {{ margin-top: 0; font-size: 1rem; color: #444; }}
  .section-jobs h3 {{ color: #0a5c36; border-bottom: 2px solid #0a5c36; padding-bottom: 0.25rem; }}
  .section-connects h3 {{ color: #0a4c8c; border-bottom: 2px solid #0a4c8c; padding-bottom: 0.25rem; }}
  .item {{ border-left: 3px solid #ddd; padding: 0.5rem 0 0.5rem 0.75rem; margin-bottom: 0.75rem; }}
  .item .title {{ font-weight: 600; }}
  .item .meta {{ color: #666; font-size: 0.85rem; }}
  .item .draft, .item .note {{ background: #f5f5f5; padding: 0.5rem; border-radius: 4px; margin-top: 0.4rem; white-space: pre-wrap; font-size: 0.9rem; }}
  a {{ color: #0a4c8c; }}
  button.copy {{ margin-top: 0.3rem; font-size: 0.8rem; cursor: pointer; }}
  .empty {{ color: #888; font-style: italic; }}
</style>
</head>
<body>
<h1>NAADVION Job Agent Dashboard</h1>
<p class="tagline">Draft-only. Nothing here auto-applies, auto-connects, or auto-posts — review everything and act yourself.</p>
{runs_html}
<script>
function copyText(el) {{
  navigator.clipboard.writeText(el.dataset.copytext);
}}
</script>
</body>
</html>
"""


def _load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_history(runs: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2)


def _job_to_record(sp: ScoredPosting, draft: str | None) -> dict:
    p = sp.posting
    return {
        "title": p.title,
        "company": p.company,
        "region": "Pakistan" if sp.is_pakistan else "International/Remote",
        "score": sp.score,
        "url": p.url,
        "draft": draft,
    }


def _connect_to_record(c: ConnectSuggestion) -> dict:
    return {"company": c.company, "search_url": c.search_url, "note": c.note}


def _render_job_item(job: dict) -> str:
    draft_html = ""
    if job.get("draft"):
        draft_html = f'<div class="draft">{html.escape(job["draft"])}</div>'
    return f"""<div class="item">
  <div class="title">{html.escape(job['title'])} @ {html.escape(job['company'])}</div>
  <div class="meta">{html.escape(job['region'])} · score {job['score']}</div>
  <div><a href="{html.escape(job['url'])}" target="_blank" rel="noopener">Apply link</a></div>
  {draft_html}
</div>"""


def _render_connect_item(c: dict) -> str:
    escaped_note = html.escape(c["note"])
    return f"""<div class="item">
  <div class="title">{html.escape(c['company'])}</div>
  <div><a href="{html.escape(c['search_url'])}" target="_blank" rel="noopener">LinkedIn people search</a></div>
  <div class="note" data-copytext="{escaped_note}">{escaped_note}</div>
  <button class="copy" onclick="copyText(this.previousElementSibling)">Copy note</button>
</div>"""


def _render_run(run: dict) -> str:
    jobs = run.get("jobs", [])
    connects = run.get("connects", [])

    jobs_html = "".join(_render_job_item(j) for j in jobs) or '<p class="empty">No matching postings this run.</p>'
    connects_html = "".join(_render_connect_item(c) for c in connects) or '<p class="empty">No connect suggestions this run.</p>'

    return f"""<div class="run">
  <h2>Run: {html.escape(run.get('timestamp', ''))}</h2>
  <div class="section-jobs">
    <h3>Jobs found ({len(jobs)})</h3>
    {jobs_html}
  </div>
  <div class="section-connects">
    <h3>Connect suggestions ({len(connects)})</h3>
    {connects_html}
  </div>
</div>"""


def render_dashboard(
    scored: list[ScoredPosting],
    drafts: dict[str, str],
    connects: dict[str, ConnectSuggestion],
) -> str:
    """Builds the current run's record, merges it into the persisted
    history (most recent first, capped), writes both the updated history
    JSON and docs/index.html, and returns the HTML string."""
    current_run = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "jobs": [_job_to_record(sp, drafts.get(sp.posting.id)) for sp in scored],
        "connects": [_connect_to_record(connects[sp.posting.id]) for sp in scored if sp.posting.id in connects],
    }

    history = _load_history()
    history.insert(0, current_run)
    history = history[:MAX_HISTORY_RUNS]
    _save_history(history)

    runs_html = "\n".join(_render_run(run) for run in history)
    page = PAGE_TEMPLATE.format(runs_html=runs_html)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(page, encoding="utf-8")
    # Disables Jekyll processing on GitHub Pages — without this, GitHub
    # tries to run the page through Jekyll/Liquid, which can misbehave if a
    # job description ever happens to contain "{{" or "{%" sequences.
    (DOCS_DIR / ".nojekyll").touch()

    return page
