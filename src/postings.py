"""Shared Posting data structure used by every source and downstream stage."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field


@dataclass
class Posting:
    id: str  # e.g. "remoteok:12345" — globally unique, used for dedup/caching
    source: str
    title: str
    company: str
    location: str
    remote: bool
    url: str
    description: str
    tags: list = field(default_factory=list)
    posted_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
