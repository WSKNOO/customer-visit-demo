"""Small sherpa-onnx OfflineTts adapter with a fixed CPU provider."""

from __future__ import annotations

import io
import logging
import threading
import wave
from array import array

from tts_config import Settings


LOGGER = logging.getLogger(__name__)


class ModelLoadError(RuntimeError):
    pass


def samples_to_wav(samples, sample_rate: int) -> bytes:
    pcm = array("h", (max(-32768, min(32767, round(float(value) * 32767))) for value in samples))
    if pcm.itemsize != 2:
        raise RuntimeError("Unexpected PCM sample width")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return output.getvalue()


class TTSEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = None
        self.loaded = False
        self.error_code: str | None = None
        self._lock = threading.Lock()

    def load(self) -> None:
        if not self.settings.model_files_ready:
            self.error_code = "TTS_MODEL_NOT_FOUND"
            raise ModelLoadError(self.error_code)
        try:
            import sherpa_onnx

            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(self.settings.model_file),
                lexicon=str(self.settings.lexicon_file or ""),
                tokens=str(self.settings.tokens_file),
                data_dir=str(self.settings.data_dir or ""),
            )
            model = sherpa_onnx.OfflineTtsModelConfig(
                vits=vits,
                num_threads=self.settings.num_threads,
                debug=False,
                provider="cpu",
            )
            config = sherpa_onnx.OfflineTtsConfig(
                model=model,
                max_num_sentences=1,
            )
            if hasattr(config, "validate") and not config.validate():
                raise RuntimeError("Invalid sherpa-onnx TTS configuration")
            self.engine = sherpa_onnx.OfflineTts(config)
            self.loaded = True
            self.error_code = None
        except Exception as exc:
            self.engine = None
            self.loaded = False
            self.error_code = "TTS_MODEL_LOAD_FAILED"
            LOGGER.error("Offline TTS model load failed: %s", type(exc).__name__)
            raise ModelLoadError(self.error_code) from exc

    def synthesize(self, text: str) -> bytes:
        if not self.loaded or self.engine is None:
            raise ModelLoadError(self.error_code or "TTS_MODEL_NOT_LOADED")
        with self._lock:
            audio = self.engine.generate(
                text,
                sid=self.settings.speaker_id,
                speed=self.settings.speed,
            )
        if audio is None or getattr(audio, "samples", None) is None:
            raise RuntimeError("TTS returned no audio")
        samples = audio.samples
        if len(samples) == 0 or int(audio.sample_rate) <= 0:
            raise RuntimeError("TTS returned empty audio")
        return samples_to_wav(samples, int(audio.sample_rate))
