# ResumeForge AI

ResumeForge AI is a full-stack resume workspace built with React, Flask, SQLAlchemy, and ReportLab. It provides structured resume editing, import review, practical ATS scoring, optional AI writing help, four distinct templates, and selectable-text PDF export.

## What is included

- Premium responsive home, dashboard, editor, review, and template-gallery UI
- Exactly four templates: Precision ATS, Heritage Serif, Modern Halo, and Executive Slate
- One canonical ReportLab rendering engine for both live preview and download
- A4 pagination with selectable, ATS-readable PDF text
- Resume creation, editing, duplication, archive, restore, import, and deletion
- PDF, DOCX, DOC, and TXT import validation with size and archive safety limits
- ATS section, keyword, impact, and job-description checks
- Resume-level ATS history, average dashboard score, and PDF export counters
- Groq or Anthropic integration for AI writing help, and rule-based ATS scoring (resume + job description) that runs independently of the AI provider
- SQLite quick-start configuration and optional MySQL support
- Server-issued secure guest sessions, CSRF protection, endpoint rate limits, CORS allow-list, input bounds, and security headers
- Debounced autosave with one database-backed source of truth for preview and export

## Quick start on Windows

Install Python 3.10 or newer and Node.js 20 or newer. Then double-click:

```text
start_windows.bat
```

The script creates the virtual environment, installs dependencies, copies safe development environment files, starts both servers, and opens `http://localhost:5173`.

## Manual setup

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -r requirements.txt
python run.py
```

Frontend in a second terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Backend health check: `http://localhost:5000/api/health`

## Configuration

The default example uses a local SQLite database so the project runs without MySQL. To use MySQL, remove `DATABASE_URL` from `backend/.env` and configure `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`.

AI configuration is required for the AI writing endpoints (`/ai/generate-bullets`, `/ai/generate-project-bullets`,
`/ai/improve-bullet`, `/ai/tailor-to-jd`, `/ai/generate-summary`). Set exactly one provider:

```text
AI_PROVIDER=groq
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.1-8b-instant
```

or:

```text
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=your_model
```

There is no local/offline fallback. If `AI_PROVIDER` is unset, set to `local`, or the configured provider's API key/model
is missing or invalid, the AI writing endpoints return a `500` error describing exactly what is misconfigured (e.g.
`GROQ_API_KEY is not configured`, `Groq API authentication failed: ...`) instead of silently substituting a
template-based response. ATS scoring (`/import-resume/analyze` and `/resumes/<id>/ats`) is unaffected by this setting -
it is a deterministic, rule-based scorer that analyzes the uploaded resume against the job description directly and
does not call an AI provider at all.

`/ai/optimize-resume` generates a fully AI-optimized resume in one call (summary plus bullets for every experience and
project entry that has enough raw input), reusing the same prompt rules and truthfulness constraints as the
single-field AI endpoints above. It backs the "Apply ATS Fixes" button in the resume builder - that button now calls
real AI on your actual resume content instead of the placeholder "Data Analyst" text it used to insert.

### OCR for scanned resumes

Uploaded PDFs with little or no selectable text (e.g. a scanned resume) are now run through OCR instead of being
rejected outright, using `pytesseract` and `pdf2image`. This requires the `tesseract-ocr` and `poppler-utils` system
packages to be installed on the server (`apt-get install tesseract-ocr poppler-utils` on Debian/Ubuntu). If those
system packages aren't installed, OCR is skipped automatically and the original "no extractable text" error is
returned - no crash, no missing dependency error surfaced to the end user.

## Exact preview and PDF behavior

The editor sends the current resume draft to `/api/resumes/preview`. That endpoint uses the same ReportLab service as `/api/resumes/<id>/download`. The preview and downloaded document therefore share the same template, typography, spacing, page breaks, and section order. The old canvas screenshot export was removed because it produced image-only PDFs and inconsistent pagination.

## Four templates

| Template | Layout | Best use |
| --- | --- | --- |
| Precision ATS | Single column | Data, engineering, and technical applications |
| Heritage Serif | Single column | Business, consulting, and formal roles |
| Modern Halo | Single column | Product, sales, and customer-facing roles |
| Executive Slate | Two column | Management, leadership, and communication roles |

## Additional contemporary templates

The template gallery also includes ten original contemporary layouts: Timeline Teal (`timeline-teal`), Sidebar Mono (`sidebar-mono`), Horizon Coral (`horizon-coral`), Ledger Navy (`ledger-navy`), Split Olive (`split-olive`), Canvas Sand (`canvas-sand`), Column Indigo (`column-indigo`), Arc Slate (`arc-slate`), Pulse Rose (`pulse-rose`), and Signal Amber (`signal-amber`).

## Verification

```powershell
cd backend
python -m pytest -q tests

cd ..\frontend
npm run build
```

## Production notes

The standalone application now derives ownership from a signed, HTTP-only browser session and protects mutations with CSRF tokens. `X-User-Id` is disabled by default and exists only as an explicitly gated local/test integration option. For named accounts, multi-device access, or teams, connect OAuth/OIDC and derive the user identity from the verified server-side token.

Keep `.env` files private, set `FLASK_ENV=production`, generate a strong `SECRET_KEY`, configure explicit `FRONTEND_ORIGINS`, use HTTPS, and run database migrations and backups. See `SECURITY.md` for the full checklist.

For multi-worker or multi-instance deployments, set `REDIS_URL` to enable a shared Redis-backed sliding-window rate limiter. Legacy `.doc` import is optional and requires `LIBREOFFICE_BINARY` to be an absolute path to a trusted LibreOffice binary; the app never searches `PATH` for a converter.

## ATS score interpretation

The displayed result is a transparent, deterministic compatibility estimate across contact data, section coverage, summary quality, skills, experience evidence, supporting sections, and readability. A pasted job description adds a separate weighted keyword-coverage score. No resume builder can reproduce every employer's proprietary ATS ranking, so the result is presented as guidance rather than a guarantee.
