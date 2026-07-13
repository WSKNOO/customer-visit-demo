#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:${GATEWAY_PORT:-8080}}
ASR_URL=${ASR_URL:-http://127.0.0.1:${FUNASR_DEBUG_PORT:-18000}}
AUDIO_FILE=${1:-}
curl -sS "$BASE_URL/api/asr/status" || true
echo
curl -sS "$ASR_URL/health" || true
echo
curl -sS "$ASR_URL/models/status" || true
echo
empty_file=$(mktemp)
code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$ASR_URL/transcribe" -F "file=@$empty_file" -F format=wav || true)
rm -f "$empty_file"
[[ "$code" == 400 || "$code" == 503 ]] || { echo "ERROR: empty audio was not rejected ($code)"; exit 1; }
if curl -fsS --max-time 1 http://127.0.0.1:9/health >/dev/null 2>&1; then echo "ERROR: unavailable-service check failed"; exit 1; fi
if [[ -z "$AUDIO_FILE" ]]; then echo; echo "Status checked; pass an approved local WAV/WebM fixture to test transcription."; exit 0; fi
test -f "$AUDIO_FILE"
format=${AUDIO_FILE##*.}
curl -fsS -X POST "$BASE_URL/api/asr/transcribe" -F "file=@$AUDIO_FILE" -F "format=$format" -F language=zh
echo
