"""LinkedIn post drafter — 3x/week, fixed topic rotation.

Runs on a fixed schedule with a fixed topic per day (see scheduler.py):
  Tuesday  -> project spotlight    (rotates through profile.json projects)
  Thursday -> credential/skill     (rotates through profile.json credentials + skills)
  Saturday -> learning-in-progress reflection (grounded in career_status, no rotation)

Each run drafts ONE personal LinkedIn post and one NAADVION company-page
variant, picking a single real angle rather than cramming everything in.
This follows general good-writing practice (specific > exhaustive, one
clear idea per post) — it does NOT claim any proprietary knowledge of
LinkedIn's ranking algorithm.

Rotation state lives in data/post_history.json so the same project/
credential doesn't repeat until every real item in profile.json has
been used once. When a topic's pool is fully exhausted, this module
does NOT invent new material to stay "fresh" — it writes a note asking
for profile.json to be updated instead of drafting a post that day.

Drafts are text-only (no image generation) — the output always reminds
Fozia to attach a real screenshot herself if she wants an image.

This module only writes drafts to disk (and optionally notifies via
WhatsApp that they're ready). It never posts anything itself — posting
always requires Fozia's explicit approval of that specific draft.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from .config import DATA_DIR, Settings
from .gemini_client import generate_text
from .whatsapp import get_backend

logger = logging.getLogger(__name__)

STATE_FILE = DATA_DIR / "post_history.json"
DRAFTS_DIR = DATA_DIR / "post_drafts"

TOPIC_PROJECT = "project_spotlight"
TOPIC_CREDENTIAL = "credential_skill_highlight"
TOPIC_REFLECTION = "reflection"

TOPIC_TITLES = {
    TOPIC_PROJECT: "Project spotlight",
    TOPIC_CREDENTIAL: "Credential/skill highlight",
    TOPIC_REFLECTION: "Learning-in-progress reflection",
}

NO_IMAGE_NOTE = (
    "Note: this draft is text-only — no image was generated. If you want a visual "
    "on this post, attach a real screenshot of the relevant project yourself before posting."
)

PERSONAL_PROMPT = """Write one LinkedIn post (personal profile voice) for {name}, an {career_status}

Pick exactly ONE angle for this post, described below — do not cram in every \
project/credential, just this one:

Angle: {angle_label}
Details: {angle_detail}

Rules:
- Follow general good LinkedIn-writing practice (a specific hook, one clear idea, \
a genuine takeaway, a simple closing question or CTA) — this is NOT based on any \
proprietary or insider knowledge of LinkedIn's ranking algorithm.
- Be honest: never claim a client, a testimonial, or a result that isn't in the \
details above.
- Natural, first-person, plain language. No corporate buzzwords, no excessive hashtags \
(3 max).
- No markdown formatting (no backticks, no asterisks) — plain text only.
- Roughly 80-150 words.

Return only the post text.
"""

COMPANY_PROMPT = """Write one LinkedIn post for the {business} company page (third-person \
or "we" voice, professional but not corporate-stiff).

Pick exactly ONE angle for this post, described below — do not cram in every \
project/credential, just this one:

Angle: {angle_label}
Details: {angle_detail}

Rules:
- Follow general good LinkedIn-writing practice (a specific hook, one clear idea, \
a genuine takeaway, a simple closing question or CTA) — this is NOT based on any \
proprietary or insider knowledge of LinkedIn's ranking algorithm.
- Be honest: never claim a client, a testimonial, or a result that isn't in the \
details above. {business} has no paid client work yet — do not imply otherwise.
- Plain language. No corporate buzzwords, no excessive hashtags (3 max).
- No markdown formatting (no backticks, no asterisks) — plain text only.
- Roughly 80-150 words.

Return only the post text.
"""

REFLECTION_PERSONAL_PROMPT = """Write one LinkedIn post (personal profile voice) for {name}, an {career_status}

This is a "learning in progress" reflection post — NOT a project announcement. \
Write honestly about the current learning journey / what's being built right now, \
grounded ONLY in these real facts:

Career status: {career_status}
Current skills/stack: {skills}
Real projects built so far: {projects}

