# Mock Interview Module - Technical Documentation

## 1. Module overview

The Mock Interview Module is a voice-enabled practice platform where a student configures a technical or HR interview, answers AI-generated questions, receives per-answer feedback, and reviews a final performance report. It also provides a dashboard, completed-interview history, AI-usage analytics, profile management, audio playback, and interview-focus tracking.

> **Current integration note:** the frontend uses `STUDENT_ID = 1` as a demo identity. Authentication or LMS session integration should replace this before production use.

## 2. Technology stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | React 18, React Router DOM | Single-page UI and client-side routing |
| Build/test tooling | Vite, Vitest, Testing Library, ESLint | Development server, builds, tests, and linting |
| UI assets | lucide-react, react-icons, CSS | Icons and responsive interface styling |
| Browser APIs | Web Speech API, MediaRecorder, Fetch API | Text-to-speech, speech recognition, audio capture, HTTP calls |
| Backend | Python, Flask 3, Flask-CORS | REST API, validation, routing, and CORS configuration |
| AI | OpenAI Python SDK (`gpt-4o-mini`, `gpt-4o-mini-transcribe`) | Question generation, audio transcription, answer evaluation, and final evaluation |
| Database | MySQL 8, mysql-connector-python | Persistent student, interview, answer, focus, and usage data |
| Media processing | Pillow | Validates, crops, and converts avatars to WebP |
| Production serving | Waitress / WSGI | Optional production Python application server |
| Configuration | python-dotenv | Loads environment variables from `.env` |

## 3. Main functionality

- Configure a **technical** or **HR** interview at beginner, intermediate, or advanced difficulty.
- Select 5 or 10 questions; technical interviews support preset and custom topics.
- Generate the initial question and subsequent planned main questions with AI.
- Avoid recently used questions and topic areas for the same student where possible.
- Ask questions aloud, capture the candidate's spoken answer, and provide typed-answer fallback.
- Transcribe recorded WebM, OGG, M4A, MP3, or WAV audio with contextual prompts.
- Batch-evaluate all planned answers at interview completion, then store each verdict, reason, and ideal answer.
- Generate a final report with overall score, technical accuracy, communication clarity, confidence, strengths, weaknesses, and feedback.
- Save answer audio for replay in history.
- Track browser visibility/window-focus loss events and show integrity summary data.
- Show dashboard metrics, improvement trend, weak subjects, recommendation, history, profile statistics, and provider AI token/cost analytics.
- Resume an in-progress interview after a page refresh and allow a student to exit an unfinished session.
- Start independent **Role-Based** interviews that rotate through the subjects relevant to a job role, or independent **Custom Topics** interviews outside course restrictions.

## 4. Architecture and request flow

```text
React screens/hooks
  -> frontend/src/api.js (Fetch API)
       -> Flask /api blueprints
            -> validation + policies + lifecycle services
            -> OpenAI client (question, speech-to-text, evaluation)
            -> MySQL database helpers
            -> local avatar/audio storage
```

The Flask factory in `backend/app.py` registers all blueprints under `/api`, enables CORS for configured frontend origins, adds a request ID/error handlers, and limits upload size.

## 5. Frontend routes and responsibilities

| URL | Component | Responsibility |
| --- | --- | --- |
| `/dashboard` | `Dashboard` | Metrics, trends, recommended next interview |
| `/new-interview` | `SetupScreen` | Select round, topic, difficulty, and question count |
| `/interview` | `InterviewScreen` | Live timed voice/typed interview session |
| `/result` | `ResultScreen` | Show just-completed report |
| `/history`, `/history/:interviewId` | `History` | Paginated records and question/answer detail |
| `/analytics` | `AnalyticsDashboard` | AI provider request, token, and estimated-cost reporting |
| `/profile` | `Profile` | Student details, avatar, and summary statistics |

## 6. Important function calls

### Client-side flow

