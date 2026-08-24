# NAADVION Job & Internship Finder Agent

A standalone agent that finds remote-first AI/backend/cloud jobs and internships,
scores them against your real skills, drafts a short honest application message
for each match, and sends you a WhatsApp digest twice a day — **it never applies,
connects, or posts on your behalf.** You review every draft and act on it yourself.

It also drafts LinkedIn posts 3x/week (personal + company-page variant) on a fixed
topic rotation — Tuesday project spotlight, Thursday credential/skill highlight,
Saturday learning-in-progress reflection — for you to review and post manually if
you approve. See [`src/post_drafter.py`](src/post_drafter.py) for how the rotation
avoids repeating the same project/credential until every real one has been used.

Everything specific to you (name, business, skills, real projects, credentials)
lives in [`profile.json`](profile.json) — nothing is hardcoded into the pipeline
logic, so this same codebase can be reused by anyone who drops in their own
`profile.json` and `.env`.

## Hard rules this project follows (do not remove)

- **No LinkedIn scraping, no LinkedIn login automation.** Job sources are limited
  to documented public APIs: [RemoteOK](https://remoteok.com/api),
  [Arbeitnow](https://arbeitnow.com/api/job-board-api), and
  [Adzuna](https://developer.adzuna.com/) (free tier, API key required).
- **Never auto-applies.** [`src/digest.py`](src/digest.py) only drafts messages
  and sends a digest — applying always happens manually via the posting's own link.
- **Never auto-posts to LinkedIn.** [`src/post_drafter.py`](src/post_drafter.py)
  only writes draft files — posting always requires your explicit review and
  manual action.
- **Never invents facts.** Every draft is grounded strictly in `profile.json`.
  The AI is explicitly instructed to say so, rather than invent a client,
  testimonial, result, or certification that isn't listed.

## Setup (10 minutes or less)

### 1. Install dependencies

```bash
cd linkedin-job-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Copy `.env.example` to `.env` and fill in your API keys

```bash
copy .env.example .env
```

Then open `.env` and fill in:

| Variable | Where to get it | Required? |
|---|---|---|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | [developer.adzuna.com](https://developer.adzuna.com/) — free signup | Optional (RemoteOK + Arbeitnow work without it) |
| `GEMINI_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | Required for drafts (job fetching works without it) |
| `WHATSAPP_META_TOKEN`, `WHATSAPP_META_PHONE_NUMBER_ID`, `WHATSAPP_META_TO_NUMBER` | [developers.facebook.com/apps](https://developers.facebook.com/apps) → WhatsApp product | Optional — see below |
| `WHATSAPP_WEBHOOK_URL`, `WHATSAPP_WEBHOOK_TOKEN` | Your webhook provider's dashboard (e.g. Blueticks) | Optional — alternative to the row above |

**If you skip both WhatsApp options**, the digest is written to
`data/digests/` and printed to the terminal — the whole pipeline stays
testable with zero WhatsApp setup.

*(Advanced/optional — skip if you're not a developer: you can tune
`MAX_RESULTS_PER_DIGEST`, `MIN_MATCH_SCORE`, and the schedule times at
the bottom of `.env`.)*

### 3. Edit `profile.json` with your own facts

Open [`profile.json`](profile.json) and replace the sample content with your own
name, business, skills, keywords, real projects, and credentials. **Only put
things here that are actually true** — this file is the single source of truth
the AI is allowed to draw on, and it's instructed not to go beyond it.

> Note: the `repo_url` fields in the sample `profile.json` are left blank with a
> `_fill_in` hint — add the exact GitHub URL for each project before relying on
> it, since a guessed URL is exactly the kind of unverified fact this project
> avoids inventing.

### 4. Test each piece independently

Run these one at a time, in order — each is cheap and safe to re-run:

```bash
# 1. Fetch + score jobs only (no Gemini or WhatsApp calls, free)
python -m src.main fetch-jobs

# 2. Test your WhatsApp delivery (or confirm the local fallback works)
python -m src.main test-whatsapp

# 3. Full pipeline once: fetch, score, draft with Gemini, send digest
python -m src.main run-digest

# 4. Draft each post-drafter topic on demand, without waiting for its actual day
python -m src.main draft-project-post      # Tuesday's topic: project spotlight
python -m src.main draft-credential-post   # Thursday's topic: credential/skill highlight
python -m src.main draft-reflection-post   # Saturday's topic: learning-in-progress reflection
```

Check `data/digests/` and `data/post_drafts/` after steps 3 and 4 if you're
using the local fallback (no WhatsApp configured). Project/credential rotation
state lives in `data/post_history.json` — if a topic's real material runs out
(every project or credential in `profile.json` already featured once), that
command writes a note instead of a draft asking you to add more to
`profile.json`, rather than inventing something to stay "fresh."

### 5. Schedule it

Once steps above work, start the long-running scheduler (runs the digest at
9:00 AM and 5:00 PM, and the post drafter at 10:00 AM on Tue/Thu/Sat with the
fixed topic for that day — times in `.env`, default timezone `Asia/Karachi`):

```bash
python -m src.main schedule
```

Leave this running in a terminal, a `screen`/`tmux` session, or set it up as a
background service / scheduled task so it survives reboots. APScheduler was
chosen over cron because it's one portable Python command that works the same
on Windows, macOS, and Linux — no platform-specific crontab setup needed.

**Reliability caveat:** this runs as a foreground process — it needs the
machine on and the process alive at each scheduled time. If the machine is
asleep or the process isn't running at 9:00 AM/5:00 PM/post-drafter time,
that run is skipped (not caught up later — APScheduler's default 1-second
misfire grace time means a missed run just doesn't happen). For a setup you
actually rely on daily, prefer **Windows Task Scheduler** running
`python -m src.main run-digest` / `draft-project-post` / etc. as separate
one-shot scheduled tasks instead of the long-running `schedule` command —
Windows will wake the machine and survive reboots/logouts on its own.

## Project layout

```
profile.json          Your facts — the only source of truth for drafts
.env                   Your secrets/settings (copy from .env.example)
src/
  config.py            Loads .env + profile.json
  postings.py           Shared Posting data structure
  sources/               RemoteOK / Arbeitnow / Adzuna fetchers (public APIs only)
  scoring.py             Matches + ranks postings against your skills/keywords
  gemini_client.py       Thin Gemini API wrapper
  drafting.py             Drafts application messages, grounded in profile.json
  cache.py                Avoids re-sending the same posting every run
  whatsapp/                Meta Cloud API / generic webhook / local-file fallback
  digest.py                Wires fetch -> score -> draft -> send together
  post_drafter.py          3x/week LinkedIn post drafter, fixed topic rotation
  main.py                  CLI entrypoints (see step 4 above)
  scheduler.py             Twice-daily + 3x/week APScheduler jobs
data/                    Generated at runtime: seen-posting cache, digests, drafts,
                          post_history.json (rotation state)
```

## Running the job digest on GitHub Actions (recommended)

The `schedule` command only runs while your machine is on. For a setup that
runs the twice-daily job digest reliably even when your laptop is off/asleep,
[`.github/workflows/schedule.yml`](.github/workflows/schedule.yml) runs
`run-digest` on GitHub's own infrastructure at 9:00 AM and 5:00 PM
Asia/Karachi (fixed UTC+5 offset — Pakistan has no daylight saving to account
for). See that file's comments for exactly how it works, including why it
commits `data/seen_postings.json` back to the repo after each run (GitHub's
runners don't persist any state between runs on their own).

**Note on scope:** this workflow only covers the job digest. The 3x/week post
drafter still needs `python -m src.main schedule` running locally (or a
second, similar workflow) — ask if you want that moved to GitHub Actions too.

No secret ever lives in the workflow file or gets committed — every credential
is read from GitHub Actions Secrets as a plain environment variable, exactly
the same way `src/config.py` reads a local `.env`.

## Reusing this for someone else

Everything person-specific lives in `profile.json` and `.env`. To repackage this
for another user: give them this repo, have them follow steps 1-5 above with
their own `profile.json` and `.env`, and the pipeline logic (`src/`) never needs
to change.
