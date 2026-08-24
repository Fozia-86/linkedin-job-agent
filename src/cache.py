"""Small JSON-file cache so the same posting isn't re-drafted and re-sent
in every twice-daily run.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .config import DATA_DIR

SEEN_FILE = DATA_DIR / "seen_postings.json"


def _load() -> dict:
    if not SEEN_FILE.exists():
        return {}
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_recently_seen(posting_id: str, cooldown_days: int) -> bool:
    data = _load()
    seen_at = data.get(posting_id)
    if not seen_at:
        return False
    seen_dt = datetime.fromisoformat(seen_at)
    return datetime.utcnow() - seen_dt < timedelta(days=cooldown_days)


def mark_seen(posting_ids: list[str]) -> None:
    data = _load()
    now = datetime.utcnow().isoformat()
    for pid in posting_ids:
        data[pid] = now
    _save(data)
