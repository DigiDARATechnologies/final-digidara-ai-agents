# Running DigiDARA AI Agents Locally

For the current Windows-friendly environment map and automated setup, start
with [ENV_WORKFLOW.md](ENV_WORKFLOW.md).

One entry point for getting the whole platform (React UI + orchestrator +
8 agent/worker services + MySQL + Judge0) running on your machine. Pick **Docker** (one
command, recommended) or **Native** (one terminal per service, useful for
debugging a single agent with breakpoints/hot-reload outside a container).

| | Docker | Native |
|---|---|---|
| Setup effort | Low — copy `.env`s, one command | Higher — a venv + MySQL DB per service |
| Good for | Trying the whole platform, testing changes near-production | Actively developing/debugging one service |
| Full reference | [README-docker.md](README-docker.md) | [README.md](README.md) |

Both paths need the same repo clone and the same `.env` values — they
just run the code differently.

## Prerequisites (either path)

- Git
- Node.js 20+ and npm (frontend)
- API keys for whichever LLM provider(s) you'll use (`OPENAI_API_KEY`,
  `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, etc.) — agents still boot and most
  flows work without one; AI-scored/generated content falls back to a
  deterministic response instead

Docker path additionally needs:
- Docker Desktop / Docker Engine with Compose V2 **2.20.0+**

Native path additionally needs:
- Python 3.10+ (one venv per Python service)
- A local MySQL server (8.x)

```bash
git clone https://github.com/DigiDARATechnologies/final-digidara-ai-agents.git
cd final-digidara-ai-agents
```

---

## Path A — Docker (recommended)

```bash
# 1. Create every missing .env from its committed .env.example.
#    Existing .env files are never overwritten.
npm run setup:env

# 2. Set a real MySQL root password (docker/mysql/.env), then use that
#    SAME password in DATABASE_URL / MYSQL_PASSWORD in every agent .env
#    you just copied — all agents connect to MySQL as root.

# 3. AGENT_SHARED_SECRET must be IDENTICAL across every .env you touched
#    (including the orchestrator's above). Leaving it unset everywhere
#    also works for local dev (shared fallback) — just don't set it in
#    only some files.

# 4. Fill in real API keys (OPENAI_API_KEY / GROQ_API_KEY / etc.) where
#    each .env.example has a placeholder. certificate-agent refuses to
#    boot without real SECRET_KEY, OPENAI_API_KEY and DB_PASSWORD values.

# 5. Build and start everything
docker compose up -d --build
```

Open **http://localhost:5173**. Check status with `docker compose ps`
(every service should show `healthy` once warmed up) and logs with
`docker compose logs -f <service>`.

Full detail — rebuilding one service, resetting data, Judge0 wiring,
every deliberate Docker-specific decision — is in
**[README-docker.md](README-docker.md)**.

---

## Path B — Native (one process per terminal)

### 1. MySQL

Start MySQL, then create every database once:

```sql
CREATE DATABASE digidara_registry;
CREATE DATABASE capstone_agent      CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE leetcode;
CREATE DATABASE communication_module CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE aptitude_ai;
CREATE DATABASE resume_builder;
CREATE DATABASE career_agent_db;
```

Each service creates/migrates its own tables on first startup — no schema
files to load, except CodeForge (see its terminal below).

### 2. Install each service into its own venv

```bash
for svc in orchestrator project_AI_Agent codeforge_agent/services/lms-api \
           communication-ai-agent/backend aptitude_agent \
           resume_builder_agent/backend certificate_agent; do
  ( cd "agents/$svc" && python -m venv .venv && ./.venv/bin/pip install -r requirements.txt )
done
npm install
```

(Windows PowerShell: replace `.venv/bin/pip` with `.venv\Scripts\python.exe -m pip`.)

### 3. Configure each `.env`

Copy every `.env.example` to `.env` as in Path A step 1 (same files, same
`AGENT_SHARED_SECRET`-must-match rule), but point every `DATABASE_URL` /
`MYSQL_HOST` at your local MySQL (`127.0.0.1`/`localhost`) instead of the
Docker service names. Full field-by-field reference for every agent's
`.env` is **[README.md §7](README.md#7-environment-configuration)**.

### 4. Start every service (one terminal each)

```bash
# Terminal 1 — orchestrator
cd agents/orchestrator && ./.venv/bin/python -m uvicorn app.main:app --reload --port 8100

# Terminal 2 — capstone
cd agents/project_AI_Agent && ./.venv/bin/python -m uvicorn app.api.main:app --reload --port 8000

# Terminal 3 — codeforge
cd agents/codeforge_agent/services/lms-api
./.venv/bin/python scripts/migrate.py up   # once, first time only
./.venv/bin/python scripts/seed.py         # once, first time only
./.venv/bin/python run.py

# Terminal 4 — communication coach
cd agents/communication-ai-agent/backend && ./.venv/bin/python run.py

# Terminal 5 — aptitude
cd agents/aptitude_agent && ./.venv/bin/python app.py

# Terminal 6 — resume builder
cd agents/resume_builder_agent/backend && ./.venv/bin/python run.py

# Terminal 7 — certificate
cd agents/certificate_agent && ./.venv/bin/python run.py

# Terminal 8 — frontend
npm run dev
```

Any agent can be started independently — the UI and orchestrator work
fine with only some running; a stopped agent just shows offline in the UI.

CodeForge's `run_problem`/`submit_problem` additionally need Judge0:

```bash
cd agents/codeforge_agent/judge0
docker compose up -d db redis server worker
curl http://127.0.0.1:2358/about   # confirm it's reachable
```

### 5. Verify

```bash
curl http://127.0.0.1:8100/health
curl "http://127.0.0.1:8100/registry/agents?healthy_only=true"
```

Full agent list, ports, invoke-action tables, and troubleshooting (agent
shows offline, 503 from the gateway, MySQL connection errors, etc.) are in
**[README.md](README.md)**, sections 3–10 and 14.

---

## Running the test suite locally

```bash
python -m pip install -r requirements-quality.txt
python -m ruff check agents scripts tests
python -m mypy
python -m pytest tests/unit -v
npm run lint
npm run typecheck
npm run test:ci
npm run build
```

Full per-agent Docker test suite (builds every image and runs its tests
against a real disposable MySQL):

```bash
python -m pip install "pytest>=8.3,<10"
npm run test:agents
```

See [CI_CD_SETUP.md](CI_CD_SETUP.md) for what each of these actually
checks and how they map to the GitHub Actions pipeline.

## Common problems

- **An agent shows offline in the UI** — check MySQL is up, the
  orchestrator's `/health` returns ok, the agent's own process is running
  on its expected port, and `AGENT_SHARED_SECRET` matches across every
  `.env` you touched.
- **Gateway returns 503** — the agent hasn't registered yet or its
  heartbeat is stale (default TTL 90s); check that agent's own logs.
- **`certificate-agent` won't start** — it refuses to boot without real
  (non-placeholder) `SECRET_KEY`, `OPENAI_API_KEY`, and `DB_PASSWORD`.
- **Orchestrator/communication agent refuse to start** — `JWT_SECRET` /
  `SECRET_KEY` / `JWT_SECRET_KEY` have no insecure fallback; generate real
  values with `openssl rand -hex 32`.
- **CodeForge run/submit returns `503 evaluator_unavailable`** — Judge0
  isn't running (see step above).

More detail on all of these, plus agent-specific issues, is in
[README.md §14](README.md#14-troubleshooting).
