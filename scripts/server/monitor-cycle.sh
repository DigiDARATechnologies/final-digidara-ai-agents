#!/bin/bash
# Boss's regular check of the server: agent logs and container health go to the
# orchestrator, which records any failure and sends email that is due.
# Installed as a cron job by deploy.sh and deploy-staging.sh; only reads the logs.
# Usage: monitor-cycle.sh <production|staging>
set -uo pipefail
cd /opt/digidara-agents
{
  docker compose ps -a --format '@ps {{.Service}} {{.State}} {{.Health}}'
  docker compose exec -T job-agent python -m job_agent.fetch_report
  docker compose logs --since 11m --no-color --tail 5000
} 2>/dev/null | docker compose exec -T orchestrator python -m app.monitoring.cycle --label "${1:-server}"
