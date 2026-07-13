"""Offline, CPU-only VITS TTS HTTP service."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from tts_config import Settings
from tts_engine import ModelLoadError, TTSEngine


logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger(__name__)
settings = Settings.from_env()
engine = TTSEngine(settings)
synthesis_slot = asyncio.Semaphore(1)


class TTSRequest(BaseModel):
    text: str


def failure(error_code: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error_code": error_code})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await asyncio.to_thread(engine.load)
    except ModelLoadError:
        LOGGER.error("TTS starts in degraded mode: %s", engine.error_code)
    yield


app = FastAPI(title="Offline CPU TTS Service", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, _exc):
    return failure("TTS_REQUEST_INVALID", 400)


@app.exception_handler(Exception)
async def unhandled_error(_request, exc):
    LOGGER.error("Unhandled TTS service error: %s", type(exc).__name__)
    return failure("TTS_INTERNAL_ERROR", 500)


@app.get("/health")
async def health():
    ready = engine.loaded
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "degraded",
            "model_loaded": ready,
            "device": settings.device,
            "provider": "cpu",
            "engine": "sherpa-onnx-vits",
            "error_code": None if ready else (engine.error_code or "TTS_MODEL_NOT_LOADED"),
        },
    )


@app.get("/models/status")
async def models_status():
    return {
        **settings.model_status(),
        "model_loaded": engine.loaded,
        "device": settings.device,
        "provider": "cpu",
        "error_code": engine.error_code,
    }


@app.post("/tts")
async def synthesize(payload: TTSRequest):
    text = payload.text.strip()
    if not text:
        return failure("TTS_TEXT_REQUIRED", 400)
    if len(text) > settings.max_text_chars:
        return failure("TTS_TEXT_TOO_LONG", 413)
    if not engine.loaded:
        return failure("TTS_MODEL_NOT_LOADED", 503)
    try:
        async with synthesis_slot:
            wav = await asyncio.to_thread(engine.synthesize, text)
        return Response(
            content=wav,
            media_type="audio/wav",
            headers={"Content-Disposition": 'inline; filename="speech.wav"', "Cache-Control": "no-store"},
        )
    except ModelLoadError:
        return failure("TTS_MODEL_NOT_LOADED", 503)
    except Exception as exc:
        LOGGER.error("TTS synthesis failed: %s", type(exc).__name__)
        return failure("TTS_SYNTHESIS_FAILED", 500)
