#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_DIR=${FUNASR_MODELS_DIR:-$ROOT_DIR/models/funasr}
failed=0

fail() {
  echo "NOT_READY: $*" >&2
  failed=1
}

for name in paraformer vad punc; do
  dir="$MODEL_DIR/$name"
  [[ -d "$dir" ]] || { fail "missing directory: $dir"; continue; }
  [[ -r "$dir" && -x "$dir" ]] || fail "directory is not readable/searchable: $dir"
  for file in configuration.json config.yaml model.pt; do
    [[ -s "$dir/$file" ]] || fail "missing or empty file: $dir/$file"
  done
done

[[ -s "$MODEL_DIR/paraformer/seg_dict" ]] || fail "missing or empty file: $MODEL_DIR/paraformer/seg_dict"
if [[ -d "$MODEL_DIR" ]] && find "$MODEL_DIR" -name '*.incomplete' -print -quit | grep -q .; then
  fail "incomplete download marker exists under $MODEL_DIR"
fi

[[ -s "$MODEL_DIR/MODEL_ASSET_INFO.txt" ]] || fail "missing asset metadata: $MODEL_DIR/MODEL_ASSET_INFO.txt"
[[ -s "$MODEL_DIR/SHA256SUMS" ]] || fail "missing checksum manifest: $MODEL_DIR/SHA256SUMS"

if [[ -d "$MODEL_DIR" ]]; then
  if ! python3 - "$MODEL_DIR" <<'PY'
import os, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
for path in root.rglob('*'):
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise SystemExit(f"broken link: {path}")
    if root != resolved and root not in resolved.parents:
        raise SystemExit(f"path escapes model root: {path}")
    if path.is_file():
        if not os.access(path, os.R_OK):
            raise SystemExit(f"unreadable file: {path}")
        if path.stat().st_mode & 0o002:
            raise SystemExit(f"world-writable file: {path}")
PY
  then
    fail "unsafe model permissions or links"
  fi
fi

if [[ -s "$MODEL_DIR/SHA256SUMS" ]]; then
  if ! python3 - "$MODEL_DIR" <<'PY'
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
    actual = sha256(path)
    if actual != digest:
        raise SystemExit(f"checksum mismatch: {relative}")
PY
  then
    fail "SHA256 verification failed"
  fi
  if [[ "${FUNASR_SKIP_UPSTREAM_SHA_CHECK:-false}" != true ]]; then
    for expected in \
      "5bba782a5e9196166233b9ab12ba04cadff9ef9212b4ff6153ed9290ff679025  paraformer/model.pt" \
      "b3be75be477f0780277f3bae0fe489f48718f585f3a6e45d7dd1fbb1a4255fc5  vad/model.pt" \
      "a5818bb9d933805a916eebe41eb41648f7f9caad30b4bd59d56f3ca135421916  punc/model.pt"; do
      grep -Fqx "$expected" "$MODEL_DIR/SHA256SUMS" || fail "official model checksum is not present: ${expected#*  }"
    done
  fi
fi

if (( failed )); then
  echo "NOT_READY"
  exit 1
fi

echo "READY"
du -sh "$MODEL_DIR"
