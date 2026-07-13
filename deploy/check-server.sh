#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR/deploy"

env_value() {
  python3 - "$1" "$2" <<'PY'
import sys
key, default = sys.argv[1:]
value = default
try:
    for line in open('.env', encoding='utf-8'):
        if line.lstrip().startswith(key + '='):
            value = line.split('=', 1)[1].strip().strip('"\'')
except FileNotFoundError:
    pass
print(value)
PY
}
DATA_DIR=${TRAINING_KNOWCARD_DIR:-$(env_value TRAINING_KNOWCARD_DIR ../ai-visit-training/knowcard_output)}
MODEL_DIR=${FUNASR_MODELS_DIR:-$(env_value FUNASR_MODELS_DIR ../models/funasr)}
PORT=${GATEWAY_PORT:-$(env_value GATEWAY_PORT 8080)}

command -v docker >/dev/null || { echo "ERROR: docker is not installed"; exit 1; }
docker compose version
docker info --format 'Docker={{.ServerVersion}} CPUs={{.NCPU}} Memory={{.MemTotal}} Storage={{.Driver}}'
df -h "$ROOT_DIR"
free -h 2>/dev/null || true
lscpu | grep -E 'Architecture|CPU\(s\)|Model name' || true
if command -v nvidia-smi >/dev/null; then nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader; echo "INFO: FunASR remains CPU-only unless explicitly configured."; fi
ss -lnt 2>/dev/null | grep -E ":($PORT|8000|5000)\b" || true
test -f .env || echo "WARNING: deploy/.env is missing"
docker compose config --quiet
python3 validate-data.py "$DATA_DIR" || true
for name in paraformer-zh fsmn-vad ct-punc-c; do
  test -d "$MODEL_DIR/$name" || echo "WARNING: missing ASR model directory: $name"
done
docker compose ps
curl -sS "http://127.0.0.1:$PORT/api/health" || true
echo
curl -sS "http://127.0.0.1:$PORT/api/asr/status" || true
echo
