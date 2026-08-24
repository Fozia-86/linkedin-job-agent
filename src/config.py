"""Loads all runtime configuration from .env and profile.json.

Nothing about a specific person or business should ever be hardcoded
outside of profile.json — this module only knows how to read config,
never what the config says.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PROFILE_PATH = Path(os.environ.get("PROFILE_PATH", BASE_DIR / "profile.json"))
DATA_DIR = BASE_DIR / "data"


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "")
    return int(value) if value.strip() else default


@dataclass(frozen=True)
class Settings:
    # Adzuna
    adzuna_app_id: str = os.environ.get("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.environ.get("ADZUNA_APP_KEY", "")
    adzuna_countries: tuple = tuple(
        c.strip() for c in os.environ.get("ADZUNA_COUNTRIES", "gb,us,ca").split(",") if c.strip()
    )

    # Gemini
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    # WhatsApp — Meta Cloud API
    whatsapp_meta_token: str = os.environ.get("WHATSAPP_META_TOKEN", "")
    whatsapp_meta_phone_number_id: str = os.environ.get("WHATSAPP_META_PHONE_NUMBER_ID", "")
    whatsapp_meta_to_number: str = os.environ.get("WHATSAPP_META_TO_NUMBER", "")

    # WhatsApp — generic webhook
    whatsapp_webhook_url: str = os.environ.get("WHATSAPP_WEBHOOK_URL", "")
    whatsapp_webhook_token: str = os.environ.get("WHATSAPP_WEBHOOK_TOKEN", "")

    # Scheduling
    timezone: str = os.environ.get("TIMEZONE", "Asia/Karachi")
    morning_run_time: str = os.environ.get("MORNING_RUN_TIME", "09:00")
    evening_run_time: str = os.environ.get("EVENING_RUN_TIME", "17:00")
    # Post drafter runs 3x/week on fixed days (Tue/Thu/Sat) with a fixed topic
    # per day — see src/post_drafter.py. Only the time-of-day is configurable.
    post_drafter_time: str = os.environ.get("POST_DRAFTER_TIME", "10:00")

    # Matching / ranking
    max_results_per_digest: int = field(default_factory=lambda: _env_int("MAX_RESULTS_PER_DIGEST", 10))
    min_match_score: int = field(default_factory=lambda: _env_int("MIN_MATCH_SCORE", 4))
    seen_posting_cooldown_days: int = field(default_factory=lambda: _env_int("SEEN_POSTING_COOLDOWN_DAYS", 3))


def get_settings() -> Settings:
    return Settings()


def get_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"profile.json not found at {PROFILE_PATH}. Copy/edit the example in the README first."
        )
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
