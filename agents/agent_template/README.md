# DigiDARA Agent Template — plug-and-run

This is the whole thing an agent developer needs to join the DigiDARA fleet
and be reachable from the orchestrator's `/chat` — no changes to the
orchestrator, no changes to any other agent.

## 3 steps

1. **Copy this folder**, rename it to your agent's name.
2. **Write your logic** in `invoke(payload: dict) -> dict` in `main.py` —
   call your own LangGraph graph, an LLM, a plain function, whatever. It can
   be sync or async.
3. **Fill `manifest.json`**:
   - `agent_name` — unique, stable identity (this is the "tool name" the
     orchestrator's LLM router sees — make it descriptive, e.g.
     `resume_builder`, not `agent7`).
   - `description` — what the orchestrator's LLM reads to decide whether to
     route a user's message to you. Be specific; vague descriptions cause
     misrouting.
   - `input_schema` — JSON Schema for what `invoke()` expects, same shape as
     OpenAI function-calling `parameters`.
   - `host` / `port` — where *your* service will actually be reachable.

Then:

```bash
pip install -r requirements.txt
copy .env.example .env      # point ORCHESTRATOR_URL at your running orchestrator
uvicorn main:app --reload --port <your port>
```

On boot, `agent_wrapper.py` POSTs your manifest to the orchestrator's
`/registry/register` and starts heartbeating. The orchestrator's very next
`/chat` call sees you and can route to you. On shutdown it deregisters.
Nothing else changes — not the orchestrator, not any other agent.

## What you are NOT responsible for

- Registering yourself with a database — `agent_wrapper.py` does it.
- Heartbeating — `agent_wrapper.py` does it on a background loop.
- Deregistering on crash — the orchestrator's heartbeat TTL filters out a
  dead agent within `HEARTBEAT_TTL_SECONDS` even if you never got the
  chance to deregister cleanly.

## What you ARE responsible for

- Your own `/invoke` logic being fast enough for a chat turn, or offloading
  slow work to a queue (see "Guardrails" in the architecture brief — one
  slow agent should never be allowed to block the whole fleet).
- Validating your own input inside `invoke()` — `input_schema` is advisory
  metadata for the router, not enforced by the wrapper.
