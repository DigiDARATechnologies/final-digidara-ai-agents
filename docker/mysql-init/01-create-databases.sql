-- Runs on the mysql container's first boot and is replayed idempotently by
-- deploy.sh for existing production volumes. MySQL initially loads it via
-- /docker-entrypoint-initdb.d. Each DigiDARA service
-- owns and migrates its own schema inside its database; this script only
-- makes sure the databases themselves exist so every service's own startup
-- (SQLAlchemy create_all / Flask-Migrate / etc.) has somewhere to write.
CREATE DATABASE IF NOT EXISTS digidara_registry;   -- orchestrator
CREATE DATABASE IF NOT EXISTS capstone_agent;       -- project_AI_Agent
CREATE DATABASE IF NOT EXISTS leetcode;             -- codeforge_agent (lms-api)
CREATE DATABASE IF NOT EXISTS communication_module; -- communication-ai-agent
CREATE DATABASE IF NOT EXISTS aptitude_ai;          -- aptitude_agent
CREATE DATABASE IF NOT EXISTS resume_builder;       -- resume_builder_agent
CREATE DATABASE IF NOT EXISTS career_agent_db;      -- certificate_agent
CREATE DATABASE IF NOT EXISTS job_agent;             -- job_agent
