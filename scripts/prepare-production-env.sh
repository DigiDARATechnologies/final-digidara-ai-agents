#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
JOB_ENV="$PROJECT_ROOT/agents/job_agent/.env"
JOB_EXAMPLE="$JOB_ENV.example"
MYSQL_ENV="$PROJECT_ROOT/docker/mysql/.env"
ORCHESTRATOR_ENV="$PROJECT_ROOT/agents/orchestrator/.env"

if [ -f "$JOB_ENV" ]; then
  echo "kept    agents/job_agent/.env"
  exit 0
fi

for required_file in "$JOB_EXAMPLE" "$MYSQL_ENV" "$ORCHESTRATOR_ENV"; do
  if [ ! -f "$required_file" ]; then
    echo "Cannot create agents/job_agent/.env: missing ${required_file#"$PROJECT_ROOT/"}}." >&2
    exit 1
  fi
done

read_env_value() {
  local file=$1
  local key=$2
  local line

  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "$key="*)
        printf '%s' "${line#*=}"
        return 0
        ;;
    esac
  done < "$file"
  return 1
}

MYSQL_PASSWORD=$(read_env_value "$MYSQL_ENV" MYSQL_ROOT_PASSWORD || true)
AGENT_SECRET=$(read_env_value "$ORCHESTRATOR_ENV" AGENT_SHARED_SECRET || true)

case "$MYSQL_PASSWORD" in
  ""|change-me|replace-*|REPLACE_*)
    echo "Cannot create agents/job_agent/.env: MYSQL_ROOT_PASSWORD is missing or still a placeholder." >&2
    exit 1
    ;;
esac

case "$AGENT_SECRET" in
  ""|change-me|dev-only-*|replace-*|REPLACE_*|must-match-*)
    echo "Cannot create agents/job_agent/.env: orchestrator AGENT_SHARED_SECRET is missing or still a placeholder." >&2
    exit 1
    ;;
esac

TEMP_ENV=$(mktemp "$JOB_ENV.tmp.XXXXXX")
trap 'rm -f "$TEMP_ENV"' EXIT
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    DB_PASSWORD=*) printf 'DB_PASSWORD=%s\n' "$MYSQL_PASSWORD" ;;
    AGENT_SHARED_SECRET=*) printf 'AGENT_SHARED_SECRET=%s\n' "$AGENT_SECRET" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$JOB_EXAMPLE" > "$TEMP_ENV"

chmod 600 "$TEMP_ENV"
mv "$TEMP_ENV" "$JOB_ENV"
trap - EXIT
echo "created agents/job_agent/.env from existing production secrets"
