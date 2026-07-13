"""Safe audio validation and FFmpeg normalization."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path


class AudioValidationError(ValueError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


ALLOWED_FORMATS = {"wav", "webm", "ogg", "mp3", "pcm"}
MIME_FORMATS = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "application/octet-stream": "pcm",
}


def detect_format(data: bytes, content_type: str | None, format_hint: str | None) -> str:
    hint = (format_hint or "").strip().lower().lstrip(".")
    mime_format = MIME_FORMATS.get((content_type or "").split(";", 1)[0].strip().lower())
    detected = None
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        detected = "wav"
    elif data.startswith(b"\x1a\x45\xdf\xa3"):
        detected = "webm"
    elif data.startswith(b"OggS"):
        detected = "ogg"
    elif data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        detected = "mp3"
    elif hint == "pcm" and mime_format in {None, "pcm"}:
        detected = "pcm"
    if detected not in ALLOWED_FORMATS:
        raise AudioValidationError("ASR_AUDIO_FORMAT_UNSUPPORTED")
    if hint and hint != detected:
        raise AudioValidationError("ASR_AUDIO_FORMAT_MISMATCH")
    if mime_format and mime_format != detected:
        raise AudioValidationError("ASR_AUDIO_MIME_MISMATCH")
    return detected


def normalize_to_wav(input_path: Path, output_path: Path, source_format: str, timeout_seconds: int) -> None:
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
    ]
    if source_format == "pcm":
        command.extend(["-f", "s16le", "-ar", "16000", "-ac", "1"])
    command.extend([
        "-i", str(input_path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output_path),
    ])
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
    except FileNotFoundError as exc:
        raise AudioValidationError("ASR_FFMPEG_NOT_AVAILABLE") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioValidationError("ASR_AUDIO_CONVERSION_TIMEOUT") from exc
    except subprocess.CalledProcessError as exc:
        raise AudioValidationError("ASR_AUDIO_INVALID") from exc


def wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            if rate <= 0:
                raise AudioValidationError("ASR_AUDIO_INVALID")
            return round(frames / rate * 1000)
    except (wave.Error, EOFError) as exc:
        raise AudioValidationError("ASR_AUDIO_INVALID") from exc
