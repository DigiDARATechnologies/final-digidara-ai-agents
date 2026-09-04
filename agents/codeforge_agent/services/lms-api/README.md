# CodeForge application API

This private Flask service owns standalone CodeForge account, catalog, submission, progress, and tutor data in MySQL. Judge0 remains isolated on its own PostgreSQL and Redis services.

## Local setup

Keep real settings in ignored `.env.local`; `.env.example` contains only safe placeholders. Production must use a least-privilege MySQL account instead of `root`.

```powershell
cd E:\leetcode\services\lms-api
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\migrate.py up
.\.venv\Scripts\python.exe scripts\seed.py
.\.venv\Scripts\python.exe scripts\verify.py
.\.venv\Scripts\python.exe run.py
```

The service listens at `http://127.0.0.1:4000`. `GET /health` checks database and Judge0 connectivity. The web server calls it with a short-lived HMAC signature and, for protected operations, an opaque student session token. Browser code never receives database or service credentials.

Start Judge0 before using run/submit evaluation:

```powershell
cd E:\leetcode\judge0
docker compose up -d db redis server worker
curl.exe http://127.0.0.1:2358/about
```

Author evaluated problems in `lms_api/problem_catalog.py`. Put each test case in the `tests` list as `("stdin\n", "expected stdout\n", is_hidden, score_weight)`. Public tests are used by `/api/coding/problems/<id>/run`; public plus hidden tests are used by `/api/coding/problems/<id>/submit`. Run `scripts/seed.py` after catalog edits so the cases are written to MySQL.

## Production

Deploy this service privately, connect to managed MySQL over TLS, inject all secrets from a secret manager, restrict ingress to the web service, rotate development credentials, add account/evaluation rate limits, and monitor API, database, tutor, and Judge0 health.
