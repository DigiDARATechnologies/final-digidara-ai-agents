# AptiDARA — Aptitude AI Agent

AptiDARA is a self-contained aptitude assessment application built with React, Flask, MySQL, and the OpenAI API. It provides batch-generated mixed assessments, focused category practice, conceptual hints, immediate answer feedback, completed-test analytics, AI usage tracking, and an editable learner profile in the existing purple/light AptiDARA interface.

This README describes the application as implemented on **27 August 2026**.

## Current product status

Implemented and active:

- Dashboard is the landing page; `/` redirects to `/dashboard`.
- Learner-configurable Mixed Test across all six aptitude categories, with 3–10 questions required per category.
- 10-question fixed-level Category Practice with Beginner selected by default.
- Shared topic taxonomy with researched priority metadata and visible priority-topic stars.
- Equal-probability, all-topic rotation for Mixed Test.
- 50/50 priority weighting and non-priority-topic rotation for Category Practice.
- Shared per-category topic history across Mixed Test and Category Practice.
- One complete-test OpenAI generation request with strict batch validation before the test starts.
- Transactional persistence of every question before the first question is served.
- Recent and in-test duplicate-question prevention.
- Topic and difficulty transparency tags on every question.
- Difficulty-based, server-authoritative timer: 60s Easy, 90s Medium, and 120s Hard.
- Conceptual hints with answer-safety validation and deterministic fallback.
- Immediate local scoring with no negative marking.
- Step-by-step explanation formatting.
- Completed-test Results and question review.
- Downloadable PDF reports for completed assessments from History.
- Dashboard score trend, category bars/radar, performance snapshot, and focus area.
- Completed-attempt History with local-time display.
- AI token usage dashboards without learner-facing cost estimates.
- Technical Aptitude language selection for C, Java, Python, and SQL, with Python as the default.
- Editable learner profile and persisted profile photo.
- Synchronous, persisted AI focus recommendation on the Results page.
- MySQL-backed analytics and maintenance worker.
- Backend tests, frontend lint/build checks, and GitHub Actions CI.

Current verification baseline: **141 backend tests passing**, **9 aptitude frontend tests passing**, frontend ESLint and TypeScript checks passing, and the Vite production build passing.

Retired from the active product:

- Reusable learner question-bank sourcing and question-bank bootstrap jobs.
- Confidence rating.
- Written reasoning evaluation.
- Mistake diagnosis.
- Answer-evaluation calls to an AI provider.
- Resume-test functionality.
- Separate Home, Login, and Register pages in the React UI.

Some legacy database columns, tables, and dormant compatibility service code remain so migration history and existing data stay safe. Learner-facing runtime paths do not call them for the retired features.

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, HTML5, CSS3, React Router, Lucide icons |
| Backend | Python 3.12, Flask, Flask-SQLAlchemy, Flask-Migrate, Werkzeug |
| Database | MySQL 8 with PyMySQL |
| AI provider | OpenAI API |
| Production WSGI | Waitress |
| Background work | Python worker with a transactional MySQL job table |
| Testing and quality | Pytest, ESLint, Vite production build, GitHub Actions |

Docker, Redis, SQLite, PostgreSQL, and an external LMS are not required. Learner identity and assessment ownership are stored inside AptiDARA's MySQL database.

## Architecture

```text
React/Vite browser
       |
       | REST/JSON
       v
Flask application --------------------> OpenAI API
       |                                  | questions
       | SQLAlchemy                       | hints
       |                                  | recommendations
       v
MySQL 8 <---------------------------- worker.py
                                      analytics, cleanup,
                                      jobs and heartbeat
```

### Runtime responsibilities

The Flask web process owns learner-facing work:

- Creates tests.
- Generates and validates the complete question batch.
- Persists the complete batch before marking a test ready.
- Generates safe conceptual hints.
- Scores submitted answers locally.
- Generates the Results recommendation synchronously on first access.
- Serves the REST API and compiled React application.

The separate `worker.py` process owns non-critical background work:

- Materialized analytics updates.
- Stale assessment cleanup.
- Background-job recovery and maintenance.
- Worker heartbeat and lifecycle status.

