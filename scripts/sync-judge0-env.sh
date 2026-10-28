#!/bin/bash
# Gives the Capstone agent the same Judge0 access settings the CodeForge agent
# already has. Judge0 requires its authentication token on every request, and
# without it every Capstone "does it run" check failed with 401 Unauthorized.
#
# Copies only keys the Capstone .env does not have yet, never overwrites one,
# and never prints a value. Safe to run on every deploy.
set -euo pipefail

SOURCE=agents/codeforge_agent/services/lms-api/.env
TARGET=agents/project_AI_Agent/.env
KEYS="JUDGE0_AUTHN_HEADER JUDGE0_AUTHN_TOKEN JUDGE0_AUTHZ_HEADER JUDGE0_AUTHZ_TOKEN"

if [ ! -f "$SOURCE" ] || [ ! -f "$TARGET" ]; then
  echo "Judge0 settings: $SOURCE or $TARGET is missing; skipped."
  exit 0
fi

added=""
for key in $KEYS; do
  if grep -q "^${key}=" "$TARGET"; then
    continue
  fi
  line=$(grep -m1 "^${key}=" "$SOURCE" || true)
  if [ -n "$line" ]; then
    # Make sure the file ends with a newline before appending.
    if [ -s "$TARGET" ] && [ "$(tail -c1 "$TARGET")" != "" ]; then
      printf '\n' >> "$TARGET"
    fi
    printf '%s\n' "$line" >> "$TARGET"
    added="$added $key"
  fi
done

if [ -n "$added" ]; then
  echo "Judge0 settings copied to the Capstone agent:$added"
else
  echo "Judge0 settings: Capstone agent already configured."
fi
