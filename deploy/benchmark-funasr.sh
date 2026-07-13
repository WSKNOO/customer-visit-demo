#!/usr/bin/env bash
set -euo pipefail

AUDIO_FILE=${1:?usage: benchmark-funasr.sh APPROVED_AUDIO_FILE}
ASR_URL=${ASR_URL:-http://127.0.0.1:${FUNASR_DEBUG_PORT:-18000}}
test -f "$AUDIO_FILE"
echo "container stats before:"; docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} memory={{.MemUsage}}' | grep funasr || true
for seconds in 10 30 60; do
  temp=$(mktemp --suffix=.wav)
  ffmpeg -loglevel error -y -i "$AUDIO_FILE" -t "$seconds" -ar 16000 -ac 1 "$temp"
  echo "benchmark ${seconds}s fixture"
  /usr/bin/time -p curl -fsS -X POST "$ASR_URL/transcribe" -F "file=@$temp" -F format=wav -F language=zh >/dev/null
  rm -f "$temp"
done
echo "container stats after:"; docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} memory={{.MemUsage}}' | grep funasr || true