The worker does **not** generate learner questions, hints, or Results recommendations.

## Assessment modes

### Mixed Test

| Property | Behavior |
| --- | --- |
| Questions | Configurable per learner: 3–10 in every category, 18–60 total; 21 by default |
| Categories | 6 |
| Timer | Easy 60s, Medium 90s, Hard 120s per question |
| Difficulty | Fixed schedule containing Easy, Medium, and Hard questions |
| Hints | 3 by default, configurable with `HINTS_PER_TEST` |
| Topic policy | Equal probability across all eligible topics; every recent topic rotates |
| Technical language | C, Java, Python, or SQL; Python by default |
| Scoring | +1 correct, 0 wrong/timed out, no negative marking |

Category distribution:

| Category | Default | Allowed range | Description |
| --- | ---: | ---: | --- |
| Quantitative Aptitude | 5 | 3–10 | Numerical and mathematical problem-solving |
| Logical Reasoning | 4 | 3–10 | Pattern recognition and logical deduction |
| Verbal Ability | 3 | 3–10 | Language, comprehension, and grammar skills |
| Analytical Reasoning | 3 | 3–10 | Structured problem-solving and reasoning puzzles |
| Computer Fundamentals | 3 | 3–10 | Core computer science concepts |
| Technical Aptitude | 3 | 3–10 | Programming logic and technical problem-solving |

Counts are stored per learner in MySQL. The overview updates the total live and provides explicit Save and Reset to Default actions. No category can be excluded from a Mixed Test.

Mixed difficulty is assigned when the complete test schedule is built. The
Easy, Medium, and Hard labels are persisted with the questions and do not
change in response to earlier answers.

### Category Practice

| Property | Behavior |
| --- | --- |
| Questions | 10 |
| Categories | One learner-selected category |
| Level | Beginner, Intermediate, or Advanced |
| Difficulty mapping | Beginner = Easy, Intermediate = Medium, Advanced = Hard |
| Timer | Beginner 60s, Intermediate 90s, Advanced 120s per question |
| Hints | 2 |
| Adaptation | None; the selected level remains fixed |
| Topic variety | Ten weighted topics are sampled from the shared category taxonomy; non-starred topics from the learner's previous Mixed or Practice attempt are deprioritized |
| Technical language | C, Java, Python, or SQL for Technical Aptitude; Python by default |
| Scoring | +1 correct, 0 wrong/timed out, no negative marking |

Technical Aptitude questions support structured, multi-line code in the question, options, and explanation without collapsing indentation.

Mixed Test and Category Practice topic labels come from a config-only taxonomy covering all six categories. Priority topics display a `★` marker in live question and Results topic labels. Category Practice keeps 50/50 priority weighting and rotates recently used non-priority topics. Mixed Test ignores priority metadata when selecting, gives every eligible topic equal probability, and rotates all recently used topics. Both modes consult the same latest per-category `learner_last_topics` history, including across mode changes. Question content remains fully live and is never stored in this rotation table.

## Learner workflow

```text
Dashboard
  -> Mixed Test overview
     -> Instructions
        -> Mixed-difficulty test session
           -> Results

Dashboard
  -> Category Practice overview
     -> Choose category and level
        -> Fixed-level practice session
           -> Results
```

Only one question is shown at a time. After submission, the learner immediately sees whether the answer was correct, the stored correct answer, and a readable explanation before continuing.

Tests cannot be resumed. Re-entering an already-started question or confirming navigation away abandons the attempt. Starting a new test also abandons any previous unfinished attempt. Abandoned records remain in MySQL for operational analysis but are excluded from learner-facing History and Dashboard performance calculations.

## AI generation and reliability

### Complete-test batch generation

Every test is generated as one complete OpenAI JSON batch. The reusable question-bank architecture is retired; the legacy table remains only for migration compatibility. The server validates the full response and stores all questions in one transaction before returning a ready test ID. Question fetch and answer submission read stored rows and never call the provider.

The generation path includes:

