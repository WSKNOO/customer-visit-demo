"""Single-instance, CPU-first FunASR inference engine."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from config import Settings


LOGGER = logging.getLogger(__name__)


class ModelLoadError(RuntimeError):
    pass


class ASREngine:
    provider = "funasr-local"
    model_name = "paraformer-zh"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = None
        self.loaded = False
        self.error_code: str | None = None
        self.load_duration_ms: int | None = None
        self._inference_lock = threading.Lock()

    def load(self) -> None:
        started = time.perf_counter()
        status = self.settings.model_status()
        if not all(status.values()):
            self.error_code = "ASR_MODEL_FILES_MISSING"
            raise ModelLoadError(self.error_code)
        if self.settings.allow_model_download:
            LOGGER.warning("Model download flag is enabled, but local model directories remain mandatory")
        try:
            import torch
            from funasr import AutoModel

            torch.set_num_threads(self.settings.torch_threads)
            if hasattr(torch, "set_num_interop_threads"):
                try:
                    torch.set_num_interop_threads(min(4, self.settings.torch_threads))
                except RuntimeError:
                    pass
            self.model = AutoModel(
                model=str(self.settings.model_dir),
                vad_model=str(self.settings.vad_model_dir),
                punc_model=str(self.settings.punc_model_dir),
                device=self.settings.device,
                disable_update=True,
                disable_pbar=True,
            )
            self.loaded = True
            self.error_code = None
            self.load_duration_ms = round((time.perf_counter() - started) * 1000)
            self.warmup()
        except ModelLoadError:
            raise
        except Exception as exc:
            LOGGER.error("FunASR model initialization failed: %s", type(exc).__name__)
            self.error_code = "ASR_MODEL_LOAD_FAILED"
            raise ModelLoadError(self.error_code) from exc

    def warmup(self) -> None:
        if not self.loaded or self.model is None:
            return
        try:
            import numpy as np

            silence = np.zeros(16000, dtype="float32")
            with self._inference_lock:
                self.model.generate(input=silence, batch_size_s=60)
        except Exception as exc:
            LOGGER.warning("FunASR warmup did not complete: %s", type(exc).__name__)

    def transcribe(self, wav_path: Path) -> str:
        if not self.loaded or self.model is None:
            raise ModelLoadError("ASR_MODEL_NOT_LOADED")
        with self._inference_lock:
            result = self.model.generate(input=str(wav_path), batch_size_s=60)
        if not result:
            return ""
        first = result[0] if isinstance(result, list) else result
        if isinstance(first, dict):
            return str(first.get("text", "")).strip()
        return str(first).strip()
