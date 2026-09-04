# certificate_agent Integration (Strategy F)

This document describes how `certificate_agent` integrates with the DigiDARA multi-agent architecture via **Strategy F** (REST + Registry + Gateway).

---

## 1. Overview

- **Agent Name**: `certificate_agent`
- **Version**: `v1.0.0`
- **Default Port**: `8008`
- **Invocation Endpoint**: `/api/invoke`
- **Framework**: FastAPI + MySQL

The React frontend calls `certificate_agent` exclusively through the orchestrator gateway at:
```text
POST /gateway/agents/certificate_agent/invoke
```

---

## 2. Dispatcher Architecture

`certificate_agent` uses **Test-Client Re-entry** via `httpx.AsyncClient` against FastAPI's ASGI transport in `cert_app/api/invoke.py`.

### Why Test-Client Re-Entry?
1. Existing FastAPI routes under `/api/auth`, `/api/exam`, `/api/certificate`, and `/api/chat` utilize Pydantic schemas, URL path parameters, and FastAPI `Depends(get_current_user)` authentication.
2. In-process test-client re-entry delegates gateway actions directly to internal routes by setting `Authorization: Bearer <token>` from the payload without duplicating route validation or handler logic.

### Canonical Identity Bridge (`ensure_profile`)
- Action: `ensure_profile`
- Payload: `{ "user_id": "...", "name": "...", "email": "..." }`
- Behavior: Lazily registers or updates a user record in the MySQL `users` table for DigiDARA dev mode logins and returns a JWT `token` / `sessionToken`.

### Binary Response Handling (`download_certificate`)
- When `action == "download_certificate"` or the internal response contains `media_type="application/pdf"`, `/api/invoke` returns a raw PDF stream with `Content-Disposition`, allowing the gateway to forward binary certificate files byte-for-byte to the frontend.

---

## 3. Supported Invoke Actions

| Action | HTTP Method & Target Path | Payload Parameters |
|---|---|---|
| `health` | Static Handler | `{}` |
| `ensure_profile` | Identity Bridge | `{user_id, name, email}` |
| `me` | `GET /api/auth/me` | `{sessionToken}` |
| `start_exam` | `POST /api/exam/start` | `{sessionToken, topic}` |
| `submit_exam` | `POST /api/exam/submit` | `{sessionToken, exam_id, answers}` |
| `get_history` | `GET /api/exam/history` | `{sessionToken}` |
| `get_leaderboard` | `GET /api/exam/leaderboard` | `{topic?}` |
| `get_exam_detail` | `GET /api/exam/{exam_id}` | `{sessionToken, exam_id}` |
| `get_chat_session_questions` | `GET /api/exam/chat-session/{session_id}/questions` | `{sessionToken, session_id}` |
| `get_my_certificates` | `GET /api/certificate/my-certificates` | `{sessionToken}` |
| `download_certificate` | `GET /api/certificate/download/{cert_id}` | `{sessionToken, cert_id}` (Returns PDF binary) |
| `interpret_certificate_request` | `POST /api/certificate/interpret` | `{sessionToken, message, context?}` — LLM-backed natural-language certificate concierge |
| `update_certificate_recipient` | `POST /api/certificate/{cert_id}/recipient` | `{sessionToken, cert_id, recipient_name}` — regenerates one owned certificate after confirmation |
| `request_certificate_email_verification` | `POST /api/certificate/{cert_id}/email` | `{sessionToken, cert_id, email}` — sends a short-lived verification code to the requested inbox |
| `verify_certificate_email` | `POST /api/certificate/{cert_id}/email/verify` | `{sessionToken, cert_id, email, code}` — verifies the code, then sends the owned PDF |
| `start_chat` | `POST /api/chat/start` | `{sessionToken, topic}` |
| `send_chat_message` | `POST /api/chat/message` | `{sessionToken, session_id, message}` |
| `get_chat_sessions` | `GET /api/chat/sessions` | `{sessionToken}` |
| `get_chat_session` | `GET /api/chat/session/{session_id}` | `{sessionToken, session_id}` |
| `recover_chat_certificate` | `POST /api/chat/session/{session_id}/certificate` | `{sessionToken, session_id}` — retrieves or issues the certificate for a previously passed chat exam |

---

## 4. Startup & Environment Setup

Copy `.env.example` to `.env` inside `agents/certificate_agent/`:
```env
ORCHESTRATOR_URL=http://127.0.0.1:8100
AGENT_PUBLIC_URL=http://127.0.0.1:8008/api/invoke
HEARTBEAT_INTERVAL_SECONDS=30
AGENT_SHARED_SECRET=dev-only-agent-shared-secret
```

To run the agent manually:
```powershell
cd agents/certificate_agent
python run.py
```

For certificate email delivery, add your SMTP provider values to the agent's
`.env` file: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
`SMTP_FROM`, and `SMTP_USE_TLS`. Email delivery remains unavailable until
`SMTP_HOST` and `SMTP_FROM` are configured.

Certificate delivery is protected by a six-digit, one-time email verification
code. Codes expire after 10 minutes and permit five verification attempts.

Upon boot, the agent self-registers with the orchestrator at `http://127.0.0.1:8100/registry/register` and sends heartbeats every 30 seconds.
