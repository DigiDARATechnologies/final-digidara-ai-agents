# DigiDARA Agent Integration Guide

A complete, repeatable, step-by-step runbook for adding a new agent to the
live DigiDARA fleet: scaffold → local run → Docker → Compose → CI/CD →
tests → security → (optional) frontend card → PR → merge → verify.

Every path, command, field name, and line reference below was read directly
out of this repo (`agent_template`, `docker-compose.yml`, `ci.yml`,
`scripts/test_agents.py`, `tests/agents/test_agent_health.py`,
`mypy.ini`, `ruff.toml`) — nothing here is generic boilerplate. If a file
changes shape after this guide was written, trust the file over this
document and update this guide to match.

If you only want to push an early/experimental agent's code into the repo
as a branch for later review — no runtime wiring yet — use
[`DigiDARA AI Agents — Agent Submission Guide.md`](<DigiDARA AI Agents — Agent Submission Guide.md>)
instead. This guide is the next step: actually plugging an agent into the
running platform.

---

## Quick checklist (for the 2nd, 3rd, 4th agent you add)

Once you've done this end-to-end once, this is the whole thing:

```
[ ] cp -r agents/agent_template agents/<name>
[ ] Write invoke() in main.py, fill manifest.json
[ ] Run locally with uvicorn, confirm it registers (orchestrator logs)
[ ] Add service block to docker-compose.yml
[ ] Add tuple to scripts/test_agents.py AGENTS (+ SUITES if you have a test dir)
[ ] Add entry to tests/agents/test_agent_health.py AGENTS
[ ] Add agent name to ci.yml: docker-build matrix, publish-ghcr matrix,
    "Compile Python services" list, "Create CI-only env files" directory list
[ ] Write unit tests for invoke()
[ ] Write security-relevant tests (identity trust, bad input)
[ ] Run: python scripts/test_agents.py --agent <name>
[ ] Run: security-review skill against the diff
[ ] (Optional) Add storefront card: src/data/agents.ts entry (+ kind wiring
    in App.tsx only if you need custom UX)
[ ] Write agents/<name>/README.md
[ ] Open PR, confirm CI green, get review, merge
[ ] After merge to main: confirm GHCR image published, confirm it comes up
    on next deploy (deploy.sh runs automatically per DEPLOYMENT.md)
```

Everything below is the detailed version of each line, with exact commands
and exact file diffs, plus a fully worked example.

---

## 0. Before you start

### 0.1 What you need installed

