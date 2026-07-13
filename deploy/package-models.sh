#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_ROOT=${MODEL_ROOT:-$ROOT_DIR/models}
OUTPUT=${1:-$ROOT_DIR/customer-visit-models.tar.gz}
[[ "$(basename "$MODEL_ROOT")" == models ]] || { echo "ERROR: MODEL_ROOT must end with /models" >&2; exit 2; }

FUNASR_MODELS_DIR="$MODEL_ROOT/funasr" bash "$ROOT_DIR/deploy/check-funasr-model.sh"
TTS_MODELS_DIR="$MODEL_ROOT/tts" bash "$ROOT_DIR/deploy/check-tts-model.sh"

temp_output="$OUTPUT.partial"
rm -f "$temp_output"
tar -czf "$temp_output" --exclude='models/.downloads' -C "$(dirname "$MODEL_ROOT")" models

if tar -tzf "$temp_output" | grep -Eq '(^|/)(\.git|node_modules|venv|\.venv)(/|$)'; then
  rm -f "$temp_output"
  echo "ERROR: forbidden path detected in package" >&2
  exit 1
fi
mv "$temp_output" "$OUTPUT"

python3 - "$OUTPUT" >"$OUTPUT.sha256" <<'PY'
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
digest = hashlib.sha256()
with path.open('rb') as stream:
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
        digest.update(chunk)
print(f"{digest.hexdigest()}  {path.name}")
PY

count=$(tar -tzf "$OUTPUT" | grep -v '/$' | wc -l | tr -d ' ')
echo "Package: $OUTPUT"
du -h "$OUTPUT"
echo "Files: $count"
cat "$OUTPUT.sha256"
