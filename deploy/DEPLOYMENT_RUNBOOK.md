# AI 陪练与本地 FunASR 部署手册

## 1. 目标状态

- 情报助手继续使用原有业务逻辑，默认保持 Mock。
- AI 陪练支持 OpenAI Chat Completions 兼容网关；Qwen3 默认 `enable_thinking=false`。
- 本地语音识别是独立、单进程、CPU-only 服务；其故障不阻塞文字陪练。
- 陪练数据与模型权重均从宿主机只读挂载，镜像不包含模型权重。
- 默认 Compose 不启用 ASR；设置 `ASR_PROVIDER=http` 并使用 `--profile asr` 才启动服务。

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

沿用旧代码实际使用的三类 ModelScope 模型：

| 目录 | 用途 | 典型体积（仅估算） |
|---|---|---:|
| `paraformer-zh` | 中文非流式识别 | 约 1 GiB |
| `fsmn-vad` | 语音活动检测 | 数 MiB 至数十 MiB |
| `ct-punc-c` | 中文标点恢复 | 数百 MiB，依 revision 而异 |

应从已批准、已验证的 ModelScope 缓存复制完整快照，不在生产服务器下载。完整目录应包含模型配置、权重以及配置引用的 tokenizer/字典文件。固定并记录缓存来源的 revision/commit；不能只复制单个权重文件。

```bash
cd /mnt/disk/customer-visit-demo
FUNASR_MODEL_ROOT=/mnt/disk/models/funasr \
  bash deploy/prepare-funasr-models.sh /mnt/disk/customer-visit-demo-package/funasr-models 20260713-v1
du -sh /mnt/disk/models/funasr/current/*
sha256sum -c /mnt/disk/models/funasr/current/SHA256SUMS
```

默认 16 个 Torch/OMP/MKL 线程、最多接纳 2 个请求，但模型推理段串行化。这样允许一个请求预处理时另一个排队，又不会让同一模型实例并发进入不确定状态。应使用 8/16/24 线程做实测后再调整。禁止多 Uvicorn/Gunicorn worker，因为每个 worker 都会重复加载模型、成倍占用内存并造成 CPU 争抢。

## 4. 服务器首次升级

服务器目录约定：

```text
/mnt/disk/customer-visit-demo
/mnt/disk/customer-visit-demo-package
/mnt/disk/models/funasr/current
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

python3 deploy/validate-data.py /mnt/disk/customer-visit-demo-data/knowcard_output/current
bash deploy/check-server.sh
cd deploy
docker compose config --quiet
ASR_PROVIDER=http docker compose --profile asr up -d funasr-service ai-training
docker compose up -d unified-portal customer-intelligence-api customer-intelligence-frontend nginx
docker compose --profile asr ps
curl -fsS http://127.0.0.1:${GATEWAY_PORT:-18088}/api/health
curl -sS http://127.0.0.1:${GATEWAY_PORT:-18088}/api/asr/status
```

正式 `.env` 至少设置：镜像名称和 tag、`TRAINING_KNOWCARD_DIR`、`FUNASR_MODELS_DIR`、`ASR_PROVIDER=http`、`ASR_BASE_URL=http://funasr-service:8000`、模型网关三项配置。不要写占位字符串；Mock 关闭时无效配置会使健康检查返回 `MODEL_CONFIG_INVALID`。

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
- HTML/CSS/JavaScript：同步 `static/`，重启 `ai-training` 以清理运行态；浏览器强制刷新。
- 陪练数据：准备新 release，先运行 `validate-data.py`，原子切换 `current` 软链接，再执行 `bash deploy/update-server.sh data`。
- FunASR 代码：同步 `funasr-service/*.py`，执行 `bash deploy/update-server.sh funasr-service`。新增依赖时仍须重建镜像。
- FunASR 模型：用 `prepare-funasr-models.sh` 创建校验后的 release，切换 `current` 后重启 `funasr-service`。
- 环境变量：备份并修改 `deploy/.env`，执行 `docker compose config --quiet` 后重建对应容器（`up -d --force-recreate`）。
- Nginx：修改并执行 `nginx -t`（容器内）后重启 nginx；配置文件挂载无需重建镜像。

热更新覆盖文件仅用于内网开发/演示维护，不作为正式生产默认。生产发布应使用版本化镜像。

## 7. 验证与性能测试

```bash
bash deploy/test-training.sh
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.asr-debug.yml --profile asr up -d funasr-service
bash deploy/test-asr.sh /path/to/anonymous-test.webm
bash deploy/benchmark-funasr.sh /path/to/anonymous-at-least-60s.wav
```

性能脚本输出 10/30/60 秒样本的实耗时，并配合接口返回的 RTF 和 `docker stats` 记录 CPU/内存。首次模型加载耗时由 `/models/status` 与容器日志确认；重复请求记录热启动耗时。不得使用含客户隐私的录音。

## 8. 回滚

优先保留上一镜像 tag、代码目录和数据/model release：

1. ASR 故障：在 `.env` 设置 `ASR_PROVIDER=disabled`，重新创建 `ai-training`；文字陪练继续可用。
2. 数据故障：把 `knowcard_output/current` 原子切回上一 release，运行校验并重启 `ai-training`。
3. 模型故障：把 `/mnt/disk/models/funasr/current` 切回上一 release 并重启 `funasr-service`。
4. 镜像故障：将 `IMAGE_TAG` 或单独镜像变量切回上一 tag，执行 `docker compose up -d --no-deps ai-training funasr-service`。
5. 环境故障：执行 `bash deploy/rollback-server.sh deploy/backups/<timestamp>` 恢复备份 `.env`。

回滚前后都执行 `docker compose config --quiet`、健康检查和三轮文字陪练。FunASR 不健康时不要阻塞恢复文字主链路。

## 9. TTS 当前结论

陪练代码保留 `/api/tts` 和 `/api/tts/voices` 契约，但已移除 `edge-tts` 公网实现。本阶段必须保持 `TTS_ENABLED=false`，不得把该入口作为真实可用能力。此次不接入任何新 TTS 模型；如后续确有需求，应另行评审一个独立的离线适配器，只提供“文本输入、WAV 输出”接口，并在选定引擎、中文音质、许可证和 CPU 性能验证后再实施。

## 10. 领导演示模式

明天演示建议在 `deploy/.env` 设置：

```dotenv
DEMO_MODE=true
DEMO_SCENE_ID=knowcard/标品/省产品运营中心-安全大脑
TRAINING_MOCK_MODE=false
ASR_PROVIDER=disabled
TTS_ENABLED=false
```

Demo 模式仍优先调用已配置的内部模型，但单次等待最长 12 秒且不重试；配置无效、超时或模型异常时自动切换到确定性演示回答。页面点击“✨ 一键演示”后会自动创建政务客户训练会话、选中推荐场景并展示第一轮客户问题。

本次只需重建和传输 `ai-training` 镜像，FunASR 服务代码、依赖和镜像均未变化。在 Windows 构建机执行（版本号按实际发布号替换）：

```powershell
$env:IMAGE_TAG="20260714-demo"
$env:AI_TRAINING_IMAGE="deploy-ai-training"
docker compose -f deploy/docker-compose.yml build ai-training
docker save -o E:\customer-visit-ai-training-20260714-demo.tar deploy-ai-training:20260714-demo
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
