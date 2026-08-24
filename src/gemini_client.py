"""Thin wrapper around the Gemini API REST endpoint.

Uses plain `requests` (no extra SDK dependency) so the project stays
easy to install. Docs: https://ai.google.dev/api/generate-content
"""
from __future__ import annotations

import logging

import requests

from .config import Settings

logger = logging.getLogger(__name__)

API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 60
MAX_ATTEMPTS = 2  # Gemini occasionally read-times-out; one retry covers most transient cases


class GeminiNotConfigured(RuntimeError):
    pass


def generate_text(settings: Settings, prompt: str, temperature: float = 0.6) -> str:
    if not settings.gemini_api_key:
        raise GeminiNotConfigured(
            "GEMINI_API_KEY is not set in .env — drafting requires a Gemini API key "
            "from https://aistudio.google.com/app/apikey"
        )

    url = API_URL_TEMPLATE.format(model=settings.gemini_model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key}

    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Gemini request failed (attempt %d/%d): %s", attempt, MAX_ATTEMPTS, exc)
    else:
        raise last_exc

    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError) as exc:
        logger.warning("Unexpected Gemini response shape: %s", data)
        raise RuntimeError("Gemini returned no usable text") from exc
