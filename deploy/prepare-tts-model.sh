#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_ROOT=${TTS_MODELS_DIR:-$ROOT_DIR/models/tts}
MODEL_NAME=vits-melo-tts-zh_en
MODEL_DIR="$MODEL_ROOT/$MODEL_NAME"
DOWNLOAD_DIR="$MODEL_ROOT/.downloads"
ARCHIVE="$DOWNLOAD_DIR/$MODEL_NAME.tar.bz2"
SOURCE_URL=https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-melo-tts-zh_en.tar.bz2
EXPECTED_ARCHIVE_BYTES=167006755

if [[ -s "$MODEL_DIR/model.onnx" && -s "$MODEL_DIR/tokens.txt" && -s "$MODEL_DIR/lexicon.txt" && -s "$MODEL_DIR/LICENSE" && -s "$MODEL_ROOT/MODEL_ASSET_INFO.txt" && -s "$MODEL_ROOT/SHA256SUMS" ]]; then
  echo "SKIP: verified $MODEL_NAME asset set already exists"
  exec bash "$ROOT_DIR/deploy/check-tts-model.sh"
fi

mkdir -p "$MODEL_ROOT" "$DOWNLOAD_DIR"
if [[ -s "$MODEL_DIR/model.onnx" && -s "$MODEL_DIR/tokens.txt" && -s "$MODEL_DIR/lexicon.txt" && -s "$MODEL_DIR/LICENSE" ]]; then
  echo "SKIP: $MODEL_NAME already exists"
else
  if [[ -e "$MODEL_DIR" ]]; then
    echo "ERROR: incomplete target exists; move it aside before retrying: $MODEL_DIR" >&2
    exit 1
  fi
  command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required" >&2; exit 2; }
  echo "Downloading official sherpa-onnx model (resume enabled): $SOURCE_URL"
  curl --fail --location --retry 3 --retry-delay 2 --continue-at - --output "$ARCHIVE" "$SOURCE_URL"
  archive_bytes=$(python3 -c 'import os,sys; print(os.path.getsize(sys.argv[1]))' "$ARCHIVE")
  [[ "$archive_bytes" == "$EXPECTED_ARCHIVE_BYTES" ]] || { echo "ERROR: unexpected archive size: $archive_bytes" >&2; exit 1; }
  if tar -tjf "$ARCHIVE" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
    echo "ERROR: unsafe archive paths" >&2
    exit 1
  fi
  temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/customer-visit-tts.XXXXXX")
  trap 'rm -rf "$temp_dir"' EXIT
  tar -xjf "$ARCHIVE" -C "$temp_dir"
  extracted="$temp_dir/$MODEL_NAME"
  for file in model.onnx tokens.txt lexicon.txt LICENSE; do
    [[ -s "$extracted/$file" ]] || { echo "ERROR: archive missing $file" >&2; exit 1; }
  done
  mv "$extracted" "$MODEL_DIR"
fi

archive_sha=not-retained
if [[ -f "$ARCHIVE" ]]; then
  archive_sha=$(python3 - "$ARCHIVE" <<'PY'
import hashlib, sys
digest = hashlib.sha256()
with open(sys.argv[1], 'rb') as stream:
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
        digest.update(chunk)
print(digest.hexdigest())
PY
)
fi
cat >"$MODEL_ROOT/MODEL_ASSET_INFO.txt" <<EOF
asset_set=customer-visit-tts
model=$MODEL_NAME
release=tts-models
source=$SOURCE_URL
upstream=https://huggingface.co/myshell-ai/MeloTTS-Chinese
license=MIT
archive_sha256=$archive_sha
archive_bytes=$EXPECTED_ARCHIVE_BYTES
sample_rate_hz=44100
prepared_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

python3 - "$MODEL_ROOT" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
paths = [path for path in (root / 'vits-melo-tts-zh_en').rglob('*') if path.is_file()]
paths.append(root / 'MODEL_ASSET_INFO.txt')
with (root / 'SHA256SUMS').open('w', encoding='utf-8') as output:
    for path in sorted(paths):
        output.write(f"{sha256(path)}  {path.relative_to(root).as_posix()}\n")
PY

rm -rf "$DOWNLOAD_DIR"
chmod -R a+rX,go-w "$MODEL_ROOT"
bash "$ROOT_DIR/deploy/check-tts-model.sh"
echo "Files: $(find "$MODEL_ROOT" -type f | wc -l | tr -d ' ')"
du -sh "$MODEL_DIR"
echo "SHA256 manifest: $MODEL_ROOT/SHA256SUMS"
