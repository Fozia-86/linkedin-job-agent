"""Drafts short, honest, tailored application messages for matched postings.

Grounding rule: the prompt sent to Gemini contains ONLY facts pulled
from profile.json (real projects, real credentials, real career
status). The model is explicitly instructed never to invent a client,
testimonial, result, or certification, and to say so plainly if it
cannot make a genuine connection to a posting without stretching the
facts. This module never auto-applies anything — it only produces a
draft string for a human (Fozia) to review before applying herself.
"""
from __future__ import annotations

from .gemini_client import generate_text
from .postings import Posting
from .config import Settings

WORD_LIMIT = 120

PROMPT_TEMPLATE = """You are drafting a short, honest, tailored outreach message from {name} \
({business}) applying to a job/internship posting.

STRICT FACTS — use ONLY what is listed below. Never invent a client, a testimonial, \
a result, or a certification that isn't listed. If nothing here is genuinely relevant \
to this posting, say so plainly instead of forcing a connection.

Career status: {career_status}
Skills: {skills}
Real projects (refer to by name only, do not invent others):
{projects}
Credentials: {credentials}

Job posting being applied to:
Title: {title}
Company: {company}
Location: {location}
Description excerpt: {description}

Write a message under {word_limit} words that:
- Is honest and never claims past client work, testimonials, or results that aren't listed above
- References 1-2 of the real projects/credentials above ONLY if genuinely relevant to this posting
- Is specifically tailored to this posting, not generic boilerplate
- Ends with a simple, low-pressure call to action
- Uses plain, natural language — no corporate buzzwords
- Uses NO markdown formatting (no backticks, no asterisks, no bullet points) — this is sent \
as a plain WhatsApp text message, so project names should appear as plain text, e.g. \
smart-retail-reconciler, not `smart-retail-reconciler` or *smart-retail-reconciler*

Return only the message text, nothing else.
"""


def _format_projects(profile: dict) -> str:
    lines = []
    for p in profile.get("projects", []):
        lines.append(f"- {p['name']}: {p['description']}")
    return "\n".join(lines)


def build_prompt(profile: dict, posting: Posting) -> str:
    return PROMPT_TEMPLATE.format(
        name=profile["name"],
        business=profile["business"],
        career_status=profile["career_status"],
        skills=", ".join(profile.get("skills", [])),
        projects=_format_projects(profile),
        credentials=", ".join(profile.get("credentials", [])),
        title=posting.title,
        company=posting.company,
        location=posting.location,
        description=posting.description[:1500],
        word_limit=WORD_LIMIT,
    )


def _enforce_word_limit(text: str) -> str:
    words = text.split()
    if len(words) <= WORD_LIMIT:
        return text
    return " ".join(words[:WORD_LIMIT]) + "..."


def draft_application_message(settings: Settings, profile: dict, posting: Posting) -> str:
    prompt = build_prompt(profile, posting)
    raw = generate_text(settings, prompt)
    return _enforce_word_limit(raw)
