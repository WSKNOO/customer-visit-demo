#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR=${1:?usage: prepare-funasr-models.sh SOURCE_DIR [RELEASE_NAME]}
RELEASE=${2:-$(date +%Y%m%d-%H%M%S)}
MODEL_ROOT=${FUNASR_MODEL_ROOT:-/mnt/disk/models/funasr}
TARGET="$MODEL_ROOT/releases/$RELEASE"
test ! -e "$TARGET" || { echo "ERROR: target release already exists: $TARGET"; exit 1; }
for model in paraformer-zh fsmn-vad ct-punc-c; do
  test -d "$SOURCE_DIR/$model" || { echo "ERROR: source model missing: $model"; exit 1; }
done
mkdir -p "$TARGET"
for model in paraformer-zh fsmn-vad ct-punc-c; do cp -a "$SOURCE_DIR/$model" "$TARGET/$model"; done
find "$TARGET" -type f -print0 | sort -z | xargs -0 sha256sum > "$TARGET/SHA256SUMS"
ln -sfn "releases/$RELEASE" "$MODEL_ROOT/current.next"
mv -Tf "$MODEL_ROOT/current.next" "$MODEL_ROOT/current"
echo "Prepared read-only model release: $TARGET"
echo "Set FUNASR_MODELS_DIR=$MODEL_ROOT/current"
