# DigiDARA environment and run workflow

This is the shortest reliable path for running the complete platform on
Windows. Docker is recommended because it starts the frontend, MySQL,
orchestrator, all eight agents/workers, and Judge0 together.

## 1. How the application is connected

```text
Browser (http://localhost:5173)
  -> Orchestrator / gateway (port 8100)
       -> agent registry (heartbeats + shared-secret signatures)
       -> Capstone, CodeForge, Communication, Aptitude,
          Resume Builder, Certificate, and Job agents
             -> MySQL (one database per service)
       -> Judge0 for code execution
```

The browser never calls an agent directly. It calls the orchestrator, which
looks up a healthy registered agent and forwards the request.

## 2. Where every `.env` file belongs

Do not put every variable in the root `.env`. Each process loads the file next
to that process.

| File | Used by | Put here |
|---|---|---|
| `.env` | Root Vite frontend and Docker Compose interpolation | Only `VITE_*` browser settings |
| `docker/mysql/.env` | MySQL container | `MYSQL_ROOT_PASSWORD` |
| `agents/orchestrator/.env` | API gateway, auth, billing, registry | Database URL, JWT/shared secrets, OAuth, Razorpay |
| `agents/project_AI_Agent/.env` | Capstone agent | Database, LLM key/model, registry URLs |
| `agents/codeforge_agent/services/lms-api/.env` | CodeForge agent | MySQL, Judge0, optional OpenAI, registry URLs |
| `agents/communication-ai-agent/backend/.env` | Communication agent | Database, OpenAI/Groq, Flask/JWT, registry URLs |
| `agents/aptitude_agent/.env` | Aptitude agent | Database, OpenAI, app/JWT secrets, registry URLs |
| `agents/resume_builder_agent/backend/.env` | Resume Builder agent | Database, AI provider, Flask secret, registry URLs |
| `agents/certificate_agent/.env` | Certificate agent | Database, OpenAI, app secret, optional SMTP, registry URLs |
| `agents/job_agent/.env` | Job API and worker | Database, scraper/worker settings, optional Apify, registry URLs |

The separate `agents/resume_builder_agent/frontend/.env` is only for running
that agent's standalone frontend. It is not used by the root DigiDARA UI.

Anything beginning with `VITE_` is compiled into browser JavaScript and must be
treated as public. Never put an API secret, database password, Razorpay secret,
or OAuth client secret in a `VITE_*` variable.

## 3. Create the files safely

From the repository root:

```powershell
npm run setup:env
```

The command copies every `.env.example` to the corresponding `.env`. It skips
files that already exist, so it will not overwrite credentials. All real
`.env` files are ignored by Git.

## 4. Fill the required values

1. Set a strong `MYSQL_ROOT_PASSWORD` in `docker/mysql/.env`.
2. Replace `change-me` (or the equivalent placeholder) in every database URL,
   `MYSQL_PASSWORD`, or `DB_PASSWORD` with that exact MySQL password.
3. Generate one long random `AGENT_SHARED_SECRET`, then put the exact same
   value in the orchestrator and every agent `.env`.
4. Generate independent application secrets for `JWT_SECRET`, `SECRET_KEY`,
   and `JWT_SECRET_KEY`. Do not reuse the shared agent secret for these.
5. Add the API key for the provider each agent uses. OpenAI is the default in
   most templates; Communication and Resume Builder can use another listed
   provider.
6. Optional integrations belong in the service that owns them:
   Google OAuth and Razorpay in `agents/orchestrator/.env`, SMTP in the
   Certificate file, and Apify in the Job file.

Generate a secret in PowerShell (run once for each independent secret):

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

For Docker, keep hostnames such as `mysql`, `orchestrator`, and
`capstone-agent` exactly as shown in the templates. `localhost` inside a
container means that same container, not another service.

## 5. Start and verify the full platform

Prerequisites: Docker Desktop with Compose v2 and enough memory for MySQL,
Judge0, and the Python services.

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Open <http://localhost:5173>. Initial image builds can take several minutes.
Only the frontend is published to the host in the Docker stack. Check the
orchestrator and registry from inside its container:

```powershell
docker compose exec orchestrator python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/health').read().decode())"
docker compose exec orchestrator python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/registry/agents?healthy_only=true').read().decode())"
```

If a container is unhealthy or an agent is absent from the registry:

```powershell
docker compose logs --tail 200 orchestrator
docker compose logs --tail 200 <service-name>
```

The usual causes are a database password mismatch, a different
`AGENT_SHARED_SECRET`, a placeholder required secret, or a Docker URL changed
to `localhost`.

## 6. Normal development loop

- Frontend-only change in Docker: run
  `docker compose up -d --build frontend`.
- To use `npm run dev` on the host, also run the orchestrator natively or
  explicitly publish its port; the Docker Compose service is internal-only.
- Backend change: rebuild only that service with
  `docker compose up -d --build <service-name>`.
- Inspect a service with `docker compose logs -f <service-name>`.
- Stop without deleting data: `docker compose down`.
- `docker compose down -v` deletes database volumes and should only be used
  when a full data reset is intended.

Useful Compose service names are `orchestrator`, `capstone-agent`,
`codeforge-agent`, `communication-agent`, `aptitude-agent`,
`resume-builder-agent`, `certificate-agent`, `job-agent`, and `job-worker`.

## 7. Quality checks before committing

```powershell
npm run lint
npm run typecheck
npm run test:ci
npm run build
```

For Python checks and the full per-agent suite, see `LOCAL_SETUP.md` and
`CI_CD_SETUP.md`.

## 8. Native mode

Use native mode only when you need Python breakpoints or per-service reload.
It requires local MySQL, one virtual environment per Python service, and one
terminal per service. In every backend `.env`, change Docker names to host
addresses: `mysql` becomes `127.0.0.1`, `orchestrator` becomes
`127.0.0.1:8100`, and each `AGENT_PUBLIC_URL` must use that agent's local
port. The complete terminal commands are in `LOCAL_SETUP.md` under Path B.
