"""Scores and ranks fetched postings against the profile's skills/keywords."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .postings import Posting

PAKISTAN_MARKERS = (
    "pakistan", "karachi", "lahore", "islamabad", "rawalpindi",
    "faisalabad", "peshawar", "quetta", "multan", "hyderabad, pk",
)

TITLE_MATCH_WEIGHT = 3
BODY_MATCH_WEIGHT = 1
NON_PK_TIEBREAK_PENALTY = 1  # subtracted from a Pakistan posting's rank score only

# Fozia is early-career/beginner right now — down-weight senior-sounding
# titles and up-weight entry-level ones. This is a soft score adjustment,
# NOT a hard exclude: a senior title with strong skill matches can still
# clear MIN_MATCH_SCORE and show up, just ranked lower.
SENIOR_TITLE_KEYWORDS = ("senior", "lead", "staff", "principal", "manager", "director")
JUNIOR_TITLE_KEYWORDS = ("junior", "associate", "entry-level", "entry level", "graduate", "intern", "internship")
SENIORITY_ADJUSTMENT = 3


def _title_contains_word(title_lower: str, word: str) -> bool:
    # Word-boundary match, not substring — a plain "in" check would wrongly
    # flag e.g. "International Sales Manager" as junior because "intern" is
    # a substring of "International".
    return re.search(rf"\b{re.escape(word)}\b", title_lower) is not None


def _seniority_adjustment(title: str) -> int:
    title_lower = title.lower()
    adjustment = 0
    if any(_title_contains_word(title_lower, kw) for kw in SENIOR_TITLE_KEYWORDS):
        adjustment -= SENIORITY_ADJUSTMENT
    if any(_title_contains_word(title_lower, kw) for kw in JUNIOR_TITLE_KEYWORDS):
        adjustment += SENIORITY_ADJUSTMENT
    return adjustment


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

    score += _seniority_adjustment(posting.title)
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
