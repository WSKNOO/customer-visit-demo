# Offline CPU TTS service

This service exposes sherpa-onnx OfflineTts/VITS through `POST /tts`. Runtime inference is fully offline, uses the CPU provider, never downloads a model, and starts in `degraded` state when model files are absent.

Expected read-only model layout:

```text
/mnt/disk/models/tts/vits-melo-tts-zh_en/
├── model.onnx
├── tokens.txt
├── lexicon.txt       # set TTS_LEXICON_FILE= when the converted model does not use it
└── espeak-ng-data/   # optional; set TTS_DATA_DIR when the selected model requires it
```

The model package must be obtained through the organization's approved offline software/model process. Keep its original license and checksum record. Do not add model files to Git or the Docker image.

```bash
curl -fsS http://127.0.0.1:8001/health
curl -fsS -X POST http://127.0.0.1:8001/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"你好，欢迎参加客户拜访AI陪练"}' \
  --output speech.wav
python3 -c "import wave; w=wave.open('speech.wav'); print(w.getparams()); w.close()"
```

Supported environment variables are `TTS_MODEL_DIR`, `TTS_MODEL_FILE`, `TTS_TOKENS_FILE`, `TTS_LEXICON_FILE`, `TTS_DATA_DIR`, `TTS_DEVICE`, `TTS_NUM_THREADS`, `TTS_MAX_TEXT_CHARS`, `TTS_SPEAKER_ID`, and `TTS_SPEED`. `TTS_DEVICE` only accepts `cpu`; the runtime provider is never auto-selected. The model loads once at startup and requests are serialized through that instance.
