from pathlib import Path
import sys

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as service


def test_health_is_degraded_without_model(monkeypatch):
    def fail_load():
        service.engine.loaded = False
        service.engine.error_code = "TTS_MODEL_NOT_LOADED"
        raise service.ModelLoadError("TTS_MODEL_NOT_LOADED")

    monkeypatch.setattr(service.engine, "load", fail_load)
    with TestClient(service.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["model_loaded"] is False
    assert response.json()["device"] == "cpu"


def test_tts_returns_wav_from_loaded_singleton(monkeypatch):
    monkeypatch.setattr(service.engine, "load", lambda: None)
    monkeypatch.setattr(service.engine, "loaded", True)
    monkeypatch.setattr(service.engine, "synthesize", lambda _text: b"RIFF0000WAVEdata")
    with TestClient(service.app) as client:
        response = client.post("/tts", json={"text": "您好，欢迎参加客户拜访陪练。"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content.startswith(b"RIFF")
