# Local FunASR Service

CPU-first, single-process HTTP wrapper for FunASR 1.3.1. Models are mounted read-only and are never downloaded at production startup.

Required model layout:

```text
/mnt/disk/models/funasr/
├── paraformer/
├── vad/
└── punc/
```

The three directories must contain complete ModelScope snapshots, including model configuration, weights and tokenizer files referenced by each model configuration. Copy an already verified cache; do not copy only weight files.

Approximate sizes vary by revision: Paraformer is commonly about 1 GB, FSMN VAD is several MB, and CT-PUNC may be hundreds of MB to about 1 GB. Verify with `du -sh` and a release checksum manifest. The CPU image is expected to be roughly 2–3 GB because it includes CPU PyTorch, FunASR and FFmpeg; model weights are not included.

Default runtime:

- Python 3.11
- FunASR 1.3.1, matching the audited legacy source
- CPU-only PyTorch 2.3.1
- one Uvicorn worker and one model instance
- 16 Torch/OMP/MKL threads
- at most two admitted requests, with inference serialized around the model instance

Multiple workers are intentionally prohibited: every worker would load another full model copy, multiply memory use, increase cold-start time and make CPU contention unpredictable. Scale only after measuring one instance with 8/16/24 threads.

WAV, WebM/Opus, Ogg/Opus and MP3 are normalized through FFmpeg. Raw signed 16-bit, 16 kHz, mono PCM is accepted only when `format=pcm` is explicitly supplied.

Production must keep `FUNASR_ALLOW_MODEL_DOWNLOAD=false` and `ASR_DEVICE=cpu`. `ASR_MODEL_DIR` points to the common root. `FUNASR_MODEL_DIR`, `FUNASR_VAD_MODEL_DIR` and `FUNASR_PUNC_MODEL_DIR` remain optional per-model overrides. Future GPU use requires an explicit `cuda:N` value and `CUDA_VISIBLE_DEVICES`; the service never auto-selects CUDA.

The service also recognizes the historical directory names `paraformer-zh`, `fsmn-vad` and `ct-punc-c` when the preferred names are absent. Retain the exact tested snapshot revision when copying its cache. Local paths are passed to `AutoModel` with updates disabled, so a complete local snapshot is required and startup never downloads missing content. The model is loaded once during process startup; use one worker.
