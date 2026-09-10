# Running DigiDARA AI Agents in Docker

This containerizes the platform for local/dev use: one container per agent,
one for the orchestrator, one for the React frontend (nginx), a shared
`mysql` container, and Judge0 (already containerized — included as-is, not
rebuilt). Docker is an **addition**, not a replacement — the existing
`ecosystem.config.js` / PM2 setup for the VPS is untouched.

Every agent still self-registers with the orchestrator by logical name over
HTTP and heartbeats every 30s, same as outside Docker — only the *addresses*
agents use to find each other changed (Docker service names instead of
`127.0.0.1`).

## Prerequisites

- Docker Desktop (or Docker Engine) with Compose V2 **2.20.0 or newer** —
  required for the `include:` directive this stack uses to fold in Judge0's
  own compose file.
- `agents/codeforge_agent/judge0/judge0.conf` already exists in this repo
  (Judge0's own config) — nothing to set up there.

## First-time setup

1. Copy every service's `.env.example` to `.env` (compose will fail to
   start a service if its `.env` is missing):

   ```
   cp agents/orchestrator/.env.example agents/orchestrator/.env   # only if you don't already have one
   cp agents/project_AI_Agent/.env.example agents/project_AI_Agent/.env
   cp agents/codeforge_agent/services/lms-api/.env.example agents/codeforge_agent/services/lms-api/.env
   cp agents/communication-ai-agent/backend/.env.example agents/communication-ai-agent/backend/.env
   cp agents/aptitude_agent/.env.example agents/aptitude_agent/.env
   cp agents/resume_builder_agent/backend/.env.example agents/resume_builder_agent/backend/.env
   cp agents/certificate_agent/.env.example agents/certificate_agent/.env
   cp agents/job_agent/.env.example agents/job_agent/.env
   cp docker/mysql/.env.example docker/mysql/.env
   ```

2. In `docker/mysql/.env`, set a real `MYSQL_ROOT_PASSWORD`.

3. In **every** agent `.env` you just copied, set `DATABASE_URL` /
   `MYSQL_PASSWORD` / `DB_PASSWORD` to that **same** password (all agents connect to MySQL
   as `root` — no separate per-service MySQL user is created). The
   `.env.example` files use `change-me` as a placeholder in the same spot.

4. **`AGENT_SHARED_SECRET`** must be identical across every agent's `.env`
   and the orchestrator's `.env` — this was already a requirement before
   Docker and still is. If you're not setting it explicitly, every
   agent's registry client and `agent_wrapper.py` share the same
   `dev-only-agent-shared-secret` fallback, so leaving it unset everywhere
   is fine for local dev; setting it in only *some* `.env` files will break
   registration.

5. Fill in your real `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY`
   / `GOOGLE_CLIENT_ID` / etc. in the relevant `.env` files as you would
   outside Docker. `certificate-agent` is stricter than the others here: it
   refuses to boot at all unless `SECRET_KEY`, `OPENAI_API_KEY`, and
   `DB_PASSWORD` are set to real values (not the `your_...` placeholders in
   its `.env.example`) — see `cert_app/config.py`'s `validate_secrets`.

6. To expose the administration area, set `ADMIN_EMAIL` and
   `ADMIN_PASSWORD` in `agents/orchestrator/.env`. Startup creates or
   promotes that account without resetting an existing password.

## Running the stack

```
docker compose up -d --build
```

This builds and starts, in dependency order: `mysql` → `orchestrator` →
the seven agent APIs (plus the Job ingestion worker) → `frontend`, plus
Judge0's `server`/`worker`/`db`/`redis`.
First boot creates the eight MySQL databases automatically (see
`docker/mysql-init/01-create-databases.sql`); each service still runs its
own migrations/`create_all()` against its database the same as before.

Open the app at **http://localhost:5173**.

## Checking everything is healthy

```
docker compose ps
```

