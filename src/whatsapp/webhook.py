"""Generic webhook-style WhatsApp backend.

POSTs {"message": text} as JSON to any provider's webhook URL — this is
what lets a different provider (e.g. Blueticks) be plugged in later
without touching the rest of the pipeline.
"""
from __future__ import annotations

import logging

import requests

from .base import WhatsAppBackend

logger = logging.getLogger(__name__)
TIMEOUT = 20


class WebhookBackend(WhatsAppBackend):
    def __init__(self, url: str, token: str = ""):
        self.url = url
        self.token = token

    def send(self, text: str) -> bool:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            resp = requests.post(self.url, json={"message": text}, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Webhook WhatsApp send failed: %s", exc)
            return False
