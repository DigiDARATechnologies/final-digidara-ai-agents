# Strategy F integration

The shared React application at the repository root is the DigiDARA UI. This
service exposes the common agent contract at `POST /api/invoke`, the same
contract `agents/project_AI_Agent` and `agents/codeforge_agent` use.

## Why a re-entry dispatcher instead of a hand-written action map

This agent's vendored Flask app (`backend/app/*`) has ~45 pre-existing
routes across 8 blueprints — `auth`, `dashboard`, `daily_challenges`,
`history`, `practice`, `pronunciation`, `speaking`, `writing`, `profile` —
roughly 4,000 lines of route logic. Every protected route reads
`request.get_json()` / `request.args` / `request.files` directly and is
guarded by `flask_jwt_extended`'s `@jwt_required()`, which reads the JWT
from the `Authorization` header. The orchestrator gateway forwards only
`Content-Type` and the raw request body — never an `Authorization` header,
never cookies — so none of that changes for `/api/invoke`.

Hand-porting every route into a parallel `action → payload-taking function`
map (the shape Capstone uses) would mean re-implementing that entire
surface a second time, by hand, with every risk of drifting from the real
routes over time. Instead, `backend/app/routes/invoke.py` re-enters the
app's *own* routes **unmodified** through an in-process test client
(`current_app.test_client()`), using a static `{action: (method, path)}`
map (`ACTION_MAP`). Every protected action carries an `authToken` inside
the JSON `payload`; the dispatcher pops it and attaches it as a normal
`Authorization: Bearer` header on the re-entered request, so
`@jwt_required()` sees exactly what it would from a real browser call. This
is the third dispatcher shape described in
[STRATEGY_F.md](../../STRATEGY_F.md#the-common-apiinvoke-contract) — pick it
whenever there are too many pre-existing routes to reasonably hand-port.

`{name}` segments in a path template (e.g. `/api/history/{session_id}`) are
popped from the payload to build the concrete path; everything left in the
payload becomes the query string (`GET`) or JSON body (`POST`/`PUT`/`DELETE`)
of the re-entered request.

## Identity bridge: `bridge_identity`

DigiDARA's dev-mode login only collects name + email — no password — but
every other route here needs a real JWT. `/api/auth/register` and
`/api/auth/login` both require a password, so the bridge doesn't call
either of them. Instead `bridge_identity` gets-or-creates a `users` row by
email directly (matching Capstone's identity-bridge pattern) with an
unusable, randomly-generated password hash — that account is only ever
reached through the bridge, never through `/api/auth/login` — and mints a
real JWT with `create_access_token(identity=str(user.id))`. Every
subsequent action carries that JWT as `authToken` in its payload.

## Known scope limitations

- **No live microphone capture in chat.** The original standalone frontend
  (`frontend/*`, not wired into the shared UI) uses the browser's Web
  Speech API to turn spoken audio into text before calling
  `/api/pronunciation/submit` (`recognised_text`) or
  `/api/speaking/respond` (`answer`) — both routes already expect *text*,
  not audio, so the shared chat UI's Pronunciation and Speaking loops
  accept typed text directly in place of a spoken transcript, exercising
  the exact same scoring backend. `/api/speaking/transcribe` (Whisper
  audio→text) and `/api/profile/photo` (multipart image upload) are the
  only routes that genuinely need a file upload; neither is wired into
  `ACTION_MAP` or the chat flow yet.
- **~35 secondary actions are backend-ready but not chat-wired.** Topic-list
  browsing (`writing_topics`/`speaking_topics`, useful once `topics` is
  seeded), `*_insights`, `pronunciation_streak`, the sentence-rewrite tool,
  `writing_hint`/`writing_tone`, and `writing_draft_save`/`_delete` are all
  in `manifest.json`'s action enum and `invoke.py`'s `ACTION_MAP`, reachable
  today via `/api/invoke`, but `src/lib/communicationFlow.ts` doesn't drive
  them yet. The chat flow instead lets the learner type a free-text custom
  topic (`topic_source: "custom"`) for Writing/Speaking, which works
  whether or not `topics` is seeded.
- **Pronunciation sessions never self-report `done: true` server-side.**
  `pronunciation.py`'s `submit_attempt` has its session-complete branch
  gated behind `if False and ...` in the vendored code — every submission
  returns a `next_item` regardless of `total_questions`. The chat flow
  relies on the learner explicitly choosing "End session"
  (`pronunciation_session_end`), which works today and always did.
- Rate limiting (`Flask-Limiter`, keyed by remote address) collapses to one
  shared bucket for all `/api/invoke`-forwarded traffic, since every
  re-entered request originates from the same in-process test client — the
  same known limitation documented in STRATEGY_F.md §6 for CodeForge.

## Start order

Start MySQL first (with a `communication_module` database created — see the
root README §6.3), then run:

```bash
# agents/orchestrator
uvicorn app.main:app --reload --port 8100

# agents/communication-ai-agent/backend
python run.py

# repository root
npm run dev
```

Set `AGENT_PUBLIC_URL` to an address reachable by the orchestrator. The
default `127.0.0.1` endpoint works only when both processes share a host
outside separate containers.

## Verification

```powershell
# Registered and healthy
Invoke-RestMethod "http://127.0.0.1:8100/registry/agents?healthy_only=true"

# Gateway-forwarded health check
$body = @{ action = "health"; payload = @{} } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/gateway/agents/communication_agent/invoke" `
  -Method Post -ContentType "application/json" -Body $body
# Expect: {"status":"ok","agent_name":"communication_agent"}
```

A full request path (bridge identity, then a protected action) without the
orchestrator in front, hitting the Flask app directly:

```powershell
$bridge = Invoke-RestMethod -Uri "http://127.0.0.1:5001/api/invoke" -Method Post -ContentType "application/json" `
  -Body (@{ action = "bridge_identity"; payload = @{ name = "Ada"; email = "ada@example.com" } } | ConvertTo-Json)

Invoke-RestMethod -Uri "http://127.0.0.1:5001/api/invoke" -Method Post -ContentType "application/json" `
  -Body (@{ action = "dashboard"; payload = @{ authToken = $bridge.authToken } } | ConvertTo-Json)
```
