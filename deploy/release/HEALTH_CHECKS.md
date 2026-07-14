# 健康检查与验收

## 网关和陪练

```bash
curl -fsS http://127.0.0.1:18088/gateway-health
curl -fsS http://127.0.0.1:18088/training/api/health
curl -fsS http://127.0.0.1:18088/training/api/mode
```

## ASR

容器内接口：`GET /health`、`GET /models/status`、`POST /transcribe`。无模型时服务保持运行但 `/health` 返回 degraded/非 2xx；文字陪练不依赖该服务。

```bash
docker compose --profile asr exec -T funasr-service python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/models/status').read().decode())"
curl -fsS -X POST http://127.0.0.1:18088/training/api/asr/transcribe -F 'audio=@/path/to/approved-demo.wav' -F 'format=wav'
```

验收：`model_loaded=true`，转写响应 `success=true` 且 `text` 非空。

## TTS

容器内接口：`GET /health`、`GET /models/status`、`POST /tts`。不记录业务文本，返回 WAV；模型只加载一次，单实例串行合成。

```bash
docker compose --profile tts exec -T tts-service python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/models/status').read().decode())"
curl -fsS -X POST http://127.0.0.1:18088/training/api/tts -H 'Content-Type: application/json' -d '{"text":"你好，欢迎参加客户拜访AI陪练。"}' -o /tmp/demo.wav
file /tmp/demo.wav
```

验收：`model_loaded=true`，响应 `Content-Type: audio/wav`，文件非空且浏览器可播放。前端送入 TTS 前过滤 `<think>`、COACH、SCORE、REPORT 和 HTML 标签。

## 已验证与未验证边界

2026-07-14 已在 A 电脑完成真实 CPU 推理：FunASR 能从 WAV 返回中文文本；TTS 能加载外置 ONNX 模型并通过 HTTP 接口返回 44.1 kHz、单声道、16-bit PCM WAV。两个模型检查脚本均输出 `READY`。

本机没有 Docker，因此未执行镜像构建、Compose 运行态、服务器只读挂载、浏览器麦克风权限和服务器内部模型连通性。上述项目仍必须在服务器逐项验收。

特别注意：`http://192.168.240.14:18088` 不是 localhost，浏览器可能因非 HTTPS 安全上下文拒绝麦克风。必须使用现场设备实测录音权限；失败时使用文字输入，ASR 服务本身可用预录 WAV 通过 `test-asr.sh` 独立验证。
