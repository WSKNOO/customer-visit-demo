#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "$0")" && pwd)
CALLER_DIR=$PWD
BACKUP_INPUT=${1:?usage: rollback-server.sh BACKUP_DIR}
if [[ "$BACKUP_INPUT" = /* ]]; then BACKUP_DIR=$BACKUP_INPUT; else BACKUP_DIR=$CALLER_DIR/$BACKUP_INPUT; fi
cd "$DEPLOY_DIR"
test -f "$BACKUP_DIR/.env" || { echo "ERROR: backup .env not found"; exit 1; }
cp -p .env ".env.before-rollback.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
cp -p "$BACKUP_DIR/.env" .env
chmod 600 .env
docker compose config --quiet
# Roll back to the safest baseline first: pure-text training with ASR disabled.
ASR_PROVIDER=disabled docker compose up -d --remove-orphans
docker compose ps
