# AI 陪练与本地 FunASR 部署手册

## 1. 目标状态

- 情报助手继续使用原有业务逻辑，默认保持 Mock。
- AI 陪练支持 OpenAI Chat Completions 兼容网关；Qwen3 默认 `enable_thinking=false`。
- 本地语音识别是独立、单进程、CPU-only 服务；其故障不阻塞文字陪练。
- 陪练数据与模型权重均从宿主机只读挂载，镜像不包含模型权重。
- 默认 Compose 不启用语音；设置 `ASR_ENABLED=true`/`TTS_ENABLED=true` 并启用对应 profile 才启动语音服务。

## 2. 版本、镜像和 Windows 离线构建

在 PowerShell 中从项目根目录执行（示例版本需替换）：

```powershell
$env:IMAGE_TAG="20260713-v2"
$env:AI_TRAINING_IMAGE="deploy-ai-training"
$env:FUNASR_IMAGE="deploy-funasr-service"
docker compose -f deploy/docker-compose.yml build ai-training funasr-service
docker save -o E:\customer-visit-ai-training-20260713-v2.tar deploy-ai-training:20260713-v2
docker save -o E:\customer-visit-funasr-20260713-v2.tar deploy-funasr-service:20260713-v2
```

如果 Debian 官方源不可达，可在构建前设置 `DEBIAN_MIRROR=mirrors.aliyun.com`。只有 `requirements.txt`、Dockerfile、apt 系统包、Python 新依赖、Torch/FunASR/FFmpeg 版本变化才必须重建镜像。此次首次升级两个镜像都需构建；后续只导出实际变化的镜像。

预计 CPU FunASR 镜像约 2–3 GiB，具体以 `docker images` 为准；模型不在镜像中。AI 陪练镜像需重建一次以包含 `model_client.py` 和新后端代码。

## 3. 模型离线准备

模型不进入 Git、不复制进镜像。A 电脑联网准备并校验，B 电脑只传输生成的模型包，生产服务器不联网下载。

| 目录 | 官方资产 | 固定版本 | License | 典型体积 |
|---|---|---|---|---:|
| `funasr/paraformer` | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | `v2.0.4` | Apache-2.0 | 根文件约 889 MB |
| `funasr/vad` | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` | `v2.0.4` | Apache-2.0 | 根文件约 1.74 MB |
| `funasr/punc` | `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch` | `v2.0.4` | Apache-2.0 | 根文件约 296 MB |
| `tts/vits-melo-tts-zh_en` | sherpa-onnx 维护者发布的 Hugging Face 仓库 | 当前仓库快照 | MIT | 四个运行文件约 169 MiB |

ModelScope `v2.0.4` 元数据中的主权重校验值：

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| `paraformer/model.pt` | 880,502,012 | `5bba782a5e9196166233b9ab12ba04cadff9ef9212b4ff6153ed9290ff679025` |
| `vad/model.pt` | 1,721,366 | `b3be75be477f0780277f3bae0fe489f48718f585f3a6e45d7dd1fbb1a4255fc5` |
| `punc/model.pt` | 291,979,892 | `a5818bb9d933805a916eebe41eb41648f7f9caad30b4bd59d56f3ca135421916` |

TTS 准备脚本默认从 sherpa-onnx 维护者的 Hugging Face 仓库下载四个运行必需文件，并在 A 电脑生成逐文件 SHA256 清单。旧版 GitHub release archive（167,006,755 字节）仅作为可选备用源，可通过 `TTS_MODEL_SOURCE=github` 选择。

### A 电脑：下载、检查、打包

```bash
cd /path/to/customer-visit-demo

# FunASR 使用官方 ModelScope CLI；也可复用已构建的 funasr-service 镜像。
# python3 -m pip install --user 'modelscope>=1.15,<2'
bash deploy/prepare-funasr-model.sh

# TTS 默认从 sherpa-onnx 维护者的 Hugging Face 仓库下载；GitHub release 可作备用。
bash deploy/prepare-tts-model.sh

bash deploy/check-funasr-model.sh
bash deploy/check-tts-model.sh
bash deploy/package-models.sh
ls -lh customer-visit-models.tar.gz customer-visit-models.tar.gz.sha256
```

2026-07-14 本机实测结果：两个检查脚本均输出 `READY`；FunASR 使用 CPU 完成中文 WAV 转写，TTS 使用 CPU 生成 44.1 kHz 单声道 PCM WAV。已生成的模型包 SHA256 为 `bf6394c00547e794c237444bcad1f6d85466a7fe983b44f3469cda0bc315bdef`。这只证明 A 电脑模型资产与本机 Python 推理可用，不代表 Docker、服务器挂载或浏览器链路已经验收。

输出结构：

```text
models/
├── funasr/
│   ├── paraformer/
│   ├── vad/
│   ├── punc/
│   ├── MODEL_ASSET_INFO.txt
│   └── SHA256SUMS
└── tts/
    ├── vits-melo-tts-zh_en/
    ├── MODEL_ASSET_INFO.txt
    └── SHA256SUMS
