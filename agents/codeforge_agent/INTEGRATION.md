# Strategy F integration

The shared React application at the repository root is the DigiDARA UI. This
service exposes the common agent contract at `POST /api/invoke`, the same
contract `agents/project_AI_Agent` uses.

Unlike that agent, every *existing* route on this service (`/api/auth/*`,
`/api/coding/*`) requires an HMAC-signed request envelope
(`X-CodeForge-Timestamp/Request-Id/Signature/Session` headers) — that
requirement is untouched. `/api/invoke` is an additive, separate surface: it
skips that envelope (the orchestrator gateway only forwards `Content-Type`
and the raw body, never signs anything) and instead requires an unguessable,
revocable, expiring `sessionToken` inside the JSON `payload`, obtained once
via the `ensure_session` action and validated against `student_sessions` on
every other call — the same real check `require_student` already performs,
just carried in the body instead of a header.

On startup (`create_app()` in `lms_api/app.py`) it registers with the
orchestrator and starts a heartbeat loop on a background thread
(`integration/registry_client.py`). On process exit it best-effort
deregisters via `atexit`.

## Start order

Start MySQL first (with a `leetcode` database created and migrated/seeded —
see below), then run:

```bash
# agents/orchestrator
uvicorn app.main:app --reload --port 8100

# agents/codeforge_agent/services/lms-api
python run.py

# repository root
npm run dev
```

## Database setup (first time only)

```bash
cd agents/codeforge_agent/services/lms-api
python scripts/migrate.py up
python scripts/seed.py
```

(`scripts/verify.py` has a stale hardcoded problem/test-case count from an
earlier, smaller catalog — it will report a mismatch even on a correctly
seeded database. Query the tables directly if you want to sanity-check:
`SELECT COUNT(*) FROM coding_problems` etc.)

## Judge0 (code execution) — requires Docker

`run_problem`/`submit_problem` depend on a running Judge0. Without it they
correctly return `503 evaluator_unavailable` — that's the honest expected
state until you run:

```bash
cd agents/codeforge_agent/judge0
docker compose up -d db redis server worker
curl http://127.0.0.1:2358/about   # confirm it's reachable
```

The AI Tutor's deterministic fallback and everything else (identity bridge,
course/technology/topic/problem browsing, dashboard) works without Docker.

## Verification

```powershell
# Both agents show up healthy
Invoke-RestMethod "http://127.0.0.1:8100/registry/agents?healthy_only=true"

# Gateway-forwarded health check
$body = @{ action = "health"; payload = @{} } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/gateway/agents/codeforge_agent/invoke" `
  -Method Post -ContentType "application/json" -Body $body
```

Expected: `{"status":"ok","agent_name":"codeforge_agent"}`.