- Primary and fallback models configured by `OPENAI_MODEL` and `OPENAI_FALLBACK_MODELS`.
- OpenAI SDK retries disabled with `max_retries=0` so retry behavior is visible and bounded by the application.
- A 120-second provider timeout and 180-second complete-batch deadline by default.
- At most two complete-batch validation attempts.
- Immediate failover to the fallback model after a `429`; the same rate-limited model is not retried.
- Exactly one same-model retry for eligible transient transport errors.
- Per-model circuit breaker and Retry-After awareness.
- Strict JSON, option, answer, explanation, category, topic, and difficulty validation.
- Structural and semantic duplicate detection within the batch and against recent learner history.
- Exact question-count validation before any questions are committed.

When `ALLOW_DEMO_QUESTIONS=true`, local development assessments fall back to validated fixtures if the provider is temporarily unavailable or generated content repeatedly fails validation. Production validation requires `ALLOW_DEMO_QUESTIONS=false`, so deployed assessments remain AI-only and surface provider failures normally.

### Conceptual hints

Hints use the smaller configured OpenAI model, a five-second budget, and a small completion limit. Safety validation rejects hints that reveal an option, repeat the answer, include calculations, or expose answer-specific numeric values. If OpenAI is unavailable or both safety attempts fail, the application returns a topic-specific deterministic hint instead of a raw provider error.

The external OpenAI call runs before the endpoint acquires MySQL write locks. The lock covers only final revalidation and persistence, preventing slow AI calls from blocking other requests on the same test.

### Answer scoring

Answer correctness is authoritative and local:

```text
selected_answer == stored correct_answer
```

Submitting an answer never calls OpenAI. This keeps scoring deterministic and the critical answer-submission path limited to validation and MySQL writes.

### AI focus recommendation

The first request to a completed test's Results page generates a concise recommendation synchronously under a bounded deadline. The result is stored in MySQL and reused on later visits. If OpenAI fails, the application stores and returns a deterministic fallback recommendation so the Results page remains complete.

### Completed-test PDF reports

History provides a Download action for every completed assessment. Flask builds the PDF on demand with the learner/test summary and question-review content, verifies assessment ownership, and returns it as an attachment. Incomplete and abandoned attempts cannot be downloaded.

## Frontend routes

| Route | Page |
| --- | --- |
| `/` | Redirects to Dashboard |
| `/dashboard` | Landing page and performance overview |
| `/aptitude-test` | Mixed Test overview |
| `/aptitude-test/instructions` | Mixed Test instructions |
| `/aptitude-test/session` | Creates a Mixed Test and redirects to its session |
| `/aptitude-test/session/:id` | Mixed Test session |
| `/aptitude-test/category-practice` | Category Practice overview |
| `/aptitude-test/category-practice/setup` | Category and level selection |
| `/aptitude-test/category-practice/session/:id` | Category Practice session |
| `/test/:id` | Compatibility route for the shared assessment screen |
| `/results/:id` | Completed assessment details and question review |
| `/history` | Completed assessments only |
| `/analytics` | OpenAI token usage by day, test, question, and operation |
| `/profile` | Editable learner profile |

Legacy `/agents`, `/login`, and `/register` frontend URLs redirect into the current Dashboard/Aptitude Test experience.

## REST API

Base path: `/api/aptitude`

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/me` | Read learner profile |
| `PATCH` | `/me` | Update learner profile |
| `GET/PUT/POST/DELETE` | `/me/photo` | Read, upload, or remove profile photo |
| `GET` | `/dashboard` | Completed-test performance data |
| `POST` | `/tests` | Create Mixed Test or Category Practice |
| `GET` | `/tests/<id>/status` | Read assessment lifecycle status |
| `GET` | `/tests/<id>/question` | Serve the current safe question |
| `POST` | `/tests/<id>/hint` | Request a conceptual hint |
| `POST` | `/tests/<id>/answer` | Score and persist an answer |
| `POST` | `/tests/<id>/abandon` | Forfeit an unfinished attempt |
| `GET` | `/tests/<id>` | Completed Results and question review |
| `GET` | `/tests/<id>/download` | Download a completed assessment PDF |
| `GET` | `/history` | Completed tests only |
| `GET` | `/analytics` | Category and score analytics |
| `GET` | `/usage` | OpenAI token usage analytics |
| `GET` | `/operations` | Worker and job health |
| `POST` | `/operations/jobs/<id>/retry` | Retry an eligible failed job |

Native backend `/auth/register`, `/auth/login`, and `/auth/logout` endpoints remain available for future multi-user integration. The current React application intentionally has no authentication screens.

Mixed Test configuration uses a learner-scoped API outside the aptitude base path:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/learner/mixed-test-config` | Read six category counts, limits, defaults, and total |
| `PUT` | `/api/learner/mixed-test-config` | Validate and persist all six category counts |

