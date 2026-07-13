# 模型部署说明

详细来源、许可证和固定校验值见 [`../MODEL_ASSET_README.md`](../MODEL_ASSET_README.md)。

## 模型准备机

```bash
bash deploy/prepare-funasr-model.sh
bash deploy/prepare-tts-model.sh
bash deploy/check-funasr-model.sh
bash deploy/check-tts-model.sh
bash deploy/package-models.sh
```

只有两个检查都输出 `READY` 才会生成 `customer-visit-models.tar.gz`。模型下载中断时可重跑准备脚本；不得手工创建空文件绕过检查。

## 离线传输与服务器目录

```bash
scp customer-visit-models.tar.gz customer-visit-models.tar.gz.sha256 user@192.168.240.14:/mnt/disk/
```

服务器执行：

```bash
cd /mnt/disk
sha256sum -c customer-visit-models.tar.gz.sha256
sudo mkdir -p /mnt/disk/models
sudo tar -xzf customer-visit-models.tar.gz -C /mnt/disk
FUNASR_MODELS_DIR=/mnt/disk/models/funasr bash /path/to/customer-visit-demo/deploy/check-funasr-model.sh
TTS_MODELS_DIR=/mnt/disk/models/tts bash /path/to/customer-visit-demo/deploy/check-tts-model.sh
```

Compose 以只读方式挂载：

- `/mnt/disk/models/funasr:/models/funasr:ro`
- `/mnt/disk/models/tts:/models/tts:ro`

更换模型文件只需重新校验并重启对应服务，不需要 `docker save/load`。
