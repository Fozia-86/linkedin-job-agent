"""Official Meta WhatsApp Business Cloud API backend.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""
from __future__ import annotations

import logging

import requests

from .base import WhatsAppBackend

logger = logging.getLogger(__name__)
API_URL_TEMPLATE = "https://graph.facebook.com/v20.0/{phone_number_id}/messages"
TIMEOUT = 20


class MetaCloudBackend(WhatsAppBackend):
    def __init__(self, token: str, phone_number_id: str, to_number: str):
        self.token = token
        self.phone_number_id = phone_number_id
        self.to_number = to_number

    def send(self, text: str) -> bool:
        url = API_URL_TEMPLATE.format(phone_number_id=self.phone_number_id)
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": self.to_number,
            "type": "text",
            "text": {"body": text[:4096]},  # WhatsApp text message body limit
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Meta WhatsApp Cloud API send failed: %s", exc)
            return False
