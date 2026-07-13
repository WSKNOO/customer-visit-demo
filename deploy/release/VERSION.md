# 代码版本说明

- 发布提交信息：`feat: prepare ai visit demo release package`
- 发布基线提交：`e270522 feat: polish ai visit demo mode`
- 分支与最终提交 ID：部署前执行 `git branch --show-current` 和 `git rev-parse HEAD` 记录。
- 运行基线：Python 3.11、Node.js 20、Docker Compose v2。
- 公网入口规划：`http://192.168.240.14:18088`。

## 本次范围

- `ai-visit-training`：单次录音上传代理、离线 TTS 代理、浏览器播放和文字降级。
- `funasr-service`：CPU 单实例模型加载、健康检查、模型状态和单次转写。
- `tts-service`：sherpa-onnx VITS CPU 服务、健康检查、模型状态和 WAV 输出。
- `deploy`：只读模型/数据挂载、热更新 Compose、模型准备/检查/打包及发布文档。

未修改：`customer-intelligence`。未纳入版本控制：`legacy-funasr`、`models/`、模型压缩包、密钥和本地缓存。
