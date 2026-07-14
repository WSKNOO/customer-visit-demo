#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_DIR=${FUNASR_MODELS_DIR:-$ROOT_DIR/models/funasr}
REVISION=${FUNASR_MODEL_REVISION:-v2.0.4}
DOWNLOAD_DIR="$MODEL_DIR/.downloads"

declare -a NAMES=(paraformer vad punc)
declare -a IDS=(
  iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
  iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
  iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch
)
declare -a MODEL_SHA256=(
  5bba782a5e9196166233b9ab12ba04cadff9ef9212b4ff6153ed9290ff679025
  b3be75be477f0780277f3bae0fe489f48718f585f3a6e45d7dd1fbb1a4255fc5
  a5818bb9d933805a916eebe41eb41648f7f9caad30b4bd59d56f3ca135421916
)

if [[ -s "$MODEL_DIR/paraformer/model.pt" && -s "$MODEL_DIR/paraformer/seg_dict" && -s "$MODEL_DIR/vad/model.pt" && -s "$MODEL_DIR/punc/model.pt" && -s "$MODEL_DIR/MODEL_ASSET_INFO.txt" && -s "$MODEL_DIR/SHA256SUMS" ]] && ! find "$MODEL_DIR" -name '*.incomplete' -print -quit | grep -q .; then
  echo "SKIP: verified FunASR asset set already exists"
  exec bash "$ROOT_DIR/deploy/check-funasr-model.sh"
fi

download_model() {
  local name=$1 model_id=$2 expected_sha=$3 target="$MODEL_DIR/$1" partial="$DOWNLOAD_DIR/$1"
  if [[ -s "$target/configuration.json" && -s "$target/config.yaml" && -s "$target/model.pt" ]]; then
    echo "SKIP: $name already exists"
    return
  fi
  if [[ -e "$target" ]]; then
    echo "ERROR: incomplete target exists; move it aside before retrying: $target" >&2
    exit 1
  fi
  mkdir -p "$partial"
  echo "Downloading $model_id revision $REVISION -> $partial"
  if command -v modelscope >/dev/null 2>&1; then
    modelscope download --model "$model_id" --revision "$REVISION" --local_dir "$partial"
  elif python3 -c 'import modelscope' >/dev/null 2>&1; then
    python3 - "$model_id" "$REVISION" "$partial" <<'PY'
import sys
from modelscope.hub.snapshot_download import snapshot_download
snapshot_download(sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3])
PY
  elif command -v docker >/dev/null 2>&1 && docker image inspect "${FUNASR_PREP_IMAGE:-deploy-funasr-service:${IMAGE_TAG:-dev}}" >/dev/null 2>&1; then
    docker run --rm \
      -v "$partial:/download" \
      "${FUNASR_PREP_IMAGE:-deploy-funasr-service:${IMAGE_TAG:-dev}}" \
      modelscope download --model "$model_id" --revision "$REVISION" --local_dir /download
  else
    cat >&2 <<EOF
ModelScope downloader is not installed. Install the official CLI on the model-preparation computer, then rerun:
  python3 -m pip install --user 'modelscope>=1.15,<2'
Official download documentation:
  https://modelscope.cn/docs/models/download
Manual command:
  modelscope download --model '$model_id' --revision '$REVISION' --local_dir '$partial'
Alternatively, build the existing funasr-service image first; the script can use its bundled ModelScope client.
EOF
    exit 2
  fi
  for file in configuration.json config.yaml model.pt; do
    [[ -s "$partial/$file" ]] || { echo "ERROR: incomplete download, missing $partial/$file" >&2; exit 1; }
  done
  if [[ "$name" == paraformer ]]; then
    [[ -s "$partial/seg_dict" ]] || { echo "ERROR: incomplete download, missing $partial/seg_dict" >&2; exit 1; }
  fi
  if find "$partial" -name '*.incomplete' -print -quit | grep -q .; then
    echo "ERROR: downloader left incomplete files in $partial" >&2
    exit 1
  fi
  actual_sha=$(python3 - "$partial/model.pt" <<'PY'
import hashlib, sys
digest = hashlib.sha256()
with open(sys.argv[1], 'rb') as stream:
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
        digest.update(chunk)
print(digest.hexdigest())
PY
)
  [[ "$actual_sha" == "$expected_sha" ]] || { echo "ERROR: upstream SHA256 mismatch for $name/model.pt" >&2; exit 1; }
  mv "$partial" "$target"
}

mkdir -p "$MODEL_DIR" "$DOWNLOAD_DIR"
for index in 0 1 2; do
  download_model "${NAMES[$index]}" "${IDS[$index]}" "${MODEL_SHA256[$index]}"
done

cat >"$MODEL_DIR/MODEL_ASSET_INFO.txt" <<EOF
asset_set=customer-visit-funasr
revision=$REVISION
license=Apache-2.0
paraformer_source=https://modelscope.cn/models/${IDS[0]}
vad_source=https://modelscope.cn/models/${IDS[1]}
punc_source=https://modelscope.cn/models/${IDS[2]}
paraformer_model_sha256=${MODEL_SHA256[0]}
vad_model_sha256=${MODEL_SHA256[1]}
punc_model_sha256=${MODEL_SHA256[2]}
prepared_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

python3 - "$MODEL_DIR" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
paths = []
for name in ('paraformer', 'vad', 'punc'):
    paths.extend(path for path in (root / name).rglob('*') if path.is_file())
paths.append(root / 'MODEL_ASSET_INFO.txt')
with (root / 'SHA256SUMS').open('w', encoding='utf-8') as output:
    for path in sorted(paths):
        output.write(f"{sha256(path)}  {path.relative_to(root).as_posix()}\n")
PY

rm -rf "$DOWNLOAD_DIR"
chmod -R a+rX,go-w "$MODEL_DIR"
bash "$ROOT_DIR/deploy/check-funasr-model.sh"
echo "Files: $(find "$MODEL_DIR" -type f | wc -l | tr -d ' ')"
du -sh "$MODEL_DIR"
echo "SHA256 manifest: $MODEL_DIR/SHA256SUMS"
