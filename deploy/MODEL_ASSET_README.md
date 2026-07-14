# 模型资产说明

模型不进入 Git，也不复制进 Docker 镜像。模型准备机需要能够访问下列官方来源；部署服务器只接收校验后的模型包，运行时不联网下载。

## 目录

```text
models/
├── funasr/
│   ├── paraformer/
│   ├── vad/
│   └── punc/
└── tts/
    └── vits-melo-tts-zh_en/
```

服务器统一放在 `/mnt/disk/models`。Compose 将 FunASR 目录只读挂载到 `/models/funasr`，将 TTS 目录只读挂载到 `/models/tts`。

## FunASR

固定 ModelScope revision：`v2.0.4`，许可证：Apache-2.0。

| 用途 | ModelScope 模型 ID | 关键权重 SHA256 |
|---|---|---|
| 中文 ASR | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | `5bba782a5e9196166233b9ab12ba04cadff9ef9212b4ff6153ed9290ff679025` |
| VAD | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` | `b3be75be477f0780277f3bae0fe489f48718f585f3a6e45d7dd1fbb1a4255fc5` |
| 标点 | `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch` | `a5818bb9d933805a916eebe41eb41648f7f9caad30b4bd59d56f3ca135421916` |

准备和检查：

```bash
bash deploy/prepare-funasr-model.sh
bash deploy/check-funasr-model.sh
```

准备脚本使用官方 ModelScope CLI/SDK，校验三份 `model.pt` 的固定 SHA256，生成全文件 `SHA256SUMS`。模型下载文档：<https://modelscope.cn/docs/models/download>。

## TTS

模型：sherpa-onnx 维护者发布的 `vits-melo-tts-zh_en`，许可证：模型包内 MIT License。准备脚本默认从维护者 `csukuangfj` 的 Hugging Face 仓库下载四个运行必需文件：

<https://huggingface.co/csukuangfj/vits-melo-tts-zh_en>

GitHub Release 压缩包仍作为可选备用源：

<https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-melo-tts-zh_en.tar.bz2>

备用压缩包固定大小为 `167006755` 字节。无论来源如何，准备脚本都会为最终的 `model.onnx`、`tokens.txt`、`lexicon.txt` 和 `LICENSE` 生成本地 `SHA256SUMS`。如需强制使用 GitHub 包，可设置 `TTS_MODEL_SOURCE=github`。

```bash
bash deploy/prepare-tts-model.sh
bash deploy/check-tts-model.sh
```

模型说明：<https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/vits.html>。

## 打包与部署

只有两个检查脚本都输出 `READY` 时才允许打包：

```bash
bash deploy/package-models.sh
sha256sum -c customer-visit-models.tar.gz.sha256
```

在服务器执行：

```bash
sudo mkdir -p /mnt/disk/models
sudo tar -xzf customer-visit-models.tar.gz -C /mnt/disk
FUNASR_MODELS_DIR=/mnt/disk/models/funasr bash deploy/check-funasr-model.sh
TTS_MODELS_DIR=/mnt/disk/models/tts bash deploy/check-tts-model.sh
```

禁止执行 `git add models/`，禁止把模型目录放入 Docker build context。更换模型后必须重新运行检查、打包和 SHA256 校验，但不需要重新构建业务镜像。
