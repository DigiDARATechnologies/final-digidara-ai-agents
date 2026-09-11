#!/bin/bash
set -euo pipefail
cd /opt/digidara-agents

PREVIOUS_COMMIT=$(git rev-parse HEAD)
echo "Current commit: $PREVIOUS_COMMIT"

git fetch origin main
git reset --hard origin/main
NEW_COMMIT=$(git rev-parse HEAD)
echo "Deploying commit: $NEW_COMMIT"

docker compose up -d --build

echo "Waiting for services to stabilize..."
sleep 20

HEALTH_OK=true
if ! curl -fsS -o /dev/null -w "%{http_code}" https://digidaraaiagents.com/ | grep -q "200"; then
  HEALTH_OK=false
  echo "Site health check FAILED."
fi

BAD_CONTAINERS=$(docker compose ps --format '{{.Name}} {{.State}}' | grep -v "running" || true)
if [ -n "$BAD_CONTAINERS" ]; then
  echo "Containers not in a running state:"
  echo "$BAD_CONTAINERS"
  HEALTH_OK=false
fi

for container in $(docker compose ps --services); do
  ERRORS=$(docker compose logs --tail=50 "$container" 2>&1 | grep -iE "traceback|fatal|unhandled exception" | grep -v "LangChainPendingDeprecationWarning" || true)
  if [ -n "$ERRORS" ]; then
    echo "Errors found in $container logs:"
    echo "$ERRORS"
    HEALTH_OK=false
  fi
done

if [ "$HEALTH_OK" = false ]; then
  echo "Health check FAILED. Rolling back to $PREVIOUS_COMMIT"
  git reset --hard "$PREVIOUS_COMMIT"
  docker compose up -d --build
  echo "Rolled back. Deploy of $NEW_COMMIT was NOT applied."
  exit 1
fi

echo "Deploy successful: $NEW_COMMIT is live."