API errors use a stable structure:

```json
{
  "error": "Human-readable message",
  "code": "stable_error_code",
  "request_id": "uuid"
}
```

## Project structure

```text
Aptitude_ai_agent/
├── app.py                         # Flask development entry point
├── worker.py                      # Analytics and maintenance worker
├── requirements.txt               # Runtime Python dependencies
├── requirements-dev.txt           # Test dependencies
├── backend/
│   ├── app/
│   │   ├── models/                # SQLAlchemy/MySQL models
│   │   ├── routes/                # REST endpoints
│   │   ├── services/              # Generation, hints, analytics, jobs
│   │   └── utils/                 # Errors, auth, formatting, logging
│   ├── migrations/versions/       # Alembic migrations 0001–0024
│   ├── tests/                     # MySQL integration tests
│   └── unit_tests/                # Focused service/unit tests
├── frontend/
│   ├── src/pages/                 # Dashboard, tests, Results, History
│   ├── src/components/            # Shared assessment/UI components
│   ├── src/layouts/               # Shared application shell/sidebar
│   └── src/styles.css             # AptiDARA design system
├── database/                      # Standalone MySQL SQL and instructions
├── docs/                          # Architecture/API/operations documents
├── scripts/                       # MySQL setup utilities
└── .github/workflows/quality.yml  # CI quality gate
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- MySQL 8+
- OpenAI API key for complete-test batch generation

## Local installation

### 1. Create the MySQL databases and users

Sign in to MySQL as an administrator and run:

```sql
CREATE DATABASE aptitude_ai_dev
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE aptitude_ai_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'aptitude_user'@'localhost'
  IDENTIFIED BY 'change-this-dev-password';

CREATE USER 'aptitude_test_user'@'localhost'
  IDENTIFIED BY 'change-this-test-password';

GRANT ALL PRIVILEGES ON aptitude_ai_dev.*
  TO 'aptitude_user'@'localhost';

GRANT ALL PRIVILEGES ON aptitude_ai_test.*
  TO 'aptitude_test_user'@'localhost';

FLUSH PRIVILEGES;
```

You can also run the interactive setup helper:

```powershell
python scripts\setup_mysql.py
python scripts\setup_mysql.py --test
```

### 2. Create the Python environment

```powershell
cd D:\Aptitude_ai_agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install dependencies from the pinned `requirements.txt` so the OpenAI client and HTTP transport remain compatible.

### 3. Configure `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

At minimum, configure:

```dotenv
DATABASE_URL=mysql+pymysql://aptitude_user:url-encoded-password@localhost:3306/aptitude_ai_dev
TEST_DATABASE_URL=mysql+pymysql://aptitude_test_user:url-encoded-password@localhost:3306/aptitude_ai_test
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODELS=
SECRET_KEY=replace-with-a-long-random-secret
JWT_SECRET=replace-with-a-long-random-jwt-secret
SINGLE_USER_MODE=true
LOCAL_USER_EMAIL=kiruthika@example.edu
LOCAL_USER_NAME=Kiruthika
```

URL-encode reserved password characters in SQLAlchemy URLs. For example, the password `March&10&may` becomes `March%2610%26may`:

```dotenv
DATABASE_URL=mysql+pymysql://aptitude_user:March%2610%26may@localhost:3306/aptitude_ai_dev
```

### 4. Apply MySQL migrations

```powershell
flask --app app db upgrade
```

Do not use `db.create_all()` for this project. The reviewed Flask-Migrate/Alembic chain is the schema source of truth.

