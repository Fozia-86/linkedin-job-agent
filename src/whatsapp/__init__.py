"""WhatsApp delivery backends.

get_backend() picks the first configured backend in this priority order:
  1. Meta WhatsApp Business Cloud API
  2. Generic webhook backend (e.g. Blueticks or any provider accepting a JSON POST)
  3. Local fallback (writes to ./data/digests/ and prints to stdout)

This keeps the pipeline fully testable without any WhatsApp account
connected yet, and lets a future backend be swapped in just by adding
a new class here + one branch in get_backend().
"""
from __future__ import annotations

import logging

from ..config import Settings
from .base import WhatsAppBackend
from .meta_cloud import MetaCloudBackend
from .webhook import WebhookBackend
from .local_fallback import LocalFallbackBackend

logger = logging.getLogger(__name__)


def get_backend(settings: Settings) -> WhatsAppBackend:
    if settings.whatsapp_meta_token and settings.whatsapp_meta_phone_number_id and settings.whatsapp_meta_to_number:
        logger.info("Using WhatsApp backend: Meta Cloud API")
        return MetaCloudBackend(
            token=settings.whatsapp_meta_token,
            phone_number_id=settings.whatsapp_meta_phone_number_id,
            to_number=settings.whatsapp_meta_to_number,
        )

    if settings.whatsapp_webhook_url:
        logger.info("Using WhatsApp backend: generic webhook")
        return WebhookBackend(url=settings.whatsapp_webhook_url, token=settings.whatsapp_webhook_token)

    logger.info("No WhatsApp backend configured — using local fallback")
    return LocalFallbackBackend()