Rules:
- Follow general good LinkedIn-writing practice (a specific hook, one clear idea, \
a genuine takeaway, a simple closing question or CTA) — this is NOT based on any \
proprietary or insider knowledge of LinkedIn's ranking algorithm.
- Be honest: never claim a client, a testimonial, a result, or a milestone that isn't \
implied by the facts above. Do not claim paid client work.
- Natural, first-person, plain language. No corporate buzzwords, no excessive hashtags \
(3 max).
- No markdown formatting (no backticks, no asterisks) — plain text only.
- Roughly 80-150 words.

Return only the post text.
"""

REFLECTION_COMPANY_PROMPT = """Write one LinkedIn post for the {business} company page (third-person \
or "we" voice, professional but not corporate-stiff).

This is a "learning in progress" reflection post — NOT a project announcement. \
Write honestly about the current learning journey / what's being built right now, \
grounded ONLY in these real facts:

Career status: {career_status}
Current skills/stack: {skills}
Real projects built so far: {projects}

Rules:
- Follow general good LinkedIn-writing practice (a specific hook, one clear idea, \
a genuine takeaway, a simple closing question or CTA) — this is NOT based on any \
proprietary or insider knowledge of LinkedIn's ranking algorithm.
- Be honest: never claim a client, a testimonial, a result, or a milestone that isn't \
implied by the facts above. {business} has no paid client work yet — do not imply otherwise.
- Plain language. No corporate buzzwords, no excessive hashtags (3 max).
- No markdown formatting (no backticks, no asterisks) — plain text only.
- Roughly 80-150 words.

