from pathlib import Path
import wave
import sys

import pytest
from fastapi.testclient import TestClient


pytest.importorskip("multipart", reason="python-multipart is installed in the service image")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as service


def test_health_is_degraded_without_models(monkeypatch):
    def fail_load():
        service.engine.loaded = False
        service.engine.error_code = "ASR_MODEL_FILES_MISSING"
        raise service.ModelLoadError("ASR_MODEL_FILES_MISSING")

    monkeypatch.setattr(service.engine, "load", fail_load)
    with TestClient(service.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["error_code"] == "ASR_MODEL_FILES_MISSING"


def test_invalid_upload_is_rejected_without_inference(monkeypatch):
    monkeypatch.setattr(service.engine, "load", lambda: None)
    monkeypatch.setattr(service.engine, "loaded", True)
    with TestClient(service.app) as client:
        response = client.post("/transcribe", files={"file": ("bad.exe", b"not audio", "application/octet-stream")})
    assert response.status_code == 415
    assert response.json()["error_code"].startswith("ASR_AUDIO")


def test_wav_upload_returns_text_and_normalizes_to_16k_mono(monkeypatch):
    monkeypatch.setattr(service.engine, "load", lambda: None)
    monkeypatch.setattr(service.engine, "loaded", True)

    def fake_normalize(_input_path, output_path, _source_format, _timeout):
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\x00\x00" * 1600)

    monkeypatch.setattr(service, "normalize_to_wav", fake_normalize)
    monkeypatch.setattr(service.engine, "transcribe", lambda _path: "这是语音识别测试")
    wav_header = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"test"
    with TestClient(service.app) as client:
        response = client.post(
            "/transcribe",
            files={"file": ("demo.wav", wav_header, "audio/wav")},
            data={"format": "wav"},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["text"] == "这是语音识别测试"
