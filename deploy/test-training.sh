#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:${GATEWAY_PORT:-8080}}
curl -fsS "$BASE_URL/api/health" >/dev/null
curl -fsS "$BASE_URL/api/scenes" >/dev/null
mode=$(curl -fsS "$BASE_URL/api/mode")
if grep -Eq '"demo_mode"[[:space:]]*:[[:space:]]*true' <<<"$mode"; then
  demo=$(curl -fsS -X POST "$BASE_URL/api/demo/start")
  grep -q '"opening_question"' <<<"$demo" || { echo "ERROR: demo opening question missing"; exit 1; }
fi
response=$(curl -fsS -X POST "$BASE_URL/api/chat" -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"请先介绍一下今天沟通的重点。"}],"difficulty":"中等","scene":"通用销售"}')
if grep -Eqi '<think' <<<"$response"; then echo "ERROR: model reasoning leaked"; exit 1; fi
grep -q '<!--COACH' <<<"$response" || { echo "ERROR: COACH block missing"; exit 1; }
grep -q '<!--SCORE' <<<"$response" || { echo "ERROR: SCORE block missing"; exit 1; }
echo "$response"
