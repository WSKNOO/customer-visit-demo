#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_ROOT=${TTS_MODELS_DIR:-$ROOT_DIR/models/tts}
MODEL_DIR="$MODEL_ROOT/vits-melo-tts-zh_en"
failed=0

fail() {
  echo "NOT_READY: $*" >&2
  failed=1
}

[[ -d "$MODEL_DIR" ]] || fail "missing directory: $MODEL_DIR"
for file in model.onnx tokens.txt lexicon.txt LICENSE; do
  [[ -s "$MODEL_DIR/$file" ]] || fail "missing or empty file: $MODEL_DIR/$file"
done
[[ -s "$MODEL_ROOT/MODEL_ASSET_INFO.txt" ]] || fail "missing asset metadata: $MODEL_ROOT/MODEL_ASSET_INFO.txt"
[[ -s "$MODEL_ROOT/SHA256SUMS" ]] || fail "missing checksum manifest: $MODEL_ROOT/SHA256SUMS"

if [[ -f "$MODEL_DIR/model.onnx" ]]; then
  bytes=$(python3 -c 'import os,sys; print(os.path.getsize(sys.argv[1]))' "$MODEL_DIR/model.onnx")
  (( bytes >= 100000000 )) || fail "model.onnx is unexpectedly small: $bytes bytes"
fi

if [[ -d "$MODEL_ROOT" ]]; then
  if ! python3 - "$MODEL_ROOT" <<'PY'
import os, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
for path in root.rglob('*'):
    resolved = path.resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise SystemExit(f"path escapes model root: {path}")
    if path.is_file() and (not os.access(path, os.R_OK) or path.stat().st_mode & 0o002):
        raise SystemExit(f"unsafe file permissions: {path}")
PY
  then
    fail "unsafe model permissions or links"
  fi
fi

if [[ -s "$MODEL_ROOT/SHA256SUMS" ]]; then
  if ! python3 - "$MODEL_ROOT" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
for line in (root / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    digest, relative = line.split('  ', 1)
    path = (root / relative).resolve()
    if root not in path.parents:
        raise SystemExit(f"checksum path escapes root: {relative}")
    if sha256(path) != digest:
        raise SystemExit(f"checksum mismatch: {relative}")
PY
  then
    fail "SHA256 verification failed"
  fi
fi

if (( failed )); then
  echo "NOT_READY"
  exit 1
fi

echo "READY"
du -sh "$MODEL_DIR"
