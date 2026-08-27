"""Scores and ranks fetched postings against the profile's skills/keywords."""
from __future__ import annotations

import math
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

# Adzuna's API only covers 12 countries (not Pakistan) and, unlike RemoteOK/
# Arbeitnow, isn't a worldwide-remote-native board — many of its results are
# tied to a specific national labor market. Keep it a supplementary minority
# of the digest via a rank tiebreak penalty AND a hard cap on its share of
# the final selected postings (see select_with_source_cap below), rather
# than a primary source.
ADZUNA_SOURCE_TIEBREAK_PENALTY = 2
ADZUNA_MAX_SHARE = 0.3

# Fozia is early-career/beginner right now — down-weight senior-sounding
# titles and up-weight entry-level ones. This is a soft score adjustment,
# NOT a hard exclude/hard requirement: a senior title with strong skill
# matches can still clear MIN_MATCH_SCORE and show up, just ranked lower,
# and "Junior" in the title is one signal among several below, not a gate.
SENIOR_TITLE_KEYWORDS = ("senior", "lead", "staff", "principal", "manager", "director")
JUNIOR_TITLE_KEYWORDS = ("junior", "associate", "entry-level", "entry level", "graduate", "intern", "internship")
SENIORITY_ADJUSTMENT = 3

# Genuinely junior, fully-remote roles are rare across the whole market, not
# just missing from our sources — so "Junior" in the title can't be a hard
# requirement. These are supplementary positive/negative signals instead:
# an explicit multi-year experience requirement in the description is a real
# gate regardless of title, while flexible arrangements (contract/part-time/
# temporary/etc.) are often more open to less-experienced applicants.
EXPERIENCE_YEARS_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:-\s*\d+\s*)?\s*years?\s*(?:of\s+)?(?:relevant\s+|professional\s+|prior\s+)?experience",
    re.IGNORECASE,
)
EXPERIENCE_GATE_YEARS_THRESHOLD = 3  # 3+ years stated reads as a real gate against an early-career candidate
EXPERIENCE_GATE_PENALTY = 2

FLEXIBLE_ROLE_KEYWORDS = (
    "part time", "part-time", "contract", "temporary", "freelance",
    "working student", "apprenticeship",
)
FLEXIBLE_ROLE_BONUS = 2


def _contains_word(text_lower: str, word: str) -> bool:
    # Word-boundary match, not substring — a plain "in" check would wrongly
    # flag e.g. "International Sales Manager" as junior because "intern" is
    # a substring of "International".
    return re.search(rf"\b{re.escape(word)}\b", text_lower) is not None


def _seniority_adjustment(title: str) -> int:
    title_lower = title.lower()
    adjustment = 0
    if any(_contains_word(title_lower, kw) for kw in SENIOR_TITLE_KEYWORDS):
        adjustment -= SENIORITY_ADJUSTMENT
    if any(_contains_word(title_lower, kw) for kw in JUNIOR_TITLE_KEYWORDS):
        adjustment += SENIORITY_ADJUSTMENT
    return adjustment


def _experience_gate_adjustment(text: str) -> int:
    years = [int(y) for y in EXPERIENCE_YEARS_PATTERN.findall(text)]
    if years and min(years) >= EXPERIENCE_GATE_YEARS_THRESHOLD:
        return -EXPERIENCE_GATE_PENALTY
    return 0


def _flexible_role_adjustment(text_lower: str) -> int:
    if any(_contains_word(text_lower, kw) for kw in FLEXIBLE_ROLE_KEYWORDS):
        return FLEXIBLE_ROLE_BONUS
    return 0


@dataclass
class ScoredPosting:
    posting: Posting
    score: int
    is_pakistan: bool

    @property
    def rank_score(self) -> int:
        penalty = NON_PK_TIEBREAK_PENALTY if self.is_pakistan else 0
        if self.posting.source.startswith("Adzuna"):
            penalty += ADZUNA_SOURCE_TIEBREAK_PENALTY
        return self.score - penalty


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
    score += _experience_gate_adjustment(posting.description)
    score += _flexible_role_adjustment(text)
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


def select_with_source_cap(candidates: list[ScoredPosting], max_results: int) -> list[ScoredPosting]:
    """Take up to max_results from an already rank_score-sorted list, capping
    how many can come from Adzuna so it stays supplementary rather than
    dominating the digest — while still filling all max_results slots from
    RemoteOK/Arbeitnow candidates further down the list if available."""
    if not candidates or max_results <= 0:
        return []

    max_adzuna = max(1, math.floor(max_results * ADZUNA_MAX_SHARE))
    selected: list[ScoredPosting] = []
    adzuna_count = 0

    for sp in candidates:
        if len(selected) >= max_results:
            break
        is_adzuna = sp.posting.source.startswith("Adzuna")
        if is_adzuna and adzuna_count >= max_adzuna:
            continue
        selected.append(sp)
        if is_adzuna:
            adzuna_count += 1

    return selected
