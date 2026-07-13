#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DEPLOY_DIR"
TARGET=${1:-all}
case "$TARGET" in ai-training|funasr-service|data|all) ;; *) echo "usage: $0 {ai-training|funasr-service|data|all}"; exit 2 ;; esac
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
ASR_MODE=${ASR_PROVIDER:-$(env_value ASR_PROVIDER disabled)}
PORT=${GATEWAY_PORT:-$(env_value GATEWAY_PORT 8080)}
HOT_MODE=${USE_HOT_COMPOSE:-$(env_value USE_HOT_COMPOSE false)}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-$DEPLOY_DIR/backups/$STAMP}
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
if [[ -f .env ]]; then cp -p .env "$BACKUP_DIR/.env"; chmod 600 "$BACKUP_DIR/.env"; fi
docker compose ps --format json > "$BACKUP_DIR/compose-ps.json" 2>/dev/null || true
docker compose images > "$BACKUP_DIR/images.txt" 2>/dev/null || true

if [[ "$TARGET" != funasr-service ]]; then
  python3 validate-data.py "$DATA_DIR"
fi

files=(-f docker-compose.yml)
if [[ "$HOT_MODE" == true ]]; then files+=(-f docker-compose.hot.yml); fi
docker compose "${files[@]}" config --quiet
profiles=()
if [[ "$ASR_MODE" == http && ( "$TARGET" == all || "$TARGET" == funasr-service ) ]]; then
  for model in paraformer-zh fsmn-vad ct-punc-c; do test -d "$MODEL_DIR/$model" || { echo "ERROR: missing $model"; exit 1; }; done
  profiles=(--profile asr)
fi
build_args=()
if [[ ${REBUILD:-false} == true ]]; then build_args=(--build); fi

case "$TARGET" in
  ai-training) docker compose "${files[@]}" up -d --no-deps "${build_args[@]}" ai-training ;;
  funasr-service) docker compose "${files[@]}" --profile asr up -d --no-deps "${build_args[@]}" funasr-service ;;
  data) docker compose "${files[@]}" restart ai-training ;;
  all) docker compose "${files[@]}" "${profiles[@]}" up -d --remove-orphans "${build_args[@]}" ;;
esac
deadline=$((SECONDS + ${HEALTH_WAIT_SECONDS:-180}))
if [[ "$TARGET" == funasr-service ]]; then
  until docker compose "${files[@]}" --profile asr exec -T funasr-service python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then docker compose "${files[@]}" --profile asr logs --tail=80 funasr-service; echo "Rollback with: bash deploy/rollback-server.sh $BACKUP_DIR"; exit 1; fi
    sleep 3
  done
else
  until curl -fsS "http://127.0.0.1:$PORT/gateway-health" >/dev/null; do
    if (( SECONDS >= deadline )); then docker compose "${files[@]}" ps; docker compose "${files[@]}" logs --tail=80 ai-training nginx; echo "Rollback with: bash deploy/rollback-server.sh $BACKUP_DIR"; exit 1; fi
    sleep 3
  done
fi
if [[ "$TARGET" == funasr-service || ( "$TARGET" == all && "$ASR_MODE" == http ) ]]; then
  docker compose "${files[@]}" --profile asr ps funasr-service
fi
echo "Update complete. Backup: $BACKUP_DIR"