1. `App` starts by calling `getProfile()` and `getActiveInterview()`.
2. `SetupScreen.handleStart()` calls `getDailyUsage()`, `getProfile()`, and then `startInterview()`.
3. `InterviewScreen.askQuestion()` uses `useSpeech().speak()` and starts `useInterviewTimer` plus `useAnswerCapture`.
4. `useAnswerCapture` records audio and uses browser speech recognition when available. `transcribeAudio()` is used for the recorded audio path.
5. `useInterviewSubmission.handleSubmit()` calls `submitAnswer()`; the response either supplies the next question or signals completion.
6. At the end, the submission hook calls `endInterview()` and passes the final result to `ResultScreen`.
7. `useInterviewFocusTracking` calls `recordFocusEvent()` when the tab/window is left or restored. `useExitGuard` calls `exitInterview()` if the candidate exits early.

### Backend flow

| Function/module | Responsibility |
| --- | --- |
| `routes.interviews.start_interview()` | Validates setup, checks student/quota/active session, generates and stores first question |
| `routes.answers.transcribe()` | Validates audio, stores it, and requests contextual transcription |
| `routes.answers.submit_answer()` | Saves answer, updates usage, then issues the next planned question |
| `routes.answers._issue_next_question()` | Selects a generated main question and persists it |
| `routes.interviews.end_interview()` | Batch-evaluates planned answers, runs final AI evaluation, stores scores, invalidates dashboard cache |
| `routes.interviews.exit_interview()` | Optionally saves current text, closes focus events, marks session `exited` |
| `ai.question_generation.generate_question()` | Produces a difficulty-appropriate question and topic area |
| `ai.answer_evaluation.evaluate_answers_batch()` | Produces per-answer verdicts, reasons, and ideal answers at completion |
| `ai.answer_evaluation.evaluate_interview()` | Produces final interview-level feedback and scores |
| `services.interview_state.active_interview_payload()` | Reconstructs a resumable active session |
| `services.focus_tracking.focus_summary()` | Calculates focus-loss count and total away time |
| `services.ai_usage.track_ai_usage()` | Captures provider tokens, latency, and estimated cost |
| `dashboard_logic.build_dashboard_payload()` | Converts completed interview data into dashboard charts/summary data |

## 7. REST API reference

Base URL: `http://localhost:5000/api` by default, overridden with `VITE_API_BASE_URL`.

| Method | Endpoint | Called by | Request body / query | Result |
| --- | --- | --- | --- | --- |
| `POST` | `/start_interview` | `startInterview` | `student_id`, `round_type`, `subject`, `difficulty`, `num_questions` | Creates/resumes a session and returns first question, quota, and session metadata |
| `GET` | `/daily_usage/:studentId` | `getDailyUsage` | None | Daily answered count, remaining count, and quota status |
| `GET` | `/active_interview/:studentId` | `getActiveInterview` | None | Active/recoverable session and current question, or `{ active: false }` |
| `POST` | `/transcribe` | `transcribeAudio` | `multipart/form-data`: `audio`; optional `interview_id`, `question_order` | Transcript; associates/stores answer audio when session metadata is supplied |
| `POST` | `/submit_answer` | `submitAnswer` | `interview_id`, `question_order`, `answer`, `time_taken_sec`, `timed_out` (and optional audio data/path as supported) | Saved-answer status plus next planned question or completion state |
| `POST` | `/end_interview` | `endInterview` | `interview_id` | Final scores, feedback, scorecard, question results, and integrity summary |
| `POST` | `/exit_interview` | `exitInterview` | `interview_id`, optional `question_order`, `answer`, `time_taken_sec` | Marks active session exited |
| `POST` | `/interviews/:id/focus-events` | `recordFocusEvent` | `event_uuid`, `action` (`left`/`returned`), and `source` for `left` | Idempotently opens or closes a focus-loss event |
| `GET` | `/dashboard/:studentId` | `getDashboard` | None | Interview summary, trend, recommendation, weak subjects, recent interview |
| `GET` | `/history/:studentId` | `getHistory` | `page`, `limit` | Completed interview list with pagination and integrity summary |
| `GET` | `/history/detail/:interviewId` | `getHistoryDetail` | None | Interview record, Q&A entries, scorecard, and focus summary |
| `GET` | `/profile/:studentId` | `getProfile` | None | Student information and interview statistics |
| `PUT` | `/profile/:studentId` | `updateProfile` | Any of `name`, `email`, `phone`, `course_enrolled`, `target_role`, `bio`, `avatar_color` | Updated profile |
| `POST` | `/profile/:studentId/avatar` | `uploadProfileAvatar` | `multipart/form-data`: `avatar` | Updated profile with normalized WebP avatar URL |
| `DELETE` | `/profile/:studentId/avatar` | `removeProfileAvatar` | None | Updated profile without avatar |
| `GET` | `/uploads/avatars/:filename` | browser asset request | None | Stored avatar file |
| `GET` | `/uploads/audio/:filename` | browser audio request | None | Stored answer recording |
| `GET` | `/analytics/summary` | `getAnalyticsSummary` | `student_id` plus optional filters | Aggregate AI provider usage/cost |
| `GET` | `/analytics/daily` | `getAnalyticsDaily` | `student_id` plus optional filters | Daily AI usage/cost series |
| `GET` | `/analytics/monthly` | `getAnalyticsMonthly` | `student_id` plus optional filters | Monthly AI usage/cost series |
| `GET` | `/analytics/interviews` | `getAnalyticsInterviews` | `student_id`, filters, pagination | AI usage by interview |
| `GET` | `/analytics/questions` | `getAnalyticsQuestions` | `student_id`, filters, pagination | AI usage by question |
| `GET` | `/analytics/recent` | `getAnalyticsRecent` | `student_id`, filters, pagination | Latest tracked AI requests |
| `GET` | `/analytics/token-breakdown` | `getAnalyticsTokenBreakdown` | `student_id` plus optional filters | Prompt/completion/total token breakdown |

