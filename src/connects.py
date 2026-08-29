"""Draft-only LinkedIn connection suggestions for matched postings.

For each job match, builds a LinkedIn People search URL (company name +
role-relevant recruiting keywords) and drafts a short, honest connection
request note grounded in profile.json — same grounding rules as
drafting.py. The search URL is a plain constructed link, not scraping:
Fozia clicks it herself and picks the actual person to connect with.
Nothing here ever sends a connection request or message automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from .config import Settings
from .gemini_client import generate_text
from .postings import Posting

NOTE_CHAR_LIMIT = 200  # LinkedIn's connection-request note character limit

SEARCH_ROLE_KEYWORDS = ("recruiter", "talent acquisition", "hiring manager")

NOTE_PROMPT_TEMPLATE = """You are drafting a short LinkedIn CONNECTION REQUEST note (not a full \
message) from {name} ({business}) to someone at {company}.

STRICT FACTS — use ONLY what is listed below. Never invent a client, a testimonial, \
a result, or a certification that isn't listed. If nothing here is genuinely relevant, \
say so plainly instead of forcing a connection.

Career status: {career_status}
Real projects (refer to by name only, do not invent others):
{projects}
Credentials: {credentials}

Role/company context this note is about:
Title: {title}
Company: {company}

Write a connection note under {char_limit} CHARACTERS (not words — this is LinkedIn's hard \
limit for connection notes) that:
- Is honest and never claims past client work, testimonials, or results that aren't listed above
- References the specific role/company briefly
- Mentions at most one real project/credential ONLY if it genuinely fits in the tight character limit
- Is warm and low-pressure, not a sales pitch
- Uses plain language, no markdown formatting

Return only the note text, nothing else.
"""


@dataclass
class ConnectSuggestion:
    company: str
    search_url: str
    note: str


def build_search_url(posting: Posting) -> str:
    terms = f"{posting.company} " + " OR ".join(SEARCH_ROLE_KEYWORDS)
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(terms)}"


def _format_projects(profile: dict) -> str:
    return "\n".join(f"- {p['name']}: {p['description']}" for p in profile.get("projects", []))


def build_note_prompt(profile: dict, posting: Posting) -> str:
    return NOTE_PROMPT_TEMPLATE.format(
        name=profile["name"],
        business=profile["business"],
        company=posting.company,
        career_status=profile["career_status"],
        projects=_format_projects(profile),
        credentials=", ".join(profile.get("credentials", [])),
        title=posting.title,
        char_limit=NOTE_CHAR_LIMIT,
    )


def _enforce_char_limit(text: str) -> str:
    text = text.strip()
    if len(text) <= NOTE_CHAR_LIMIT:
        return text
    return text[: NOTE_CHAR_LIMIT - 1].rstrip() + "…"


def draft_connect_note(settings: Settings, profile: dict, posting: Posting) -> str:
    prompt = build_note_prompt(profile, posting)
    raw = generate_text(settings, prompt)
    return _enforce_char_limit(raw)


def build_connect_suggestion(settings: Settings, profile: dict, posting: Posting) -> ConnectSuggestion:
    return ConnectSuggestion(
        company=posting.company,
        search_url=build_search_url(posting),
        note=draft_connect_note(settings, profile, posting),
    )
