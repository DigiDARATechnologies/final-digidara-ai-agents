#!/bin/bash
set -euo pipefail
cd /opt/digidara-agents

# CI checks out the exact commit before starting this script so Bash executes
# the new deployment logic immediately. The fallback keeps manual invocation
# working and captures the current revision as the rollback target.
PREVIOUS_COMMIT=${PREVIOUS_COMMIT:-$(git rev-parse HEAD)}
echo "Current commit: $PREVIOUS_COMMIT"

git fetch origin main
TARGET_COMMIT=${DEPLOY_COMMIT:-origin/main}
git reset --hard "$TARGET_COMMIT"
NEW_COMMIT=$(git rev-parse HEAD)
echo "Deploying commit: $NEW_COMMIT"

# A newly added service has no server-side .env yet. Seed its configuration
# from the already configured MySQL and orchestrator secrets without printing
# either value. Existing job-agent configuration is never overwritten.
bash scripts/prepare-production-env.sh

# Catch missing env files and other Compose configuration errors before any
# containers are touched.
docker compose config --quiet

# MySQL only runs /docker-entrypoint-initdb.d when its data volume is empty.
# Replay the idempotent database-creation script on every deploy so services
# added after the production volume was created get their database too.
echo "Ensuring service databases exist..."
docker compose up -d --wait --wait-timeout 120 mysql
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --protocol=socket -uroot' \
  < docker/mysql-init/01-create-databases.sql
echo "Service databases are ready."

DEPLOY_STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HEALTH_OK=true
if ! docker compose up -d --build --wait --wait-timeout 180; then
  echo "Docker Compose failed to start a healthy stack."
  HEALTH_OK=false
fi

JOB_AGENT_GATEWAY_OK=false
for _ in $(seq 1 12); do
  if docker compose exec -T orchestrator python -c \
    "import urllib.request; request=urllib.request.Request('http://127.0.0.1:8100/gateway/agents/job_agent/invoke', data=bytes.fromhex('7b22616374696f6e223a226865616c7468227d'), headers={'Content-Type':'application/json'}); urllib.request.urlopen(request, timeout=10).read()" \
    >/dev/null 2>&1; then
    JOB_AGENT_GATEWAY_OK=true
    break
  fi
  sleep 5
done
if [ "$JOB_AGENT_GATEWAY_OK" = false ]; then
  HEALTH_OK=false
  echo "Job Agent gateway health check FAILED."
fi


SITE_OK=false
for _ in $(seq 1 12); do
  if curl -fsS -o /dev/null https://digidaraaiagents.com/; then
    SITE_OK=true
    break
  fi
  sleep 5
done
if [ "$SITE_OK" = false ]; then
  HEALTH_OK=false
  echo "Site health check FAILED."
fi

BAD_CONTAINERS=$(docker compose ps --format '{{.Name}} {{.State}} {{.Health}}' | awk '$2 != "running" || $3 == "unhealthy"' || true)
if [ -n "$BAD_CONTAINERS" ]; then
  echo "Containers not running or unhealthy:"
  echo "$BAD_CONTAINERS"
  HEALTH_OK=false
fi

for container in $(docker compose ps --services); do
  # Print the whole tail, not just the matching grep line -- a bare
  # "Traceback (most recent call last):" or "Errors found in..." with no
  # context tells you a container broke but not why, which is useless for
  # actually fixing the regression from the CI log alone.
  LOGS=$(docker compose logs --since "$DEPLOY_STARTED_AT" --tail=80 "$container" 2>&1)
  if echo "$LOGS" | grep -v "LangChainPendingDeprecationWarning" | grep -qiE "traceback|fatal|unhandled exception"; then
    echo "Errors found in $container logs (last 80 lines):"
    echo "$LOGS"
    # Log matches are diagnostic only; container health determines rollback.
  fi
done

if [ "$HEALTH_OK" = false ]; then
  echo "Logs from this deployment attempt:"
  docker compose logs --since "$DEPLOY_STARTED_AT" --tail=200 || true
  echo "Health check FAILED. Rolling back to $PREVIOUS_COMMIT"
  git reset --hard "$PREVIOUS_COMMIT"
  if ! docker compose up -d --build --wait --wait-timeout 180 --remove-orphans; then
    echo "ROLLBACK FAILED. Manual intervention is required."
    exit 2
  fi
  echo "Rolled back. Deploy of $NEW_COMMIT was NOT applied."
  exit 1
fi

echo "Deploy successful: $NEW_COMMIT is live."
