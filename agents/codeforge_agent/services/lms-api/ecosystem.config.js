// PM2 process definition for the CodeForge (LeetCode/DSA) Agent. Local dev
// runs this via `run.py` (waitress) — production uses gunicorn directly
// against the Flask app factory instead. Real config
// (MYSQL_*, LMS_API_SHARED_SECRET, AGENT_SHARED_SECRET, JUDGE0_URL, ...)
// lives in this directory's own .env, loaded by python-dotenv.
module.exports = {
  apps: [{
    name: "digidara-codeforge-agent",
    cwd: "/www/wwwroot/digidaraaiagents/agents/codeforge_agent/services/lms-api",
    script: ".venv/bin/gunicorn",
    args: "-w 4 -b 127.0.0.1:4000 'lms_api:create_app()'",
    interpreter: "none",
    env: { PORT: 4000 },
  }],
};
