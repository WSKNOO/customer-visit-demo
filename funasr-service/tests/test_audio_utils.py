from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_utils import AudioValidationError, detect_format


def test_detects_wav_header():
    data = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 20
    assert detect_format(data, "audio/wav", "wav") == "wav"


def test_detects_webm_header():
    assert detect_format(b"\x1a\x45\xdf\xa3payload", "audio/webm", "webm") == "webm"


def test_detects_ogg_header():
    assert detect_format(b"OggSpayload", "audio/ogg", "ogg") == "ogg"


def test_rejects_mismatched_hint():
    with pytest.raises(AudioValidationError) as exc:
        detect_format(b"\x1a\x45\xdf\xa3payload", "audio/webm", "wav")
    assert exc.value.error_code == "ASR_AUDIO_FORMAT_MISMATCH"


def test_pcm_requires_explicit_hint():
    with pytest.raises(AudioValidationError):
        detect_format(b"\x00" * 20, "application/octet-stream", None)
    assert detect_format(b"\x00" * 20, "application/octet-stream", "pcm") == "pcm"
