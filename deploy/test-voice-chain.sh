#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:${GATEWAY_PORT:-8080}}
AUDIO_FILE=${1:-}
if [[ -z "$AUDIO_FILE" || ! -f "$AUDIO_FILE" ]]; then
  echo "Usage: $0 /path/to/approved-demo.wav" >&2
  exit 2
fi

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
format=${AUDIO_FILE##*.}

curl -fsS -X POST "$BASE_URL/api/asr/transcribe" \
  -F "audio=@$AUDIO_FILE" -F "format=$format" -F language=zh >"$work_dir/asr.json"

python3 - "$work_dir/asr.json" "$work_dir/chat-request.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
text = str(payload.get("text") or "").strip()
if not payload.get("success") or not text:
    raise SystemExit("ASR did not return usable text")
json.dump({
    "messages": [{"role": "user", "content": text}],
    "difficulty": "中等",
    "scene": "通用销售",
}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print("ASR text:", text)
PY

curl -fsS -X POST "$BASE_URL/api/chat" -H 'Content-Type: application/json' \
  --data-binary "@$work_dir/chat-request.json" >"$work_dir/chat.json"

python3 - "$work_dir/chat.json" "$work_dir/tts-request.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
text = str(payload.get("customer_reply") or "").strip()
if not payload.get("success") or not text:
    raise SystemExit("AI training did not return a customer reply")
json.dump({"text": text}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print("AI reply:", text)
PY

curl -fsS -X POST "$BASE_URL/api/tts" -H 'Content-Type: application/json' \
  --data-binary "@$work_dir/tts-request.json" -o "$work_dir/reply.wav"

python3 - "$work_dir/reply.wav" <<'PY'
import sys, wave
with wave.open(sys.argv[1], "rb") as audio:
    assert audio.getnchannels() == 1
    assert audio.getnframes() > 0
    print(f"Voice chain OK: rate={audio.getframerate()} frames={audio.getnframes()}")
PY

bash "$(dirname "$0")/test-training.sh" >/dev/null
echo "Text training fallback OK"
