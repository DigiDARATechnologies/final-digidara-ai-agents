# Project AI Agent — Capstone Automation Backend

LangGraph-driven backend for the DigiDARA capstone project flow: eligibility
check → topic generation → requirement expansion → 7-day timer → submission
validation (docx + zip) → LLM code review → scored feedback.

## LLM provider — pluggable, not hardcoded

The app never imports a vendor SDK directly. Every LLM call goes through
`app/llm/client.py`, which uses [`litellm`](https://github.com/BerriAI/litellm)
to talk to whichever provider you point it at. Switch providers by changing
one line in `.env`:

```
LLM_MODEL=gpt-4o-mini                    # OpenAI (default)
LLM_MODEL=openai/gpt-4o                  # ChatGPT/OpenAI
LLM_MODEL=anthropic/claude-opus-5       # Claude
LLM_MODEL=groq/llama-3.3-70b-versatile   # Groq
LLM_MODEL=ollama/llama3.1                # local Ollama, no API key needed
```

Set only the matching API key env var (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` /
`GROQ_API_KEY`). No code change is needed to switch models.

**Screenshots are handled via OCR, not vision models.** The `OutputVerificationNode`
and `StructureValidationNode` never see raw images — `app/ocr/extractor.py`
extracts embedded screenshots from the submitted `.docx` and runs them through
Tesseract OCR, then hands the LLM the extracted text. This keeps the whole
pipeline working on text-only models (Groq's fast models, local Ollama, etc.),
not just vision-capable ones.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

**OCR requires the Tesseract binary** (not just the `pytesseract` pip package).
Install it separately:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- macOS: `brew install tesseract`
- Linux: `apt install tesseract-ocr`

If Tesseract isn't installed, the app still runs — screenshot *presence* is
still detected, but OCR text extraction is skipped with a warning noted in the
validation output.

```bash
copy .env.example .env          # then fill in your LLM_MODEL + API key + DATABASE_URL
```

Start MySQL first and make sure the database in `DATABASE_URL` exists (e.g.
`CREATE DATABASE capstone_agent;`) — `scripts.init_db` creates the tables but
not the schema itself.

```bash
python -m scripts.init_db
python -m scripts.seed_demo_data
uvicorn app.api.main:app --reload
python -m scripts.add_student --name "Ravi Kumar" --phone "+919876543210" --course "Python for Data Automation"
```

API docs: http://127.0.0.1:8000/docs

## Flow / endpoints

| Step | Endpoint | Notes |
|---|---|---|
| 1. Check eligibility + generate topics | `POST /api/eligibility/check` | `{name, phone, course_name}` → `thread_id` + 2 topic options (if eligible) |
| 2. Choose a topic | `POST /api/topic/choose` | `{thread_id, topic_id}` → expanded requirements brief |
| 3. Confirm & start the 7-day timer | `POST /api/timer/confirm` | `{thread_id}` → `deadline_at` + submission guide |
| 4. Upload submission | `POST /api/submission/upload` | multipart form: `thread_id`, `docx_file`, `zip_file` → score/feedback or revision notes |
| Poll progress | `GET /api/status/{thread_id}` | current stage + status |

State between steps is persisted by LangGraph's MySQL checkpointer
([`langgraph-checkpoint-mysql`](https://github.com/tjni/langgraph-checkpoint-mysql),
same `DATABASE_URL` as the app tables), keyed by `thread_id` — the server can
restart between steps (including across the 7-day submission window) without
losing progress.

## What's implemented vs. out of scope

**Implemented:** the full LangGraph pipeline (all 13 nodes from the spec),
provider-agnostic LLM calls, sandboxed zip ingestion (path-traversal /
zip-bomb / password-protection guards), OCR-based screenshot validation,
server-side 7-day deadline enforcement, and the FastAPI surface driving it.

**Not implemented (flagged, not silently skipped):** the Part 1 frontend UI,
an admin/enrollment-management API (use `scripts/seed_demo_data.py` or insert
rows directly for now), and the resubmission-without-clock-reset policy
(currently: a revision-needed submission can simply be re-uploaded any time
before the deadline — no separate "one free retry" bookkeeping).