All JSON responses are processed through `readJsonResponse()` in `frontend/src/api.js`. Non-2xx responses, or a returned `error` without `done`, become JavaScript errors that include `X-Request-ID` when present.

## 8. Key request examples

### Start an interview

```json
POST /api/start_interview
{
  "student_id": 1,
  "round_type": "technical",
  "subject": "react",
  "difficulty": "intermediate",
  "num_questions": 5
}
```

### Submit an answer

```json
POST /api/submit_answer
{
  "interview_id": 42,
  "question_order": 1,
  "answer": "React hooks let function components use state and effects...",
  "time_taken_sec": 58,
  "timed_out": false
}
```

### Record a focus-loss event

```json
POST /api/interviews/42/focus-events
{
  "event_uuid": "2f1fe937-bf29-43da-bd19-8454ac1130ea",
  "action": "left",
  "source": "visibility"
}
```

## 9. Database design

| Table | Purpose |
| --- | --- |
| `students` | Student identity, profile fields, avatar settings |
| `interviews` | Session configuration, status, final scores, and feedback |
| `interview_details` | Ordered questions, answer text/audio, timing, verdict, and ideal answer |
| `interview_focus_events` | UUID-idempotent tab/window focus-loss episodes |
| `daily_usage` | Per-student answered-question count by date |
| `ai_usage_records` | Provider, model, tokens, cost estimate, request type, and latency |
| `schema_migrations` | Records applied incremental schema migrations |

Relationships: one student has many interviews; one interview has many `interview_details`, `interview_focus_events`, and AI usage records. Foreign keys enforce the main relationships, while a unique `(interview_id, question_order)` constraint preserves question order.

### Role-based interview data

Role sessions store `interview_mode`, `role_name`, and `resolved_subjects` on `interviews`; each question stores `subject_tag`. Preset roles use the maintained mapping in `backend/services/role_interviews.py`. Custom roles use one LLM decomposition request to resolve three to six relevant subjects. Planned questions rotate across those subjects. The final report derives a deterministic Strong/Weak subject breakdown from stored verdicts and may launch a separate `weak_topic_practice` mini-session. Existing historical follow-up rows remain readable.

## 10. Validation, limits, and error handling

