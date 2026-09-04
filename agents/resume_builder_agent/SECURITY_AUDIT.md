# Security and Reliability Audit

## Resolved in this release

| Area | Original risk | Resolution |
| --- | --- | --- |
| Ownership | Public browser could choose any `X-User-Id` and impersonate another user. | Signed server session is now authoritative; the header fallback is disabled by default. |
| Cross-site requests | Cookie-backed mutations had no CSRF design. | Session bootstrap issues a CSRF token required on POST, PUT, PATCH, and DELETE. |
| Resource abuse | AI, import, PDF preview, export, and ATS analysis were unthrottled. | Per-user sliding-window limits protect expensive routes. |
| Upload consistency | TXT used browser scoring while PDF/DOCX used server parsing; Review expected a non-existent `text` field. | Every supported format now uses the validated server parser and one ATS engine. |
| Data consistency | Declaration appeared in preview state but was not stored, so download could differ. | Declaration is persisted in SQL and included in canonical serialization. |
| Analytics | ATS and export activity could not be measured reliably. | ATS score, job match, analysis time, export time, and export count are persisted. |
| Secrets and origins | Deployment depended on permissive development assumptions. | Production requires a secret; origins are allow-listed; safe environment examples contain no credentials. |
| Browser hardening | Baseline headers were incomplete. | CSP, frame, MIME, referrer, permissions, cross-origin resource, no-store, and production HSTS policies are set. |
| Secret key defaults | A missing or blank `FLASK_ENV` could silently use the insecure default Flask secret. | App startup now hard-fails without a non-default `SECRET_KEY` unless `DEV_MODE_INSECURE_DEFAULTS=true` is explicitly set; tests cover both paths. |
| DOCX XML parsing | DOCX XML used the standard library parser, allowing entity-expansion payloads to consume resources. | DOCX parsing now uses `defusedxml.ElementTree`; a crafted entity payload is rejected cleanly. |
| DOCX decompression limits | DOCX size enforcement trusted ZIP metadata before reading the real decompressed stream. | DOCX entries are streamed with a cumulative decompressed-byte limit; a regression test simulates understated `ZipInfo.file_size`. |
| Legacy DOC conversion | `.doc` conversion reused the default LibreOffice profile and did not document macro-execution isolation limits. | Conversion now uses an isolated per-call LibreOffice profile with macro security set to very high; production isolation remains required and documented. |
| Dependency scanning | Dependency audit checks were manual/absent and existing pins contained known vulnerabilities. | CI now runs `pip-audit` and `npm audit --production --audit-level=high`; current backend findings were fixed by upgrading Flask, flask-cors, cryptography, pypdf, python-dotenv, and pytest, and frontend audit reports 0 vulnerabilities. |
| Header authentication regression | Test mode implicitly trusted `X-User-Id`, risking drift from production behavior. | Header trust now requires explicit `ALLOW_DEV_USER_HEADER`; a non-testing regression test proves the header is ignored when unset. |

## Remaining production decisions

- Add OAuth/OIDC for named users, teams, multi-device continuity, or account recovery.
- Use Redis or an API gateway for rate limits across multiple WSGI workers.
- Adopt Alembic/Flask-Migrate for reviewed production migrations; startup column upgrades are for smooth local upgrades.
- Add managed backups, restore drills, centralized audit logs, and alerting.
- Add malware scanning if uploaded files will ever be retained, shared, or processed asynchronously.
- Run legacy `.doc` conversion in a low-privilege, network-isolated worker/container before accepting `.doc` uploads in production.
- Put Flask behind HTTPS and a production WSGI server; never expose the development server.

## ATS accuracy boundary

The score is a reproducible readiness estimate, not a reverse-engineered employer score. It evaluates explicit categories totaling 100 points and reports job-description coverage separately. This avoids presenting proprietary ATS behavior as a guarantee.
