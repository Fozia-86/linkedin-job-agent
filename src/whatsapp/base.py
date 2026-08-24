from __future__ import annotations

from abc import ABC, abstractmethod


class WhatsAppBackend(ABC):
    @abstractmethod
    def send(self, text: str) -> bool:
        """Send text. Returns True on success, False on failure (never raises
        for expected failure modes — callers should be able to keep the
        pipeline running even if delivery fails)."""
        raise NotImplementedError