The `STATUS` column shows `healthy`/`unhealthy` for every service that has
a `HEALTHCHECK` (all 8 Python services + the frontend). Judge0's own
services (`server`, `worker`, `db`, `redis`) don't define one — see
[Judge0 wiring](#judge0-wiring) below.

Manual checks (from the host, since every backend port is internal-only,
you must exec into a container or use `docker compose exec`):

```
docker compose exec orchestrator python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/health').read())"
docker compose exec codeforge-agent python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:4000/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); print(urllib.request.urlopen(req).read())"
docker compose exec job-agent python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5020/health').read())"
```

(Swap the service name/port for `capstone-agent:8000`,
`communication-agent:5001`, `aptitude-agent:5000`,
`resume-builder-agent:5010`, `certificate-agent:8008` — all use the same
`POST /api/invoke {"action": "health"}` pattern.)

## Rebuilding one service after a code change

```
docker compose up -d --build <service>
```

e.g. `docker compose up -d --build aptitude-agent`. This is the add-one-agent
/ change-one-agent workflow: rebuild just that image and recreate just that
container — everything else keeps running.

To add a brand-new agent later: copy `agents/agent_template/` (see its own
`Dockerfile`, already written), add a matching service block to
`docker-compose.yml` (copy the shape of any existing agent block), add its
`.env`, and `docker compose up -d --build <new-service>`.

## Logs

```
docker compose logs -f <service>          # one service
docker compose logs -f                     # everything
```

Service names: `mysql`, `orchestrator`, `capstone-agent`, `codeforge-agent`,
`communication-agent`, `aptitude-agent`, `resume-builder-agent`,
`certificate-agent`, `job-agent`, `job-worker`, `frontend`, plus Judge0's
`server`, `worker`, `db`, `redis`.

## Stopping / resetting

```
docker compose down          # stop everything, keep data (mysql + judge0 volumes)
docker compose down -v       # stop everything AND delete mysql/judge0 data
```

---

## What was created / changed

**New files:**
- `Dockerfile` in each of: `agents/orchestrator`, `agents/project_AI_Agent`,
  `agents/codeforge_agent/services/lms-api`,
  `agents/communication-ai-agent/backend`, `agents/aptitude_agent`,
  `agents/resume_builder_agent/backend`, `agents/certificate_agent`,
  `agents/job_agent`, `agents/agent_template` — plus a matching
  `.dockerignore` next to each.
- `Dockerfile.frontend`, `nginx.conf`, `.dockerignore` (repo root).
- `docker-compose.yml` (repo root).
- `docker/mysql-init/01-create-databases.sql`, `docker/mysql/.env.example`.
- This file.

**Edited files (and why):**
- `agents/aptitude_agent/requirements.txt`,
  `agents/resume_builder_agent/backend/requirements.txt`,
  `agents/agent_template/requirements.txt`,
  `agents/certificate_agent/requirements.txt` — added `gunicorn==23.0.0`.
  None of these four declared it before (only `waitress`/`uvicorn`/plain
  `uvicorn.run` for local dev); the other four services already had it for
  their PM2 production target, so this brings all eight in line with the
  same pattern/comment.
- `agents/job_agent/requirements.txt` — added the same pinned Gunicorn
  runtime used by the other containerized Flask services.
- `.env.example` in `agent_template`, `codeforge_agent/services/lms-api`,
  `communication-ai-agent/backend`, `project_AI_Agent`, `aptitude_agent`,
  `resume_builder_agent/backend`, `certificate_agent` — changed
  `ORCHESTRATOR_URL`, `AGENT_PUBLIC_URL`, `JUDGE0_URL`, and MySQL/DB
  host/credentials from `127.0.0.1`/`localhost` to the corresponding Docker
  service name (`orchestrator`, `mysql`, `server` for Judge0, or the
  agent's own service name). `aptitude_agent/.env.example` was also missing
  `ORCHESTRATOR_URL`/`AGENT_PUBLIC_URL`/`HEARTBEAT_INTERVAL_SECONDS`
  entirely (it silently relied on a `127.0.0.1` code default) — added them.
  `resume_builder_agent/backend/.env.example` defaulted to SQLite
  (`sqlite:///dev.db`) rather than MySQL like every other service — changed
  its default to MySQL for Docker; flagged below since it's a datastore
  change, not just an address change.
  `communication-ai-agent/backend/.env.example`'s `FRONTEND_ORIGIN` was
  **left unchanged** — see the port-5173 note below.
  `agents/orchestrator/.env` (the real file, not `.env.example`) was **not**
  edited — see "Needs your decision" below.
- `docker/mysql-init/01-create-databases.sql`, `docker-compose.yml`,
  and this file — updated to add `certificate-agent` after it landed on
  `origin/ui_branch` partway through this work (it wasn't in the original
  7-service table).
- `docker/mysql-init/01-create-databases.sql` and `docker-compose.yml` also
  add the isolated `job_agent` database, `job-agent` API, persistent resume
  upload volume, and the separately scalable `job-worker` queue consumer.

Nothing in `agents/codeforge_agent/judge0/` was touched.

## Decisions made per your answers

- **Judge0**: root `docker-compose.yml` uses `include:` to fold in
  `agents/codeforge_agent/judge0/docker-compose.yml` unmodified — one
  `docker compose up -d` starts everything, Judge0's services land on the
  same default network as everything else.
- **Frontend → orchestrator**: the frontend image is built with
  `VITE_GATEWAY_API_URL=""`, so the browser calls relative paths
  (`/auth/...`, `/chat/...`, `/gateway/...`, `/billing/...`, `/registry/...`)
  and `nginx.conf` reverse-proxies each of those prefixes to
  `orchestrator:8100`. The orchestrator's own port is never published to
  the host, matching your "only frontend published" constraint. I also
  picked `5173:80` for the published frontend port specifically because
  `orchestrator`'s default `ALLOWED_ORIGINS` and the communication agent's
  default `FRONTEND_ORIGIN` both already default to
  `http://localhost:5173` — so CORS needs zero `.env` changes with this
  port choice. Pick a different published port and you'll need to update
  both.
- **Missing `gunicorn`**: added directly to the three `requirements.txt`
  files (matching the other four services' existing pattern) rather than
  installed ad hoc in the Dockerfile.

## Judge0 wiring

`agents/codeforge_agent/judge0/docker-compose.yml` is referenced via
`include:` and otherwise untouched. Its `server` service (port 2358) is how
`codeforge-agent` and `capstone-agent` reach it — both now use
`JUDGE0_URL=http://server:2358`. Its own compose file still publishes
`2358:2358` to the host too (unchanged), so you can hit it directly for
debugging. It defines no `HEALTHCHECK`, so `capstone-agent`'s and
`codeforge-agent`'s `depends_on: server: condition: service_started` can
only wait for the container to start, not for Judge0 to actually be
accepting requests — acceptable here because both agents already treat a
Judge0 outage as best-effort ("no execution evidence", never a hard
failure), per their own code comments.

## Places the existing code assumes it's outside Docker

- **PM2 / `ecosystem.config.js`** (4 files, under `orchestrator`,
  `project_AI_Agent`, `codeforge_agent/services/lms-api`,
  `communication-ai-agent/backend`): all bind to `127.0.0.1`, not `0.0.0.0`
  — correct for their PM2/VPS use (a reverse proxy on the same host), left
  untouched. The Docker `CMD`s bind `0.0.0.0` instead, which is required
  for other containers to reach them at all.
- **`agents/resume_builder_agent/backend/run.py`** calls
  `load_dotenv(..., override=True)` on its own `.env` at import time — if a
  real `.env` were ever baked into that image, it would silently override
  whatever `env_file:` values docker-compose injects. Each service's
  `.dockerignore` excludes `.env`, so this can't happen, but it's worth
  knowing if that Dockerfile is ever changed to `COPY` more broadly.
- **`agents/resume_builder_agent/backend/.env.example`** defaulted to
  SQLite (`sqlite:///dev.db`, and there's a real `dev.db` file sitting in
  `instance/`) even though the rest of the platform is MySQL-only. I
  changed the Docker-facing default to MySQL — confirm that's what you
  want; the SQLite path still exists in the app if you'd rather keep this
  one agent on SQLite for now.
- **`agents/orchestrator/.env`** (your real file, not the example) already
  has `DATABASE_URL` pointing at `localhost` with a live password. I didn't
  touch it — you'll need to change that host to `mysql` yourself (and put
  the matching password in `docker/mysql/.env`) before `orchestrator` will
  reach the containerized database.
- **`agents/resume_builder_agent/frontend/.env.example`** has
  `VITE_PROXY_API_TARGET=http://localhost:5000` — port 5000 is
  `aptitude_agent`'s port, not resume-builder's own `5010`. Looks like a
  pre-existing local-dev typo, unrelated to Docker (this frontend isn't
  part of the containerized stack — only the repo-root React app is, per
  your service table) — flagging it, not fixing it.
- **`agent_template`'s health/invoke convention differs from every real
  agent**: `agent_wrapper.py` exposes `GET /health` + `POST /invoke`, while
  all six real agents — including `certificate_agent`, confirmed once it
  landed — (and their manifests' `"path": "/api/invoke"`) use
  `POST /api/invoke {"action": "health", ...}` instead. I dockerized the
  template using its actual `/health` convention rather than assuming
  `/api/invoke`. Every real agent so far has diverged from the template on
  this point, which makes `agent_template` a questionable reference for
  that part specifically — worth a look next time a new agent is built
  from it.
- **`agents/project_AI_Agent`'s Playwright browser check**
  (`app/execution/browser_check.py`) is not installed in its image
  (`playwright install --with-deps chromium` is a heavy step). Its own
  docstring says a missing Playwright install degrades to "no execution
  evidence" rather than failing, so this was a deliberate lean-image
  choice, not an oversight — add that install step yourself if you want
  that evidence path active in Docker.
- **`tesseract-ocr`** (OCR, used by `project_AI_Agent` and
  `resume_builder_agent`) and **`poppler-utils`** (PDF rendering, used by
  `resume_builder_agent`'s `pdf2image`) are installed via `apt-get` in
  their Dockerfiles, since neither is a pip package.
- **`agents/certificate_agent/requirements.txt`** pins no versions at all
  (`fastapi`, `langchain`, `openai>=1.99.0`, etc. — every other service in
  this repo pins exact versions). `pip install` in its image will always
  resolve to whatever's newest on build day, so its build isn't
  reproducible the way the other seven are; I only added a pinned
  `gunicorn==23.0.0` line and left the rest as-is rather than pinning
  versions that weren't mine to choose.
- **MySQL users**: every agent's `.env.example` now connects to MySQL as
  `root` (matching `docker/mysql/.env`'s `MYSQL_ROOT_PASSWORD`) since the
  `mysql:8` image only creates that one user by default. No per-service
  MySQL users/grants were set up — everything shares root, same trust
  level as most people's local dev MySQL already has.
