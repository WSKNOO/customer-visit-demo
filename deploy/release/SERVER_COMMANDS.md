# 服务器执行命令

以下命令在项目 `deploy/` 目录执行。先备份现有 `.env`，不要覆盖未知配置。

## 1. 预检

```bash
cd /path/to/customer-visit-demo/deploy
cp -p .env ".env.before-release.$(date +%Y%m%d-%H%M%S)"
chmod 600 .env
bash check-server.sh
docker compose config --quiet
```

## 2. 先启动稳定文字版

```bash
ASR_ENABLED=false TTS_ENABLED=false docker compose up -d --remove-orphans
curl -fsS http://127.0.0.1:18088/gateway-health
curl -fsS http://127.0.0.1:18088/training/api/health
bash test-training.sh
```

## 3. 启用 ASR

前提：`check-funasr-model.sh` 输出 `READY`。

```bash
docker compose --profile asr up -d funasr-service ai-training
docker compose --profile asr exec -T funasr-service python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/models/status').read().decode())"
BASE_URL=http://127.0.0.1:18088 bash test-asr.sh /path/to/approved-demo.wav
```

## 4. 启用 TTS

前提：`check-tts-model.sh` 输出 `READY`，且服务器已有 `deploy-tts-service` 镜像。

```bash
docker compose --profile tts up -d tts-service ai-training
docker compose --profile tts exec -T tts-service python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/models/status').read().decode())"
BASE_URL=http://127.0.0.1:18088 bash test-tts.sh
```

## 5. 完整链路

```bash
BASE_URL=http://127.0.0.1:18088 bash test-voice-chain.sh /path/to/approved-demo.wav
docker compose ps
```

若使用热更新：

```bash
docker compose -f docker-compose.yml -f docker-compose.hot.yml --profile asr --profile tts up -d
```