- Python 3.12 (matches CI: `actions/setup-python@v5` pins `3.12`)
- Docker Desktop, running, set to Linux containers
- Node.js 22 (only needed if you're also touching the frontend — §11)
- Access to run the orchestrator locally (its own `.env` — see
  [LOCAL_SETUP.md](LOCAL_SETUP.md) if you don't have one yet)

### 0.2 Ports already in use — pick a free one

| Service | Port |
|---|---|
| orchestrator | 8100 |
| capstone-agent | 8000 |
| codeforge-agent | 4000 |
| communication-agent | 5001 |
| aptitude-agent | 5000 |
| resume-builder-agent | 5010 |
| certificate-agent | 8008 |
| `agent_template` default | 8201 |
| frontend (published) | 5173 |

Pick something outside this list for your new agent (e.g. `8210`,
`8220`...). This port only matters for local/dev runs and the isolated CI
test harness — **Docker Compose does not publish agent ports to the host**
in the real stack (only `orchestrator` and `frontend` are reachable
directly; everything else talks over the Compose-internal network by
service name). Don't add a `ports:` mapping for your agent in
`docker-compose.yml` unless you have a specific reason to reach it directly
from the host.

### 0.3 Decide: generic chat agent, or dedicated storefront card?

- **Generic** (§1–§10 below, most agents should be this): register with the
  orchestrator, done. The user reaches you through free-text chat — the
  orchestrator's `POST /chat` builds an LLM tool spec from every healthy
  registry row (`app/orchestrator/tools.py`'s `build_tools()`) and calls
  your `/invoke` when the LLM decides your `description` matches the
  user's message. **Zero frontend changes required.**
- **Dedicated card** (§11, optional, more work): your own storefront tile,
  custom chat/dashboard UX, direct calls through
  `POST /gateway/agents/{agent_name}/invoke` bypassing the LLM router —
  like CodeForge's embedded IDE or Capstone's file upload flow. Only do
  this if plain chat genuinely can't express your agent's UX.

Read §1–§10 fully even if you're building a dedicated-card agent — all of
that infrastructure wiring still applies; §11 is additive, not a
replacement.

---

## 1. Scaffold the agent from the template

```bash
cd E:\final-digidara-ai-agents\digidara-agents\digidara-agents
cp -r agents/agent_template agents/<your_agent_name>
cd agents/<your_agent_name>
```

Use a `snake_case` directory/agent name matching your `manifest.json`'s
`agent_name` (see §2). This is the name you'll type, verbatim, into every
file in §5–§7 — pick it once, don't rename later without updating all of
them.

You now have:

```
agents/<your_agent_name>/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── agent_wrapper.py     # copy as-is, don't edit
├── main.py              # your invoke() logic goes here
├── manifest.json         # your agent's identity/description/schema
└── requirements.txt
```

**Do not edit `agent_wrapper.py`.** It is the shared contract every agent
uses to register/heartbeat/deregister and expose `/health` + `/invoke`. If
you think you need to change it, you're probably trying to do something
that belongs in your own `main.py`'s `invoke()` instead.

---

## 2. Fill in `manifest.json`

Open `agents/<your_agent_name>/manifest.json` (it currently has the
template's `echo_agent` example — replace all of it):

```json
{
  "agent_name": "<your_agent_name>",
  "version": "v1.0.0",
  "description": "<one clear sentence the orchestrator's LLM reads to decide whether to route a user's message here>",
  "owner": "<your name or team>",
  "plan_tier": "free",
  "host": "127.0.0.1",
  "port": <your chosen port, e.g. 8210>,
  "input_schema": {
    "type": "object",
    "properties": {
      "<field>": { "type": "string", "description": "<what it's for>" }
    },
    "required": ["<field>"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "<field>": { "type": "string" }
    }
  }
}
```

Field-by-field:

| Field | What it does | Notes |
|---|---|---|
| `agent_name` | Unique, stable identity | Literally the tool name the LLM router sees. Used again in §5–§7 as the CI/Compose service name (with `-` instead of `_` by repo convention — see the worked example in §12). |
| `version` | e.g. `v1.0.0` | Registry rows key on `(agent_name, version)` — bumping lets old/new coexist during a migration. |
| `description` | Routing signal | Be specific. A vague description causes the LLM to misroute unrelated messages to you, or never route relevant ones. |
| `input_schema` | JSON Schema, OpenAI function-calling shape | **Advisory only** — `agent_wrapper.py` does not enforce it. Still write it accurately; it's what the LLM uses to construct the call arguments. |
| `output_schema` | Documents your response shape | Optional but recommended. |
| `owner` | Free text | Your name/team, for `GET /registry/agents` listings. |
| `plan_tier` | `"free"` unless told otherwise | |
| `host` / `port` | Where you're reachable | Must match wherever you actually run the process — `127.0.0.1` for local dev; once containerized in Compose, this becomes the Compose service name (§6) and the container's internal port. |

---

## 3. Write `invoke()` — your agent's actual logic

Open `agents/<your_agent_name>/main.py`. The template's example:

```python
from pathlib import Path
from agent_wrapper import create_agent_app

def invoke(payload: dict) -> dict:
    text = payload.get("text", "")
    return {"echoed": text, "length": len(text)}

app = create_agent_app(Path(__file__).parent / "manifest.json", invoke)
```

Replace `invoke()` with your real logic. It can be sync or async, and can
call anything — a LangGraph graph, an LLM SDK, a plain function:

```python
def invoke(payload: dict) -> dict:
    # 1. Validate input yourself — input_schema is advisory, not enforced.
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("`text` is required and must be a non-empty string.")

    # 2. Read identity from the trusted header, never from the payload body,
    #    if your logic needs to know who's asking (see §9.3).
    user_id = payload.get("x_digidara_user_id")  # see the worked example in §12 for how this actually arrives

    # 3. Do the real work.
    result = my_langgraph_app.invoke({"input": text})

    # 4. Return a JSON-serializable dict matching output_schema.
    return {"answer": result["output"]}

app = create_agent_app(Path(__file__).parent / "manifest.json", invoke)
```

`agent_wrapper.py`'s `POST /invoke` route wraps your function in a
try/except and turns any uncaught exception into a `500` with your
agent_name in the log line — so an unhandled exception is safe (won't crash
the process), but the caller only sees a generic 500. Raise/return clear
errors yourself for anything you want the LLM or user to actually
understand (see §9.2).

Add whatever extra files you need (`graph.py`, `prompts.py`, a `services/`
package, etc.) — `main.py` just needs to end with `app = create_agent_app(...)`.

---

## 4. Add dependencies

Edit `agents/<your_agent_name>/requirements.txt`. It starts as:

```
fastapi==0.115.6
uvicorn[standard]==0.32.1
httpx==0.28.1
python-dotenv==1.0.1
gunicorn==23.0.0
```

Keep all five (the wrapper and Docker `CMD` depend on them). Add your own
**pinned** versions below — floating/unpinned versions make the CI
pip-audit/Trivy scan (§10) non-reproducible between your machine and CI:

```
langgraph==<pin>
openai==<pin>
# ...whatever your invoke() actually imports
```

Install locally:

```bash
cd agents/<your_agent_name>
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 5. Configure environment variables

Edit `agents/<your_agent_name>/.env.example` (empty/placeholder values
only — never real secrets):

```
# http://127.0.0.1:8100 only works when this agent runs directly on the
# host. Once wired into docker-compose.yml, this must point at the
# orchestrator's Compose service name instead.
ORCHESTRATOR_URL=http://orchestrator:8100
HEARTBEAT_INTERVAL_SECONDS=30

# Add your own, e.g.:
# OPENAI_API_KEY=
# MY_AGENT_SPECIFIC_SETTING=
```

Then create your real local `.env` (this file is `.gitignore`d by the
template — confirm it stays that way):

```bash
copy .env.example .env
```

Edit `.env` and set `ORCHESTRATOR_URL=http://127.0.0.1:8100` for a
directly-on-host run (not the Compose hostname yet), plus any real secret
values you need for local testing.

---

## 6. Run it locally and confirm registration

Make sure your local orchestrator is already running (see
[LOCAL_SETUP.md](LOCAL_SETUP.md)) — `agent_wrapper.py` needs
`ORCHESTRATOR_URL` reachable on boot to register.

```bash
cd agents/<your_agent_name>
uvicorn main:app --reload --port <your chosen port>
```

Confirm it worked — you should see, in your agent's own log output:

```
registered with orchestrator: <your_agent_name>@v1.0.0 -> http://127.0.0.1:<port>/invoke
```

And in the orchestrator's own log output, a `POST /registry/register`
`201`. If you instead see `could not reach orchestrator at ... to register`,
the agent still runs (answers `/invoke` directly) but is unreachable via
`/chat` until the next heartbeat succeeds — check `ORCHESTRATOR_URL` and
that the orchestrator is actually up.

Smoke-test directly:

```bash
curl http://127.0.0.1:<port>/health
# {"status":"ok","agent_name":"<your_agent_name>","version":"v1.0.0"}

curl -X POST http://127.0.0.1:<port>/invoke -H "Content-Type: application/json" -d "{\"text\":\"hello\"}"
# whatever your invoke() returns
```

Then confirm the orchestrator sees you as healthy (this call itself needs
an HMAC-signed request — easiest to just check orchestrator logs, or send
a real chat message through the running frontend that should route to your
agent and confirm it gets called).

---

## 7. Dockerize

The template's `Dockerfile` and `.dockerignore` are already correct for
most agents — check, don't blindly trust, these two things before moving
on:

1. **`EXPOSE`/`HEALTHCHECK`/`CMD` port** — the template hardcodes `8201`
   in three places (`EXPOSE 8201`, the `HEALTHCHECK` URL, and the `gunicorn
   -b 0.0.0.0:8201` in `CMD`). Update all three to your chosen port.
2. **`HEALTHCHECK start-period`** — the template default is
   `--interval=30s --timeout=5s --start-period=15s --retries=3`. If your
   agent has a slow cold start (large model load, heavy imports, DB
   migrations), widen `start-period` — a too-short value gets your
   container marked unhealthy during real deploys even though it would
   have become healthy shortly after (this exact bug hit the orchestrator
   itself; its `start-period` was widened from 15s to 60s after it showed
   up in production — see the file history of `agents/orchestrator/Dockerfile`
   for the reference fix). Size it to what your agent actually needs, not
   a copy-pasted guess.

Build and run it standalone to confirm the image itself is correct (not
just `uvicorn --reload` on your host):

```bash
cd agents/<your_agent_name>
docker build -t digidara-test/<your_agent_name>:local .
docker run --rm -p <port>:<port> --env-file .env digidara-test/<your_agent_name>:local
```

If your agent needs to reach the orchestrator from inside this standalone
container, `ORCHESTRATOR_URL` needs to resolve to something reachable from
inside a container (not `127.0.0.1` inside the container itself) —
`host.docker.internal` on Docker Desktop, or just move straight to the
full Compose stack in §8, which handles this via the shared network.

---

## 8. Wire into `docker-compose.yml`

Open [`docker-compose.yml`](docker-compose.yml) at the repo root. Add a new
service block, following the existing pattern exactly (compare to the
`resume-builder-agent` block already there):

```yaml
  <your-agent-name>:
    build:
      context: ./agents/<your_agent_name>
    restart: unless-stopped
    env_file:
      - ./agents/<your_agent_name>/.env
    depends_on:
      mysql:
        condition: service_healthy
      orchestrator:
        condition: service_healthy
```

- Use `<your-agent-name>` with **hyphens**, not underscores, for the
  Compose service key — that's the repo's convention
  (`resume-builder-agent`, `codeforge-agent`, etc.) even though the
  directory and `manifest.json`'s `agent_name` use underscores.
- Only depend on `mysql` if your agent actually has its own database. A
  simple LLM-wrapper agent with no persistence doesn't need it — drop that
  block if so.
- Do **not** add a `ports:` mapping (see §0.2) unless you have a specific
  reason to reach it directly from the host.
- In this agent's real `.env` (not `.env.example`), set
  `ORCHESTRATOR_URL=http://orchestrator:8100` — inside Compose's network,
  services resolve each other by service name, not `127.0.0.1`.

### 8.1 If your agent needs a new secret/config value that isn't per-agent

Check `app/gateway/routes.py`'s `ALLOWED_AGENT_HOSTS` — it defaults to
`127.0.0.1,localhost` in the orchestrator's own `.env` and gates every
gateway-proxied call (this exists so a tampered registration can't turn
the gateway into an SSRF proxy to an arbitrary host). Inside Compose, every
agent is reached by its Compose service hostname — if that's not already
covered by the default, the orchestrator's `.env`'s `ALLOWED_AGENT_HOSTS`
needs your service's hostname added, comma-separated.

### 8.2 Bring up the whole stack and verify

```bash
docker compose up -d --build
docker compose logs -f <your-agent-name>
```

Confirm the registration log line appears, then:

```bash
docker compose ps
```

Confirm your service shows `running`/`healthy` (once its `HEALTHCHECK`
passes).

---

## 9. Security requirements

Everything below is either enforced automatically or required for review to
pass. Work through this as a checklist for every new agent, not just once.

### 9.1 Service-to-service auth — already handled

Registration/heartbeat/deregister are HMAC-signed by `agent_wrapper.py`'s
`_sign_request()` against `AGENT_SHARED_SECRET`, verified by the
orchestrator's `require_service_signature`
(`agents/orchestrator/app/auth/service_auth.py`): timestamp + request-id +
method + path + body-hash, with a max-age window (`SIGNATURE_MAX_AGE_SECONDS`,
default 300s) and a replay guard. **You write none of this** as long as you
use `agent_wrapper.py` unmodified. Never hardcode a real
`AGENT_SHARED_SECRET` anywhere in code, comments, logs, or tests — it comes
from the environment only.

### 9.2 Validate your own input

`input_schema` in `manifest.json` is metadata for the LLM only —
`agent_wrapper.py`'s `/invoke` route does not check the body against it.
Inside `invoke()`:

- Check types and required fields yourself before touching them (Pydantic
  is already a dependency across this codebase if you want structured
  validation instead of manual checks).
- Reject clearly, with a message — don't let a `KeyError`/`TypeError`
  bubble up as an opaque 500.
- If you accept a file, path, or filename from the caller, treat it as
  hostile: no path traversal (`../`), no unbounded size, no executing it.

### 9.3 Identity — read it, never accept it from the payload

When the gateway forwards a real user's call to your agent, it sets an
`x-digidara-user-id` **header** derived from the caller's verified JWT — it
never trusts anything the browser put in the JSON body for identity. The
reference is `app/gateway/routes.py`'s `ensure_session` handling: it
overwrites any browser-supplied `user_id`/`name`/`email`/`mobile` in the
payload with the authenticated user's real profile before ever forwarding
it. Your agent must follow the same rule: if `invoke()` needs to know who's
calling, read it from the trusted header your framework exposes (FastAPI:
`request.headers.get("x-digidara-user-id")`), never from a `user_id` field
inside the JSON body — a payload field can be set to anything by whoever
crafts the request.

### 9.4 Billing / free actions

Every gateway call is billed in tokens (flat `TOKEN_COST_PER_CALL`, default
100, unless you report real usage — §9.5) unless its `action` is one of
`FREE_ACTIONS` in `app/gateway/routes.py`: `ensure_session`,
`usage_summary`, `list_courses`, `list_languages`, `ensure_profile`,
`get_thread_status`, `getThreadStatus`. If your agent has an equivalent
no-LLM bookkeeping action, note it in your PR description — adding to
`FREE_ACTIONS` is an orchestrator-level change, not something your own
agent code can do unilaterally.

### 9.5 Report real token usage (recommended, not required)

Return an `X-Tokens-Used` response header with your actual per-call cost
and the gateway bills that instead of the flat fallback. Reference
implementation: `agents/aptitude_agent/app/services/usage_service.py`.

### 9.6 Secrets — never commit them

- `.env` is real secrets, always `.gitignore`d — confirm your copied
  template's `.gitignore` still has it (§1's scaffold already includes
  this; don't remove it).
- `.env.example` is checked in — every value in it must be empty or an
  obviously-fake placeholder.
- If a real deployed secret is needed, that's an orchestrator-host `.env`
  / repo-secret concern for whoever manages `DEPLOY_HOST` (see
  `DEPLOYMENT.md`) — it never enters git.

### 9.7 Dependency and container scanning — CI-enforced

Once your agent is in the `docker-build` CI matrix (§10.3), every PR
touching it gets:

- **pip-audit** — runs `pip freeze` inside your built image, fails on any
  known vulnerability (`--strict`, no silent `--ignore-vuln`). Pin real
  versions in `requirements.txt` (§4); update promptly on a CVE.
- **Trivy** — scans the built image for HIGH/CRITICAL OS-package
  vulnerabilities with an available fix (`ignore-unfixed: true`), fails if
  any exist. Stay on `python:3.12-slim` (the repo convention) and avoid
  adding unnecessary OS packages in your `Dockerfile`.

If a dependency has a genuinely unfixable CVE (no upstream patch), do not
silently suppress it — follow the pattern already documented in
`CI_CD_SETUP.md` (a named `--ignore-vuln` with a comment explaining why,
reviewed periodically) and call it out explicitly in your PR description.

### 9.8 Run a security review before opening the PR

```
/security-review
```

or the `security-review` skill against your diff, before requesting human
review. It checks the OWASP top-10 classes relevant to what changed
(injection, auth bypass, SSRF, secret exposure, unsafe deserialization).

---

## 10. Wire into CI/CD — all seven places

A new agent must be added in **seven** exact places or it silently never
gets tested, scanned, type-compiled, or published. Do all seven in the same
PR.

### 10.1 `scripts/test_agents.py` — the `AGENTS` list

Open [`scripts/test_agents.py`](scripts/test_agents.py). Add a tuple to
`AGENTS` (around line 13):

```python
AGENTS = [
    ('orchestrator', 'agents/orchestrator', 8100, 'app.main:app', 'uvicorn.workers.UvicornWorker'),
    # ...existing entries...
    ('<your-agent-name>', 'agents/<your_agent_name>', <port>, 'main:app', 'uvicorn.workers.UvicornWorker'),
]
```

- `'main:app'` matches the template's `main.py` (`app = create_agent_app(...)`)
  — change it if your real entry point/module differs.
- `'uvicorn.workers.UvicornWorker'` is correct for a FastAPI/ASGI app
  (everything built from `agent_wrapper.py` is). Use `'sync'` only if your
  agent is a WSGI framework like Flask.

If you have a real test suite (§10.4 onward), also add it to `SUITES`
(around line 22):

```python
SUITES = {
    # ...existing entries...
    '<your-agent-name>': ['tests'],
}
```

If you skip this, `run_agent()` still runs the fleet-level health check
against your container, just prints `no existing unit/integration suite;
health check only` instead of running your own tests — you want `SUITES`
filled in once you have real tests.

### 10.2 `tests/agents/test_agent_health.py` — the `AGENTS` dict

Open [`tests/agents/test_agent_health.py`](tests/agents/test_agent_health.py).
Add an entry to the `AGENTS` dict (around line 13):

```python
AGENTS = {
    "orchestrator": (8100, None),
    # ...existing entries...
    "<your-agent-name>": (<port>, None),
}
```

Use `None` as the identity — the second tuple element is only non-`None`
for agents that implement the older `POST /api/invoke {"action": "health"}`
convention (`capstone-agent`, `codeforge-agent`, etc.). A template-based
agent exposes plain `GET /health` returning
`{"status": "ok", "agent_name": ..., "version": ...}`, and `check_health()`
already branches on `identity is None` to hit `/health` instead and skip
the `agent_name` match — this is exactly what `agent_wrapper.py` gives you,
no extra code needed on your side.

### 10.3 `.github/workflows/ci.yml` — `docker-build` matrix

Open [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Find the
`docker-build` job's matrix (around line 137–145):

```yaml
    strategy:
      fail-fast: false
      matrix:
        agent:
          - orchestrator
          - capstone-agent
          - codeforge-agent
          - communication-agent
          - aptitude-agent
          - resume-builder-agent
          - certificate-agent
          - <your-agent-name>          # add this line
```

This job builds your image, runs
`scripts/test_agents.py --agent <name> --skip-build` (using the context
path it looks up from `scripts/test_agents.py`'s `AGENTS` list — §10.1 must
be done first or this step fails to resolve your context), then pip-audit
+ Trivy scans it (§9.7).

### 10.4 `.github/workflows/ci.yml` — `publish-ghcr` matrix

Same file, the `publish-ghcr` job's matrix (around line 388–398) — the
**exact same list**, add your agent there too:

```yaml
    strategy:
      fail-fast: false
      matrix:
        agent:
          - orchestrator
          - capstone-agent
          - codeforge-agent
          - communication-agent
          - aptitude-agent
          - resume-builder-agent
          - certificate-agent
          - <your-agent-name>          # add this line
```

This job only runs on push to `main` (after `docker-build` and friends
pass) and pushes `ghcr.io/<owner>/digidara-<your-agent-name>:<sha>` and
`:latest`. Don't add here without also being in `docker-build` — this job
depends on the other jobs succeeding.

### 10.5 `.github/workflows/ci.yml` — "Compile Python services" step

Same file, inside the `python-quality` job (around line 96–105):

```yaml
      - name: Compile Python services
        run: |
          python -m compileall -q \
            agents/orchestrator \
            agents/project_AI_Agent \
            agents/codeforge_agent/services/lms-api \
            agents/communication-ai-agent/backend \
            agents/aptitude_agent \
            agents/resume_builder_agent/backend \
            agents/certificate_agent \
            agents/<your_agent_name>       # add this line (use the directory path, with underscores)
```

This just confirms every `.py` file in your agent parses — a cheap,
fast syntax check that runs on every PR regardless of Docker.

### 10.6 `.github/workflows/ci.yml` — "Create CI-only env files from examples" step

Same file, inside the `compose-validation` job (around line 114–124):

```yaml
      - name: Create CI-only env files from examples
        shell: bash
        run: |
          set -euo pipefail
          for directory in agents/orchestrator agents/project_AI_Agent agents/codeforge_agent/services/lms-api agents/communication-ai-agent/backend agents/aptitude_agent agents/resume_builder_agent/backend agents/certificate_agent agents/<your_agent_name> docker/mysql; do
            if [ -f "$directory/.env.example" ]; then
              cp "$directory/.env.example" "$directory/.env"
            else
              touch "$directory/.env"
            fi
          done
```

Add `agents/<your_agent_name>` into that `for directory in ...` list
(directory path with underscores, matching your actual folder). Without
this, `docker compose config --quiet` fails because your `env_file:`
reference in `docker-compose.yml` (§8) points at a file that doesn't exist
in the CI checkout.

### 10.7 mypy — usually nothing to do

`mypy.ini`'s `files = ...` is an explicit allowlist (currently just
`scripts/test_agents.py`, `scripts/test_e2e.py`,
`scripts/run_agent_suite.py`, and one Capstone file) — most existing agents
aren't in it either. **You don't need to add your agent here** unless the
team specifically wants strict typing enforced on it; if so, add your
agent's entry-point files to that `files =` list and expect to fix whatever
`mypy` then flags.

### 10.8 ruff — nothing to do

`ruff.toml`'s CI invocation is `ruff check agents scripts tests` — your new
`agents/<your_agent_name>/` directory is automatically included, no
wiring needed. It only checks for actual syntax/undefined-name errors
(`E9, F63, F7, F82`), not a style rewrite.

---

## 11. (Optional) Add a dedicated frontend storefront card

Skip this whole section if the generic LLM-routed chat path (§0.3) is
enough — most new agents should stop after §10.

If you need a dedicated card, custom chat flow, or dashboard:

### 11.1 Add the storefront entry

Open [`src/data/agents.ts`](src/data/agents.ts). Add an object to the
`AGENTS` array:

```ts
{
  id: "<short-kebab-id>", name: "<Display Name>", icon: "🔧", color: "#22c55e",
  author: "DigiDARA", rating: 4.8,
  category: ["<one or more from CATEGORIES at the top of this file>"], featured: false,
  backendAgentName: "<your_agent_name>",   // must exactly match manifest.json's agent_name
  desc: "<one-sentence card description>",
  greeting: "<first message shown when a user opens this agent's chat>",
},
```

`backendAgentName` is how `getAgentByBackendName()` and the usage/billing
lookups in `SettingsModal.tsx` find your agent — it must match
`manifest.json`'s `agent_name` character-for-character.

If plain chat turns through the generic path are enough, **stop here** —
you do not need a `kind`. Agents like `career-guide`, `research`, and
`content-writer` in that same file have no `kind`/`backendAgentName` at
all and just get canned/LLM-routed replies; adding `backendAgentName`
alone is already enough to let usage/billing display work for a
`backendAgentName`-bearing agent without a `kind`.

### 11.2 Only if you need custom UX: add a `kind`

Add your new kind to the union in [`src/types/index.ts`](src/types/index.ts):

```ts
kind?: "capstone" | "codeforge" | "aptitude" | "communication" | "resume-builder" | "certificate" | "<your-kind>";
```

Then, in `src/App.tsx`, find how an existing `kind` (e.g. `"communication"`)
branches the chat-send/dashboard logic and add a matching branch for yours.
Build a dedicated API client under `src/lib/` following the shape of
`communicationApi.ts` or `billingApi.ts` — a `fetch` wrapper against
`POST /gateway/agents/{agent_name}/invoke` with the signed-in user's bearer
token attached, and (if you need one) a dashboard component following
`CommunicationDashboard`/`AptitudeDashboard`/`ResumeBuilderDashboard`.

This is meaningfully more work than §11.1 alone — confirm you actually
need it before starting.

### 11.3 Frontend checks

```bash
npm run typecheck
npm run lint
npm run test:ci
npm run build
```

All four must pass — they're exactly what the `frontend` CI job runs.

---

## 12. Worked example, start to finish

A minimal but complete example: an agent called `faq_agent` that answers
from a hardcoded FAQ dict (swap the FAQ lookup for a real LLM/RAG call in
practice — the point here is the wiring, not the logic).

```bash
cp -r agents/agent_template agents/faq_agent
cd agents/faq_agent
```

`manifest.json`:

```json
{
  "agent_name": "faq_agent",
  "version": "v1.0.0",
  "description": "Answers frequently asked questions about DigiDARA's platform, pricing and agents.",
  "owner": "digidara-team",
  "plan_tier": "free",
  "host": "127.0.0.1",
  "port": 8210,
  "input_schema": {
    "type": "object",
    "properties": { "question": { "type": "string", "description": "The user's question" } },
    "required": ["question"]
  },
  "output_schema": {
    "type": "object",
    "properties": { "answer": { "type": "string" } }
  }
}
```

`main.py`:

```python
from pathlib import Path
from agent_wrapper import create_agent_app

_FAQ = {
    "pricing": "DigiDARA Free includes a starting token balance; DigiDARA Pro adds higher limits — see Settings > Billing.",
    "agents": "DigiDARA hosts specialized agents for coding practice, communication coaching, aptitude training, resumes and certificates.",
}

def invoke(payload: dict) -> dict:
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("`question` is required and must be a non-empty string.")
    key = next((k for k in _FAQ if k in question.lower()), None)
    answer = _FAQ.get(key, "I don't have an answer for that yet — try rephrasing, or contact support@digidaraaiagents.com.")
    return {"answer": answer}

app = create_agent_app(Path(__file__).parent / "manifest.json", invoke)
```

Dockerfile edits: change `8201` → `8210` in `EXPOSE`, `HEALTHCHECK`, and
`CMD`.

Local run + confirm registration:

```bash
copy .env.example .env
uvicorn main:app --reload --port 8210
curl http://127.0.0.1:8210/health
```

`docker-compose.yml` addition:

```yaml
  faq-agent:
    build:
      context: ./agents/faq_agent
    restart: unless-stopped
    env_file:
      - ./agents/faq_agent/.env
    depends_on:
      orchestrator:
        condition: service_healthy
```

(No `mysql` dependency — this agent has no database.)

`scripts/test_agents.py`:

```python
AGENTS = [
    ...
    ('faq-agent', 'agents/faq_agent', 8210, 'main:app', 'uvicorn.workers.UvicornWorker'),
]
```

`tests/agents/test_agent_health.py`:

```python
AGENTS = {
    ...
    "faq-agent": (8210, None),
}
```

`ci.yml` — add `faq-agent` to `docker-build`'s matrix, `publish-ghcr`'s
matrix, the `compileall` list (as `agents/faq_agent`, underscore form), and
the compose-validation env-file list (also `agents/faq_agent`).

Run the full local validation before opening a PR:

```bash
python scripts/test_agents.py --agent faq-agent
```

That's the entire loop. Repeat for the next agent.

---

## 13. Tests to write

### 13.1 Unit tests — `invoke()`

Create `agents/<your_agent_name>/tests/test_invoke.py` (or wherever the
sibling agent you're modeling after keeps its tests):

```python
from main import invoke

def test_happy_path():
    result = invoke({"question": "what's your pricing?"})
    assert "token balance" in result["answer"]

def test_missing_required_field_raises():
    import pytest
    with pytest.raises(ValueError):
        invoke({})

def test_empty_string_raises():
    import pytest
    with pytest.raises(ValueError):
        invoke({"question": "   "})

def test_unknown_question_gets_fallback():
    result = invoke({"question": "what is the meaning of life"})
    assert "contact support" in result["answer"]
```

Mock any external call (LLM provider, third-party API, your own DB) —
never let a unit test make a real network call.

### 13.2 Integration — over the wire

`scripts/test_agents.py --agent <your-agent-name>` (§10.1) builds your real
image, spins up an isolated MySQL (if you declared one) plus your
container, and runs whatever's in `SUITES[<name>]` against the live
process, then tears everything down. This *is* your integration layer —
don't hand-roll a separate one. Make sure `SUITES` points at a directory
that actually exercises `POST /invoke` over real HTTP at least once (not
just calling `invoke()` in-process) to catch serialization/routing bugs
unit tests can't see.

### 13.3 Security-relevant tests

```python
def test_does_not_trust_payload_user_id(monkeypatch):
    # If your invoke() ever reads identity, confirm it comes from the
    # trusted header path your framework exposes, never from a
    # client-suppliable "user_id" field inside the JSON body.
    ...

def test_rejects_oversized_input():
    huge = "x" * 10_000_000
    import pytest
    with pytest.raises(ValueError):
        invoke({"question": huge})
```

Tailor these to what your agent actually accepts — file uploads need a
path-traversal test, code execution needs a sandbox-escape test, etc. (see
§9.2–§9.3).

### 13.4 Fleet health check

Once §10.2 is done, this already runs for you:

```bash
python -m pytest tests/agents/test_agent_health.py -k "<your-agent-name>" -v
```

(only meaningful once your container is actually up — either run it
directly, or let `scripts/test_agents.py` orchestrate it.)

---

## 14. Full local validation before opening a PR

Run the same checks CI will run, locally, in this order:

```bash
# 1. Python syntax across the whole tree (matches ci.yml's Lint Python services)
python -m pip install -r requirements-quality.txt
python -m ruff check agents scripts tests

# 2. Your agent's own unit tests
cd agents/<your_agent_name> && python -m pytest tests -v && cd ../..

# 3. Full build + integration + fleet health check for your agent
python scripts/test_agents.py --agent <your-agent-name>

# 4. Compose file still parses
docker compose config --quiet

# 5. (only if you touched the frontend, §11)
npm run typecheck && npm run lint && npm run test:ci && npm run build

# 6. Security review
```

Then run `/security-review` (or the `security-review` skill) against your
diff.

---

## 15. PR checklist

- [ ] `agents/<your_agent_name>/` scaffolded from `agent_template`,
      `invoke()` has real logic, `manifest.json` fully filled in.
- [ ] `requirements.txt` has pinned versions for anything you added.
- [ ] `.env.example` present with empty/placeholder values; real `.env`
      confirmed **not** committed (`git status` / `git diff` review).
- [ ] `agents/<your_agent_name>/README.md` written: what it does, how to
      run it, required env vars, API shape.
- [ ] Added to `docker-compose.yml` (§8).
- [ ] Added to `scripts/test_agents.py`'s `AGENTS` (+ `SUITES` if you have
      tests) (§10.1).
- [ ] Added to `tests/agents/test_agent_health.py`'s `AGENTS` (§10.2).
- [ ] Added to `ci.yml`'s `docker-build` matrix (§10.3).
- [ ] Added to `ci.yml`'s `publish-ghcr` matrix (§10.4).
- [ ] Added to `ci.yml`'s `Compile Python services` step (§10.5).
- [ ] Added to `ci.yml`'s `Create CI-only env files from examples` step
      (§10.6).
- [ ] Unit tests written and passing locally (§13.1).
- [ ] Security-relevant tests written (identity trust, bad/oversized
      input, anything sandboxed) (§13.3).
- [ ] `python scripts/test_agents.py --agent <your-agent-name>` passes
      locally (§14).
- [ ] `docker compose config --quiet` passes (§14).
- [ ] `/security-review` run against the diff, findings addressed.
- [ ] If a dedicated frontend card was built (§11): `src/data/agents.ts`
      entry, `kind` wiring, Jest coverage, all four frontend checks pass.
- [ ] No secrets anywhere in the diff.

---

## 16. Open the PR and merge

```bash
git checkout -b feat/add-<your-agent-name>
git add agents/<your_agent_name> docker-compose.yml scripts/test_agents.py \
        tests/agents/test_agent_health.py .github/workflows/ci.yml
# + src/data/agents.ts, src/types/index.ts, src/App.tsx if §11 applies
git commit -m "Add <your-agent-name> agent"
git push -u origin feat/add-<your-agent-name>
gh pr create --base main --title "Add <your-agent-name> agent" --body "..."
```

Branch protection on `main`/`develop` requires at least one review and all
required CI checks green (per `DEPLOYMENT.md`) — there is no way around
this, and there shouldn't be.

---

## 17. After merge — verify it actually deployed

Per `DEPLOYMENT.md`: a push to `main` triggers, in order,
`publish-ghcr`/`publish-ghcr-frontend` (pushes
`ghcr.io/<owner>/digidara-<your-agent-name>:<sha>` and `:latest`), then
`deploy` — which SSHes into the deploy host and runs
`/opt/digidara-agents/deploy.sh` **automatically, with no manual approval
step**. Once your PR merges, it goes live on the next deploy run.

Confirm:

1. The `publish-ghcr` job for your agent succeeded (GitHub Actions tab).
2. On the next deploy, `docker compose ps` on the deploy host shows your
   service `running`/`healthy`.
3. Send a chat message through the production frontend that should route
   to your agent (generic path) or open its storefront card (§11 path) and
   confirm it actually answers.
4. Check `SLACK_WEBHOOK_URL` notifications (if configured) for any
   `notify-failure` message — it fires if any job on that `main` push
   failed.

---

## 18. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Agent never appears in `/chat` responses | Not registered, or heartbeat stale | Check agent's own logs for the `registered with orchestrator` line; check `ORCHESTRATOR_URL`; confirm the orchestrator is actually reachable from your agent's network context (host vs. Compose). |
| `could not reach orchestrator at ... to register` | Wrong `ORCHESTRATOR_URL` for the run context | `http://127.0.0.1:8100` only works running directly on the host; inside Compose it must be `http://orchestrator:8100`. |
| Gateway returns `403 Registered endpoint ... is not on an allowed host` | `ALLOWED_AGENT_HOSTS` doesn't include your agent's Compose hostname | Add it to the orchestrator's `.env` (§8.1). |
| `docker compose config --quiet` fails in CI only | Missing your agent's directory in the `compose-validation` job's env-file list | §10.6 — CI creates `.env` from `.env.example` per an explicit list; your directory must be in it. |
| CI's `docker-build` job can't find your agent's context | Missing/typo'd tuple in `scripts/test_agents.py`'s `AGENTS` | §10.1 — `ci.yml`'s "Resolve agent build context" step looks your context path up from that exact list. |
| Health check flaps `unhealthy` during real deploys but the agent is actually fine | `HEALTHCHECK start-period` too short for real cold start | Widen it (§7) — don't copy-paste another agent's value without checking your own startup time. |
| pip-audit/Trivy fails the build | A dependency has a known CVE | Update to a patched version; only suppress with `--ignore-vuln` + justification if genuinely unfixable (§9.7). |
| Your agent gets called for messages that have nothing to do with it, or never gets called for messages that should reach it | `manifest.json`'s `description` is too vague/broad, or too narrow | Rewrite it to be specific about what the agent does and doesn't handle. |
| A billed action of yours should have been free (or vice versa) | Your agent's `action` name isn't (or is) in `FREE_ACTIONS` | This is an orchestrator-level list (`app/gateway/routes.py`) — raise it in your PR, don't try to route around it from your own agent. |
