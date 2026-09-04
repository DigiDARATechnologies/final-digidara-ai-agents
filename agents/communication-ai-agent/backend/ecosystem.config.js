// PM2 process definition for the Communication Coach Agent. Real config
// (DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY, AGENT_SHARED_SECRET,
// OPENAI_API_KEY/GROQ_API_KEY, ...) lives in this directory's own .env,
// loaded by python-dotenv. SECRET_KEY/JWT_SECRET_KEY have no fallback —
// create_app() in app/__init__.py refuses to boot without real values.
module.exports = {
  apps: [{
    name: "digidara-communication-agent",
    cwd: "/www/wwwroot/digidaraaiagents/agents/communication-ai-agent/backend",
    script: ".venv/bin/gunicorn",
    args: "-w 4 -b 127.0.0.1:5001 run:app",
    interpreter: "none",
    env: { PORT: 5001 },
  }],
};
