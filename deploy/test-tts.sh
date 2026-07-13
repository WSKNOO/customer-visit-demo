#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:${GATEWAY_PORT:-8080}}
OUTPUT=${1:-/tmp/customer-visit-demo-tts.wav}

mode=$(curl -fsS "$BASE_URL/api/mode")
grep -Eq '"tts_available"[[:space:]]*:[[:space:]]*true' <<<"$mode" || {
  echo "ERROR: offline TTS is not ready" >&2
  exit 1
}

curl -fsS -X POST "$BASE_URL/api/tts" \
  -H 'Content-Type: application/json' \
  -d '{"text":"你好，欢迎参加客户拜访AI陪练"}' \
  --output "$OUTPUT"

python3 - "$OUTPUT" <<'PY'
import sys
import os
import wave

with wave.open(sys.argv[1], 'rb') as wav:
    assert wav.getnchannels() == 1
    assert wav.getsampwidth() == 2
    assert wav.getframerate() == 44100
    assert wav.getnframes() > 0
    duration = wav.getnframes() / wav.getframerate()
    assert duration >= 0.2
    size = os.path.getsize(sys.argv[1])
    assert size > 1024
    print(f"TTS READY: rate={wav.getframerate()}Hz duration={duration:.2f}s size={size}B frames={wav.getnframes()}")
PY