```

准备脚本不会覆盖完整模型；半下载内容保存在忽略目录 `.downloads`。检查脚本会验证关键文件、路径逃逸、可读权限、world-writable 权限和所有 SHA256。

Compose 将宿主机 `/mnt/disk/models/funasr` 和 `/mnt/disk/models/tts` 分别只读挂载到容器同名目录。宿主机目录不存在时 Docker 可创建空目录，语音服务仍会启动但 `/health` 返回 `degraded`；模型完整且加载成功后 `/health` 返回 `status=ok`、`model_loaded=true`。AI 陪练不依赖两个语音容器健康才能启动。

### B 电脑与服务器：只传模型包

```bash
# B 电脑：通过批准的传输通道上传，不用 Git 获取模型。
scp customer-visit-models.tar.gz customer-visit-models.tar.gz.sha256 user@server:/mnt/disk/

# 服务器：先核对传输包，再解压到统一目录。
cd /mnt/disk
sha256sum -c customer-visit-models.tar.gz.sha256
mkdir -p /mnt/disk/models
tar -xzf customer-visit-models.tar.gz -C /mnt/disk/

cd /mnt/disk/customer-visit-demo
FUNASR_MODELS_DIR=/mnt/disk/models/funasr bash deploy/check-funasr-model.sh
TTS_MODELS_DIR=/mnt/disk/models/tts bash deploy/check-tts-model.sh
```

默认 16 个 Torch/OMP/MKL 线程、最多接纳 2 个请求，但模型推理段串行化。这样允许一个请求预处理时另一个排队，又不会让同一模型实例并发进入不确定状态。应使用 8/16/24 线程做实测后再调整。禁止多 Uvicorn/Gunicorn worker，因为每个 worker 都会重复加载模型、成倍占用内存并造成 CPU 争抢。

## 4. 服务器首次升级

服务器目录约定：

```text
/mnt/disk/customer-visit-demo
/mnt/disk/customer-visit-demo-package
/mnt/disk/models/funasr
/mnt/disk/models/tts
/mnt/disk/customer-visit-demo-data/knowcard_output/current
```

逐步执行：

```bash
cd /mnt/disk/customer-visit-demo
mkdir -p deploy/backups/$(date +%Y%m%d-%H%M%S)
cp -p deploy/.env deploy/backups/$(date +%Y%m%d-%H%M%S)/env.backup
chmod 600 deploy/.env deploy/backups/*/env.backup

docker load -i /mnt/disk/customer-visit-demo-package/customer-visit-ai-training-20260713-v2.tar
docker load -i /mnt/disk/customer-visit-demo-package/customer-visit-funasr-20260713-v2.tar
docker load -i /mnt/disk/customer-visit-demo-package/customer-visit-tts-20260714-tts.tar

python3 deploy/validate-data.py /mnt/disk/customer-visit-demo-data/knowcard_output/current
FUNASR_MODELS_DIR=/mnt/disk/models/funasr bash deploy/check-funasr-model.sh
TTS_MODELS_DIR=/mnt/disk/models/tts bash deploy/check-tts-model.sh
bash deploy/check-server.sh
cd deploy
docker compose config --quiet
docker compose --profile asr --profile tts up -d funasr-service tts-service ai-training
docker compose up -d unified-portal customer-intelligence-api customer-intelligence-frontend nginx
docker compose --profile asr --profile tts ps
curl -fsS http://127.0.0.1:${GATEWAY_PORT:-18088}/api/health
curl -sS http://127.0.0.1:${GATEWAY_PORT:-18088}/api/asr/status
```

正式 `.env` 至少设置：镜像名称和 tag、`TRAINING_KNOWCARD_DIR`、`FUNASR_MODELS_DIR=/mnt/disk/models/funasr`、`TTS_MODELS_DIR=/mnt/disk/models/tts`、ASR/TTS 开关和内部地址、模型网关三项配置。不要写占位字符串；Mock 关闭时无效配置会使健康检查返回 `MODEL_CONFIG_INVALID`。

当前仓库数据校验会阻止更新，因为 `解决方案/数智省分-工业事业部-数字工厂-智慧仓储` 是完全空目录。发布数据前应由数据负责人补齐 `scene_card.json` 或从 release 中排除该空场景；另有缺少可选知识卡的场景会作为 warning 报告。

## 5. HTTPS 与浏览器麦克风

远程 `http://192.168.240.14:18088` 不是浏览器安全上下文，不能作为稳定麦克风入口。正式方案应为内部 DNS 名称申请企业内部 CA 或正式 CA 证书，将 `server.crt`、`server.key` 放到服务器 `deploy/certs/`（不提交 Git），然后：

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d nginx
```

内部 CA 的根证书必须通过组织批准的方式导入客户端信任库。HTTPS 配置将 HTTP 跳转到 HTTPS、允许 50 MiB WebM 上传并设置 150 秒 ASR 超时，不暴露 FunASR 端口。Chrome 关闭安全策略只能用于临时诊断，不是部署方案。

## 6. 后续免 `docker save` 更新

- Prompt/Python：启用 `USE_HOT_COMPOSE=true`，同步代码后执行 `bash deploy/update-server.sh ai-training`；Python 代码变更需重启容器。
- 客户情报搜索：热覆盖会只读挂载 `research_cli.py`、`config.yaml` 和 `search_mcp/`。修改代理或搜索开关后重新创建 `customer-intelligence-api`，然后执行 `bash deploy/test-intelligence-search.sh`。
- HTML/CSS/JavaScript：同步 `static/`，重启 `ai-training` 以清理运行态；浏览器强制刷新。
- 陪练数据：准备新 release，先运行 `validate-data.py`，原子切换 `current` 软链接，再执行 `bash deploy/update-server.sh data`。
- FunASR 代码：同步 `funasr-service/*.py`，执行 `bash deploy/update-server.sh funasr-service`。新增依赖时仍须重建镜像。
- FunASR/TTS 模型：在 A 电脑重新运行准备与打包脚本，服务器校验并更新 `/mnt/disk/models` 后重启对应语音服务；模型变化不重建镜像。
- TTS 代码：同步 `tts-service/` 后重启 `tts-service`；依赖变化仍需重建镜像。
- 环境变量：备份并修改 `deploy/.env`，执行 `docker compose config --quiet` 后重建对应容器（`up -d --force-recreate`）。
- Nginx：修改并执行 `nginx -t`（容器内）后重启 nginx；配置文件挂载无需重建镜像。

热更新覆盖文件仅用于内网开发/演示维护，不作为正式生产默认。生产发布应使用版本化镜像。

演示维护环境可叠加 `deploy/docker-compose.hot.yml`。它只读挂载客户情报搜索代码、AI 陪练代码、静态页面、陪练数据、FunASR/TTS 服务代码和 `/mnt/disk/models` 下的模型，因此修改 Prompt、Python、前端、数据、模型或 `.env` 后无需 `docker save/load`，但 Python、模型或环境变量变化后仍需重启对应容器：

```bash
cd /mnt/disk/customer-visit-demo/deploy
docker compose -f docker-compose.yml -f docker-compose.hot.yml --profile asr --profile tts config --quiet
docker compose -f docker-compose.yml -f docker-compose.hot.yml --profile asr --profile tts up -d --no-deps --force-recreate ai-training funasr-service tts-service
```

`requirements.txt`、Dockerfile、系统包或运行时依赖发生变化时必须重建镜像，不能用热挂载代替。

## 7. 验证与性能测试

```bash
bash deploy/test-training.sh
bash deploy/test-intelligence-search.sh '中国电信 数字化 最新动态'
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.asr-debug.yml --profile asr up -d funasr-service
bash deploy/test-asr.sh /path/to/anonymous-test.webm
bash deploy/test-tts.sh
bash deploy/test-voice-chain.sh /path/to/anonymous-test.webm
bash deploy/benchmark-funasr.sh /path/to/anonymous-at-least-60s.wav
```

性能脚本输出 10/30/60 秒样本的实耗时，并配合接口返回的 RTF 和 `docker stats` 记录 CPU/内存。首次模型加载耗时由 `/models/status` 与容器日志确认；重复请求记录热启动耗时。不得使用含客户隐私的录音。

## 8. 回滚

优先保留上一镜像 tag、代码目录和数据/model release：

1. ASR 故障：在 `.env` 设置 `ASR_ENABLED=false`，重新创建 `ai-training`；文字陪练继续可用。
2. 数据故障：把 `knowcard_output/current` 原子切回上一 release，运行校验并重启 `ai-training`。
3. 模型故障：恢复上一份 `/mnt/disk/models` 备份，重新运行两个检查脚本并重启语音服务。
4. 镜像故障：将 `IMAGE_TAG` 或单独镜像变量切回上一 tag，执行 `docker compose up -d --no-deps ai-training funasr-service`。
5. 环境故障：执行 `bash deploy/rollback-server.sh deploy/backups/<timestamp>` 恢复备份 `.env`。

回滚前后都执行 `docker compose config --quiet`、健康检查和三轮文字陪练。FunASR 不健康时不要阻塞恢复文字主链路。

## 9. 可选离线 TTS

`tts-service` 使用 sherpa-onnx OfflineTts/VITS，固定 CPU provider，不包含模型、不自动下载，也不暴露宿主机端口。AI 陪练仅通过内部 HTTP 调用它；服务缺失、模型缺失、超时或推理失败均不会阻塞文字陪练。

准备脚本会把经过许可证和校验记录的中文 VITS 模型放到：

```text
/mnt/disk/models/tts/vits-melo-tts-zh_en/model.onnx
/mnt/disk/models/tts/vits-melo-tts-zh_en/tokens.txt
/mnt/disk/models/tts/vits-melo-tts-zh_en/lexicon.txt
/mnt/disk/models/tts/vits-melo-tts-zh_en/LICENSE
```

`.env` 设置：

```dotenv
TTS_ENABLED=true
TTS_PROVIDER=http
TTS_BASE_URL=http://tts-service:8001
TTS_MODELS_DIR=/mnt/disk/models/tts
TTS_DATA_DIR=
TTS_DEVICE=cpu
TTS_NUM_THREADS=8
TTS_SPEED=1.0
```

该模型已在 CPU 上使用上述四个文件完成真实中文 WAV 生成，保持 `TTS_DATA_DIR=`。首次离线部署需在 Windows 构建并导出 `tts-service` 镜像；服务器只执行 `docker load`：

```powershell
$env:IMAGE_TAG="20260714-tts"
$env:TTS_IMAGE="deploy-tts-service"
docker compose -f deploy/docker-compose.yml --profile tts build tts-service
docker save -o E:\customer-visit-tts-20260714-tts.tar deploy-tts-service:20260714-tts
```

```bash
docker load -i /mnt/disk/customer-visit-demo-package/customer-visit-tts-20260714-tts.tar
cd /mnt/disk/customer-visit-demo/deploy
docker compose --profile tts config --quiet
docker compose --profile tts up -d --no-deps tts-service
docker compose up -d --no-deps --force-recreate ai-training
docker compose --profile tts ps tts-service
docker compose --profile tts exec -T tts-service python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/health').read().decode())"
bash test-tts.sh
```

停用或回滚只需设置 `TTS_ENABLED=false` 并重新创建 `ai-training`；随后可停止 `tts-service`。前端会立即恢复为纯文字模式。页面默认不自动播放；用户点击每条客户回复下方的“播放语音”后才合成。

## 10. 领导演示模式

明天演示建议在 `deploy/.env` 设置：

```dotenv
DEMO_MODE=true
DEMO_SCENE_ID=knowcard/标品/省产品运营中心-安全大脑
TRAINING_MOCK_MODE=false
ASR_ENABLED=true
ASR_PROVIDER=http
TTS_ENABLED=true
TTS_PROVIDER=http
```

只有两个模型检查脚本均输出 `READY` 且容器健康检查通过后才保持上述开关为 `true`；否则将对应开关改回 `false`，文字陪练不受影响。

Demo 模式仍优先调用已配置的内部模型，但单次等待最长 12 秒且不重试；配置无效、超时或模型异常时自动切换到确定性演示回答。页面点击“✨ 一键演示”后会自动创建政务客户训练会话、选中推荐场景并展示第一轮客户问题。

若启用本轮完整语音链路，首次需要重建并传输 `ai-training`、`funasr-service`、`tts-service` 三个镜像；已有且摘要一致的语音服务镜像不必重复传输。Windows 构建机执行（版本号按实际发布号替换）：

```powershell
$env:IMAGE_TAG="20260714-demo"
$env:AI_TRAINING_IMAGE="deploy-ai-training"
docker compose -f deploy/docker-compose.yml --profile asr --profile tts build ai-training funasr-service tts-service
docker save -o E:\customer-visit-voice-demo-20260714-demo.tar deploy-ai-training:20260714-demo deploy-funasr-service:20260714-demo deploy-tts-service:20260714-demo
```

将 tar 包和本次变更的 `deploy/docker-compose.yml`、`deploy/.env.example`、`deploy/test-training.sh` 上传到批准的离线介质后，在服务器执行；服务器不在线构建镜像：

```bash
docker load -i /mnt/disk/customer-visit-demo-package/customer-visit-ai-training-20260714-demo.tar
cd /mnt/disk/customer-visit-demo/deploy
# 先备份 .env，再设置 IMAGE_TAG=20260714-demo、DEMO_MODE=true 及上文演示配置
docker compose config --quiet
docker compose up -d --no-deps --force-recreate ai-training
curl -fsS http://127.0.0.1:${GATEWAY_PORT:-18088}/api/health
curl -fsS http://127.0.0.1:${GATEWAY_PORT:-18088}/api/mode
curl -fsS -X POST http://127.0.0.1:${GATEWAY_PORT:-18088}/api/demo/start
bash test-training.sh
```