### 5. Verify OpenAI

```powershell
flask --app app openai-check --full
```

The command verifies both JSON generation used by questions and plain-text generation used by hints/recommendations.

## Run locally

### Terminal 1 — Flask

```powershell
cd D:\Aptitude_ai_agent
.\.venv\Scripts\Activate.ps1
python app.py
```

Flask runs at `http://127.0.0.1:5000`.

### Terminal 2 — React/Vite

```powershell
cd D:\Aptitude_ai_agent\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` and `/health` to Flask.

### Terminal 3 — worker

```powershell
cd D:\Aptitude_ai_agent
.\.venv\Scripts\Activate.ps1
python worker.py
```

The worker is a separate process. Flask debug reloads do not start it. Stop it with `Ctrl+C`; it records a clean `stopped` heartbeat, while stale heartbeats are later marked `dead`.

## Local single-user mode

The current frontend opens directly on the Dashboard and does not show Login or Register pages.

With `SINGLE_USER_MODE=true`:

- The backend selects the learner identified by `LOCAL_USER_ID`.
- If the learner does not exist, it is created once from local configuration.
- All frontend pages operate directly for that learner.
- Profile changes are stored in MySQL.

Single-user mode is intended for a trusted local environment. Production configuration rejects `SINGLE_USER_MODE=true`; a production multi-user deployment must supply its own completed authentication UI/integration and set safe secrets.

## Important configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_MODEL` | `gpt-4o-mini` | Primary generation model |
| `OPENAI_FALLBACK_MODELS` | empty | Ordered fallback model list |
| `OPENAI_TIMEOUT_SECONDS` | `12` | Foreground provider-call timeout |
| `OPENAI_BATCH_TIMEOUT_SECONDS` | `120` | Complete-test batch provider timeout ceiling |
| `BATCH_GENERATION_DEADLINE_SECONDS` | `180` | Shared batch generation and validation budget |
| `BATCH_GENERATION_MAX_ATTEMPTS` | `2` | Maximum complete-batch validation attempts |
| `QUESTION_GENERATION_MAX_COMPLETION_TOKENS` | `16000` | Complete question-batch JSON completion ceiling |
| `HINT_TIMEOUT_SECONDS` | `5` | Hint-generation budget |
| `HINT_MAX_COMPLETION_TOKENS` | `96` | Hint completion ceiling |
| `RECOMMENDATION_TIMEOUT_SECONDS` | `7` | Results recommendation budget |
| `HINT_CACHE_TTL_SECONDS` | `120` | In-process hot-cache lifetime for persisted hints |
| `RECENT_QUESTION_HISTORY_LIMIT` | `30` | Recent-question exclusion history |
| `QUESTION_SECONDS` | `60` | Legacy/default Easy timer |
| `QUESTION_SECONDS_EASY` | `60` | Easy / Beginner timer |
| `QUESTION_SECONDS_MEDIUM` | `90` | Medium / Intermediate timer |
| `QUESTION_SECONDS_HARD` | `120` | Hard / Advanced timer |
| `HINTS_PER_TEST` | `3` | Mixed Test hint budget |
| `START_TEST_RATE_LIMIT` | `100` in development, `10` otherwise | Successful test starts allowed per learner/window |
| `START_TEST_RATE_WINDOW_SECONDS` | `3600` | Test-start rate-limit window |
| `ABANDON_AFTER_SECONDS` | `180` | Crash/network-loss abandonment safety net |
| `APP_TIMEZONE_OFFSET_MINUTES` | `330` | Daily usage boundary; 330 is IST |
| `WORKER_HEARTBEAT_SECONDS` | `10` | Worker heartbeat interval |
| `WORKER_STALE_SECONDS` | `45` | Worker-dead threshold |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection-pool size |
| `DB_MAX_OVERFLOW` | `20` | Additional temporary DB connections |

Operational usage rows retain estimated-cost fields for historical/internal reporting compatibility, but the learner-facing AI Usage page displays tokens only.

## Health checks

