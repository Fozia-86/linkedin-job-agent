"""APScheduler wiring for the twice-daily job digest and weekly post drafter.

Chosen over cron because it's a single portable Python process — no
platform-specific crontab/Task Scheduler setup needed, which keeps
first-time setup simple on any OS (see README for the one-line command
to run this persistently).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings, get_profile
from .digest import run_digest
from .post_drafter import TOPIC_CREDENTIAL, TOPIC_PROJECT, TOPIC_REFLECTION, draft_post

logger = logging.getLogger(__name__)

# Fixed day -> topic mapping, per spec: Tue = project spotlight,
# Thu = credential/skill highlight, Sat = learning-in-progress reflection.
POST_DRAFTER_SCHEDULE = {
    "tue": TOPIC_PROJECT,
    "thu": TOPIC_CREDENTIAL,
    "sat": TOPIC_REFLECTION,
}


def _job_run_digest() -> None:
    settings = get_settings()
    profile = get_profile()
    try:
        run_digest(settings, profile)
    except Exception:
        logger.exception("run_digest job failed")


def _job_post_drafter(topic: str) -> None:
    settings = get_settings()
    profile = get_profile()
    try:
        draft_post(settings, profile, topic)
    except Exception:
        logger.exception("post drafter job failed for topic=%s", topic)


def run_scheduler() -> None:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.timezone)

    morning_h, morning_m = settings.morning_run_time.split(":")
    evening_h, evening_m = settings.evening_run_time.split(":")
    post_h, post_m = settings.post_drafter_time.split(":")

    scheduler.add_job(
        _job_run_digest, CronTrigger(hour=morning_h, minute=morning_m, timezone=settings.timezone),
        id="morning_digest", name="Morning job digest",
    )
    scheduler.add_job(
        _job_run_digest, CronTrigger(hour=evening_h, minute=evening_m, timezone=settings.timezone),
        id="evening_digest", name="Evening job digest",
    )
    for day, topic in POST_DRAFTER_SCHEDULE.items():
        scheduler.add_job(
            _job_post_drafter, CronTrigger(day_of_week=day, hour=post_h, minute=post_m, timezone=settings.timezone),
            id=f"post_drafter_{day}", name=f"Post drafter ({topic})", kwargs={"topic": topic},
        )

    logger.info(
        "Scheduler started (timezone=%s): digest at %s and %s daily, post drafter at %s on %s",
        settings.timezone, settings.morning_run_time, settings.evening_run_time,
        settings.post_drafter_time, ", ".join(POST_DRAFTER_SCHEDULE.keys()),
    )
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_scheduler()
