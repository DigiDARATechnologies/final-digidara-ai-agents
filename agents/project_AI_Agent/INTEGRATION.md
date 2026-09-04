# Strategy F integration

The shared React application at the repository root is the Capstone UI. This
service exposes the common agent contract at `POST /api/invoke`.

On startup it reads `manifest.json`, registers with the orchestrator, and
starts a heartbeat loop. On shutdown it deregisters. The browser sends JSON
and multipart requests to port 8100; the orchestrator resolves this service
from the healthy registry and forwards each request. The browser does not call
port 8000 directly.

## Start order

Start MySQL first, then run:

```bash
# agents/orchestrator
uvicorn app.main:app --reload --port 8100

# agents/project_AI_Agent
uvicorn app.api.main:app --reload --port 8000

# repository root
npm run dev
```

Set `AGENT_PUBLIC_URL` to an address reachable by the orchestrator. The
default `127.0.0.1` endpoint works only when both Python services share a host
outside separate containers.
