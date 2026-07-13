"""Offline FunASR HTTP service. Audio is never retained after a request."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from asr_engine import ASREngine, ModelLoadError
from audio_utils import AudioValidationError, detect_format, normalize_to_wav, wav_duration_ms
from config import Settings


logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger(__name__)
settings = Settings.from_env()
engine = ASREngine(settings)
inference_slots = asyncio.Semaphore(settings.max_concurrency)


def failure(error_code: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "text": "", "error_code": error_code},
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await asyncio.to_thread(engine.load)
    except ModelLoadError:
        LOGGER.error("FunASR starts in degraded mode: %s", engine.error_code)
    yield


app = FastAPI(title="Local FunASR Service", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_error(_request, exc):
    LOGGER.error("Unhandled ASR service error: %s", type(exc).__name__)
    return failure("ASR_INTERNAL_ERROR", 500)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, _exc):
    return failure("ASR_REQUEST_INVALID", 400)


@app.get("/health")
async def health():
    ready = engine.loaded
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "degraded",
            "model_loaded": ready,
            "device": settings.device,
            "provider": engine.provider,
            "error_code": None if ready else (engine.error_code or "ASR_MODEL_NOT_LOADED"),
        },
    )


@app.get("/models/status")
async def models_status():
    status = settings.model_status()
    return {
        **status,
        "model_loaded": engine.loaded,
        "warmup_completed": engine.loaded,
        "error_code": engine.error_code,
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("zh"),
    format: str | None = Form(None),
):
    del language  # Paraformer Chinese model is fixed for this first release.
    data = await file.read(settings.max_file_size_bytes + 1)
    await file.close()
    if not data:
        return failure("ASR_AUDIO_EMPTY", 400)
    if len(data) > settings.max_file_size_bytes:
        return failure("ASR_FILE_TOO_LARGE", 413)
    try:
        source_format = detect_format(data, file.content_type, format)
        if not engine.loaded:
            return failure("ASR_MODEL_NOT_LOADED", 503)
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="funasr_") as temp_dir:
            input_path = Path(temp_dir) / f"input.{source_format}"
            wav_path = Path(temp_dir) / "normalized.wav"
            input_path.write_bytes(data)
            normalize_to_wav(input_path, wav_path, source_format, settings.request_timeout_seconds)
            audio_duration_ms = wav_duration_ms(wav_path)
            if audio_duration_ms > settings.max_audio_seconds * 1000:
                return failure("ASR_AUDIO_TOO_LONG", 413)
            acquired = False
            try:
                await asyncio.wait_for(inference_slots.acquire(), timeout=settings.request_timeout_seconds)
                acquired = True
                text = await asyncio.wait_for(
                    asyncio.to_thread(engine.transcribe, wav_path),
                    timeout=settings.request_timeout_seconds,
                )
            finally:
                if acquired:
                    inference_slots.release()
        duration_ms = round((time.perf_counter() - started) * 1000)
        if not text:
            return failure("ASR_NO_SPEECH", 422)
        return {
            "success": True,
            "text": text,
            "duration_ms": duration_ms,
            "audio_duration_ms": audio_duration_ms,
            "audio_duration_seconds": round(audio_duration_ms / 1000, 3),
            "rtf": round(duration_ms / max(audio_duration_ms, 1), 4),
            "model": engine.model_name,
            "request_id": uuid.uuid4().hex,
            "error_code": None,
        }
    except AudioValidationError as exc:
        return failure(exc.error_code, 415)
    except asyncio.TimeoutError:
        return failure("ASR_REQUEST_TIMEOUT", 504)
    except ModelLoadError as exc:
        return failure(str(exc), 503)
