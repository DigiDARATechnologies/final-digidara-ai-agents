# ResumeForge AI — Project & AI Session Log

> **Purpose:** This is the maintained technical memory for ResumeForge AI. It records the product scope, architecture, current capabilities, security posture, verification approach, known gaps, and AI-assisted work sessions. Update the newest session entry whenever significant work is completed.
>
> **Snapshot date:** 2026-08-11  
> **Repository branch at snapshot:** `Resume-builder`  
> **Source of truth:** implementation and configuration in this repository. This file intentionally distinguishes verified behavior from planned work.

## 1. Product overview

ResumeForge AI is a full-stack resume-building workspace. Users can create and maintain structured resumes, import existing resume documents, inspect ATS-readiness feedback, request optional AI writing assistance, choose a visual template, and export a selectable-text PDF.

The application is designed around a server-backed resume record: editing, previewing, analysis, and download should all operate from the same normalized data model. AI functionality is optional; deterministic local fallbacks keep the product usable if an external AI provider is not configured.

## 2. Technology and runtime

| Area | Implementation |
| --- | --- |
| Frontend | React 19, Vite 6, custom first-party history router |
| Backend | Flask 3, Flask-SQLAlchemy, Flask-CORS |
| Data | SQLite quick start; MySQL-compatible schema/configuration supported |
| PDF | ReportLab server-side renderer; pypdf for imported PDF text extraction |
| Import safety | `defusedxml`, ZIP-size/file-count checks, optional isolated LibreOffice conversion for `.doc` |
| AI providers | Groq or Anthropic; deterministic local mode/fallback |
| Tests | pytest backend suite; frontend production build; manual frontend cases |
| CI | GitHub Actions dependency audit using `pip-audit` and production `npm audit` |

### Local startup

The intended Windows entry point is `start_windows.bat`. It provisions Python/Node dependencies, prepares safe local environment files, starts backend and frontend services, and opens the Vite application. Manual startup commands and configuration examples are in `README.md`.

## 3. Architecture

```text
React/Vite browser client
  ├─ First-party route views: home, dashboard, resume builder
  ├─ API client adds credentials and CSRF token
  └─ Preview/download workflows use backend PDF renderer
             │
             ▼
Flask API
  ├─ Secure guest-session and CSRF endpoints
  ├─ Resume CRUD, import, ATS, preview, export, template endpoints
  ├─ Optional AI writing endpoints
  └─ Validation, rate limiting, security headers, ownership checks
             │
             ▼
SQLAlchemy persistence (SQLite/MySQL)
  ├─ Resume and normalized content sections
  └─ ATS analysis history and export metadata
```

The PDF preview endpoint and the download endpoint share the ReportLab renderer. This is an important design decision: preview is meant to match the exported document’s content, typography, page breaks, and section ordering, while retaining selectable text for ATS compatibility.

## 4. Main user workflows

1. **Start and browse** — landing page, dashboard, and resume workspace are rendered by the React application.
2. **Create or edit a resume** — users provide title, target role, contact details, summary, experience, education, skills, projects, certifications, publications, languages, achievements, and declaration data. The frontend uses debounced autosave.
3. **Manage records** — resumes can be listed, read, updated, duplicated, archived, restored, status-changed, or deleted, subject to owner context.
4. **Import and review** — TXT, PDF, DOCX, and optionally DOC files are validated, text is extracted, sections are parsed, ATS feedback is computed, and a draft can be created from the reviewed result.
5. **Improve content** — AI endpoints can generate experience/project bullets, summaries, skill suggestions, declaration text, job-description analysis, tailoring suggestions, and bullet improvements. If external AI is unavailable or configured as local, deterministic content helpers are used.
6. **Assess ATS readiness** — saved resumes and imports are scored for quality/readability; pasted job descriptions add skills, context, experience, education, and keyword coverage analysis. Results and recommendations are persisted for saved resumes.
7. **Choose a template and export** — a normalized resume is rendered into a ReportLab PDF for live preview and downloadable export. Export counters and timestamps are stored.

## 5. Backend API groups

The concrete route definitions live in `backend/app/routes/`.