| Endpoint | Meaning |
| --- | --- |
| `GET /health` | Flask can query MySQL |
| `GET /ready` | MySQL is available and a worker heartbeat is online |

`/ready` can report `503 not_ready` when the worker is stopped even though Flask can still serve live questions. This is intentional operational readiness behavior.

## Tests and quality checks

Integration tests require a dedicated MySQL database whose name ends in `_test`. Test fixtures delete table data, so never point `TEST_DATABASE_URL` at `aptitude_ai_dev`.

```powershell
cd D:\Aptitude_ai_agent
.\.venv\Scripts\python.exe scripts\setup_mysql.py --test
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm install
npm run lint
npm run build
```

GitHub Actions runs the same quality gate on every push and pull request:

1. Starts MySQL and creates `aptitude_ai_test`.
2. Installs Python and Node dependencies.
3. Applies all migrations.
4. Runs backend tests.
5. Runs frontend lint.
6. Builds the production frontend.

## Local production build

```powershell
cd D:\Aptitude_ai_agent\frontend
npm install
npm run build

cd D:\Aptitude_ai_agent
.\.venv\Scripts\Activate.ps1
flask --app app db upgrade
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

Run `python worker.py` in another terminal and open `http://127.0.0.1:5000`. Flask serves the compiled files from `frontend/dist`.

## Troubleshooting

### MySQL unavailable or access denied

Check that MySQL is running, the account grants match the selected database, and reserved password characters are URL-encoded.

```powershell
python scripts\setup_mysql.py
flask --app app db upgrade
```

### `503` while starting a test

Complete-test batch generation depends on OpenAI. Inspect the structured Flask log and its `request_id`. Common causes include:

- Missing or invalid API key.
- Retired or inaccessible model.
- OpenAI `429` token/rate limit.
- Provider timeout or open circuit breaker.
- Invalid/truncated JSON.
- Generated question failing answer/explanation/duplicate validation.

Run:

```powershell
flask --app app openai-check --full
```

The test-creation route does not use the legacy question bank as an outage fallback. If all configured models are unavailable, the learner receives a bounded `503` instead of an incomplete test.

### Hint appears after a short delay

Hints are synchronous because they must match the active question and pass answer-safety checks. The request is bounded and returns a deterministic fallback when OpenAI cannot provide a safe hint.

### Dashboard analytics are stale

Start the worker:

```powershell
python worker.py
```

### React changes do not appear on port 5000

Port 5000 serves the compiled frontend. Rebuild it:

```powershell
cd frontend
npm run build
```

Use `npm run dev` and port 5173 for automatic development refresh.

### `.venv` reports that Python is missing in a managed sandbox

The virtual environment uses Python 3.12.8 from `C:\Users\DELL\AppData\Local\Programs\Python\Python312`. Verify `.venv\pyvenv.cfg` and the base executable before recreating the environment. A restricted tool may simply need permission to read the base installation.

## Known production boundaries

- The current React application is optimized for trusted local single-user access and has no production login UI.
- New test creation depends on OpenAI availability and quota.
- Validated hints are persisted on their question for reuse across processes; each process also keeps a short-lived hot cache.
- The legacy question-bank and retired diagnostic schema remain until a separate reviewed cleanup migration is approved.
- Mixed Test and Category Practice use one OpenAI batch at creation; the validated questions are then stored for sequential delivery.
- `APP_TIMEZONE_OFFSET_MINUTES` is a fixed offset, not a daylight-saving-aware timezone database.
- Production deployment still needs external process supervision, TLS termination, backups, monitoring, and a completed multi-user authentication journey.

## Additional documentation

This README is the current runtime reference. The deeper documents below also contain architectural and migration history; when historical text differs from the current implementation, use this README and the source code as the authoritative current behavior.

- [Architecture](docs/architecture.md)
- [REST API](docs/api.md)
- [Database](docs/database.md)
- [Production operations](docs/production-operations.md)
- [Production roadmap](docs/production-roadmap.md)
- [Standalone MySQL import](database/README.md)

The standalone schema is available at [database/aptitude_ai_mysql.sql](database/aptitude_ai_mysql.sql). Prefer migrations for normal development and deployments.
