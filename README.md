# DigiDARA AI Agents

DigiDARA is a multi-agent platform with a React chat interface, a FastAPI
orchestrator, a MySQL-backed runtime agent registry, and independently
deployed agents. The platform agents are integrated through the
**REST + Registry + Gateway (Strategy F)** architecture:

- **Capstone Project Agent** (`agents/project_AI_Agent`, FastAPI + MySQL) —
  eligibility check, AI-generated project topics, a 7-day timer, and graded
  `.docx`/`.zip` submission review.
- **CodeForge (LeetCode / DSA) Agent** (`agents/codeforge_agent`, Flask +
  MySQL) — course/technology/topic/problem browsing, Judge0-sandboxed code
  execution (Run = public tests, Submit = public + hidden tests), and an
  OpenAI-backed AI Tutor with a deterministic offline fallback.
- **Communication Coach Agent** (`agents/communication-ai-agent`, Flask +
  MySQL) — Pronunciation, Speaking and Writing practice loops scored live by
  an LLM, daily challenges, and a progress dashboard.
- **Job Fetching Agent** (`agents/job_agent`, Flask + MySQL) — learner job
  profiles, resume upload, explainable matching, saved/application tracking,
  Greenhouse and Apify-backed ingestion, and administrator moderation.

All integrated agents register with the same orchestrator and are driven entirely
from the same shared React chat UI — the orchestrator's gateway is generic
per agent name, so adding an agent needs no orchestrator code changes. See
[STRATEGY_F.md](STRATEGY_F.md) for the full architecture reference, and each
agent's own `agents/<name>/INTEGRATION.md` for agent-specific detail.

This document explains the architecture, startup process, user workflows,
database verification, integration contracts, and common problems.

For the complete container stack, including the Job API and its separate
ingestion worker, see [README-docker.md](README-docker.md).

## Resume Builder Strategy F

Resume Builder now registers as `resume_builder_agent` and is available from
the shared React UI through the generic gateway, never a direct Flask URL.
Its default local port is `5010`; configure the root frontend with
`VITE_RESUME_BUILDER_AGENT_NAME=resume_builder_agent`. See
[`agents/resume_builder_agent/INTEGRATION.md`](agents/resume_builder_agent/INTEGRATION.md)
for its action map, startup settings, identity bridge, and verification.

## 1. What was implemented

### Capstone Project Agent

- One shared React chat UI; the old standalone Capstone HTML UI was removed.
- Signup and login screens collecting name, email, and mobile number.
- Mobile-based lookup of completed enrollments and issued certificates.
- Multiple-choice chat actions for certificate confirmation, course choice,
  generated topic choice, and timer confirmation.
- Two AI-generated project topics for the selected certified course.
- Seven-day project timer, submission instructions, `.docx` and `.zip`
  upload, validation, grading, revision feedback, and final score.
- A right-side project dashboard opened from the top-right Dashboard button.
- Capstone self-registration, heartbeat, re-registration, and deregistration.
- A registry-resolved gateway supporting JSON and multipart forwarding.
- Frontend traffic routed through the gateway instead of directly to the
  Capstone service.
- Student email storage and a backward-compatible database column migration.

### CodeForge (LeetCode / DSA) Agent

- Chat-driven browsing: course → technology → topic → problem, each step a
  clickable chat option.
- An in-chat code editor (`ChatView`'s `codeMode`) with **Run** (public
  tests) and **Submit** (public + hidden tests) actions against a
  Judge0-sandboxed evaluator.
- An AI Tutor (`tutor` action) that explains a failed submission — error
  category, a short debugging workflow, and a next action — with a safe
  deterministic fallback when no LLM key is configured or the call fails.
  The tutor never reveals hidden tests or a complete solution.
- `ensure_session` action bridging DigiDARA's login identity to an
  unguessable, revocable, expiring session token carried in the JSON
  payload — since the gateway forwards only `Content-Type` and the raw body
  and never signs anything, this agent's pre-existing HMAC-signed
  `/api/auth/*`/`/api/coding/*` routes are left completely untouched, and
  `/api/invoke` is an additive, parallel auth surface (see
  `agents/codeforge_agent/INTEGRATION.md`).
- The same self-registration/heartbeat/deregistration and registry-resolved
  gateway forwarding as Capstone, implemented in Flask.

### Communication Coach Agent

- Chat-driven main menu: Daily Challenge, Speaking, Writing, Pronunciation,
  My Progress (dashboard), History.
- `bridge_identity` action bridging DigiDARA's login identity into a real
  `users` row and a `flask_jwt_extended` JWT — since the gateway never
  forwards cookies or an `Authorization` header (which every pre-existing
  route reads via `@jwt_required()`), that JWT is instead carried as
  `authToken` inside the JSON payload of every subsequent action.
- `/api/invoke` re-enters this agent's own ~45 pre-existing routes across 8
  Flask blueprints (dashboard, daily challenges, history, practice,
  pronunciation, speaking, writing, profile) **unmodified**, through an
  in-process test client, attaching `authToken` as a normal
  `Authorization: Bearer` header — see
  `agents/communication-ai-agent/INTEGRATION.md`.
- Writing and Speaking practice loops: an AI-generated prompt/question, a
  typed answer, live LLM-scored feedback (grammar/vocabulary/clarity/
  fluency/confidence, a corrected answer), and the next prompt — repeating
  until the learner ends the session.
