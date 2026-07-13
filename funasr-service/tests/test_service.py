from pathlib import Path
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
