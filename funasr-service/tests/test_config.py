from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Settings


def test_defaults_to_cpu(monkeypatch):
    monkeypatch.delenv("FUNASR_DEVICE", raising=False)
    assert Settings.from_env().device == "cpu"


def test_cuda_requires_explicit_visible_device(monkeypatch):
    monkeypatch.setenv("FUNASR_DEVICE", "cuda:0")
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_concurrency_is_bounded(monkeypatch):
    monkeypatch.setenv("FUNASR_MAX_CONCURRENCY", "99")
    assert Settings.from_env().max_concurrency == 2
