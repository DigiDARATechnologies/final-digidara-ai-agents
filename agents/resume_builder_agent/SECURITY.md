# Security Guide

## Implemented safeguards

- Resume ownership is derived from a signed HTTP-only browser session; cross-user access returns a non-enumerating 404.
- Cookie-authenticated mutations require a per-session CSRF token.
- The legacy `X-User-Id` development path is disabled by default and gated to tests or explicit local configuration.
- Startup requires a non-default `SECRET_KEY`; using the local `dev-secret-key` fallback requires `DEV_MODE_INSECURE_DEFAULTS=true`.
- User IDs, template IDs, statuses, strings, lists, AI prompts, and section sizes are validated and bounded.
- Uploads are limited to 5 MB and checked by extension, declared MIME type, content validity, DOCX file count, streamed uncompressed archive size, and XML entity expansion protection.
- API requests are capped at 6 MB.
- CORS uses an explicit origin allow-list.
- Expensive AI, import, preview, ATS, and export endpoints have per-user sliding-window rate limits.
- Responses include `X-Content-Type-Options`, same-origin framing, referrer, permissions, CSP, and no-store headers.
- PDF filenames are sanitized and PDFs contain selectable text.
- Real `.env` files, logs, caches, virtual environments, build output, and generated resumes are excluded from the release package.
- Optional AI SDK failure does not prevent the main application from starting.
- CI runs `pip-audit -r backend/requirements.txt` and `npm audit --production --audit-level=high`; local releases should run the same commands before packaging.

## Required before public deployment

1. Add OAuth/OIDC if named accounts, multi-device access, password recovery, or team sharing are required.
2. Replace the in-process limiter with gateway- or Redis-backed rate limiting when running multiple workers.
3. Set a randomly generated 64-character `SECRET_KEY`; never use `DEV_MODE_INSECURE_DEFAULTS=true` outside a local throwaway environment.
4. Restrict `FRONTEND_ORIGINS` to the deployed HTTPS frontend.
5. Store API and database secrets in a managed secret service.
6. Use a production WSGI server and reverse proxy; do not expose the Flask development server.
7. Enable database backups, reviewed migrations, monitoring, dependency scanning, and centralized audit logs.
8. Run malware scanning if uploaded documents are retained or shared outside the request lifecycle.
9. Run legacy `.doc` conversion in a separate low-privilege, network-isolated container or worker. The app now uses an isolated LibreOffice profile with macro security set to very high, but LibreOffice does not provide a universally reliable command-line guarantee that every macro-capable document format will never execute active content; production deployment must isolate this conversion step from the main app process.

Never commit `.env` or paste production API keys into frontend environment variables.
