# Voice-Based Mock Interview Module

An AI-powered mock interview practice application for students. The module supports voice-first Technical and HR interview rounds, adaptive question generation, answer evaluation, follow-up questions, audio transcription and playback, performance reporting, interview history, profile management, and interview-integrity tracking.

The project is designed as a standalone module that can later be integrated into an LMS. It currently uses a hardcoded demo student and does not yet provide production authentication.

## Contents

- [Overview](#overview)
- [Features](#features)
- [How an Interview Works](#how-an-interview-works)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [AI and Evaluation Behaviour](#ai-and-evaluation-behaviour)
- [Database](#database)
- [API Overview](#api-overview)
- [Project Structure](#project-structure)
- [Local Setup](#local-setup)
- [Configuration](#configuration)
- [Testing and Linting](#testing-and-linting)
- [Production Deployment](#production-deployment)
- [Known Limitations and Roadmap](#known-limitations-and-roadmap)

## Overview

Students can configure a mock interview by choosing:

- A Technical or HR round
- A preset technical subject or a custom technical topic
- Beginner, Intermediate, or Advanced difficulty
- Five or ten main questions

For preset Technical interviews, the New Interview page uses the student's
`course_enrolled` profile value to show the matching subject group. Matching is
case-insensitive and ignores surrounding whitespace. Blank, unknown, or
temporarily unavailable course values safely fall back to the complete subject
catalog, while Custom Topic remains available in every case.

During the interview, the application reads each question aloud, records the student's answer, displays a live browser-generated transcript, and submits the recorded audio to OpenAI for a more accurate final transcription.

Each answer is evaluated by AI and receives a `correct`, `partial`, or `wrong` verdict with a concise reason and a difficulty-matched interview-recommended answer. When an answer has a material gap, the interviewer may ask one validated follow-up question.

After all main questions are complete, the full transcript is evaluated to produce an interview report with scores, strengths, areas for improvement, detailed feedback, per-question results, audio playback, and interview-focus information.

## Features

### Interview setup

- Technical and HR interview rounds
- Five or ten configurable main questions
- Beginner, Intermediate, and Advanced difficulty levels
- Preset technical subjects grouped into five course-aligned categories
- Profile-aware preset filtering with a full-catalog fallback
- Custom technical topics up to 150 characters
- Interview summary before starting
- Optional daily-quota preflight check
- Automatic resumption of an existing active interview

Current preset subjects include:

| Course group | Preset subjects |
| --- | --- |
| Full Stack Development | Python, MySQL, JavaScript, React, Flask |
| Data Science & Analytics | Data Science, Power BI, MongoDB, Machine Learning, AI & ML |
| Generative & Agentic AI | Generative AI, LangChain & LangGraph, RAG & Vector Databases, FastAPI, AI Agent Development |
| Digital Marketing | SEO, SEM & Google Ads, Social Media Marketing, Content Marketing, Email Marketing |
| AI System Engineer | MLOps, Docker & Kubernetes, CI/CD Pipelines, Cloud Platforms, System Design |

Each preset has a dedicated topic-area checklist. Free-text Custom Topics are
canonicalized with case-insensitive, whitespace-normalized matching so repeated
sessions on the same custom topic share rotation history.

### Difficulty-calibrated question generation

Questions are generated according to the selected difficulty:

- **Beginner:** short questions about one fundamental concept
- **Intermediate:** practical application, comparison, debugging, or moderate reasoning
- **Advanced:** trade-offs, architecture, reliability, failure modes, design decisions, and deeper judgment

Technical interviews are conversational and concept-based. The AI is explicitly instructed not to require code snippets, syntax, function implementations, complete programs, or dictated code.

HR questions are behavioural and situational. Beginner HR rounds allow examples from education, projects, volunteering, clubs, and everyday responsibilities instead of requiring formal employment experience.

Main-question generation returns structured JSON containing `topic_area` and
`question`. Every generated main question passes through deterministic output,
topic, and complexity validation. The validator checks difficulty-specific word
limits, question-mark count, excessive qualifiers, semicolon-joined clauses,
complexity markers, interrogative clauses, and topic-label shape.

For preset Technical and HR paths, OpenAI must return the exact normalized topic
area selected by the rotation logic. For Custom Topics, OpenAI must not return a
normalized topic area from the recent exclusion list. Invalid output is rejected
and regenerated up to three times. If OpenAI cannot produce a valid result, the
backend uses a safe, difficulty-matched fallback that also satisfies the topic
contract.

### Cross-session question and topic rotation

Question avoidance is not limited to the current interview. Before every new
main question, the backend combines:

- Main questions already asked in the current interview
- Up to 40 recent main questions from the student's completed or exited
  interviews with the same round type, subject, and difficulty
- Current-interview topic areas
- Up to 80 recent topic areas from matching completed or exited interviews
  across difficulty levels

Text is Unicode-normalized, whitespace-normalized, case-insensitively
de-duplicated, and kept in recency order. Follow-ups are excluded from this
history.

Rotation differs appropriately by path:

- Preset Technical subjects prioritize unseen checklist areas, then the
  least-recently-used areas.
- Custom Topics exclude recently used areas for the same canonical free-text
  topic.
- HR interviews rotate through difficulty-specific behavioural checklists such
  as motivation, teamwork, conflict, communication, leadership, failure,
  accountability, and career goals.

### Validated follow-up questions

The AI may ask one follow-up when an answer contains a genuine conceptual or behavioural gap.

Follow-ups:

- Stay at the selected difficulty
- Focus on one material gap
- Use the same complexity-validation, retry, and fallback pipeline as main questions
- Do not ask for unnecessary polish or optional detail
- Do not count toward the configured main-question total
- Do not consume the daily question quota
- Are not asked after the final configured main question
- Are grouped with the original question in the final scorecard

When a follow-up is answered, its verdict becomes the effective verdict for that main-question scorecard item.

### Voice interview experience

- Browser text-to-speech reads questions aloud
- Browser speech recognition provides live captions
- `MediaRecorder` captures answer audio
- OpenAI creates the final transcription
- Manual text-answer mode is available when speech recognition is unsupported or fails
- Microphone, recording, timer, and speech resources are cleaned up safely
- Accidental refresh and navigation are guarded during a live interview
- An accessible exit-confirmation dialog provides keyboard focus management
- Recoverable network and AI failures provide retry handling

Answer time limits are:

| Difficulty | Time per question |
| --- | ---: |
| Beginner | 60 seconds |
| Intermediate | 90 seconds |
| Advanced | 120 seconds |

### Context-aware transcription

Recorded answers are transcribed with OpenAI's `gpt-4o-mini-transcribe` model. The transcription request includes the interview type, technical subject, current question, and subject-specific terminology for supported topics.

The browser transcript remains available as a fallback if Whisper is temporarily unavailable. Transcription is currently configured for English.

### AI answer evaluation

Each answer receives:

- A verdict: `correct`, `partial`, or `wrong`
- A short verdict reason
- A difficulty-matched interview-recommended answer
- A decision about whether a follow-up is materially necessary
- A validated follow-up question when required

The evaluator is designed for spoken interviews. It judges the candidate's intended meaning and is tolerant of fillers, repetition, rambling, false starts, self-corrections, informal wording, harmless terminology imprecision, and minor spoken-language disfluencies. It does not penalize a technical candidate for omitting code or exact syntax when the conceptual answer is sufficient.

Timed-out questions without an answer are deterministically marked wrong and receive zero credit.

### Final interview report

The final report includes:

- Overall score out of 10
- Technical accuracy, communication clarity, and confidence
- Average answer time
- Two to four concise strengths
- Two to four concise areas for improvement
- Detailed actionable feedback
- Per-question verdicts and explanations
- Interview-recommended answers
- Follow-up question and answer details
- Recorded-answer playback
- Deterministic question marks
- Interview-focus summary and integrity flag

Per-question deterministic marks are:

| Verdict | Mark |
| --- | ---: |
| Correct | 1 |
| Partial | 0.5 |
| Wrong | 0 |

The full-transcript AI evaluation and deterministic per-question scorecard are both included in the result data.

### Audio persistence and playback

Recorded audio is uploaded to the backend before answer submission completes. The backend validates its content type and configurable size limit, stores it in the managed audio directory, associates it with the relevant question, safely replaces older managed recordings, and exposes it for playback from interview results and history.

### Interview-focus and integrity tracking

The live interview tracks browser-tab visibility and window blur/focus changes, including when the student leaves, returns, and the total time spent away. Focus events use UUIDs and idempotent backend handling to avoid duplicates.

An interview is flagged for review when either:

- Focus is lost four or more times, or
- Total time away reaches 60 seconds

The integrity flag is informational and does not automatically change the AI-generated interview score.

### Daily usage quota

The application contains a transactional daily quota system with a default allowance of ten answered main questions per student per day.

Rules include:

- Only first-time, non-empty main-question answers consume quota
- Follow-up answers do not consume quota
- Duplicate submissions cannot increment usage twice
- A session can be reduced when fewer questions remain than the selected session length
- The quota date uses a configurable timezone offset
- Old usage records can be cleaned up automatically

The quota system is currently disabled through configuration. It is ready to be re-enabled after real authentication and trustworthy student identity handling are implemented.

### Dashboard

The dashboard provides:

- Total interviews, average score, highest score, and most recent score
- Technical and communication performance
- Weekly practice count and interviews completed this month
- Percentage improvement
- Skill-performance trend chart
- Five most recent completed interviews
- Subjects averaging below 6/10
- Recommended next interview

Recommendations use stored performance data and consider the student's weakest technical subject and the balance between technical and communication scores. Dashboard payloads use a short process-local TTL cache that is invalidated after relevant changes.

### Interview history

History provides server-side pagination, completed and exited interviews, and dedicated URL-based detail views. A detail view includes the full transcript, follow-ups, verdicts, recommended answers, time taken, timeout state, audio playback, focus-loss summary, and integrity status.

### Student profile

Students can view and edit their name, email, phone, enrolled course, target role, biography, and avatar fallback colour. JPG/JPEG, PNG, and WebP profile photos can be uploaded, replaced, and removed. Images receive content-based validation, pixel-count protection, and configurable size limits.

The profile also displays total interviews, average score, Technical-round count, and HR-round count.

The enrolled-course value also personalizes `/new-interview`: an exact
trimmed, case-insensitive match to a configured course group limits the default
preset view to that group's five subjects. Unknown or blank values retain the
full catalog.

### Navigation and responsive interface

The frontend uses URL-based navigation through React Router. Main routes include:

- `/dashboard`
- `/new-interview`
- `/history`
- `/history/:interviewId`
- `/profile`
- `/interview`
- `/result`

The interface includes responsive desktop/mobile layouts, a collapsible desktop
sidebar, a mobile sidebar drawer, a sidebar preference persisted in
`localStorage`, route-aware page metadata, and an application-level React error
boundary. Setup cards remain fully styled during slow profile requests and
sidebar rerenders; the complete preset catalog stays available until filtering
can be resolved safely.

## How an Interview Works

1. The student selects the round type, course-filtered preset or Custom Topic,
   difficulty, and question count.
2. The backend validates the request and checks for an existing active interview.
3. The backend loads matching cross-session question and topic history.
4. An existing interview is resumed; otherwise, OpenAI generates a structured
   `{topic_area, question}` result.
5. Topic and complexity validators accept, regenerate, or safely replace the
   question.
6. The frontend reads the question aloud and starts the answer timer.
7. Browser speech recognition displays a live transcript while audio is recorded.
8. The audio is uploaded and transcribed by Whisper with interview context.
9. The answer is saved transactionally and evaluated.
10. The student sees the verdict and reason.
11. The backend returns a validated follow-up or generates the next main
    question using combined current and historical context.
12. After every main question is evaluated, the full transcript is scored.
13. The final report is saved and displayed, and dashboard/history data is refreshed.

## Technology Stack

### Frontend

- React 18 and React DOM
- Vite 5
- React Router 6
- Lucide React and React Icons
- Browser Web Speech and MediaRecorder APIs
- Vitest, React Testing Library, and jsdom
- ESLint

### Backend

- Python and Flask 3
- Flask-CORS
- mysql-connector-python
- OpenAI Python SDK
- python-dotenv
- Pillow
- Waitress
- Python `unittest`

### Database

- MySQL 8 with InnoDB
- Foreign keys, check constraints, and unique constraints
- Stored compatibility routines and a scheduled cleanup event
- SQL migrations and a migration ledger

### AI

- OpenAI chat completions using `gpt-4o-mini`
- OpenAI transcription using `gpt-4o-mini-transcribe`

OpenAI powers question generation, answer evaluation, transcription, and the optional live
web-search feature through `OPENAI_SEARCH_MODEL`; if unavailable, the search
path falls back to AI-generated questions.

Model names are also configured through `OPENAI_MODEL` (legacy/OpenAI chat),
`OPENAI_EVAL_MODEL` (legacy/OpenAI evaluation), and
`OPENAI_TRANSCRIPTION_MODEL` in `backend/.env`.

## Architecture

### Backend architecture

The Flask application uses an application factory in `backend/app.py`.

HTTP responsibilities are split into Blueprints under `backend/routes/`:

- `answers.py` — audio transcription and answer submission
- `interviews.py` — interview start, resume, completion, exit, quota, and focus events
- `dashboard.py` — dashboard statistics and recommendations
- `history.py` — paginated history and interview details
- `profile.py` — student profile and avatar management
- `uploads.py` — managed avatar and audio delivery

AI responsibilities are split under `backend/ai/`:

- `chat_client.py` — OpenAI chat and transcription transport
- `question_generation.py` — structured main-question generation, preset
  catalogs, topic rotation, and follow-up prompts
- `answer_evaluation.py` — per-answer and full-interview evaluation
- `validators.py` — structured output, topic, complexity, retry, and fallback validation

Shared services live under `backend/services/`:

- `interview_state.py` — active interviews, canonical subject matching,
  cross-session question/topic history, context merging, and quota state
- `focus_tracking.py` — focus-loss persistence and summaries
- `media_storage.py` — safe managed-file cleanup

Other backend modules provide MySQL pooling and transactions, scorecard construction, business policies, request validation, pagination, keyed locks, bounded TTL caching, structured JSON logging, request IDs, shared error handling, and runtime schema compatibility checks.

### Frontend architecture

The React frontend is organized around:

- `App.jsx` — application shell, routes, live-interview state, and student context
- `api.js` — Flask API client
- `SetupScreen.jsx` — profile-aware course filtering, preset/custom setup,
  difficulty, question count, and interview-start orchestration
- `useSpeech.js` — text-to-speech, speech recognition, and recording support
- `useInterviewFocusTracking.js` — tab and window focus tracking
- `components/` — feature screens
- `components/ui/` — reusable presentation components
- `utils/` — icons, verdict formatting, profile helpers, and client logging
- `test/` — component, hook, and routing tests

```text
Student
  |
  v
React + browser speech/media APIs
  |
  v
Flask Blueprints
  |----------------------|
  v                      v
OpenAI chat/transcription       MySQL
  |                      |
  v                      v
Questions, verdicts,    Students, interviews,
transcripts, reports    answers, usage, focus events
```

## AI and Evaluation Behaviour

Question generation, follow-up selection, per-answer evaluation, recommended
answers, and final scoring use strict prompt and output contracts. Main questions
must pass deterministic structured-output, selected/excluded-topic, and
difficulty-complexity validation before reaching the student. JSON evaluation
responses are parsed, type-checked, range-checked, and normalized before being
stored.

The `topic_area` saved with every new main question powers cross-session
rotation. Older questions created before the topic-area migration may have a
`NULL` value and remain fully readable; they simply cannot contribute a topic
label until new interviews populate that field.

Question timeouts and deterministic marks do not depend on a successful AI response. Recoverable processing states allow a failed or interrupted operation to be retried without counting the same answer twice.

## Database

The fresh-install schema is defined in `backend/schema.sql`.

### Main tables

- `students` — personal, academic, role, biography, and avatar data
- `interviews` — configuration, lifecycle, final scores, feedback, and timestamps
- `interview_details` — main/follow-up questions, structured `topic_area` for
  new main questions, answers, verdicts, recommended answers, audio, and
  processing state
- `interview_focus_events` — focus-loss episodes and away duration
- `daily_usage` — quota-counted main-question answers by student and date
- `schema_migrations` — ledger of recorded migration filenames

Interview lifecycle states are `in_progress`, `completed`, and `exited`.

The migrations ledger was introduced after some older migrations already existed. Newer SQL migration files insert their filenames into `schema_migrations`; older pre-ledger files do not. Existing installations should still review and apply migration files in filename order.

`20260806_add_interview_topic_area.sql` adds the nullable `topic_area` column
used by structured question generation and records itself in the migration
ledger. Existing row counts and historical question data are preserved.

### Fresh database

Run:

```bash
mysql -u root -p < backend/schema.sql
```

The schema creates `mock_interview_db` by default. Add a development student if necessary:

```sql
USE mock_interview_db;

INSERT INTO students (id, name, email)
VALUES (1, 'Demo Student', 'demo@example.com');
```

The frontend currently expects the demo student to have ID `1`.

### Existing database

Do not rerun the full fresh-install schema against an existing database. Review and apply the relevant files in `backend/migrations/` in filename order.

The backend also provides:

```bash
cd backend
python migrate.py
```

`migrate.py` is an idempotent compatibility upgrader for selected runtime schema requirements. It is not a general migration-file executor and does not replace applying the SQL migration files.

## API Overview

All API routes use the `/api` prefix.

### Interviews and answers

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/start_interview` | Create or resume an interview |
| GET | `/api/active_interview/<student_id>` | Retrieve the active interview |
| GET | `/api/daily_usage/<student_id>` | Retrieve quota status |
| POST | `/api/transcribe` | Upload, persist, and transcribe answer audio |
| POST | `/api/submit_answer` | Save and evaluate an answer |
| POST | `/api/end_interview` | Complete and score an interview |
| POST | `/api/exit_interview` | Exit an active interview |
| POST | `/api/interviews/<interview_id>/focus-events` | Open or close a focus-loss episode |

### Dashboard, history, profile, and media

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/dashboard/<student_id>` | Retrieve dashboard statistics |
| GET | `/api/history/<student_id>` | Retrieve paginated history |
| GET | `/api/history/detail/<interview_id>` | Retrieve detailed history |
| GET | `/api/profile/<student_id>` | Retrieve a student profile |
| PUT | `/api/profile/<student_id>` | Update a student profile |
| POST | `/api/profile/<student_id>/avatar` | Upload or replace a profile photo |
| DELETE | `/api/profile/<student_id>/avatar` | Remove a profile photo |
| GET | `/api/uploads/avatars/<filename>` | Serve a managed avatar |
| GET | `/api/uploads/audio/<filename>` | Serve recorded-answer audio |

## Project Structure

```text
mock_interview_module/
├── README.md
├── backend/
│   ├── ai/                 # AI transport, prompts, evaluation, validation
│   ├── routes/             # Flask Blueprints
│   ├── services/           # Interview state, focus, and media services
│   ├── migrations/         # Existing-database SQL migrations
│   ├── tests/              # Backend and cross-layer tests
│   ├── uploads/            # Managed local audio and avatar storage
│   ├── app.py              # Flask application factory
│   ├── db.py               # MySQL pool and transactional helpers
│   ├── migrate.py          # Idempotent compatibility upgrader
│   ├── schema.sql          # Fresh-install schema
│   ├── settings.py         # Environment-backed settings
│   └── wsgi.py             # Production WSGI entry point
└── frontend/
    ├── public/
    ├── src/
    │   ├── components/     # Feature screens and reusable UI
    │   ├── test/           # Frontend tests
    │   ├── utils/          # Icons, formatting, profile, and logging helpers
    │   ├── api.js          # Backend API client
    │   ├── App.jsx         # Shell, routes, and live-interview state
    │   ├── useSpeech.js
    │   └── useInterviewFocusTracking.js
    ├── package.json
    └── vite.config.js
```

## Local Setup

### Prerequisites

- Python 3
- Node.js and npm
- MySQL 8
- A company-provided OpenAI API key
- Google Chrome or another browser with suitable Web Speech API support

Chrome currently provides the most reliable speech-recognition experience.

### 1. Create the database

For a fresh installation:

```bash
mysql -u root -p < backend/schema.sql
```

Add the development student if ID `1` does not exist:

```sql
USE mock_interview_db;

INSERT INTO students (id, name, email)
VALUES (1, 'Demo Student', 'demo@example.com');
```

### 2. Configure and run the backend

Windows PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
cd backend
python -m venv venv
venv\Scripts\activate
```

macOS or Linux:

```bash
cd backend
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `backend/.env`:

```dotenv
OPENAI_API_KEY=your_company_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EVAL_MODEL=gpt-5-mini
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe

DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=mock_interview_db
DB_POOL_SIZE=10

ALLOWED_ORIGINS=http://localhost:5173
FLASK_DEBUG=false
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
LOG_LEVEL=INFO

OPENAI_REQUEST_TIMEOUT_SECONDS=20
MAX_AUDIO_UPLOAD_MB=10
MAX_AVATAR_UPLOAD_MB=3

DAILY_LIMIT_ENABLED=false
DAILY_QUOTA_TIMEZONE_OFFSET_MINUTES=330
```

Run the backend:

```bash
python app.py
```

The API runs at `http://localhost:5000`.

### 3. Configure and run the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and uses `http://localhost:5000/api` by default.

To override the API URL, create `frontend/.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:5000/api
```

## Configuration

### Backend environment variables

Role interviews can optionally use source-backed frequently-asked questions.
Live web-search sourcing is disabled by default, so sessions currently use
AI-generated questions only. To re-enable it, set `ENABLE_LIVE_WEB_SEARCH=true`
and ensure `OPENAI_API_KEY` has sufficient credits; the feature uses OpenAI's
Responses API web-search tool restricted to Glassdoor and GeeksforGeeks.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | None | Required company-provided OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Fast model for question and recommended-answer generation |
| `OPENAI_EVAL_MODEL` | `gpt-5-mini` | Reasoning model for answer evaluation and final scorecards |
| `OPENAI_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` | Audio-transcription model |
| `OPENAI_SEARCH_MODEL` | `gpt-5.5` | Responses API model for live, domain-restricted web search |
| `ENABLE_LIVE_WEB_SEARCH` | `false` | Enable background live web-search question sourcing |
| `WEB_SEARCH_TIMEOUT_SECONDS` | `45` | Maximum total time for one non-retried background live web-search request; failures retain the existing AI-generated questions |
| `WEB_SEARCH_MAX_OUTPUT_TOKENS` | `8192` | Output-token cap for the background search call, including reasoning and visible output tokens |
| `OPENAI_REQUEST_TIMEOUT_SECONDS` | `20` | OpenAI request timeout |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | Empty | MySQL password |
| `DB_NAME` | `mock_interview_db` | MySQL database |
| `DB_POOL_SIZE` | `10` | MySQL connection-pool size |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `FLASK_DEBUG` | `false` | Flask development debug mode |
| `FLASK_HOST` | `127.0.0.1` | Development-server host |
| `FLASK_PORT` | `5000` | Development-server port |
| `LOG_LEVEL` | `INFO` | Structured logging level |
| `MAX_AUDIO_UPLOAD_MB` | `10` | Maximum answer-audio size |
| `MAX_AVATAR_UPLOAD_MB` | `3` | Maximum profile-photo size |
| `AUDIO_UPLOAD_DIR` | `backend/uploads/audio` | Managed audio directory |
| `AVATAR_UPLOAD_DIR` | `backend/uploads/avatars` | Managed avatar directory |
| `DAILY_LIMIT_ENABLED` | `false` | Enables the daily quota |
| `DAILY_QUOTA_TIMEZONE_OFFSET_MINUTES` | `330` | Quota timezone offset |

### Frontend environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:5000/api` | Backend API base URL |

## Testing and Linting

### Backend tests

From the backend directory:

```bash
cd backend
python -m unittest discover -s tests
```

The default suite covers validation, business policies, AI prompts, difficulty
calibration, structured question output, deterministic topic enforcement,
cross-session question/topic rotation for preset Technical, Custom Topic, and HR
paths, follow-ups, dashboard aggregation, pagination, focus tracking, structured
logging, caching, locks, route integration, schema contracts, audio persistence,
and cross-layer contracts.

### Optional MySQL integration tests

MySQL-backed tests are disabled by default. They create a uniquely named disposable database, apply `schema.sql`, exercise the route lifecycle, and remove the disposable database during cleanup. They require a running MySQL server and credentials with permission to create and drop test databases. The configured live database is used only as a read-only safety sentinel.

Windows PowerShell:

```powershell
cd backend
$env:RUN_MYSQL_INTEGRATION_TESTS = "1"
python -m unittest tests.test_mysql_route_integration
```

Windows Command Prompt:

```bat
cd backend
set RUN_MYSQL_INTEGRATION_TESTS=1
python -m unittest tests.test_mysql_route_integration
```

macOS or Linux:

```bash
cd backend
RUN_MYSQL_INTEGRATION_TESTS=1 python -m unittest tests.test_mysql_route_integration
```

You can also enable the variable and run the complete backend suite.

### Frontend tests

```bash
cd frontend
npm run test
```

### Frontend lint

```bash
cd frontend
npm run lint
```

### Production build check

```bash
cd frontend
npm run build
```

## Production Deployment

Keep Flask debug mode disabled:

```dotenv
FLASK_DEBUG=false
```

From the backend directory, run Waitress:

```bash
cd backend
waitress-serve --call wsgi:create_app
```

For production:

- Set `ALLOWED_ORIGINS` to the exact LMS or frontend origin
- Serve the React production build through a web server or hosting platform
- Terminate HTTPS at a reverse proxy
- Do not expose Flask's development server publicly
- Replace the hardcoded student ID with authenticated server-side identity
- Store secrets outside source control
- Consider moving uploaded media to durable object storage
- Configure logging collection and retention
- Review MySQL event-scheduler and routine privileges required by `schema.sql`

## Known Limitations and Roadmap

### Authentication is not implemented

`frontend/src/App.jsx` currently contains:

```js
const STUDENT_ID = 1;
```

This is suitable only for local development and a single demo student. Implementing authentication and deriving the student identity from a trusted server-side session or verified token is the highest priority before multi-student or production LMS deployment.

Backend authorization must also ensure that a student can access only their own interviews, history, profile, recordings, and focus events.

### Daily quota is intentionally disabled

The quota system is implemented but currently disabled with:

```dotenv
DAILY_LIMIT_ENABLED=false
```

It should remain disabled until authentication provides a trustworthy student identity. It can then be re-enabled without redesigning the core quota workflow.

### Manual accessibility verification remains

Automated tests cover many interaction contracts, but manual browser-based verification remains pending for:

- Colour contrast
- Touch-target sizes
- Mobile touch behaviour
- Real-device responsive layouts
- Screen-reader behaviour
- Cross-browser speech and microphone handling

The profile-filtered New Interview layout and collapsible-sidebar behaviour have
automated slow-profile and rerender regression coverage. Manual verification on
real browsers, throttled networks, and physical mobile devices is still
recommended before production release.

### npm audit findings

Two moderate npm audit findings remain. Resolving them is tied to planned major-version dependency upgrades, particularly:

- React Router 6 to React Router 7
- Vite 5 to Vite 8

Those upgrades have not yet been completed because they require compatibility work and regression testing rather than a risk-free patch update.

### Additional production hardening

Future production work includes:

- Authenticated and authorized API requests
- CSRF/session strategy or verified bearer-token handling
- Rate limiting
- Durable object storage for avatars and audio
- Media retention and deletion policies
- Multi-instance cache and coordination strategy
- Production monitoring and alerting
- Broader manual accessibility and cross-browser voice testing
# AI Usage and Billing Analytics

The application records provider-reported AI usage in `ai_usage_records`. Chat and transcription requests are captured in `backend/ai/chat_client.py`; token values come only from the provider response's `usage` object. When a provider does not return usage, the request is stored with zero tokens and a structured warning is emitted.

Estimated cost is calculated centrally in `backend/services/ai_usage.py` from provider/model pricing per million input and output tokens. Update `MODEL_PRICING` there when published pricing changes. The schema remains provider-neutral through its `provider`, `model_name`, and `request_type` columns.

Run `python migrate.py` from `backend` (or apply `backend/migrations/20260807_add_ai_usage_records.sql`) before deploying. The dashboard is available at `/analytics` and calls student-scoped `/api/analytics/*` endpoints. This project currently uses its existing demo `student_id` request model; replace it with the authenticated server-side student identity before exposing analytics in a multi-user deployment.
