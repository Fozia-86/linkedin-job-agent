"""Local fallback backend — used when no WhatsApp provider is configured.

Writes the digest to a timestamped file under data/digests/ and prints
it to stdout, so the whole pipeline stays testable before any WhatsApp
account is connected.
"""
from __future__ import annotations

from datetime import datetime

from .base import WhatsAppBackend
from ..config import DATA_DIR

DIGESTS_DIR = DATA_DIR / "digests"


class LocalFallbackBackend(WhatsAppBackend):
    def send(self, text: str) -> bool:
        DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = DIGESTS_DIR / f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)

        print("\n" + "=" * 70)
        print(f"WHATSAPP NOT CONFIGURED — digest written to {filename}")
        print("=" * 70)
        print(text)
        print("=" * 70 + "\n")
        return True
