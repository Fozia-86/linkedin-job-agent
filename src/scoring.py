"""Scores and ranks fetched postings against the profile's skills/keywords."""
from __future__ import annotations

from dataclasses import dataclass

from .postings import Posting

PAKISTAN_MARKERS = (
    "pakistan", "karachi", "lahore", "islamabad", "rawalpindi",
    "faisalabad", "peshawar", "quetta", "multan", "hyderabad, pk",
)

TITLE_MATCH_WEIGHT = 3
BODY_MATCH_WEIGHT = 1
NON_PK_TIEBREAK_PENALTY = 1  # subtracted from a Pakistan posting's rank score only


@dataclass
class ScoredPosting:
    posting: Posting
    score: int
    is_pakistan: bool

    @property
    def rank_score(self) -> int:
        return self.score - (NON_PK_TIEBREAK_PENALTY if self.is_pakistan else 0)


def _looks_like_pakistan(location: str) -> bool:
    loc = location.lower()
    return any(marker in loc for marker in PAKISTAN_MARKERS)


def score_posting(posting: Posting, keywords: list[str]) -> int:
    title = posting.title.lower()
    text = f"{posting.title} {posting.description} {' '.join(posting.tags)}".lower()

    score = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title:
            score += TITLE_MATCH_WEIGHT
        elif kw_lower in text:
            score += BODY_MATCH_WEIGHT
    return score


def score_and_rank(
    postings: list[Posting],
    profile: dict,
    min_score: int,
) -> list[ScoredPosting]:
    keywords = profile.get("keywords", [])

    scored = []
    for posting in postings:
        score = score_posting(posting, keywords)
        if score < min_score:
            continue
        scored.append(
            ScoredPosting(
                posting=posting,
                score=score,
                is_pakistan=_looks_like_pakistan(posting.location),
            )
        )

    scored.sort(key=lambda sp: sp.rank_score, reverse=True)
    return scored
