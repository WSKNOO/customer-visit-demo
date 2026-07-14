# 环境变量说明

从 `deploy/.env.example` 复制为 `deploy/.env`，真实 API Key 只保存在服务器，权限设为 `600`。

## 明日入口与安全默认值

```dotenv
GATEWAY_PORT=18088
PUBLIC_ORIGIN=http://192.168.240.14:18088
TRAINING_MOCK_MODE=true
DEMO_MODE=true
ASR_ENABLED=false
TTS_ENABLED=false
```

## 内部大模型

```dotenv
TRAINING_MODEL_BASE_URL=
TRAINING_MODEL_NAME=
TRAINING_MODEL_API_KEY=
TRAINING_MODEL_ENABLE_THINKING=false
TRAINING_MODEL_MAX_TOKENS=1000
```

内部模型受控验证通过后，将 `TRAINING_MOCK_MODE=false`。`TRAINING_MODEL_BASE_URL` 应指向 OpenAI 兼容服务根地址；`NO_PROXY` 必须加入内部模型主机，避免误走公网代理。不要在命令行历史或日志中回显 API Key。

## 客户情报实时搜索

```dotenv
INTELLIGENCE_MOCK_MODE=false
SEARCH_MCP_ENGINE=sogou
SEARCH_MCP_PROXY=http://proxy-host:proxy-port
SEARCH_SERVICE_BASE_URL=https://www.sogou.com/web
SEARCH_MAX_FETCH_PAGES=20
SEARCH_MAX_DIMENSIONS=6
SEARCH_MAX_KEYWORDS_PER_DIMENSION=1
SEARCH_FETCH_CONTENT_ENABLED=false
SEARCH_SNIPPET_FALLBACK_ENABLED=true
```

容器不能使用宿主机的 `127.0.0.1` 代理地址，应填写容器可访问的代理主机/IP。显式搜索代理为空时会继承 `HTTPS_PROXY` 或 `HTTP_PROXY`。摘要模式不依赖浏览器爬虫；需要网页正文时才开启 `SEARCH_FETCH_CONTENT_ENABLED=true`，抓取失败仍回退到搜索摘要。

## 语音

```dotenv
ASR_ENABLED=true
ASR_PROVIDER=http
ASR_BASE_URL=http://funasr-service:8000
FUNASR_MODELS_DIR=/mnt/disk/models/funasr
ASR_DEVICE=cpu
FUNASR_ALLOW_MODEL_DOWNLOAD=false

TTS_ENABLED=true
TTS_PROVIDER=http
TTS_BASE_URL=http://tts-service:8001
TTS_MODELS_DIR=/mnt/disk/models/tts
TTS_DEVICE=cpu
TTS_NUM_THREADS=8
```

必须保持 `CUDA_VISIBLE_DEVICES=`。服务端无模型时保持开关为 `false`。

## 热更新

```dotenv
USE_HOT_COMPOSE=true
TRAINING_KNOWCARD_DIR=/mnt/disk/customer-visit-data/knowcard_output
```

陪练数据目录同样只读挂载；更新前先运行 `python3 deploy/validate-data.py "$TRAINING_KNOWCARD_DIR"`。