Return only the post text.
"""


def _project_pool(profile: dict) -> list[dict]:
    return [
        {"label": p["name"], "detail": p["description"]}
        for p in profile.get("projects", [])
    ]


def _credential_pool(profile: dict) -> list[dict]:
    pool = [
        {"label": c, "detail": f"Earned/completed credential: {c}"}
        for c in profile.get("credentials", [])
    ]
    pool += [
        {"label": s, "detail": f"Core tech-stack skill: {s}"}
        for s in profile.get("skills", [])
    ]
    return pool


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _peek_next_rotating(topic: str, pool: list[dict]) -> dict | None:
    """Read-only: which item rotation would pick next, without persisting
    anything. Returns None once every item currently in the pool has been
    used at least once — the caller must NOT invent a substitute angle in
    that case, only report that the pool needs new real material. If items
    are later appended to profile.json, the pool grows and rotation
    resumes automatically (no manual reset needed).
    """
    if not pool:
        return None

    state = _load_state()
    topic_state = state.get(topic, {"next_index": 0, "used_labels": []})
    used = set(topic_state["used_labels"])

    if len(used) >= len(pool):
        return None  # exhausted — every current item has been used at least once

    idx = topic_state["next_index"] % len(pool)
    return pool[idx]


def _commit_rotation(topic: str, pool: list[dict], item: dict) -> None:
    """Persist rotation progress. Call ONLY after a draft using `item` has
    been generated successfully — a failed Gemini call must not burn a
    rotation slot, or a transient API error would silently skip real
    material without ever drafting it."""
    state = _load_state()
    topic_state = state.setdefault(topic, {"next_index": 0, "used_labels": []})
    used = set(topic_state["used_labels"])

    idx = pool.index(item)
    topic_state["next_index"] = (idx + 1) % len(pool)
    if item["label"] not in used:
        topic_state["used_labels"].append(item["label"])
    state[topic] = topic_state
    _save_state(state)


def _write_exhausted_note(topic: str, pool: list[dict]) -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    title = TOPIC_TITLES[topic]
    used_list = "\n".join(f"- {item['label']}" for item in pool) or "(none)"

    content = (
        f"# {title} — material pool exhausted ({date.today().isoformat()})\n\n"
        f"No draft was generated today. Every real item currently in profile.json for "
        f"\"{title}\" has already been featured at least once:\n\n"
        f"{used_list}\n\n"
        "To keep this slot going, add new projects, credentials, skills, or milestones "
        "to profile.json — rotation will automatically pick up anything new next time "
        "this topic runs. Nothing was invented to fill the gap.\n"
    )
    out_path = DRAFTS_DIR / f"{date.today().isoformat()}_{topic}_EXHAUSTED.md"
    out_path.write_text(content, encoding="utf-8")
    logger.info("%s pool exhausted — wrote note to %s instead of a draft", title, out_path)
    return out_path


def _write_draft(topic: str, angle_label: str, personal_post: str, company_post: str, profile: dict) -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = angle_label.replace(" ", "_").replace(":", "").replace("/", "-")
    out_path = DRAFTS_DIR / f"{date.today().isoformat()}_{topic}_{slug}.md"

    content = (
        f"# {TOPIC_TITLES[topic]} — LinkedIn post draft ({date.today().isoformat()})\n\n"
        f"Angle: {angle_label}\n\n"
        "**DRAFT ONLY — NOT POSTED. Requires explicit review and manual posting.**\n\n"
        f"{NO_IMAGE_NOTE}\n\n"
        "## Personal profile post\n\n"
        f"{personal_post}\n\n"
        f"## {profile['business']} company page variant\n\n"
        f"{company_post}\n"
    )
    out_path.write_text(content, encoding="utf-8")
    logger.info("Wrote %s draft to %s", TOPIC_TITLES[topic], out_path)
    return out_path


def _build_notification_text(
    topic: str, angle_label: str, personal_post: str, company_post: str, profile: dict, out_path: Path
) -> str:
    """Full draft text inline, same style as the job digest — readable and
    copy-pasteable straight from WhatsApp, no need to open the file."""
    return (
        f"NAADVION Job Agent — new {TOPIC_TITLES[topic]} post draft ({angle_label}):\n\n"
        f"--- Personal profile post ---\n{personal_post}\n\n"
        f"--- {profile['business']} company page variant ---\n{company_post}\n\n"
        f"{NO_IMAGE_NOTE}\n\n"
        f"Also saved locally: {out_path}\n"
        "Reminder: review before posting — nothing here auto-posts."
    )


def draft_post(settings: Settings, profile: dict, topic: str, notify: bool = True) -> Path:
    if topic not in TOPIC_TITLES:
        raise ValueError(f"Unknown topic {topic!r}, expected one of {list(TOPIC_TITLES)}")

    if topic == TOPIC_REFLECTION:
        personal_prompt = REFLECTION_PERSONAL_PROMPT.format(
            name=profile["name"],
            career_status=profile["career_status"],
            skills=", ".join(profile.get("skills", [])),
            projects=", ".join(p["name"] for p in profile.get("projects", [])),
        )
        company_prompt = REFLECTION_COMPANY_PROMPT.format(
            business=profile["business"],
            career_status=profile["career_status"],
            skills=", ".join(profile.get("skills", [])),
            projects=", ".join(p["name"] for p in profile.get("projects", [])),
        )
        angle_label = "current learning/building focus"
        personal_post = generate_text(settings, personal_prompt)
        company_post = generate_text(settings, company_prompt)
        out_path = _write_draft(topic, angle_label, personal_post, company_post, profile)

    else:
        pool = _project_pool(profile) if topic == TOPIC_PROJECT else _credential_pool(profile)
        angle = _peek_next_rotating(topic, pool)

        if angle is None:
            out_path = _write_exhausted_note(topic, pool)
            if notify:
                backend = get_backend(settings)
                sent_ok = backend.send(
                    f"NAADVION Job Agent: {TOPIC_TITLES[topic]} material pool is exhausted — "
                    f"no draft today. Add new items to profile.json. See {out_path}"
                )
                logger.info("WhatsApp send result: %s", "SUCCESS" if sent_ok else "FAILED — see error above")
            return out_path

        angle_label = angle["label"]
        personal_prompt = PERSONAL_PROMPT.format(
            name=profile["name"], career_status=profile["career_status"],
            angle_label=angle_label, angle_detail=angle["detail"],
        )
        company_prompt = COMPANY_PROMPT.format(
            business=profile["business"],
            angle_label=angle_label, angle_detail=angle["detail"],
        )
        # Generate BEFORE committing rotation state — a failed Gemini call
        # must not burn this item's turn in the rotation (see _commit_rotation).
        personal_post = generate_text(settings, personal_prompt)
        company_post = generate_text(settings, company_prompt)
        _commit_rotation(topic, pool, angle)
        out_path = _write_draft(topic, angle_label, personal_post, company_post, profile)

    if notify:
        backend = get_backend(settings)
        sent_ok = backend.send(_build_notification_text(topic, angle_label, personal_post, company_post, profile, out_path))
        logger.info("WhatsApp send result: %s", "SUCCESS" if sent_ok else "FAILED — see error above")

    return out_path