- Pronunciation practice loop: an AI-generated word/sentence/minimal-pair
  target, a typed transcript of what the learner said (the original
  frontend does this via the browser's Web Speech API; the chat flow here
  accepts typed text directly against the same scoring backend), and
  word-accuracy/completeness/clarity/fluency scoring.
- The same self-registration/heartbeat/deregistration and registry-resolved
  gateway forwarding as the other two agents, implemented in Flask.

## 2. High-level architecture

```mermaid
flowchart LR
    U[User] --> UI[React chat UI<br/>Vite]
    UI -->|JSON<br/>Port 8100| GW[FastAPI gateway]
    GW -->|Resolve healthy agent| REG[(MySQL agent_registry)]
    GW -->|Forward request| CAP[Capstone Agent<br/>Port 8000 /api/invoke]
    GW -->|Forward request| CF[CodeForge Agent<br/>Port 4000 /api/invoke]
    GW -->|Forward request| COM[Communication Agent<br/>Port 5001 /api/invoke]
    GW -->|Forward request| JOB[Job Agent<br/>Port 5020 /api/invoke]
    CAP --> CDB[(MySQL capstone_agent)]
    CAP --> LG[LangGraph workflow]
    LG --> LLM[LiteLLM provider]
    CF --> LDB[(MySQL leetcode)]
    CF --> J0[Judge0: sandboxed code execution]
    CF --> OAI[OpenAI: AI Tutor]
    COM --> COMDB[(MySQL communication_module)]
    COM --> COMLLM[OpenAI or Groq: scoring + generation]
    JOB --> JDB[(MySQL job_agent)]
    JW[Job ingestion worker] --> JDB
    CAP -->|Register / heartbeat| REG
    CF -->|Register / heartbeat| REG
    COM -->|Register / heartbeat| REG
    JOB -->|Register / heartbeat| REG
```

The browser knows an agent only by its logical name (`capstone_project_agent`,
`codeforge_agent`, or `communication_agent`), never its deployment URL. The
orchestrator resolves the current healthy endpoint from MySQL for every
gateway request, so another agent can be added the same way without touching
the orchestrator.

## 3. Services and ports

| Component | Default address | Responsibility |
|---|---|---|
| React/Vite UI | `http://127.0.0.1:5173` | Login, chat, choices, uploads, dashboards |
| Orchestrator | `http://127.0.0.1:8100` | Registry, gateway, generic LLM chat routing |
| Capstone Agent | `http://127.0.0.1:8000` | Eligibility, project generation, monitoring, grading |
| CodeForge Agent | `http://127.0.0.1:4000` | Course/problem browsing, code execution, AI tutor |
| Communication Agent | `http://127.0.0.1:5001` | Pronunciation/Speaking/Writing practice, daily challenges, dashboard |
| Resume Builder Agent | `http://127.0.0.1:5010` | Resume creation, ATS scoring, PDF export |
| Certificate Agent | `http://127.0.0.1:8008` | Certification exam generation, chat evaluation, leaderboard, PDF certificates |
| Job Agent | `http://127.0.0.1:5020` | Job profiles, matching feed, applications and admin controls |
| Job Worker | internal process | Greenhouse/Apify ingestion queue consumer |
| Judge0 | `http://127.0.0.1:2358` | Sandboxed code execution for CodeForge's Run/Submit (Docker) |
| MySQL | `localhost:3306` | Per-service databases, including `digidara_registry` and `job_agent` |

Every agent is MySQL-backed — there is no SQLite anywhere in this stack, dev or production.

## 4. Strategy F request flow

### 4.1 Agent startup and discovery

```mermaid
sequenceDiagram
    participant A as Agent (Capstone or CodeForge)
    participant O as Orchestrator
    participant R as MySQL Registry

    A->>O: POST /registry/register (manifest + endpoint)
    O->>R: Upsert agent_name + version
    loop Every 30 seconds
        A->>O: POST /registry/heartbeat
        O->>R: Refresh last_heartbeat
    end
    A-->>O: DELETE /registry/deregister on graceful shutdown
```

If a process crashes without deregistering, the heartbeat TTL (default 90s)
automatically removes it from healthy routing.

### 4.2 Browser request

```text
POST /gateway/agents/{agent_name}/invoke
Content-Type: application/json

{
  "action": "...",
  "payload": { ... }
}
```

The gateway:

1. Reads the freshest healthy registry row for the requested agent name.
2. Returns HTTP `503` if the agent is missing or its heartbeat is stale.
3. Forwards the original JSON or multipart body — unparsed, `Content-Type`
   preserved — to the registered endpoint. This is why file uploads work
   without any gateway-side special-casing.
4. Returns the upstream status code, content type, and response body.

No agent URL is hardcoded inside the gateway.

### 4.3 Capstone invoke actions

| Action | Purpose | Payload |
|---|---|---|
| `health` | Confirm the registered agent is reachable | `{}` |
| `eligible_courses` | Find completed and certified courses | `{phone}` |
| `check_eligibility` | Verify learner and generate two topics | `{name, email, phone, course_name}` |
| `choose_topic` | Lock a topic and generate requirements | `{thread_id, topic_id}` |
| `confirm_timer` | Start the seven-day timer | `{thread_id}` |
| `status` | Read persisted workflow progress | `{thread_id}` |
| `upload_submission` | Upload and grade files | multipart form |

### 4.4 CodeForge invoke actions

