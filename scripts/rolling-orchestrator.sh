#!/bin/bash
# Replace the orchestrator without an API outage: build its new image, start a
# second orchestrator from it next to the running one, wait until the new one
# is healthy, then stop the old one gracefully (gunicorn finishes the requests
# it is serving). nginx resolves `orchestrator` on every request (nginx.conf),
# so it sends traffic to both while they overlap and only to the new one after.
#
# Run from deploy.sh and scripts/deploy-staging.sh before their
# `docker compose up -d --build --wait`; that step then finds the orchestrator
# already up to date and leaves it alone. Does nothing when the orchestrator
# image did not change. Any problem here is reported and the normal deploy
# carries on (it recreates the orchestrator the old way), so this can never
# block or break a deploy. FORCE_ROLLING=1 rolls even when nothing changed.
set -uo pipefail

SERVICE=orchestrator
WAIT_SECONDS=${ROLLING_WAIT_SECONDS:-180}

old_id=$(docker compose ps -q "$SERVICE" 2>/dev/null | head -n 1)
if [ -z "$old_id" ]; then
  echo "rolling: no running $SERVICE; the normal deploy will start it."
  exit 0
fi
if [ "$(docker compose ps -q "$SERVICE" | wc -l)" -ne 1 ]; then
  echo "rolling: more than one $SERVICE container is running; skipping."
  exit 0
fi

if ! docker compose build "$SERVICE"; then
  echo "rolling: building $SERVICE failed; the normal deploy will report it."
  exit 0
fi

image_name=$(docker inspect -f '{{.Config.Image}}' "$old_id")
running_image=$(docker inspect -f '{{.Image}}' "$old_id")
built_image=$(docker image inspect -f '{{.Id}}' "$image_name" 2>/dev/null || true)
if [ "$running_image" = "$built_image" ] && [ "${FORCE_ROLLING:-0}" != "1" ]; then
  echo "rolling: $SERVICE image unchanged; nothing to roll."
  exit 0
fi

echo "rolling: starting a new $SERVICE next to $old_id..."
if ! docker compose up -d --no-deps --no-recreate --scale "$SERVICE=2" "$SERVICE"; then
  echo "rolling: could not start a second $SERVICE; the normal deploy will recreate it."
  exit 0
fi
new_id=$(docker compose ps -q "$SERVICE" | grep -v "^$old_id" | head -n 1)
if [ -z "$new_id" ]; then
  echo "rolling: the new $SERVICE did not appear; the normal deploy will recreate it."
  exit 0
fi

deadline=$((SECONDS + WAIT_SECONDS))
status=""
while [ $SECONDS -lt $deadline ]; do
  status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$new_id" 2>/dev/null || echo gone)
  [ "$status" = "healthy" ] && break
  if [ "$status" = "unhealthy" ] || [ "$status" = "gone" ] || [ "$status" = "exited" ]; then break; fi
  sleep 2
done

if [ "$status" != "healthy" ]; then
  echo "rolling: the new $SERVICE is $status; removing it and keeping the old one."
  docker rm -f "$new_id" >/dev/null 2>&1 || true
  exit 0
fi

echo "rolling: new $SERVICE is healthy; stopping the old one."
# Let nginx's 10 s DNS cache pick up the new container before the old one goes.
sleep 11
docker stop -t 30 "$old_id" >/dev/null && docker rm "$old_id" >/dev/null
echo "rolling: $SERVICE replaced without an outage."
