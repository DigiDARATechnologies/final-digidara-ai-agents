# Resume Builder Strategy F integration

The Resume Builder runs independently on port `5010`, registers as
`resume_builder_agent@v1.0.0`, and is reached from the shared UI only through
`POST /gateway/agents/resume_builder_agent/invoke`.

At startup the Flask app reads `manifest.json`, registers with the
orchestrator, starts one daemon heartbeat thread, re-registers on a `404`
heartbeat response, and best-effort deregisters at process exit. Set
`AGENT_PUBLIC_URL` to an address reachable by the orchestrator; do not use
`127.0.0.1` across Docker containers.

## Invoke actions

| Action | Existing internal route |
|---|---|
| `health` | Adapter-only; no DB or AI call |
| `ensure_profile` | Existing `users` model lookup/create bridge |
| `create_resume`, `get_resumes`, `get_resume`, `update_resume`, `delete_resume` | `/api/resumes` and `/api/resumes/{resume_id}` |
| `analyze_upload`, `create_import_draft` | `/api/resumes/import/analyze`, `/api/resumes/import/draft` |
| `analyze_resume` | `/api/resumes/{resume_id}/ats` |
| `generate_resume` | `/api/ai/optimize-resume` |
| `generate_summary`, `generate_bullets`, `generate_project_bullets`, `improve_bullet`, `suggest_skills`, `analyze_job_description`, `generate_declaration`, `tailor_to_job` | Corresponding `/api/ai/*` endpoint |
| `select_template` | `PUT /api/resumes/{resume_id}` |
| `list_templates`, `get_template` | `/api/templates` and `/api/templates/{template_id}` |
| `preview_resume`, `export_pdf` | `/api/resumes/preview`, `/api/resumes/{resume_id}/download` |

The adapter uses `current_app.test_client()` to call those routes in-process.
It retains their validation, ownership checking, extractors, ATS scorer, AI
services, and ReportLab PDF implementation. Multipart `analyze_upload`
forwards the original Flask file stream/name/type; PDF response body,
`Content-Type`, and `Content-Disposition` remain unchanged.

## Identity and security

In development/staging, each invoke payload contains `user_id`; the adapter
uses it only when `ALLOW_DEV_USER_HEADER=true` and the process is not in
production. The existing routes then enforce resume ownership. Production
operations currently fail closed with `401` because the generic gateway does
not yet issue a signed identity assertion. This prevents raw browser identity
impersonation; add a verified gateway-to-agent assertion before enabling it.

## Configuration and local verification

Required backend settings: `ORCHESTRATOR_URL`, `AGENT_PUBLIC_URL`,
`AGENT_NAME`, `AGENT_VERSION`, `HEARTBEAT_INTERVAL_SECONDS`, and
`ALLOW_DEV_USER_HEADER=true` for local integration. The shared frontend also
needs `VITE_GATEWAY_API_URL` and `VITE_RESUME_BUILDER_AGENT_NAME`.

```powershell
$body = @{ action = "health"; payload = @{} } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8100/gateway/agents/resume_builder_agent/invoke" -Method Post -ContentType "application/json" -Body $body
```

```bash
curl -X POST http://127.0.0.1:8100/gateway/agents/resume_builder_agent/invoke \
  -H 'Content-Type: application/json' -d '{"action":"health","payload":{}}'
```
