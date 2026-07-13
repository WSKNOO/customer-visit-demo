"""Environment-only configuration for the offline CPU TTS service."""

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


@dataclass(frozen=True)
class Settings:
    model_file: Path
    tokens_file: Path
    lexicon_file: Path | None
    data_dir: Path | None
    num_threads: int
    max_text_chars: int
    speaker_id: int
    speed: float
    device: str

    @classmethod
    def from_env(cls) -> "Settings":
        model_dir = Path(os.getenv("TTS_MODEL_DIR", "/models/tts/vits-melo-tts-zh_en"))
        data_dir_value = os.getenv("TTS_DATA_DIR", "").strip()
        lexicon_value = os.getenv("TTS_LEXICON_FILE", str(model_dir / "lexicon.txt")).strip()
        device = os.getenv("TTS_DEVICE", "cpu").strip().lower()
        if device != "cpu":
            raise ValueError("TTS_DEVICE must be cpu")
        try:
            speed = float(os.getenv("TTS_SPEED", "1.0"))
        except ValueError as exc:
            raise ValueError("TTS_SPEED must be numeric") from exc
        return cls(
            model_file=Path(os.getenv("TTS_MODEL_FILE", str(model_dir / "model.onnx"))),
            tokens_file=Path(os.getenv("TTS_TOKENS_FILE", str(model_dir / "tokens.txt"))),
            lexicon_file=Path(lexicon_value) if lexicon_value else None,
            data_dir=Path(data_dir_value) if data_dir_value else None,
            num_threads=_bounded_int("TTS_NUM_THREADS", 8, 1, 16),
            max_text_chars=_bounded_int("TTS_MAX_TEXT_CHARS", 500, 20, 2000),
            speaker_id=_bounded_int("TTS_SPEAKER_ID", 0, 0, 1000),
            speed=min(2.0, max(0.5, speed)),
            device=device,
        )

    def model_status(self) -> dict[str, bool]:
        return {
            "model_exists": self.model_file.is_file(),
            "tokens_exist": self.tokens_file.is_file(),
            "lexicon_exists": self.lexicon_file is None or self.lexicon_file.is_file(),
            "data_dir_exists": self.data_dir is None or self.data_dir.is_dir(),
        }

    @property
    def model_files_ready(self) -> bool:
        return all(self.model_status().values())