- Round type is `technical` or `hr`; difficulty is `beginner`, `intermediate`, or `advanced`.
- Supported planned interview lengths are 5 or 10 questions.
- Subject input is limited to 150 characters; answer text is limited to 20,000 characters.
- Audio uploads default to 10 MB and must use an allowed audio MIME type.
- Avatar uploads default to 3 MB; JPG/JPEG, PNG, and WebP are validated, fit to 512 x 512, and stored as WebP.
- The daily limit is 10 answered questions; its enforcement is controlled by `DAILY_LIMIT_ENABLED`.
- Invalid data returns validation errors; unavailable AI operations return retry-friendly errors where applicable.
- The backend creates structured logs and exposes `X-Request-ID` so a frontend error can be traced to a server request.

## 11. Configuration and local commands

Backend environment variables include `OPENAI_API_KEY`, `OPENAI_MODEL`, MySQL connection settings, `ALLOWED_ORIGINS`, `MAX_AUDIO_UPLOAD_MB`, `MAX_AVATAR_UPLOAD_MB`, `DAILY_LIMIT_ENABLED`, and optional upload directory overrides. The frontend can set `VITE_API_BASE_URL`.

```powershell
# Backend
cd backend
pip install -r requirements.txt
python app.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Quality commands:

```powershell
cd frontend
npm run test
npm run lint
npm run build

cd ..\backend
python -m unittest discover -s tests
```

## 12. Project structure

```text
frontend/src/
  api.js                    # All HTTP client functions
  components/               # Screens and reusable UI components
  hooks/                    # Timer, capture, submission, exit guard
  useSpeech.js              # Browser speech / recording integration
  useInterviewFocusTracking.js
  test/                     # Vitest component and hook tests

backend/
  app.py                    # Flask application factory
  routes/                   # API endpoints grouped by domain
  ai/                       # Question/evaluation/transcription logic
  services/                 # Lifecycle, media, focus, AI-usage services
  db.py                     # MySQL connection and persistence helpers
  schema.sql, migrations/   # Database definition and upgrades
  tests/                    # Backend tests
```

## 13. Daily AI session log

Use this section as a chronological record of work completed with AI assistance. Add each new entry directly below the **Log template** so the newest update appears first. Keep entries factual: record what changed, what was verified, and any remaining limitations.

### Log template

```markdown
### YYYY-MM-DD - Short task title

- **Goal:** What you wanted to achieve.
- **Work completed:** Main implementation or investigation performed.
- **Files changed:** Important files added or updated.
- **Verification:** Tests, lint, build, or manual checks performed and their result.
- **Result:** Completed, in progress, blocked, or needs review.
- **Notes / next steps:** Known limitation, follow-up task, or decision needed.
```

### 2026-08-10 - Documentation and AI session-log format

- **Goal:** Add a clear, reusable daily AI work-history format to the module documentation.
- **Work completed:** Added this `Daily AI session log` section, a copy-and-fill template, and instructions for keeping the newest entry first.
- **Files changed:** `MODULE_DOCUMENTATION.md`.
- **Verification:** Reviewed the existing technical documentation structure and confirmed the new section is placed after the project structure reference.
- **Result:** Completed.
- **Notes / next steps:** Add one new entry for each day or meaningful development session. Include test results and unresolved items so the log remains useful for review and handover.

### 2026-08-07 - Interview reliability refactor and analytics dashboard

- **Goal:** Improve interview-screen maintainability, verify timer-expiry behavior, and add AI usage analytics.
- **Work completed:** Split interview responsibilities into hooks/presentational components; added timer-expiry and duplicate-submission test coverage; added provider usage capture, usage-record schema/migration, analytics REST endpoints, and the `/analytics` dashboard screen.
- **Files changed:** `frontend/src/components/InterviewScreen.jsx`, `frontend/src/hooks/`, `frontend/src/components/interview/`, `frontend/src/components/AnalyticsDashboard.jsx`, `frontend/src/api.js`, `backend/services/ai_usage.py`, `backend/routes/analytics.py`, `backend/ai/chat_client.py`, database schema/migration files, and related tests.
- **Verification:** Frontend lint passed; frontend production build passed; frontend test suite passed with 27 tests.
- **Result:** Completed for the current development environment.
- **Notes / next steps:** Run the backend migration before deployment. Backend tests could not be executed in the workspace because no Python interpreter was available. Replace the demo `STUDENT_ID` pattern with authenticated server-side identity before multi-user production deployment.
