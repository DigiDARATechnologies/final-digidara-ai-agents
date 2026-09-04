// PM2 process definition for the orchestrator. Deploy path assumes the
// standard DigiDARA VPS layout (/www/wwwroot/digidaraaiagents/...) — adjust
// `cwd` if that differs. Real secrets (JWT_SECRET, AGENT_SHARED_SECRET,
// DATABASE_URL, ALLOWED_ORIGINS, ...) live in this directory's own .env,
// loaded by python-dotenv — this file only sets what PM2 itself needs to
// know: the port and that this is a production run.
//
// Caveat: with 4 worker processes, both the per-user chat rate limit
// (app/rate_limit.py) and the registry service-auth replay guard
// (app/auth/service_auth.py's `_seen_request_ids`) are per-process, not
// shared — a client's requests can land on different workers, so the
// effective ceiling is up to ~4x the configured limit and an immediate
// replay can succeed if it happens to hit a different worker. The
// timestamp+signature freshness check on service auth is unaffected by
// this. Move to a shared store (e.g. Redis-backed slowapi storage_uri) if
// the exact configured limits need to be a hard ceiling under multiple
// workers; reducing to a single worker is the other option if throughput
// allows it.
module.exports = {
  apps: [{
    name: "digidara-orchestrator",
    cwd: "/www/wwwroot/digidaraaiagents/agents/orchestrator",
    script: ".venv/bin/gunicorn",
    args: "-k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8100 app.main:app",
    interpreter: "none",
    env: { PORT: 8100, ENV: "production" },
  }],
};
