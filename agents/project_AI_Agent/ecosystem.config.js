// PM2 process definition for the Capstone Project Agent. Real config
// (DATABASE_URL, OPENAI_API_KEY, AGENT_SHARED_SECRET, AGENT_PUBLIC_URL, ...)
// lives in this directory's own .env, loaded by python-dotenv.
module.exports = {
  apps: [{
    name: "digidara-capstone-agent",
    cwd: "/www/wwwroot/digidaraaiagents/agents/project_AI_Agent",
    script: ".venv/bin/gunicorn",
    args: "-k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000 app.api.main:app",
    interpreter: "none",
    env: { PORT: 8000, ENV: "production" },
  }],
};
