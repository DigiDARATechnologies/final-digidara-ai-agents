#!/bin/bash
# Undoes the false "reloaded or reopened" warnings of 3 November 2026 for the students
# they hit. Without --apply it only shows what would change. Safe to run twice.
#   bash scripts/server/repair-false-proctor-warnings.sh           # preview
#   bash scripts/server/repair-false-proctor-warnings.sh --apply
set -euo pipefail
cd /opt/digidara-agents
OUTPUT=$(docker compose exec -T orchestrator python -m app.proctoring.repair_false_warnings "$@")
echo "$OUTPUT" | grep -v '^@viva' || true
echo "$OUTPUT" | grep '^@viva' | docker compose exec -T capstone-agent python -m app.api.viva_chances "$@"
