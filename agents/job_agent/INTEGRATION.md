# Job Agent — Strategy F integration

The Job Agent runs independently on port `5020`, registers as
`job_agent@v1.0.0`, and is reached from the shared UI only through
`POST /gateway/agents/job_agent/invoke` — see [STRATEGY_F.md](../../STRATEGY_F.md)
for the pattern itself.

## Dispatcher shape

`invoke.py` re-enters this app's own `/api/jobs/*` routes (`routes.py`)
in-process via `current_app.test_client()`, using a static
`{action: (method, path)}` map — the same shape
`agents/resume_builder_agent/backend/app/routes/invoke.py` uses, chosen for
the same reason: `routes.py`'s handlers already read `request`/`g` directly
(query params, JSON bodies, path params) instead of exposing separate
payload-taking functions, so re-entering them avoids re-implementing that
logic a second time as a hand-written map.

## Identity

Unlike `resume_builder_agent`'s precedent (an `X-User-Id` header gated
behind `ALLOW_DEV_USER_HEADER`, since its identity rode the raw JSON
payload), this agent's identity is stronger by construction: the
orchestrator's gateway (`agents/orchestrator/app/gateway/routes.py`) already
decodes the platform's own login JWT for every non-`health` call and
forwards a **server-verified** `X-Digidara-User-Id` header — never
something the browser can forge directly. `X-Digidara-Is-Admin` follows the
same trust model, set by the gateway only when the requesting user's
`users.is_admin` column is true.

`auth.py`'s `user_required`/`admin_required` decorators read only these two
headers — nothing in this agent's own code path ever trusts an identity
value carried inside the JSON payload.

`invoke.py` re-attaches exactly these two headers (and no others) onto its
internal `test_client()` calls into `routes.py`.

## Action map

| Action | Route | Notes |
|---|---|---|
| `health` | n/a | Unauthenticated, mandatory |
| `ensure_profile` | n/a (inline in `invoke.py`) | Identity-bridge: lazily creates a `user_job_profiles` row for the platform user id on first contact |
| `get_profile` / `update_profile` | `GET`/`PUT /api/jobs/me/profile` | Includes `full_name` (collected once, separately from the DigiDARA login name) |
| `upload_resume` | `POST /api/jobs/me/resume` (multipart) | Stores the file under `config.UPLOAD_DIR/<user_id>/`; never parsed — see `config.py`'s `ALLOWED_RESUME_EXTENSIONS`/`RESUME_MAX_BYTES` |
| `get_categories` | `GET /api/jobs/me/categories` | |
| `get_feed` | `GET /api/jobs/me/feed` | Scored, free-tier capped at `JOBS_FREE_TIER_FEED_LIMIT` |
| `job_action` | `PUT /api/jobs/me/jobs/{job_id}/action` | save / unsave / hide / apply |
| `get_applications` | `GET /api/jobs/me/applications` | |
| `export_user_data` / `delete_user_data` | `GET`/`DELETE /api/jobs/me/data` | Extends platform account export/erasure to Job profiles, actions, and stored resumes |
| `admin_*` | `/api/jobs/admin/*` | Moderation, source health, Greenhouse/Apify provider ops, TN coverage, plan management — gated on `X-Digidara-Is-Admin` |

## What changed from the module as originally written

The module was originally built against a separate, external certification
portal's schema (`cert_students`, `cert_issued`, `cert_exams`,
`cert_exam_subjects`) and a `MAIN_SECRET`/`CERT_SECRET` JWT scheme — neither
of which exists in this repository's `agents/certificate_agent` (a
different, FastAPI-based service with an unrelated schema). That coupling
has been removed:

- `eligibility.py` — deleted. There is no certificate-issuance gate; any
  authenticated DigiDARA user can use this agent once their identity is
  bridged via `ensure_profile`.
- `auth.py` — rewritten around the gateway's verified headers (above)
  instead of a foreign JWT secret.
- `db.py` — `student_job_profiles`/`student_job_actions` (FK'd to
  `cert_students`) became `user_job_profiles`/`user_job_actions`, keyed
  directly on the DigiDARA platform user id string — no duplicate local
  users table, no dependency on any other agent's schema. Own database
  (`DB_NAME=job_agent`), never the shared `digidara_db` the original
  design assumed.
- `routes.py` — `/api/jobs/student/*` became `/api/jobs/me/*`;
  `/api/jobs/admin/students` and `.../students/<id>/access` (the
  cert-portal "enable job access" gate) were removed since that access
  model no longer exists; `/api/jobs/admin/users` and
  `/api/jobs/admin/users/<id>/plan` were added in their place — real SaaS
  levers (view users, set `plan_tier`) rather than a removed gate.

Everything else — `scraper.py`, `matching.py`, `categories.py`,
`tn_location.py`, `providers/` (Greenhouse, the Apify scaffold), `worker.py`,
`service.py` — is unchanged; none of it depended on the cert-portal
coupling.

## Configuration and local verification

```powershell
cd agents\job_agent
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python.exe run.py
```

```powershell
$body = @{ action = "health"; payload = @{} } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8100/gateway/agents/job_agent/invoke" -Method Post -ContentType "application/json" -Body $body
# {"status":"ok","agent_name":"job_agent"}
```

## Background ingestion worker

All batch Greenhouse and Apify admin actions enqueue per-source
`job_ingestion_runs` and return `202`; provider network calls never occupy
the Job Agent or orchestrator HTTP workers. The admin UI polls run state,
and duplicate active runs are suppressed. See [README.md](README.md) and
[providers/README.md](providers/README.md). `worker.py` uses
package-relative imports, so run it as a module from `agents/` (one level
above `job_agent/`), not from inside the package folder itself:

```powershell
cd agents
job_agent\.venv\Scripts\python.exe -m job_agent.worker
```

## Not yet implemented

- Naukri/Indeed/Glassdoor/Foundit providers still need live actor-output
  verification. LinkedIn has a dedicated normalizer and configured actor;
  production collection additionally requires `APIFY_API_TOKEN`.
- ~~The `/admin` panel UI in the root React app~~ — done: `AdminShell` and
  `src/components/admin/JobsAdminPanel.tsx` now consume this agent's admin
  actions via `src/lib/jobFetchApi.ts`.