| Action | Purpose | Payload |
|---|---|---|
| `health` | Confirm the registered agent is reachable | `{}` |
| `ensure_session` | Issue a session token for this login identity | `{name, email}` |
| `usage_summary` | Platform-wide AI token usage (no session required) | `{}` |
| `dashboard` | Student progress summary | `{sessionToken}` |
| `list_courses` | List available courses | `{sessionToken}` |
| `list_technologies` | List technologies for a course | `{sessionToken, course_slug}` |
| `list_topics` | List topics for a technology | `{sessionToken, course_slug, technology_slug}` |
| `list_problems` | List problems for a topic | `{sessionToken, course_slug, technology_slug, topic_slug}` |
| `get_problem` | Fetch one problem's detail | `{sessionToken, course_slug, technology_slug, topic_slug, problem_slug}` |
| `run_problem` | Evaluate code against public tests | `{sessionToken, problem_id, sourceCode}` |
| `submit_problem` | Evaluate code against public + hidden tests | `{sessionToken, problem_id, sourceCode}` |
| `tutor` | AI-guided explanation of a failed submission | `{sessionToken, problem_id, submissionId, hintLevel}` |

Every action other than `health`/`ensure_session`/`usage_summary` requires a
previously-issued `sessionToken` in the payload body, validated the same way
the pre-existing HMAC-signed routes validate their session header — see
`agents/codeforge_agent/INTEGRATION.md`.

### 4.5 Communication Coach invoke actions

| Action | Purpose | Payload |
|---|---|---|
| `health` | Confirm the registered agent is reachable | `{}` |
| `bridge_identity` | Get-or-create a `users` row for this login identity and issue a JWT | `{name, email}` |
| `dashboard` | Progress summary across all three modules | `{authToken}` |
| `daily_challenge_today` | Today's 3-activity challenge + streak | `{authToken}` |
| `history_list` / `history_detail` / `history_*_detail` | Paginated activity history and per-session detail | `{authToken, page?}` / `{authToken, session_id}` |
| `writing_start` / `writing_respond` / `writing_end` | Start a Writing session, submit a turn, end the session | `{authToken, mode, difficulty, topic_title?}` / `{authToken, session_id, answer}` / `{authToken, session_id}` |
| `speaking_start` / `speaking_respond` / `speaking_end` | Same loop for Speaking (typed answers — no audio capture in the chat UI) | as above |
| `pronunciation_session_start` / `pronunciation_start_attempt` / `pronunciation_submit` / `pronunciation_session_end` | Start a session, start an attempt for the current item, submit a typed transcript, end the session | see `agents/communication-ai-agent/INTEGRATION.md` |
| `profile_get` / `profile_update` | Read/update the bridged learner's profile | `{authToken}` / `{authToken, name?, phone?, ...}` |

~35 more read-mostly actions (topics lists, progress/insights/streak,
rewrite/hint/tone tools, draft save) are implemented on the backend and
listed in `manifest.json`, but are not yet wired into the chat flow — see
the "Known scope limitations" note in
`agents/communication-ai-agent/INTEGRATION.md`.

