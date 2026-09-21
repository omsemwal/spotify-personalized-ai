#!/usr/bin/env bash
#
# End-to-end smoke test: proves the whole memory loop works against the real
# stack, the way a reviewer would check it.
#
#   ./scripts/dev.sh up          # datastores
#   ./scripts/services.sh start  # the six services
#   ./scripts/smoke.sh           # this
#
# It walks the eight steps from §6.1 using nothing but HTTP, and checks the
# result of each one:
#
#   1. health of all six services
#   2. capture an event            POST /v1/events
#   3. duplicate is refused        POST /v1/events  (same idempotency key)
#   4. the consumer writes it      (poll until the memory is retrievable)
#   5. retrieve it                 POST /v1/memories/search
#   6. compose context             POST /v1/context/compose
#   7. delete it                   DELETE /v1/memories/{id}
#   8. deletion propagated         GET /v1/deletions/{job_id}, then search again
#
# Exits non-zero on the first failure, so it is usable as a release gate.

set -uo pipefail
cd "$(dirname "$0")/.."

GATEWAY="${GATEWAY:-http://localhost:8080}"
TOKEN="${INGESTION_SERVICE_TOKEN:-dev-ingestion-token}"
SUBJECT="smoke_$(date +%s)"
PASS=0
FAIL=0

if   [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ];        then PY=".venv/bin/python"
else                                        PY="python"
fi

ok()   { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $1"; echo "        $2"; FAIL=$((FAIL+1)); }
json() { "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d$1)" 2>/dev/null; }

echo "════════════════════════════════════════════════════════════════"
echo " end-to-end smoke test        subject: $SUBJECT"
echo "════════════════════════════════════════════════════════════════"

# ── 1. health ───────────────────────────────────────────────────────────────
echo
echo "1. service health"
for entry in "ingestion-api:8001" "retrieval-api:8002" "context-composer:8003" \
             "deletion-orchestrator:8004" "memory-mcp-server:8005" "memory-processor:8006"; do
  name="${entry%%:*}"; port="${entry##*:}"
  code=$(curl -s -m 5 -o /tmp/health_$port.json -w "%{http_code}" "http://localhost:$port/health")
  if [ "$code" = "200" ]; then
    ok "$name ($port)"
  else
    bad "$name ($port)" "HTTP $code — $(cat /tmp/health_$port.json 2>/dev/null | head -c 200)"
  fi
done

code=$(curl -s -m 5 -o /dev/null -w "%{http_code}" -X POST "$GATEWAY/v1/memories/search" \
  -H "Content-Type: application/json" \
  -d '{"subject_id":"smoke_probe","surface":"music_chat","intent":"probe","locale":"en-US","max_results":1}')
[ "$code" = "200" ] && ok "api gateway ($GATEWAY)" || bad "api gateway" "HTTP $code"

# ── 2. capture ──────────────────────────────────────────────────────────────
echo
echo "2. capture an event"
EVENT=$(cat <<JSON
{"event_id":"ev_$SUBJECT","subject_id":"$SUBJECT","surface":"music_chat",
 "event_type":"statement",
 "payload":{"text":"I like low-vocal focus playlists while working",
            "entities":["low-vocal","focus"],"explicit":true},
 "locale":"en-US","timestamp":"$(date -u +%Y-%m-%dT%H:%M:%SZ)",
 "consent_state":"granted","idempotency_key":"idem_$SUBJECT"}
JSON
)
resp=$(curl -s -m 10 -w "\n%{http_code}" -X POST "$GATEWAY/v1/events" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$EVENT")
code=$(echo "$resp" | tail -1)
[ "$code" = "202" ] && ok "event accepted (202)" || bad "event accepted" "HTTP $code — $(echo "$resp" | head -1)"

# ── 3. duplicate refused ────────────────────────────────────────────────────
echo
echo "3. duplicate refused"
code=$(curl -s -m 10 -o /dev/null -w "%{http_code}" -X POST "$GATEWAY/v1/events" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$EVENT")
[ "$code" = "409" ] && ok "same idempotency key rejected (409)" \
                    || bad "duplicate rejection" "expected 409, got $code"

code=$(curl -s -m 10 -o /dev/null -w "%{http_code}" -X POST "$GATEWAY/v1/events" \
  -H "Content-Type: application/json" -d "$EVENT")
[ "$code" = "401" ] && ok "unauthenticated event rejected (401)" \
                    || bad "auth check" "expected 401, got $code"

# ── 4. the consumer writes it ───────────────────────────────────────────────
echo
echo "4. asynchronous write reaches the graph"
SEARCH="{\"subject_id\":\"$SUBJECT\",\"surface\":\"music_chat\",\"intent\":\"music for working\",\"locale\":\"en-US\",\"max_results\":5}"
MEMORY_ID=""
for _ in $(seq 1 20); do
  MEMORY_ID=$(curl -s -m 10 -X POST "$GATEWAY/v1/memories/search" \
    -H "Content-Type: application/json" -d "$SEARCH" | json "['results'][0]['memory_id']")
  [ -n "$MEMORY_ID" ] && break
  sleep 1
done
if [ -n "$MEMORY_ID" ]; then
  ok "memory written and retrievable ($MEMORY_ID)"
else
  bad "asynchronous write" "no memory appeared within 20s. Check the consumer: curl localhost:8006/health"
fi

# ── 5-6. retrieve and compose ───────────────────────────────────────────────
echo
echo "5. retrieval and context composition"
if [ -n "$MEMORY_ID" ]; then
  fact=$(curl -s -m 10 -X POST "$GATEWAY/v1/memories/search" \
    -H "Content-Type: application/json" -d "$SEARCH" | json "['results'][0]['fact']")
  [ -n "$fact" ] && ok "search returns the fact: \"$fact\"" || bad "search" "no fact returned"

  compose=$(curl -s -m 10 -X POST "$GATEWAY/v1/context/compose" -H "Content-Type: application/json" \
    -d "{\"subject_id\":\"$SUBJECT\",\"surface\":\"music_chat\",\"intent\":\"music for working\",\"locale\":\"en-US\",\"token_budget\":400}")
  items=$(echo "$compose" | json "['items'].__len__()")
  budget=$(echo "$compose" | json "['token_count']")
  if [ "${items:-0}" -ge 1 ]; then
    ok "context package built ($items item(s), $budget tokens)"
  else
    bad "context composition" "$compose"
  fi
fi

# ── 7-8. delete and prove propagation ───────────────────────────────────────
echo
echo "6. deletion and propagation"
if [ -n "$MEMORY_ID" ]; then
  job=$(curl -s -m 15 -X DELETE "$GATEWAY/v1/memories/$MEMORY_ID" | json "['job_id']")
  [ -n "$job" ] && ok "deletion job started ($job)" || bad "deletion" "no job id returned"

  if [ -n "$job" ]; then
    status_json=$(curl -s -m 10 "$GATEWAY/v1/deletions/$job")
    status=$(echo "$status_json" | json "['status']")
    [ "$status" = "completed" ] && ok "job reports completed" \
                               || bad "deletion status" "status=$status — $status_json"
    echo "        per-store: $(echo "$status_json" | json "['stores']")"
  fi

  left=$(curl -s -m 10 -X POST "$GATEWAY/v1/memories/search" \
    -H "Content-Type: application/json" -d "$SEARCH" | json "['results'].__len__()")
  [ "${left:-1}" = "0" ] && ok "deleted memory is no longer retrievable" \
                         || bad "deletion propagation" "search still returns $left result(s)"
fi

# ── summary ─────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════"
echo " $PASS passed, $FAIL failed"
echo "════════════════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] || exit 1