| Group | Responsibilities |
| --- | --- |
| Session | Session bootstrap/info and session clearing; supplies CSRF context |
| Health | Backend readiness/health response |
| Resumes | CRUD, list/duplicate, archive/restore/status, templates, import review/draft creation, saved ATS analysis, preview PDF, and download |
| AI | Generate experience bullets, tailor a resume to a job description, project bullets, bullet improvements, skills, declaration, and summary; analyze job descriptions |

The resume service enforces input bounds, field cleaning, date parsing, template normalization, content serialization, completion calculation, and owner authorization. Import parsing and ATS scoring are implemented as backend services rather than browser-only logic.

## 6. Data model

The core `Resume` record is associated with a user identity and contains title, target role, template choice, lifecycle status, summary/declaration, ATS/export metadata, and timestamps.

Normalized related records include:

- `PersonalInfo` (one-to-one)
- `Education`, `Experience`, `Skill`, `Certification`, `Project`
- `Publication`, `Language`, `Achievement`
- `AtsAnalysis` history, including score, scoring version, job description, breakdown, detected requirements, recommendations, and creation time

The `backend/schema.sql` file describes the MySQL schema. SQLite is used by default for local development. The Flask app includes limited startup schema upgrades to ease local evolution; the security audit identifies reviewed migrations (such as Alembic) as the production-next-step.

## 7. Templates and PDF rendering

The current canonical template names exposed in product documentation are:

| ID | Display name | Layout | Intended audience |
| --- | --- | --- | --- |
| `steady-form` | Precision ATS | Single column | Data, engineering, technical roles |
| `classic-serif` | Heritage Serif | Single column | Consulting, business, formal roles |
| `mercury-flow` | Modern Halo | Single column | Product, sales, customer-facing roles |
| `slate-dawn` | Executive Slate | Two column | Leadership, management, communications |

Template normalization preserves compatibility with historic IDs through aliases. The rendering service contains the ReportLab implementation and also has legacy/helper rendering code. The active preview/download flow is explicitly described as ReportLab-based.

### Current catalog discrepancy — requires future reconciliation

At this snapshot, `README.md` and the frontend template metadata describe exactly four templates, but `backend/app/template_catalog.py` also contains four additional entries (`minimalist-line`, `sidebar-focus`, `compact-impact`, and `studio-bold`). The frontend component registry maps those additional IDs to existing component layouts. This file records the mismatch as observed; it does **not** claim the product is restricted to four templates until the backend catalog and client behavior are reconciled.

## 8. Security and privacy controls

Implemented safeguards documented in `SECURITY.md` and `SECURITY_AUDIT.md` include:

- Signed, HTTP-only guest session is authoritative for ownership; the browser cannot normally choose another user via `X-User-Id`.
- Stateful mutations require a server-issued CSRF token.
- CORS uses an explicit origin allow-list; security headers include content-type, framing, referrer, permissions, CSP, and no-store protections.
- User IDs, template IDs, request bodies, strings, lists, and AI prompts are validated and bounded.
- Rate limits protect AI, import, preview, ATS, and export endpoints. Redis can provide shared limiter storage in multi-worker deployments.
- Imports have a 5 MB file limit and inspect extension/MIME/content, DOCX archive file counts, streamed uncompressed size, and XML entity-expansion hazards.
- Legacy `.doc` conversion is optional, requires a configured trusted absolute LibreOffice path, and uses an isolated profile with high macro security. Production should isolate conversion in a low-privilege, network-isolated worker.
- PDF filenames are sanitized; output is selectable text rather than image/canvas-only PDFs.
- Secrets, logs, venvs, generated files, and environment files are excluded from release artifacts.

Before public deployment, the project still needs production identity/OAuth decisions, production WSGI/reverse proxy/HTTPS, managed secrets, database backups/migrations/monitoring, distributed rate limiting, and—if retained files are shared—malware scanning.

## 9. Verification and quality controls

Backend tests cover API behavior, AI routes, resume CRUD, import flows, PDF export, ATS scoring, and security-audit workflow. The documented verification sequence is:

```powershell
cd backend
python -m pytest -q tests

cd ..\frontend
npm run build
```

`frontend/MANUAL_TEST_CASES.md` also covers template switching after accepting AI content, mixed-language persistence, and multi-step validation behavior. CI checks Python and frontend production dependency vulnerabilities.

## 10. Repository status at this snapshot

Git history visible locally:

| Commit | Summary |
| --- | --- |
| `c62152b` | Merge remote `Resume-builder` branch |
| `53673eb` | Added Resume Builder project |
| `b8c0a20` | Add files via upload |

The working tree was already modified when this session began. Existing changes include backend route/security/import/PDF/template/test files, frontend shell/styles/template registry/assets, `README.md`, dependency files, database state, and untracked local helper/config/test artifacts. They are pre-existing user work and must not be overwritten or treated as part of this log-only session.

## 11. AI-assisted session entries

### 2026-08-11 — Project documentation baseline

**Request:** Create a comprehensive AI session file that captures project work and functionality in depth, including session logs.

**Actions completed:**

- Inspected the repository structure, primary project documentation, runtime configuration, schemas, backend route/service structure, frontend pages/components, tests, security audit, CI workflow, and recent Git history.
- Created this `AI_SESSION_LOG.md` as the durable project and AI-session record.
- Documented verified implementation capabilities, local run/test procedures, security design, current deployment caveats, and the observed backend/frontend template-catalog mismatch.

**Scope note:** Historical chat transcripts from sessions that are not present in the repository or this conversation cannot be reconstructed faithfully. This entry captures the current session and repository-visible project history. Add future sessions below this entry using the same format.

### 2026-08-11 — Flask startup reloader stabilization

**Request:** Fix a backend startup traceback that appeared after Flask reported `Restarting with stat`.

**Diagnosis:** `create_app()` completed successfully in 0.862 seconds and registered 36 routes. The traceback ended in `KeyboardInterrupt` while Flask/Werkzeug was compiling routes during the debug reloader restart; it was an interrupted process, not a malformed API route.

**Actions completed:**

- Updated `backend/run.py` so Flask’s reloader is disabled by default, preventing the second-process restart during ordinary Windows development startup.
- Added opt-in reloader support with `FLASK_RELOAD=true` (also accepts `1`, `yes`, or `on`) for developers who want automatic restarts.

**Verification:** `backend/.venv/Scripts/python.exe -c "import run"` completed successfully. `backend/.venv/Scripts/python.exe -m pytest -q tests/test_resumes_api.py` passed: 34 tests.

### 2026-08-11 — Contemporary template expansion

**Request:** Add ten original contemporary resume templates without changing the existing four templates, aliases, or resume schema.

**Actions completed:**

- Added Timeline Teal, Sidebar Mono, Horizon Coral, Ledger Navy, Split Olive, Canvas Sand, Column Indigo, Arc Slate, Pulse Rose, and Signal Amber.
- Registered each ID in the frontend metadata and component registry, backend catalog, shared PDF style specification, ReportLab profile, and HTML preview CSS.
- Added a catalog-wide regression test that renders a PDF directly for every registered backend template.

**Verification:** The requested PDF-export and resume-API suites passed with 49 tests. Every one of the 18 catalog IDs rendered valid PDF bytes. The frontend production build completed successfully.

### 2026-08-11 — Local preview and proxy recovery

**Request:** Fix preview `429` responses and Vite `/api/session` connection-refused errors.

**Actions completed:**

- Increased only the authenticated live-preview limit from 60 to 240 requests per minute and adjusted preview debounce from 650 ms to 900 ms.
- Updated the Windows launcher to use the repository’s existing `backend/.venv` consistently instead of creating/using a separate `backend/venv` environment.
- Started the local Flask backend and confirmed `GET http://127.0.0.1:5000/api/health` returns HTTP 200.

**Verification:** PDF export and resume API tests passed: 49 tests.

### Future session template

```markdown
### YYYY-MM-DD — Short session title

**Request:** What was asked.

**Actions completed:**

- Change or investigation.
- Files/components affected.

**Verification:** Commands, tests, or manual checks run and outcome.

**Decisions / follow-up:** Important trade-offs, known risks, or next work.
```

## 12. Suggested next maintenance actions

1. Reconcile the four-template product promise with the eight-entry backend catalog and registry aliases.
2. Run the backend test suite and frontend build after any further changes; append outcomes to the relevant session entry.
3. Add a dated entry for every substantive feature, bug fix, release, security change, or deployment decision.
4. Before production deployment, address the remaining decisions from `SECURITY_AUDIT.md`.
