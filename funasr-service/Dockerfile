FROM python:3.11-slim-bookworm

ARG DEBIAN_MIRROR=deb.debian.org
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CUDA_VISIBLE_DEVICES="" \
    FUNASR_DEVICE=cpu \
    OMP_NUM_THREADS=16 \
    MKL_NUM_THREADS=16

WORKDIR /app

RUN if [ "$DEBIAN_MIRROR" != "deb.debian.org" ]; then \
      sed -i "s|deb.debian.org|$DEBIAN_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url "$TORCH_INDEX_URL" torch==2.3.1 torchaudio==2.3.1 \
    && pip install --no-cache-dir -r requirements.txt

COPY app.py asr_engine.py audio_utils.py config.py ./

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
