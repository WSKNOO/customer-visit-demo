import os
import sys
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tts_config import Settings
from tts_engine import TTSEngine, samples_to_wav


class TTSCoreTests(unittest.TestCase):
    def test_missing_model_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("TTS_MODEL_DIR")
            try:
                os.environ["TTS_MODEL_DIR"] = directory
                settings = Settings.from_env()
                self.assertFalse(settings.model_files_ready)
            finally:
                if previous is None:
                    os.environ.pop("TTS_MODEL_DIR", None)
                else:
                    os.environ["TTS_MODEL_DIR"] = previous

    def test_pcm_wav_generation(self):
        content = samples_to_wav([0.0, 0.5, -0.5, 1.0, -1.0], 22050)
        with wave.open(BytesIO(content), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 22050)
            self.assertEqual(wav.getnframes(), 5)

    def test_engine_generates_wav_with_cpu_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("model.onnx", "tokens.txt", "lexicon.txt"):
                (root / name).write_bytes(b"test")
            settings = Settings(
                model_file=root / "model.onnx",
                tokens_file=root / "tokens.txt",
                lexicon_file=root / "lexicon.txt",
                data_dir=None,
                num_threads=2,
                max_text_chars=500,
                speaker_id=0,
                speed=1.0,
                device="cpu",
            )
            captured = {}

            class Config:
                def __init__(self, **kwargs):
                    captured.update(kwargs)

                def validate(self):
                    return True

            class OfflineTts:
                def __init__(self, _config):
                    pass

                def generate(self, text, sid, speed):
                    self.last_request = (text, sid, speed)
                    return SimpleNamespace(samples=[0.0, 0.25, -0.25], sample_rate=24000)

            fake_sherpa = SimpleNamespace(
                OfflineTtsVitsModelConfig=Config,
                OfflineTtsModelConfig=Config,
                OfflineTtsConfig=Config,
                OfflineTts=OfflineTts,
            )
            with patch.dict(sys.modules, {"sherpa_onnx": fake_sherpa}):
                engine = TTSEngine(settings)
                engine.load()
                generated = {
                    "zh": engine.synthesize("您好，欢迎参加客户拜访陪练。"),
                    "en": engine.synthesize("Welcome to the customer visit training."),
                    "mixed": engine.synthesize("欢迎参加 AI customer visit training。"),
                }

            self.assertEqual(captured["provider"], "cpu")
            for language, content in generated.items():
                with self.subTest(language=language), wave.open(BytesIO(content), "rb") as wav:
                    self.assertEqual(wav.getframerate(), 24000)
                    self.assertEqual(wav.getnframes(), 3)


if __name__ == "__main__":
    unittest.main()