Unlike Capstone and CodeForge, this dispatcher does not hand-write a
payload-taking function per action. It re-enters the agent's own ~45
pre-existing Flask routes **unmodified** through an in-process test client
(`current_app.test_client()`), attaching the payload's `authToken` as a
normal `Authorization: Bearer` header — the "re-enter your own routes" shape
described in [STRATEGY_F.md](STRATEGY_F.md#3-the-common-apiinvoke-contract).

The original `/api/*` REST endpoints remain available on all three agents
for internal testing and API documentation, but the React application uses
only the gateway contract.

### 4.6 AI role-profile generation

Authenticated clients can create a reusable AI role profile through the
orchestrator (this is not routed to a specialist agent):

```http
POST /role-profiles/generate
Authorization: Bearer <platform JWT>
Content-Type: application/json

{"target_role":"Frontend Developer","context":"React application for learners"}
```

The response is validated JSON with a concise `summary`, a `skills` list, and
a `declaration` containing `capabilities`, `limitations`, `required_inputs`,
and `suggested_next_actions`. The endpoint returns `502` if the configured
LLM cannot return a valid profile, rather than exposing malformed model output.

## 5. Learner / candidate workflow in the chat UI

### 5.1 Capstone Project Agent

1. The learner signs up with name, email, and mobile number.
2. The profile is stored locally for the development login experience.
3. The learner opens the Capstone Project Agent.
4. The agent asks whether the learner completed a course and received a
   certificate.
5. After **Yes**, the agent queries certificate-backed courses using the
   signup mobile number.
6. The learner selects an eligible course using a chat button.
7. The backend validates enrollment and certificate data.
8. LangGraph and the configured LLM generate two course-specific topics.
9. The learner selects topic A or B.
10. The agent expands the topic into detailed requirements.
11. The learner confirms the seven-day timer.
12. The dashboard monitors course, topic, deadline, files, and status.
13. The learner uploads a `.docx` report (Problem Statement, Approach, Conclusion — no code, no screenshots) and a `.zip` source archive in chat.
14. The agent parses every Python/JSON/TOML file for syntax errors, then has the LLM read all of the code and check it against each functional requirement.
15. The same chat returns the exact syntax errors (file, line, offending code), or a score and feedback. A failed grade never blocks another upload — the learner can resubmit until they pass.

### 5.2 CodeForge (LeetCode / DSA) Agent

1. The candidate opens the CodeForge Agent. The agent calls `ensure_session`
   to bridge the DigiDARA login into a CodeForge session token.
2. The candidate picks a course, then a technology, then a topic — each a
   clickable chat option — narrowing down to a list of problems.
3. The candidate picks a problem; the chat switches into code-editor mode
   with the problem statement, input/output format, and a starter seed.
4. **Run** evaluates the code against the problem's public tests via Judge0;
   **Submit** evaluates against public + hidden tests and records progress.
5. On a failed run/submission, the candidate can request AI Tutor guidance —
   an error category, a short debugging workflow, and a next action, without
   ever revealing hidden tests or a full solution.
6. The right-side dashboard tracks course/technology/topic progress and
   recent activity.

### 5.3 Communication Coach Agent

1. The learner opens the Communication Coach Agent. The agent calls
   `bridge_identity` to turn the DigiDARA login into a `users` row and a JWT.
2. The main menu offers Daily Challenge, Speaking, Writing, Pronunciation,
   My Progress, and History as clickable chat options.
3. For Speaking/Writing: pick a difficulty, type a topic (or "daily" for
   today's challenge), then answer each AI-generated prompt/question in
   chat — every turn returns live LLM-scored feedback and the next prompt.
4. For Pronunciation: pick a mode (word/sentence/minimal pairs), read the
   AI-generated target text, and type what was said; each turn returns
   accuracy/clarity/fluency scores and the next item.
5. "End session" at any point finalizes the session and shows an overall
   summary (scores, strengths, recommendation).
6. The right-side dashboard tracks the active module, turn progress, and the
   most recent turn's scores/feedback.

## 6. Database models

### 6.1 Capstone (MySQL) — certificate verification

```text
students
   ├── enrollments ──> courses
   └── certificates ─> courses
```

A course is offered to the learner only when:

- the student mobile number exists;
- the enrollment belongs to that student and course;
- enrollment status is `completed`; and
- a certificate exists for the same student and course.

The `students` table includes an optional `email` column. Existing databases
are upgraded during `init_db()` with a small compatibility migration. Create
the database once:

```powershell
mysql -u root -p -e "CREATE DATABASE capstone_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

`init_db()` (called on startup) creates all tables and runs the compatibility
migration against it — no separate schema file to load.

#### Add another certified learner

Run from `agents/project_AI_Agent`:

```powershell
.\.venv\Scripts\python.exe -m scripts.add_student `
  --name "Student Name" `
  --email "student@example.com" `
  --phone "1234567890" `
  --course "Python for Data Automation"
```

The command is idempotent for the same mobile and course: it reuses existing
records rather than creating duplicate learner enrollment rows.

### 6.2 CodeForge (MySQL) — course catalog and submissions

```text
students —< student_sessions
students —< student_coding_activity
students —< student_problem_progress
students —< tutor_interactions
students —< llm_usage

coding_courses —< course_technologies >— coding_technologies —< coding_topics
coding_topics —< coding_problems —< coding_test_cases
coding_problems —< coding_submissions
```

`ensure_session` creates/refreshes a `students` row and a `student_sessions`
token automatically on first contact — no manual seeding step is required.
Create the database and apply migrations once:

```bash
cd agents/codeforge_agent/services/lms-api
python scripts/migrate.py up
python scripts/seed.py
```

Judge0 (Docker) is required for `run_problem`/`submit_problem` to actually
execute code — without it they correctly return `503 evaluator_unavailable`.
Course/technology/topic/problem browsing, the dashboard, and the AI Tutor's
deterministic fallback all work without Judge0 running. See
`agents/codeforge_agent/INTEGRATION.md` for the Judge0 startup steps.

### 6.3 Communication Coach (MySQL) — practice sessions and results

```text
users —< speaking_sessions —< speaking_turns
users —< writing_sessions —< writing_turns
users —< pronunciation_items —< pronunciation_attempts
users —< pronunciation_sessions —< pronunciation_attempts
users —< generated_topics
users —< daily_challenge_progress
users —< daily_challenge_summary
```

Create the database once; the app creates/upgrades tables itself on startup
(`_ensure_result_schema()` in `app/__init__.py` — a hand-rolled
`ALTER TABLE ADD COLUMN` compatibility step, the same pattern Capstone uses):

```powershell
mysql -u root -p -e "CREATE DATABASE communication_module CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

`bridge_identity` creates a `users` row automatically on first contact — no
manual seeding step is required for a learner to start practicing. The
`topics` table (used by the topic-list actions, not by the chat flow's
custom-topic path) is optional to seed and unrelated to whether practice
works.

## 7. Environment configuration

### 7.1 React root `.env`

Copy `.env.example` to `.env` if custom values are required:

```env
VITE_GATEWAY_API_URL=http://127.0.0.1:8100
VITE_CAPSTONE_AGENT_NAME=capstone_project_agent
VITE_CODEFORGE_AGENT_NAME=codeforge_agent
VITE_COMMUNICATION_AGENT_NAME=communication_agent
```

### 7.2 Orchestrator `.env`

Important values:

```env
DATABASE_URL=mysql+pymysql://USER:PASSWORD@localhost:3306/digidara_registry
HEARTBEAT_TTL_SECONDS=90
HEARTBEAT_INTERVAL_SECONDS=30
AGENT_CALL_TIMEOUT_SECONDS=180
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key

# --- Auth / service security (required — see Security section below) ---
JWT_SECRET=generate-with-openssl-rand-hex-32
AGENT_SHARED_SECRET=generate-with-openssl-rand-hex-32
ALLOWED_ORIGINS=http://localhost:5173
ALLOWED_AGENT_HOSTS=capstone-agent,codeforge-agent,communication-agent,aptitude-agent,resume-builder-agent,certificate-agent,job-agent,127.0.0.1,localhost
CHAT_RATE_LIMIT_PER_MIN=20
ENV=dev
```

Use only the API key matching the selected `LLM_MODEL`. Do not commit `.env`.

`JWT_SECRET` and `AGENT_SHARED_SECRET` have no insecure fallback — the
orchestrator refuses to start without a real value for either (see
[Security](#16-security) below). `AGENT_SHARED_SECRET` must match the same
variable in every other agent's `.env` (sections 7.3–7.5); every agent's
`registry_client.py` defaults to a shared literal dev value when unset, so
local dev works with no `.env` changes, but that default must never be used
outside `ENV=dev`. `ALLOWED_ORIGINS` and `ALLOWED_AGENT_HOSTS` are
comma-separated lists; set `ENV=production` (anything other than `dev`) on
any real deployment.

### 7.3 Capstone Agent `.env`

Copy `agents/project_AI_Agent/.env.example` to `.env` and configure:

```env
ORCHESTRATOR_URL=http://127.0.0.1:8100
AGENT_PUBLIC_URL=http://127.0.0.1:8000/api/invoke
HEARTBEAT_INTERVAL_SECONDS=30
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/capstone_agent
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key
AGENT_SHARED_SECRET=must-match-the-orchestrators-AGENT_SHARED_SECRET
```

For Docker or separate hosts, `AGENT_PUBLIC_URL` must be reachable from the
orchestrator. Do not use `127.0.0.1` across separate containers.
`AGENT_SHARED_SECRET` signs this agent's registration/heartbeat calls to the
orchestrator (see §7.2) — leave it unset only for local dev, where both sides
fall back to the same literal default.

### 7.4 CodeForge Agent `.env`

Copy `agents/codeforge_agent/services/lms-api/.env.example` to `.env` and
configure:

```env
MYSQL_HOST=127.0.0.1
MYSQL_DATABASE=leetcode
MYSQL_USER=your-user
MYSQL_PASSWORD=your-password
LMS_API_SHARED_SECRET=your-shared-secret
CODING_PRACTICE_ENABLED=true
JUDGE0_URL=http://127.0.0.1:2358
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
ORCHESTRATOR_URL=http://127.0.0.1:8100
AGENT_PUBLIC_URL=http://127.0.0.1:4000/api/invoke
HEARTBEAT_INTERVAL_SECONDS=30
AGENT_SHARED_SECRET=must-match-the-orchestrators-AGENT_SHARED_SECRET
```

`OPENAI_API_KEY` is optional — without it, the AI Tutor falls back to safe
deterministic guidance instead of a real model call. `AGENT_SHARED_SECRET`
signs this agent's registration/heartbeat calls to the orchestrator (see
§7.2) — leave it unset only for local dev.

### 7.5 Communication Agent `.env`

Copy `agents/communication-ai-agent/backend/.env.example` to `.env` and
configure:

```env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/communication_module
SECRET_KEY=generate-with-openssl-rand-hex-32
JWT_SECRET_KEY=generate-with-openssl-rand-hex-32
AI_PROVIDER=auto
OPENAI_API_KEY=
GROQ_API_KEY=
FRONTEND_ORIGIN=http://localhost:5173
ORCHESTRATOR_URL=http://127.0.0.1:8100
AGENT_PUBLIC_URL=http://127.0.0.1:5001/api/invoke
HEARTBEAT_INTERVAL_SECONDS=30
AGENT_SHARED_SECRET=must-match-the-orchestrators-AGENT_SHARED_SECRET
```

`SECRET_KEY` and `JWT_SECRET_KEY` have no insecure fallback — `create_app()`
refuses to start without real values for both (see
[Security](#16-security) below).

`AI_PROVIDER=auto` prefers OpenAI when `OPENAI_API_KEY` is set, otherwise
falls back to Groq — same convention as the rest of this repo since the
Groq→OpenAI migration. Practice sessions still start and generate a
deterministic fallback prompt/question without either key configured; only
AI-scored feedback quality depends on it.

## 8. Installation

### 8.1 Orchestrator

```powershell
cd E:\digidaraaiagents\agents\orchestrator
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 8.2 Capstone Agent

```powershell
cd E:\digidaraaiagents\agents\project_AI_Agent
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 8.3 CodeForge Agent

```powershell
cd E:\digidaraaiagents\agents\codeforge_agent\services\lms-api
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Code execution (`run_problem`/`submit_problem`) additionally requires Judge0
running via Docker:

```bash
cd agents/codeforge_agent/judge0
docker compose up -d db redis server worker
curl http://127.0.0.1:2358/about   # confirm it's reachable
```

### 8.4 Communication Agent

```powershell
cd E:\digidaraaiagents\agents\communication-ai-agent\backend
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 8.5 React UI

```powershell
cd E:\digidaraaiagents
npm install
```

The orchestrator and Capstone (both use `httpx==0.27.2`) require that exact
pin because the pinned LiteLLM version is incompatible with `httpx==0.28.1`.

## 9. Running the complete platform

Start MySQL first, and make sure all databases exist: `digidara_registry`
(orchestrator), `capstone_agent` (§6.1), `leetcode` with its migrations
applied (§6.2), and `communication_module` (§6.3). Then open five PowerShell
terminals.

### Terminal 1: orchestrator

```powershell
cd E:\digidaraaiagents\agents\orchestrator
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8100
```

### Terminal 2: Capstone Agent

```powershell
cd E:\digidaraaiagents\agents\project_AI_Agent
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000
```

### Terminal 3: CodeForge Agent

```powershell
cd E:\digidaraaiagents\agents\codeforge_agent\services\lms-api
.\.venv\Scripts\python.exe run.py
```

### Terminal 4: Communication Agent

```powershell
cd E:\digidaraaiagents\agents\communication-ai-agent\backend
.\.venv\Scripts\python.exe run.py
```

### Terminal 5: React UI

```powershell
cd E:\digidaraaiagents
npm run dev
```

### Terminal 5: Resume Builder Agent

```powershell
cd agents\resume_builder_agent\backend
.\.venv\Scripts\python.exe run.py
```

The included local `backend/.env` advertises `http://127.0.0.1:5010/api/invoke`
to the registry. For Docker or remote deployment, replace that value with an
address reachable from the orchestrator.

Using the virtual-environment Python directly is more reliable than
activation and works even if a shell blocks activation scripts. Any agent
can be started independently — the UI and orchestrator work fine with only
some running; an agent that isn't up just shows as offline and its chat card
won't be usable.

## 10. Runtime verification

### Orchestrator health

```powershell
Invoke-RestMethod http://127.0.0.1:8100/health
```

### Healthy agents

```powershell
Invoke-RestMethod "http://127.0.0.1:8100/registry/agents?healthy_only=true"
```

The result should contain all three:

```text
agent_name = capstone_project_agent
endpoint   = http://127.0.0.1:8000/api/invoke
status     = healthy

agent_name = codeforge_agent
endpoint   = http://127.0.0.1:4000/api/invoke
status     = healthy

agent_name = communication_agent
endpoint   = http://127.0.0.1:5001/api/invoke
status     = healthy
```

### Gateway health invocation

```powershell
$body = @{ action = "health"; payload = @{} } | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/gateway/agents/capstone_project_agent/invoke" `
  -Method Post -ContentType "application/json" -Body $body
# {"status":"ok","agent_name":"capstone_project_agent"}

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/gateway/agents/codeforge_agent/invoke" `
  -Method Post -ContentType "application/json" -Body $body
# {"status":"ok","agent_name":"codeforge_agent"}

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/gateway/agents/communication_agent/invoke" `
  -Method Post -ContentType "application/json" -Body $body
# {"status":"ok","agent_name":"communication_agent"}
```

## 11. Files changed for the Capstone integration

### React application

| File | Integration change |
|---|---|
| `src/App.tsx` | Account persistence, per-agent state/health, choices, dashboards |
| `src/types/index.ts` | Mobile profile, chat-option types, `Agent.kind` union |
| `src/data/agents.ts` | `kind: "capstone"` on the agent card |
| `src/components/LoginOverlay.tsx` | Signup/login tabs and mobile collection |
| `src/components/ChatView.tsx` | Clickable multiple-choice responses |
| `src/components/Topbar.tsx` | Dashboard button and real per-agent connection status |
| `src/components/AgentDashboard.tsx` | Capstone right-side workflow monitoring dashboard |
| `src/components/SettingsModal.tsx` | Mobile-aware profile display |
| `src/lib/capstoneFlow.ts` / `capstoneApi.ts` | Capstone in-chat workflow + gateway client |
| `src/index.css` | Login, option, dashboard, status, and responsive styles |
| `.env.example` | Gateway URL and registered agent names |

### Orchestrator, registry, and gateway

| File | Integration change |
|---|---|
| `agents/orchestrator/app/main.py` | Mounts the gateway router |
| `agents/orchestrator/app/gateway/routes.py` | Registry-resolved JSON/multipart forwarding (generic — no per-agent code) |
| `agents/orchestrator/app/gateway/__init__.py` | Gateway package |
| `agents/orchestrator/app/registry/service.py` | Resolves freshest healthy agent version |
| `agents/orchestrator/requirements.txt` | Compatible HTTP client dependency |
| `agents/orchestrator/README.md` | Gateway behavior and startup note |

### Capstone Agent

| File | Integration change |
|---|---|
| `agents/project_AI_Agent/manifest.json` | Registry identity, endpoint, actions, schemas |
| `app/integration/registry_client.py` | Registration, heartbeat, retry, deregistration |
| `app/api/main.py` | Lifespan-managed registry connection |
| `app/api/routes.py` | Common `/api/invoke`, course lookup, email persistence |
| `app/api/schemas.py` | Eligible-course response and learner email |
| `app/db/models.py` / `app/db/database.py` | Student email field + migration |
| `scripts/add_student.py` | Email-aware certified learner creation |
| `.env.example` / `INTEGRATION.md` | Registry config + agent-specific integration summary |

The standalone Capstone frontend (`agents/project_AI_Agent/frontend/*`) was
removed — the shared React chat is the only frontend. See
`agents/codeforge_agent/INTEGRATION.md` and
`agents/communication-ai-agent/INTEGRATION.md` for the equivalent file lists
for the CodeForge and Communication Coach integrations.

## 12. Files changed for the Communication Coach integration

### React application

| File | Integration change |
|---|---|
| `src/App.tsx` | Per-chat Communication state, health polling, dashboard mounting |
| `src/types/index.ts` | `"communication"` added to `Agent.kind` |
| `src/data/agents.ts` | Communication Coach agent card, `kind: "communication"` |
| `src/lib/communicationFlow.ts` / `communicationApi.ts` | In-chat menu/practice-loop state machine + gateway client |
| `src/components/CommunicationDashboard.tsx` | Right-side module/turn/score dashboard |

### Communication Agent (`agents/communication-ai-agent`)

The vendored Flask app (`backend/app/*`) is untouched except for the two
integration seams below — see
`agents/communication-ai-agent/INTEGRATION.md` for why a
re-entry dispatcher was used instead of a hand-written action map.

| File | Integration change |
|---|---|
| `manifest.json` | Registry identity, endpoint, ~50-action enum, schemas (new file) |
| `backend/integration/registry_client.py` | Registration, heartbeat, retry, deregistration (new file, Flask flavor) |
| `backend/app/routes/invoke.py` | Common `/api/invoke`: `health`, `bridge_identity`, and a re-entry dispatcher for every other action (new file) |
| `backend/app/__init__.py` | Registers `invoke_bp`; starts the registry client outside `TESTING` |
| `backend/requirements.txt` | Added `requests` (registry client HTTP calls) |
| `backend/.env.example` | Strategy F + DB + LLM provider config (new file) |

## 13. Verification completed

### Capstone

- `npm run build` / `npm run lint`
- Python compilation for modified orchestrator and Capstone modules
- `pip check` in both virtual environments
- Real MySQL registration using live Uvicorn processes
- Healthy registry lookup
- Gateway-forwarded Capstone health invocation and certified-course lookup
- Direct verification of student, completed enrollment, and certificate joins

### Communication Coach

- `npm run build` (`tsc -b && vite build`) — clean, no type errors
- `pytest` in `agents/communication-ai-agent/backend` — all 47 pre-existing
  tests still pass with `invoke_bp` registered
- A standalone smoke test against an in-memory SQLite app (`create_app` with
  `TESTING=True`) exercising `health`, `bridge_identity` (including
  re-bridging the same email reusing the same user), `dashboard`,
  `profile_get`, an unauthenticated call correctly returning `401`, an
  unknown action correctly returning `400`, a path-param action missing its
  param correctly returning `400`, and a full `writing_topics` →
  `writing_start` round trip — including the deterministic no-LLM-key
  fallback prompt path
- No live MySQL/orchestrator run yet — start order and end-to-end gateway
  registration follow the same pattern already verified for Capstone/
  CodeForge and documented in §9–§10

## 14. Troubleshooting

### `Activate.ps1` is missing

Regenerate activation scripts without clearing installed packages:

```powershell
cd E:\digidaraaiagents\agents\orchestrator
py -3.10 -m venv .venv
```

Activation is optional. The recommended command is:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8100
```

### An agent shows offline

Check in this order:

1. MySQL is running.
2. Orchestrator `/health` returns `ok`.
3. The agent process is running on its expected port (8000 Capstone, 4000
   CodeForge, 5001 Communication).
4. `/registry/agents?healthy_only=true` contains that agent.
5. `ORCHESTRATOR_URL` in the agent's `.env` points to port 8100.
6. `AGENT_PUBLIC_URL` is reachable from the orchestrator.

### Gateway returns HTTP 503

The requested agent is unregistered or its heartbeat is older than
`HEARTBEAT_TTL_SECONDS`. Restart that agent and inspect its logs for
registration failures.

### No certified courses are found (Capstone)

- The signup mobile must exactly match the database value.
- The enrollment status must be `completed`.
- A certificate must exist for the same student and course.
- Open a new Capstone chat after correcting a learner record because an old
  chat may already be in the terminal `not_eligible` state.

### Topic generation or grading returns HTTP 502/503

Confirm `LLM_MODEL`/`OPENAI_API_KEY` in the relevant `.env`. If question/
answer generation suddenly fails with a `model_not_found` error in the
agent's logs, check
[OpenAI's current model list](https://platform.openai.com/docs/models) and
update `LLM_MODEL`. Increase `AGENT_CALL_TIMEOUT_SECONDS` in the orchestrator
for slow grading/evaluation workflows.

### CodeForge: `run_problem`/`submit_problem` return `503 evaluator_unavailable`

Judge0 isn't running. Start it via `docker compose up -d db redis server
worker` from `agents/codeforge_agent/judge0` and confirm
`http://127.0.0.1:2358/about` responds.

### Capstone or CodeForge can't connect to MySQL

Confirm MySQL is running and the relevant database exists (`capstone_agent`
for Capstone — see §6.1, `leetcode` for CodeForge — see §6.2,
`communication_module` for Communication — see §6.3), and that the
connection settings in that agent's `.env` have the right host/port/user/
password. Capstone's `init_db()` creates its own tables on first startup;
CodeForge requires `python scripts/migrate.py up` to be run once; the
Communication agent creates/upgrades its own tables on startup like Capstone.

### Communication: writing/speaking/pronunciation start but feedback looks generic

No `OPENAI_API_KEY`/`GROQ_API_KEY` is configured (or the call failed) and the
route fell back to its deterministic fallback generator — sessions still
work end-to-end, but scoring quality depends on a real LLM key. Check
`AI_PROVIDER`/`OPENAI_API_KEY`/`GROQ_API_KEY` in
`agents/communication-ai-agent/backend/.env`.

## 15. Current development limitations

- Login/signup is a localStorage development experience, not production
  authentication.
- Mobile formatting and database matching are implemented, but SMS OTP is not.
- CORS currently allows all origins and should be restricted for production.

## 15. Aptitude Trainer Agent

The Aptitude Trainer Agent is integrated through Strategy F at
`agents/aptitude_agent`. It reuses the original Flask/MySQL assessment logic
and exposes a thin `POST /api/invoke` adapter for the shared UI. The browser
uses `VITE_APTITUDE_AGENT_NAME=aptitude_agent`; the service listens on port
5000 and registers with the orchestrator on port 8100. It supports
`ensure_session`, mixed/category test
creation, questions, answers, hints, results, and dashboard data.
- Capstone uses a lightweight, hand-rolled compatibility migration
  (`ALTER TABLE ADD COLUMN` on startup) rather than a formal migration tool;
  production deployments should adopt Alembic.
- Generic agent chat via orchestrator `/chat` requires a working LLM provider.
- Registry mutation and gateway invocation endpoints are authenticated — see
  [Security](#16-security).

To run Aptitude locally, create its MySQL database, copy
`agents/aptitude_agent/.env.example` to `.env`, then start it from the agent
directory. Use `AGENT_PUBLIC_URL=http://127.0.0.1:5000/api/invoke` and
`SINGLE_USER_MODE=false` so the shared UI identity is bridged into Aptitude.
- The Communication Coach's original standalone frontend (Web Speech API
  microphone capture, live avatar, audio playback) is not ported into the
  shared chat UI — Pronunciation and Speaking practice use typed text in
  place of a spoken transcript, exercising the same scoring backend the
  original frontend's transcript would have. ~35 secondary backend actions
  (topic-list browsing, insights/streak, rewrite/hint/tone tools, draft
  save, profile photo upload) are implemented and reachable via
  `/api/invoke` but not yet wired into the chat flow.

## 16. Security

### Generating secrets

Every secret below needs a real, random value per environment — never reuse
one across dev/staging/production, and never commit a real value to `.env`.

```bash
openssl rand -hex 32
```

### Orchestrator (`agents/orchestrator/.env`)

- `JWT_SECRET` — signs the platform's session tokens
  (`app/auth/security.py`). No fallback string; the app refuses to start if
  unset or left as a known placeholder value.
- `AGENT_SHARED_SECRET` — the HMAC key every agent's own registration/
  heartbeat client signs `/registry/*` calls with
  (`app/auth/service_auth.py`, adapted from
  `agents/codeforge_agent/services/lms-api/lms_api/auth.py`'s existing
  signed-request pattern). Required outside `ENV=dev`; every agent's own
  `.env` must be set to the exact same value.
- `ALLOWED_ORIGINS` — comma-separated browser origins allowed to call this
  API (CORS). Defaults to `http://localhost:5173` for local dev only.
- `ALLOWED_AGENT_HOSTS` — comma-separated hostnames the gateway is allowed to
  proxy `/gateway/agents/{name}/invoke` calls to. Defaults to every agent's
  Compose service hostname plus `127.0.0.1,localhost` (see
  `agents/orchestrator/.env.example`); anything else is rejected with 403.
  This is what actually stops a registered (or tampered-with) agent endpoint
  from turning the gateway into an open SSRF proxy into the internal
  network — set it explicitly outside Docker Compose (a bare-metal or
  differently-orchestrated deploy) to whatever hostnames your agents
  actually run under.
- `CHAT_RATE_LIMIT_PER_MIN` — per-user requests/minute on `/chat` and
  `/chat/route` (default 20; 429 with `Retry-After` on breach).
- `ENV` — set to anything other than `dev` (e.g. `production`) on a real
  deployment; this is what turns on the `AGENT_SHARED_SECRET` fail-fast
  above.

### Communication Agent (`agents/communication-ai-agent/backend/.env`)

- `SECRET_KEY` / `JWT_SECRET_KEY` — no fallback string; `create_app()`
  refuses to start (outside `TESTING`) if either is unset or a known
  placeholder value.
- `AGENT_SHARED_SECRET` — must match the orchestrator's.

### Capstone and CodeForge Agents

- `AGENT_SHARED_SECRET` — must match the orchestrator's; used only to sign
  outbound `/registry/*` calls.

### What's already good — replicate, don't rewrite

- The Razorpay billing webhook's HMAC verification
  (`agents/orchestrator/app/billing/routes.py`) using `hmac.compare_digest`.
- CodeForge's signed-request auth module,
  `agents/codeforge_agent/services/lms-api/lms_api/auth.py` — the pattern
  `app/auth/service_auth.py` above adapts.
- bcrypt password hashing (`agents/orchestrator/app/auth/security.py`).
- `project_AI_Agent`'s zip-ingestion hardening (path traversal, zip-bomb,
  and password-protected-zip rejection) in `app/ingestion/zip_ingest.py`.

### Known gaps not yet addressed here

- `agents/aptitude_agent/.env` has `SECRET_KEY=change-me` and
  `JWT_SECRET=change-me` live — different placeholder strings than
  `agents/aptitude_agent/backend/app/config.py::Config.validate()` actually
  checks for (`development-only-change-me` / `dev-secret-change-me`), so its
  existing production fail-fast wouldn't catch what's currently configured.
  Rotate both and consider widening that check to reject *any* unset/
  obviously-placeholder value, not just its own exact default string.
- `DATABASE_URL` insecure defaults, packaging hygiene (`.venv`/`uploads`
  tracked in git in places), log redaction, parameterized SQL in
  `lms-api/scripts/verify.py`, and login rate limiting are tracked
  separately and not yet covered by this section.
