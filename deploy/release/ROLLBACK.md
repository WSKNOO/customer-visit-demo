# 回滚方案

## 30 秒语音降级

编辑 `deploy/.env`：

```dotenv
ASR_ENABLED=false
TTS_ENABLED=false
```

然后执行：

```bash
docker compose up -d --no-deps ai-training
```

这不会影响文字陪练、Mock 模式和评分报告。

## 配置回滚

使用更新前备份目录：

```bash
bash rollback-server.sh /absolute/path/to/backup-directory
```

脚本恢复 `.env`，并强制以语音关闭的安全基线启动。

## 镜像回滚

保留当前运行镜像的 tag，不要覆盖。新镜像使用新的 `IMAGE_TAG`；失败时将 `.env` 中 `IMAGE_TAG` 恢复为旧值后执行：

```bash
ASR_ENABLED=false TTS_ENABLED=false docker compose up -d --remove-orphans
docker compose ps
bash test-training.sh
```

模型和数据均为只读挂载；回滚代码无需删除模型。若热挂载代码导致问题，移除 `docker-compose.hot.yml` 覆盖文件并按原镜像启动。
