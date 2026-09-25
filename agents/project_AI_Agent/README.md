# Project AI Agent — Capstone Automation Backend

LangGraph-driven backend for the DigiDARA capstone project flow: topic
generation → requirement expansion → 7-day timer → submission validation
(docx + zip) → LLM code review → scored feedback. There is no certificate or
enrollment gate — any student can request a project for any topic.

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

**The submission is a `.docx` report plus a `.zip`.** The report has exactly three
sections (Problem Statement, Approach, Conclusion) and carries no code and no
images -- nothing is OCR'd out of it. The zip holds the source code AND an
`output_screenshots` folder: the project's output screenshots are image files in
the zip, one per item the submission guide lists (each with an exact file name, the
module it shows, what must be visible and how to capture it). The pipeline then:

0. Counts the screenshots (`app/ingestion/screenshots.py`): only real, readable
   images inside a `*screenshot*` folder count. Fewer than the guide requires sends
   the submission back with the exact list. The images are OCR'd (Tesseract) and the
   text is evidence for the requirements review; the model never sees raw images.
1. `SyntaxCheckNode` (`app/ingestion/syntax_check.py`) parses every Python, JSON and
   TOML file with a real parser. This is a fact, not an LLM opinion, so a syntax
   error sends the submission straight back — with the file, line, offending source
   line and message — before any scoring runs. JavaScript, Java, etc. are listed as
   "not machine-checked" and read line by line by the reviewer instead (parsing them
   reliably needs their own toolchain, and a wrong "syntax error" verdict must never
   fail a student).
2. `OutputVerificationNode` reads the **whole** codebase and gives a
   met / partial / not-met verdict, with evidence, for every functional requirement,
   plus a present / unclear / missing verdict for each required screenshot.
3. `CodeQualityScorerNode` reads the whole codebase against the same requirements
   and scores structure, syntax, maintainability and completeness.

The reviewers get all files in full while the zip fits `CODE_REVIEW_CHAR_BUDGET`
(default 160,000 characters); past that the largest files are trimmed fairly and
flagged as trimmed.

**Final report.** Once BOTH the code score and the viva are passed, the student can
download a PDF (`GET /api/submission/{id}/final-report.pdf`, or the gateway action
`download_final_report`, which returns it base64-encoded) with the score, the
per-requirement results, the code-quality breakdown, the viva questions and results,
and the reviewer feedback, with the DigiDARA Technologies logo on every page
(`app/reports/final_report.py`). It is rebuilt from the stored grading data, and
refused with 409 before both are passed.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

**OCR (only for a Q&A screenshot attachment) requires the Tesseract binary** (not
just the `pytesseract` pip package). Install it separately:
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
| 1. Generate topics for a topic/role/language | `POST /api/eligibility/free` | `{name, email, phone?, course_name, difficulty}` → `thread_id` + 2 topic options. No certificate/enrollment gate — `course_name` doubles as the free-text topic. |
| 2. Choose a topic | `POST /api/topic/choose` | `{thread_id, topic_id}` → expanded requirements brief |
| 3. Confirm & start the 7-day timer | `POST /api/timer/confirm` | `{thread_id}` → `deadline_at` + submission guide |
| 4. Upload submission | `POST /api/submission/upload` | multipart form: `thread_id`, `docx_file`, `zip_file` → score/feedback or revision notes |
| Poll progress | `GET /api/status/{thread_id}` | current stage + status |
| Download the project brief | `GET /api/assignment/{thread_id}/about.md` | raw Markdown: topic, requirements, required folder/report structure |
| Download the review report | `GET /api/submission/{submission_id}/review.md` | raw Markdown: full checklist-style review of one submission attempt |
| Troubleshoot a missing folder via screenshot | `POST /api/submission/{submission_id}/structure-screenshot` | multipart form: `image` — a screenshot of the student's file explorer / extracted zip / IDE tree, checked against whichever required folders/files that submission is still missing |
| Ask about your own project | `POST /api/qa/ask` | multipart form: `thread_id`, `question`, optional `attachment` (image or `.docx`) — a tool-calling agent answers using only that student's own topic/requirements/code/report/grading result, with web search available to verify a technical claim or current requirement |

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
