#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
JOB_ENV="$PROJECT_ROOT/agents/job_agent/.env"
JOB_EXAMPLE="$JOB_ENV.example"
MYSQL_ENV="$PROJECT_ROOT/docker/mysql/.env"
ORCHESTRATOR_ENV="$PROJECT_ROOT/agents/orchestrator/.env"
CANONICAL_JOB_AGENT_URL="http://job-agent:5020/api/invoke"



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

set_env_value() {
  local file=$1
  local key=$2
  local value=$3
  local temp_env line found=false

  temp_env=$(mktemp "$file.tmp.XXXXXX")
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "$key="*)
        if [ "$found" = false ]; then
          printf '%s=%s\n' "$key" "$value"
          found=true
        fi
        ;;
      *) printf '%s\n' "$line" ;;
    esac
  done < "$file" > "$temp_env"
  if [ "$found" = false ]; then
    printf '%s=%s\n' "$key" "$value" >> "$temp_env"
  fi
  chmod 600 "$temp_env"
  mv "$temp_env" "$file"
}

ensure_agent_host_allowed() {
  local agent_host=$1
  # The orchestrator's gateway rejects any registered endpoint whose host
  # isn't in this allowlist (see agents/orchestrator/app/gateway/routes.py).
  # A production .env created before the job-agent Compose service existed
  # never picked up its hostname, so a correct AGENT_PUBLIC_URL above still
  # gets a 403 here unless we repair this list too.
  if [ ! -f "$ORCHESTRATOR_ENV" ]; then
    return 0
  fi
  local current_hosts host_found=false host
  current_hosts=$(read_env_value "$ORCHESTRATOR_ENV" ALLOWED_AGENT_HOSTS || true)
  IFS=',' read -ra hosts_array <<< "$current_hosts"
  for host in "${hosts_array[@]}"; do
    if [ "$(echo "$host" | xargs)" = "$agent_host" ]; then
      host_found=true
      break
    fi
  done
  if [ "$host_found" = true ]; then
    echo "kept    agents/orchestrator/.env ALLOWED_AGENT_HOSTS ($agent_host)"
  else
    local new_hosts
    if [ -z "$current_hosts" ]; then
      new_hosts="$agent_host"
    else
      new_hosts="$current_hosts,$agent_host"
    fi
    set_env_value "$ORCHESTRATOR_ENV" ALLOWED_AGENT_HOSTS "$new_hosts"
    echo "updated agents/orchestrator/.env ALLOWED_AGENT_HOSTS ($agent_host)"
  fi
}

is_placeholder() {
  case "$1" in
    ""|change-me|dev-only-*|replace-*|REPLACE_*|must-match-*|your_*) return 0 ;;
    *) return 1 ;;
  esac
}

seed_mock_interview_env() {
  local env_file="$PROJECT_ROOT/agents/mock_interview_agent/backend/.env"
  local example="$env_file.example"
  local aptitude_env="$PROJECT_ROOT/agents/aptitude_agent/.env"

  if [ -f "$env_file" ]; then
    echo "kept    agents/mock_interview_agent/backend/.env"
    ensure_agent_host_allowed mock-interview-agent
    return 0
  fi
  for required_file in "$example" "$MYSQL_ENV" "$ORCHESTRATOR_ENV" "$aptitude_env"; do
    if [ ! -f "$required_file" ]; then
      echo "Cannot create agents/mock_interview_agent/backend/.env: missing ${required_file#"$PROJECT_ROOT/"}." >&2
      exit 1
    fi
  done

  local db_password agent_secret openai_key session_secret
  db_password=$(read_env_value "$MYSQL_ENV" MYSQL_ROOT_PASSWORD || true)
  agent_secret=$(read_env_value "$ORCHESTRATOR_ENV" AGENT_SHARED_SECRET || true)
  openai_key=$(read_env_value "$aptitude_env" OPENAI_API_KEY || true)
  for pair in "MYSQL_ROOT_PASSWORD:$db_password" "orchestrator AGENT_SHARED_SECRET:$agent_secret" "aptitude OPENAI_API_KEY:$openai_key"; do
    if is_placeholder "${pair#*:}"; then
      echo "Cannot create agents/mock_interview_agent/backend/.env: ${pair%%:*} is missing or still a placeholder." >&2
      exit 1
    fi
  done
  session_secret=$(head -c 48 /dev/urandom | base64 | tr -d '
=+/')

  local temp_env line
  temp_env=$(mktemp "$env_file.tmp.XXXXXX")
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      DB_PASSWORD=*) printf 'DB_PASSWORD=%s
' "$db_password" ;;
      AGENT_SHARED_SECRET=*) printf 'AGENT_SHARED_SECRET=%s
' "$agent_secret" ;;
      OPENAI_API_KEY=*) printf 'OPENAI_API_KEY=%s
' "$openai_key" ;;
      SESSION_JWT_SECRET=*) printf 'SESSION_JWT_SECRET=%s
' "$session_secret" ;;
      *) printf '%s
' "$line" ;;
    esac
  done < "$example" > "$temp_env"
  chmod 600 "$temp_env"
  mv "$temp_env" "$env_file"
  echo "created agents/mock_interview_agent/backend/.env from existing production secrets"
  ensure_agent_host_allowed mock-interview-agent
}

seed_mock_interview_env

if [ -f "$JOB_ENV" ]; then
  current_job_agent_url=$(read_env_value "$JOB_ENV" AGENT_PUBLIC_URL || true)
  if [ "$current_job_agent_url" = "$CANONICAL_JOB_AGENT_URL" ]; then
    echo "kept    agents/job_agent/.env"
  else
    set_env_value "$JOB_ENV" AGENT_PUBLIC_URL "$CANONICAL_JOB_AGENT_URL"
    echo "updated agents/job_agent/.env AGENT_PUBLIC_URL"
  fi
  ensure_agent_host_allowed job-agent
  exit 0
fi

for required_file in "$JOB_EXAMPLE" "$MYSQL_ENV" "$ORCHESTRATOR_ENV"; do
  if [ ! -f "$required_file" ]; then
    echo "Cannot create agents/job_agent/.env: missing ${required_file#"$PROJECT_ROOT/"}}." >&2
    exit 1
  fi
done

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
ensure_agent_host_allowed job-agent
