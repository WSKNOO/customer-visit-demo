"""Environment-only configuration for the offline FunASR service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return min(maximum, max(minimum, value))


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model_dir: Path
    vad_model_dir: Path
    punc_model_dir: Path
    device: str
    max_concurrency: int
    max_audio_seconds: int
    max_file_size_mb: int
    request_timeout_seconds: int
    allow_model_download: bool
    torch_threads: int

    @classmethod
    def from_env(cls) -> "Settings":
        device = os.getenv("FUNASR_DEVICE", "cpu").strip().lower()
        if device != "cpu" and not device.startswith("cuda:"):
            raise ValueError("FUNASR_DEVICE must be cpu or an explicit cuda:N device")
        if device.startswith("cuda:") and not os.getenv("CUDA_VISIBLE_DEVICES", "").strip():
            raise ValueError("CUDA_VISIBLE_DEVICES is required for GPU mode")
        return cls(
            model_dir=Path(os.getenv("FUNASR_MODEL_DIR", "/models/paraformer-zh")),
            vad_model_dir=Path(os.getenv("FUNASR_VAD_MODEL_DIR", "/models/fsmn-vad")),
            punc_model_dir=Path(os.getenv("FUNASR_PUNC_MODEL_DIR", "/models/ct-punc-c")),
            device=device,
            max_concurrency=_bounded_int("FUNASR_MAX_CONCURRENCY", 2, 1, 2),
            max_audio_seconds=_bounded_int("FUNASR_MAX_AUDIO_SECONDS", 120, 1, 600),
            max_file_size_mb=_bounded_int("FUNASR_MAX_FILE_SIZE_MB", 50, 1, 100),
            request_timeout_seconds=_bounded_int("FUNASR_REQUEST_TIMEOUT_SECONDS", 120, 5, 600),
            allow_model_download=_bool("FUNASR_ALLOW_MODEL_DOWNLOAD", False),
            torch_threads=_bounded_int("FUNASR_TORCH_THREADS", 16, 1, 32),
        )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def model_status(self) -> dict[str, bool]:
        return {
            "asr_model_exists": self.model_dir.is_dir() and any(self.model_dir.iterdir()),
            "vad_model_exists": self.vad_model_dir.is_dir() and any(self.vad_model_dir.iterdir()),
            "punc_model_exists": self.punc_model_dir.is_dir() and any(self.punc_model_dir.iterdir()),
        }
