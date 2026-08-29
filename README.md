# NAADVION Job & Internship Finder Agent

**🔴 Live dashboard:** https://fozia-86.github.io/linkedin-job-agent/
*(Jobs found, scored and drafted; Connect suggestions per job; run history — all real output from the last scheduled run, not a mockup.)*

A standalone agent that finds remote-first AI/backend/cloud jobs and
internships, scores them against a real skills profile, drafts tailored
outreach messages and LinkedIn connection notes with Gemini, and sends a
WhatsApp digest twice a day — **it never applies, connects, or posts on your
behalf.** Every draft is reviewed and sent by a human.

## What this does

1. **Finds postings** from three public, documented APIs —
   [RemoteOK](https://remoteok.com/api),
   [Arbeitnow](https://arbeitnow.com/api/job-board-api), and
   [Adzuna](https://developer.adzuna.com/) (optional, free tier). No
   LinkedIn scraping, ever — see [Hard rules](#hard-rules-this-project-follows-do-not-remove).
2. **Scores every posting** against `profile.json` (`src/scoring.py`) —
   keyword matches against your real skills, a soft down-weight for
   senior-sounding titles (Senior/Lead/Principal/Manager/Director) and a
   soft up-weight for entry-level signals (Junior/Intern/Graduate,
   contract/part-time roles), a penalty when a description states an
   explicit multi-year experience requirement, and a cap that keeps Adzuna
   (which doesn't cover Pakistan and isn't a worldwide-remote-native board
   like the other two) supplementary rather than dominant.
3. **Drafts a tailored application message** for each match with Gemini
   (`src/drafting.py`), grounded strictly in `profile.json` — real
   projects, real credentials, no invented client history.
4. **Drafts a LinkedIn connect suggestion** for the same posting
   (`src/connects.py`): a constructed LinkedIn People search URL (company +
   recruiter/talent-acquisition/hiring-manager keywords — you click it and
   pick the actual person, this is a plain link, not scraping) plus a short
   connection note under LinkedIn's 200-character limit, grounded the same
   way as the job draft.
5. **Sends a WhatsApp digest** twice a day (`src/whatsapp/`) with Jobs and
   Connects in clearly separate sections — Meta Cloud API, a generic
   webhook backend, or a local file if neither is configured.
6. **Publishes a dashboard** (`src/dashboard.py` → `docs/index.html`,
   GitHub Pages) mirroring the digest, with a short run history.
7. **Drafts LinkedIn posts 3x/week** (`src/post_drafter.py`) on a fixed
   topic rotation — Tuesday project spotlight, Thursday credential/skill
   highlight, Saturday learning-in-progress reflection — picking a
   different real project/credential each time until the pool is used up,
   then asking for more material instead of inventing any.

Nothing above ever applies to a job, sends a connection request, or posts
anything — every output is a draft for a human to review and act on.

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
- **Never auto-connects on LinkedIn.** [`src/connects.py`](src/connects.py) only
  builds a search link and drafts a note — sending the actual connection
  request always requires you to open LinkedIn and do it yourself.
- **Never invents facts.** Every draft is grounded strictly in `profile.json`.
  The AI is explicitly instructed to say so, rather than invent a client,
  testimonial, result, or certification that isn't listed.

## Project structure

```
profile.json                Your facts — the only source of truth for every draft
.env                         Your secrets/settings (copy from .env.example)
src/
  config.py                  Loads .env + profile.json
  postings.py                 Shared Posting data structure
  sources/                     RemoteOK / Arbeitnow / Adzuna fetchers (public APIs only)
  scoring.py                   Matches + ranks postings against your skills/keywords
  gemini_client.py             Thin Gemini API wrapper (retries, quota detection)
  drafting.py                   Drafts application messages, grounded in profile.json
  connects.py                   LinkedIn search link + connection-note drafter
  dashboard.py                   Renders docs/index.html (GitHub Pages) + run history
  cache.py                        Avoids re-sending the same posting every run
  whatsapp/                        Meta Cloud API / generic webhook / local-file fallback
  digest.py                        Wires fetch -> score -> draft -> connect -> dashboard -> send
  post_drafter.py                  3x/week LinkedIn post drafter, fixed topic rotation
  main.py                            CLI entrypoints (see Setup below)
  scheduler.py                        Twice-daily + 3x/week APScheduler jobs (local, optional)
data/                        Generated at runtime: seen-posting cache, digests, drafts,
                              post_history.json, dashboard_history.json — all committed
                              back to the repo by GitHub Actions so state survives
                              between runs on ephemeral runners
docs/                        GitHub Pages dashboard — index.html generated by dashboard.py
.github/workflows/schedule.yml   Runs the digest twice daily on GitHub's infrastructure
```

## Setup

```bash
cd linkedin-job-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then edit .env with the values below
```

| Env var | Where to get it | Required? |
|---|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | Required for drafts (job fetching works without it) |
| `WHATSAPP_META_TOKEN`, `WHATSAPP_META_PHONE_NUMBER_ID`, `WHATSAPP_META_TO_NUMBER` | [developers.facebook.com/apps](https://developers.facebook.com/apps) → WhatsApp product | Optional — see [WhatsApp delivery](#whatsapp-delivery) below |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | [developer.adzuna.com](https://developer.adzuna.com/) — free signup | Optional (RemoteOK + Arbeitnow work without it) |
| `WHATSAPP_WEBHOOK_URL`, `WHATSAPP_WEBHOOK_TOKEN` | Your webhook provider's dashboard (e.g. Blueticks) | Optional — alternative to the Meta Cloud API row above |

If none of the WhatsApp options are set, the digest is written to
`data/digests/` and printed to the terminal instead — the whole pipeline
stays testable with zero WhatsApp setup. Edit `profile.json` with your own
name, skills, real projects, and credentials before running anything for
real — it's the only source of truth the AI is allowed to draw on.

**Run locally, one piece at a time:**

```bash
python -m src.main fetch-jobs           # fetch + score only, no Gemini/WhatsApp calls, free
python -m src.main run-digest           # full pipeline: fetch, score, draft, connect, dashboard, send
python -m src.main test-whatsapp        # send a test message through the configured backend
python -m src.main draft-project-post   # test any post-drafter topic on demand, any day
python -m src.main draft-credential-post
python -m src.main draft-reflection-post
python -m src.main schedule             # long-running local scheduler (see note below)
```

`schedule` runs everything (twice-daily digest + 3x/week posts) as a
foreground process — it needs the machine on and the process alive at each
scheduled time, and a missed run isn't caught up later. For the job digest,
prefer the GitHub Actions workflow below; `schedule` (or Windows Task
Scheduler running the individual commands above) is still how the post
drafter runs, since that piece isn't on GitHub Actions yet.

## How it stays fresh

[`.github/workflows/schedule.yml`](.github/workflows/schedule.yml) runs the
job digest on GitHub's own infrastructure, targeting 9:00 AM and 5:00 PM
Asia/Karachi (fixed UTC+5 offset — Pakistan has no daylight saving to
account for), so it works even when the laptop is off or asleep. Each run:

1. Checks out the repo and installs `requirements.txt`.
2. Runs `python -m src.main run-digest`, reading every credential from
   **GitHub Actions Secrets** as a plain environment variable — no secret
   ever lives in the workflow file or gets committed.
3. Commits `data/seen_postings.json`, `data/dashboard_history.json`, and
   `docs/index.html` back to the repo as `github-actions[bot]` and pushes —
   GitHub's runners are ephemeral, so without this step every run would
   start from a blank cache/history and you'd get duplicate postings and no
   dashboard trend history.

**On timing:** `schedule:` triggers on GitHub Actions are best-effort, not
exact — GitHub explicitly does not guarantee a scheduled workflow fires at
the precise minute, especially on free-tier/low-activity repos, and delays
of tens of minutes to a few hours are expected/normal behavior, not a bug.
If a run seems very late, check the Actions tab before assuming something's
broken.

**Note on scope:** this workflow only covers the job digest. The 3x/week
post drafter still needs `python -m src.main schedule` running locally (or
a second, similar workflow).

### Manual setup — you still need to do these yourself

These require your own GitHub login, so they can't be automated:

1. **Add each GitHub Actions secret** — in this repo, go to **Settings →
   Secrets and variables → Actions → New repository secret**, and add
   `GEMINI_API_KEY`, `WHATSAPP_META_TOKEN`, `WHATSAPP_META_PHONE_NUMBER_ID`,
   `WHATSAPP_META_TO_NUMBER`, and (optional) `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`
   — same values as your local `.env`.
2. **Turn on GitHub Pages** for the dashboard — **Settings → Pages** → under
   "Build and deployment", set **Source** to "Deploy from a branch" →
   **Branch**: `main`, folder: `/docs` → **Save**. Publishes at
   `https://<your-username>.github.io/<repo-name>/` within a minute or two.

## WhatsApp delivery

### Logs say "SUCCESS" but the message never arrives

This almost always means Meta's Cloud API *accepted* the message, not that
it was actually *delivered* — a delivery-side issue, not a code bug. Common
causes, in likely order:

1. **The 24-hour customer-service window has closed.** WhatsApp Business
   only allows free-form text messages to a number within 24 hours of that
   number last messaging *your* business number. Outside that window, only
   a pre-approved message template can be delivered — a plain text digest
   is silently dropped even though the API call itself returns success.
   Send a WhatsApp message *to* your business number to reopen the window,
   or set up an approved template for outside-window delivery.
2. **An expired or unapproved message template**, if you're using one.
3. **A mismatch in `WHATSAPP_META_PHONE_NUMBER_ID`/`WHATSAPP_META_TO_NUMBER`**
   — double check these against your Meta app's WhatsApp → API Setup page.

**To check what actually happened:** go to
[business.facebook.com](https://business.facebook.com) → **WhatsApp
Manager** → your phone number → message insights/logs, and look up the
delivery status (sent/delivered/read/failed) for the message around the
time your run happened. `src/whatsapp/meta_cloud.py` also logs the full
response status code and body from Meta on every send (success or
failure) — check that log line first; it often names the exact reason
(e.g. a template-required error) without needing to open Meta Business
Suite at all.

## Dashboard

[`docs/index.html`](docs/index.html) ([live link](https://fozia-86.github.io/linkedin-job-agent/))
is a static page generated by [`src/dashboard.py`](src/dashboard.py) on
every `run-digest` (local or GitHub Actions), mirroring the WhatsApp digest
with two clearly separated sections — **Jobs found** and **Connect
suggestions** — plus a short history of the last few runs
(`data/dashboard_history.json`) so trends are visible across days instead
of only the most recent run. It's read-only: nothing on the page applies,
connects, or posts anything, it's just a browsable copy of what's already
been drafted. No JS framework, no build step — plain HTML/CSS/JS, one
Python function.

## Reusing this for someone else

Everything person-specific lives in `profile.json` and `.env`. To repackage
this for another user: give them this repo, have them follow Setup above
with their own `profile.json` and `.env`, and the pipeline logic (`src/`)
never needs to change.
