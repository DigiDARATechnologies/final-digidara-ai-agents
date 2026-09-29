# Job Agent

A standalone Strategy F agent (see [STRATEGY_F.md](../../STRATEGY_F.md))
that collects public job postings, scores them against a user's declared
profile, and serves a save/apply-tracked job feed through the shared
DigiDARA chat UI — plus an admin surface for moderation and source health,
reached through the same gateway under a verified admin flag rather than a
separate login. See [INTEGRATION.md](INTEGRATION.md) for the Strategy F
wiring detail (dispatcher shape, identity, action map).

## Flow

1. The user opens the Job Fetching Agent card in chat; `ensure_profile`
   bridges their DigiDARA login into a `user_job_profiles` row.
2. If the profile isn't complete yet, the chat collects skills, preferred
   titles, preferred locations, work mode, and experience.
3. `get_feed` returns jobs scored against that profile (see
   `matching.py`), capped by plan tier (`config.py`'s
   `FREE_TIER_DAILY_FEED_LIMIT` for the free tier).
4. `job_action` records save / hide / apply; `get_applications` lists what
   was applied to.

## Architecture

- `auth.py` — reads the orchestrator gateway's verified
  `X-Digidara-User-Id` / `X-Digidara-Is-Admin` headers; no local login.
- `db.py` — this agent's own, independent database schema.
- `memory.py` — user-isolated, database-backed conversation history,
  idempotent turns, retention, and confirmed structured profile memory.
- `matching.py` — explainable profile/job scoring.
- `categories.py` / `categories.yaml` — keyword-based job/course
  categorization, with category-relatedness (e.g. a Python-track user also
  sees Data Analytics/Science/AI-ML roles).
- `scraper.py` — permission-aware JSON-LD, RSS, and configured HTML
  collection (validates public reachability + `robots.txt` before ever
  fetching a source).
- `service.py` — deduplication, persistence, ingestion-run auditing.
- `routes.py` — user (`/api/jobs/me/*`) and admin (`/api/jobs/admin/*`)
  HTTP handlers.
- `invoke.py` — the Strategy F `/api/invoke` adapter re-entering the above.
- `worker.py` — out-of-process ingestion worker.
- `providers/` — configuration-driven collection sources (Greenhouse live;
  LinkedIn has a dedicated Apify normalizer; the remaining Apify platforms
  require live actor-output verification). See
  [providers/README.md](providers/README.md).

Conversation history is owned by the server rather than trusted from the
browser. Only confirmed structured profile fields become long-term memory;
assistant prose is never promoted to a user fact. Authenticated users can list
or delete conversations and inspect or forget individual memories through the
conversation and memory invoke actions. Account deletion cascades through
these tables, and user data export includes them.

## Run the service

```powershell
cd agents\job_agent
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# For host-local (non-Docker) startup, change DB_HOST to 127.0.0.1,
# ORCHESTRATOR_URL to http://127.0.0.1:8100, and AGENT_PUBLIC_URL to
# http://127.0.0.1:5020/api/invoke in .env.
.\.venv\Scripts\python.exe run.py
```

For the containerized platform, keep the Docker service names from
`.env.example` and run `docker compose up -d --build job-agent job-worker`
from the repository root. Both services use the same image: `job-agent`
serves HTTP while `job-worker` consumes queued ingestion runs.

## Run the ingestion worker

From `agents/` (one level above this folder — `worker.py` uses
package-relative imports):

```powershell
cd agents
job_agent\.venv\Scripts\python.exe -m job_agent.worker
```

Process at most one queued run:

```powershell
job_agent\.venv\Scripts\python.exe -m job_agent.worker --once
```

Run the continuous worker under the same process manager that runs any
other agent in this fleet. The admin API only queues work; it never scrapes
inside a web request.

The admin Greenhouse and Apify controls return HTTP `202` after creating
one `job_ingestion_runs` row per eligible source. The worker claims those
runs independently, and the Sources tab polls their queued/running/
completed/failed state. Repeated clicks reuse an existing queued/running
run for that source. On startup, the worker requeues abandoned `running`
rows older than `JOBS_RUN_STALE_SECONDS` (30 minutes by default).

## Source policy

Only configure sources that permit automated collection. A source must be
explicitly marked authorized, remain active, resolve to a public network
address, and permit the configured user agent in `robots.txt`. Redirect
destinations receive the same public-address validation. Collected jobs
enter `pending` moderation status.

Supported source types:

- `json_ld`: extracts Schema.org `JobPosting` data from a public career page.
- `rss`: reads a public RSS or Atom jobs feed.
- `html_cards`: uses explicitly configured CSS selectors for a
  server-rendered page.
- `greenhouse`: Greenhouse's public, no-auth Job Board API — see
  [providers/README.md](providers/README.md).
- `apify`: scaffolded, not yet wired to a specific actor — see
  [providers/README.md](providers/README.md).

Example `html_cards` parser configuration:

```json
{
  "item_selector": ".job-card",
  "fields": {
    "title": ".job-title",
    "company": ".company",
    "location": ".location",
    "description": ".summary",
    "skills": ".skills",
    "apply_url": {
      "selector": "a.apply",
      "attribute": "href",
      "url": true
    }
  }
}
```

Configuration variables — see [.env.example](.env.example) for the full
list, including Strategy F registration and database settings.

### Candidate search context

Explicit requests such as `send the machine learning jobs in Madurai` perform
an active, unexpired portal catalogue search, including during onboarding.
Approved role-family aliases are title filters, not inferred user skills.
Current filters override saved preferences for this search only; no profile
facts are changed. Catalogue results retain their actual experience requirements
and personal match scores rather than being silently removed by the personalized
recommendation blend. Empty results are portal-specific, not claims about the
entire job market.

Completed search filters and displayed job IDs are stored in existing response
metadata, scoped by user and conversation. Bounded recent server history supports
`what about Chennai?`, related/other-location/remote actions, and non-repeating
more-results retrieval. Client-provided history cannot supply structured search
metadata. Candidate cards/details omit ingestion-provider names while retaining
safety warnings, match scores and real application links. Admin source metadata
and ingestion configuration are unchanged. No additional schema is required.

Profile clarification runs before search or field extraction. Purpose questions
(for example, `why do you need my name?`) explain the relevant profile section;
completion questions list missing required facts rather than assuming completion
or interpreting unanswered experience as fresher. A refusal does not populate
fields or advance onboarding. A nickname is accepted for the name section, a
resume remains optional, and explicit role/city searches still work without a
completed profile. Clarification responses include read-only `profile_status`
metadata; they do not use a model to invent saved facts.

Short greetings and check-ins during onboarding are acknowledged without
being stored as names, skills, roles, or experience. The reply gives a gentle
reminder of the next missing field; a pending role confirmation remains
answerable afterward. Mixed messages containing real profile facts continue
through normal extraction. Completed profiles are not reopened by greetings.

During incomplete onboarding, unanswered career questions use a bounded
question-answer path. Profile edits and portal searches remain deterministic
and execute before that path. Common explanations and unrelated requests get
safe local replies; other career questions may use the configured language
model with a strict JSON response, a short timeout, and server-supplied profile
context. The model cannot save profile fields, supply job cards, or claim a
portal search. If it is unavailable, the agent says it cannot answer reliably
instead of repeating the onboarding question or inventing facts.
