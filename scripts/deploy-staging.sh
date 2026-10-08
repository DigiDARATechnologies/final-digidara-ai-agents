#!/bin/bash
# Staging deploy for staging.digidaraaiagents.com, run on the staging server by
# .github/workflows/staging.yml on every push to the `phase2` branch.
#
# Production never runs this file: production deploys with ../deploy.sh from
# ci.yml on pushes to `main`. This script follows deploy.sh step for step, with
# three differences for the staging server:
#   - it tracks the `phase2` branch and health-checks the staging domain;
#   - it skips prepare-production-env.sh (staging's .env files were copied
#     from production and edited by hand, so nothing needs seeding);
#   - it re-applies judge0.conf's ownership on every deploy -- the Judge0
#     containers run as uid 1000 and cannot read a root-only file.
#
# The server also hosts other live websites and another Docker Compose
# project, so this only ever touches the `digidara-agents` Compose project.
set -euo pipefail
cd /opt/digidara-agents

BRANCH=${DEPLOY_BRANCH:-phase2}
SITE_URL=${SITE_URL:-https://staging.digidaraaiagents.com}

PREVIOUS_COMMIT=${PREVIOUS_COMMIT:-$(git rev-parse HEAD)}
echo "Current commit: $PREVIOUS_COMMIT"

git fetch origin "$BRANCH"
TARGET_COMMIT=${DEPLOY_COMMIT:-origin/$BRANCH}
git reset --hard "$TARGET_COMMIT"
NEW_COMMIT=$(git rev-parse HEAD)
echo "Deploying commit: $NEW_COMMIT to $SITE_URL"

if [ -n "${GHCR_PULL_TOKEN:-}" ]; then
  echo "$GHCR_PULL_TOKEN" | docker login ghcr.io -u digidaratechnologies --password-stdin
fi

if command -v python3 >/dev/null 2>&1; then
  echo "Checking .env drift (warning only)..."
  python3 scripts/check_env_drift.py || echo "WARNING: env drift check could not run."
fi

JUDGE0_CONF=agents/codeforge_agent/judge0/judge0.conf
if [ -f "$JUDGE0_CONF" ]; then
  chown 1000:999 "$JUDGE0_CONF"
  chmod 600 "$JUDGE0_CONF"
fi

docker compose config --quiet

echo "Ensuring service databases exist..."
docker compose up -d --wait --wait-timeout 180 mysql
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --protocol=socket -uroot' \
  < docker/mysql-init/01-create-databases.sql
echo "Service databases are ready."

DEPLOY_STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HEALTH_OK=true
if ! docker compose up -d --build --wait --wait-timeout 300; then
  echo "Docker Compose failed to start a healthy stack."
  HEALTH_OK=false
fi

# Every agent through the gateway, the same way the browser reaches them.
AGENTS="job_agent aptitude_agent codeforge_agent communication_agent resume_builder_agent certificate_agent capstone_project_agent mock_interview_agent"
for agent in $AGENTS; do
  AGENT_OK=false
  for _ in $(seq 1 12); do
    if docker compose exec -T orchestrator python -c \
      "import sys, urllib.request; request=urllib.request.Request('http://127.0.0.1:8100/gateway/agents/' + sys.argv[1] + '/invoke', data=b'{\"action\":\"health\"}', headers={'Content-Type':'application/json'}); urllib.request.urlopen(request, timeout=10).read()" \
      "$agent" </dev/null >/dev/null 2>&1; then
      AGENT_OK=true
      break
    fi
    sleep 5
  done
  if [ "$AGENT_OK" = false ]; then
    HEALTH_OK=false
    echo "Gateway health check FAILED for $agent."
  fi
done

SITE_OK=false
for _ in $(seq 1 12); do
  if curl -fsS -o /dev/null "$SITE_URL/"; then
    SITE_OK=true
    break
  fi
  sleep 5
done
if [ "$SITE_OK" = false ]; then
  HEALTH_OK=false
  echo "Site health check FAILED."
fi

API_OK=false
for _ in $(seq 1 12); do
  AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL/auth/me" || true)
  PLANS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL/billing/plans" || true)
  if [ "$AUTH_CODE" = "401" ] && [ "$PLANS_CODE" = "200" ]; then
    API_OK=true
    break
  fi
  sleep 5
done
if [ "$API_OK" = false ]; then
  HEALTH_OK=false
  echo "Public API health check FAILED (auth/me=$AUTH_CODE, billing/plans=$PLANS_CODE)."
fi

BAD_CONTAINERS=$(docker compose ps --format '{{.Name}} {{.State}} {{.Health}}' | awk '$2 != "running" || $3 == "unhealthy"' || true)
if [ -n "$BAD_CONTAINERS" ]; then
  echo "Containers not running or unhealthy:"
  echo "$BAD_CONTAINERS"
  HEALTH_OK=false
fi

for container in $(docker compose ps --services); do
  LOGS=$(docker compose logs --since "$DEPLOY_STARTED_AT" --tail=80 "$container" 2>&1)
  if echo "$LOGS" | grep -v "LangChainPendingDeprecationWarning" | grep -qiE "traceback|fatal|unhandled exception"; then
    echo "Errors found in $container logs (last 80 lines):"
    echo "$LOGS"
  fi
done

if [ "$HEALTH_OK" = false ]; then
  echo "Logs from this deployment attempt:"
  docker compose logs --since "$DEPLOY_STARTED_AT" --tail=200 || true
  echo "Health check FAILED. Rolling back to $PREVIOUS_COMMIT"
  git reset --hard "$PREVIOUS_COMMIT"
  if ! docker compose up -d --build --wait --wait-timeout 300 --remove-orphans; then
    echo "ROLLBACK FAILED. Manual intervention is required."
    exit 2
  fi
  echo "Rolled back. Deploy of $NEW_COMMIT was NOT applied."
  exit 1
fi

echo "Staging deploy successful: $NEW_COMMIT is live on $SITE_URL."
