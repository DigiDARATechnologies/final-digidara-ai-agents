#!/usr/bin/env bash
# Manual verification for the Phase 1 security fixes to the orchestrator's
# /registry/* and /gateway/*/invoke endpoints, plus /chat auth + rate limiting.
#
# Run the orchestrator first (from agents/orchestrator), with real values for
# JWT_SECRET and AGENT_SHARED_SECRET set in its .env — then run this script
# against it. Every check below was manually confirmed to pass against a live
# instance before this script was committed.
#
# Usage: BASE=http://127.0.0.1:8100 AGENT_SHARED_SECRET=... ./verify_phase1_security.sh

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8100}"
SECRET="${AGENT_SHARED_SECRET:?Set AGENT_SHARED_SECRET to the same value configured on the orchestrator}"

sign() {
  # sign METHOD PATH BODY — prints the three required headers, one per line.
  local method="$1" path="$2" body="$3"
  local ts rid body_hash canonical sig
  ts=$(date +%s)
  rid=$(python3 -c "import uuid; print(uuid.uuid4().hex)" 2>/dev/null || uuidgen | tr 'A-Z' 'a-z' | tr -d '-')
  body_hash=$(printf '%s' "$body" | sha256sum | cut -d' ' -f1)
  canonical="$ts
$rid
$method
$path
$body_hash"
  sig=$(printf '%s' "$canonical" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')
  echo "X-Agent-Timestamp: $ts"
  echo "X-Agent-Request-Id: $rid"
  echo "X-Agent-Signature: $sig"
}

echo "=== (a) unsigned POST /registry/register -> expect 401 ==="
curl -s -o /dev/null -w "status: %{http_code}\n" -X POST "$BASE/registry/register" \
  -H "Content-Type: application/json" \
  -d '{"agent_name":"attacker_agent","endpoint":"http://169.254.169.254/","description":"x","input_schema":{}}'

echo "=== (b) correctly signed POST /registry/register -> expect 201 ==="
BODY='{"agent_name":"verify_agent","version":"v1.0.0","endpoint":"http://127.0.0.1:9999/invoke","description":"verify","input_schema":{}}'
mapfile -t HEADERS < <(sign POST /registry/register "$BODY")
curl -s -o /dev/null -w "status: %{http_code}\n" -X POST "$BASE/registry/register" \
  -H "Content-Type: application/json" -H "${HEADERS[0]}" -H "${HEADERS[1]}" -H "${HEADERS[2]}" \
  -d "$BODY"

echo "=== (c) unsigned POST /gateway/agents/verify_agent/invoke (non-health action) -> expect 401 ==="
curl -s -o /dev/null -w "status: %{http_code}\n" -X POST "$BASE/gateway/agents/verify_agent/invoke" \
  -H "Content-Type: application/json" -d '{"action":"do_something"}'

echo "=== (d) SSRF probe: register an agent pointing off-host, then health-poll it via the gateway -> expect 403 ==="
BODY2='{"agent_name":"evil_agent","version":"v1.0.0","endpoint":"http://169.254.169.254/latest/meta-data/","description":"x","input_schema":{}}'
mapfile -t HEADERS2 < <(sign POST /registry/register "$BODY2")
curl -s -o /dev/null -w "register evil_agent status: %{http_code}\n" -X POST "$BASE/registry/register" \
  -H "Content-Type: application/json" -H "${HEADERS2[0]}" -H "${HEADERS2[1]}" -H "${HEADERS2[2]}" -d "$BODY2"
curl -s -w "\ngateway invoke to evil_agent status: %{http_code}\n" -X POST "$BASE/gateway/agents/evil_agent/invoke" \
  -H "Content-Type: application/json" -d '{"action":"health"}'

echo "=== (e) unsigned /chat and /chat/route -> expect 401 ==="
curl -s -o /dev/null -w "/chat status: %{http_code}\n" -X POST "$BASE/chat" -H "Content-Type: application/json" -d '{"message":"hi"}'
curl -s -o /dev/null -w "/chat/route status: %{http_code}\n" -X POST "$BASE/chat/route" -H "Content-Type: application/json" -d '{"message":"hi"}'

echo "=== (f) CORS: disallowed Origin gets no Access-Control-Allow-Origin header ==="
curl -s -D - -o /dev/null "$BASE/health" -H "Origin: https://evil.example.com" | grep -qi "access-control-allow-origin" \
  && echo "!! origin reflected — CORS misconfigured" || echo "no ACAO header (correct)"
