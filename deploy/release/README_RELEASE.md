# AI 陪练 Demo 发布说明

发布日期：2026-07-14。发布目标是保持现有文字陪练主链路，增加可独立启停的 CPU ASR/TTS。`customer-intelligence` 与 `legacy-funasr` 不在本次发布范围。

## 发布结论

- 文字陪练、Demo/Mock 降级、评分和报告继续作为明日演示主链路。
- ASR/TTS 默认关闭；只有模型检查输出 `READY` 后才允许开启。
- ASR/TTS 失败不阻塞文字输入、AI 回复或评分。
- 模型、陪练数据和热更新代码均使用只读 bind mount，不进入 Git 或镜像。
- 本地无 Docker，Compose 运行态与真实模型推理尚未验证；服务器上线前必须执行本文检查。

## 文件导航

- [VERSION.md](VERSION.md)：代码边界与版本说明
- [MODEL_DEPLOYMENT.md](MODEL_DEPLOYMENT.md)：模型准备、校验与挂载
- [SERVER_COMMANDS.md](SERVER_COMMANDS.md)：服务器顺序命令
- [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)：生产环境变量
- [HEALTH_CHECKS.md](HEALTH_CHECKS.md)：健康检查与验收
- [ROLLBACK.md](ROLLBACK.md)：快速回滚

## 明日最稳演示策略

先保持 `TRAINING_MOCK_MODE=true`、`ASR_ENABLED=false`、`TTS_ENABLED=false` 验证文字主链路；内部模型连通后只切换陪练模型；语音模型检查均为 `READY` 后再分别启用 ASR、TTS。任一语音检查失败，立即关闭对应开关，不影响文字演示。

现场入口目前是 `http://192.168.240.14:18088`。主流浏览器通常只在 HTTPS 或 localhost 安全上下文开放麦克风，因此该 HTTP IP 入口的录音按钮可能无法取得权限。演示前必须在领导使用的同一浏览器验证；未配置 HTTPS 时，语音输入不得作为唯一演示路径，保留文字输入和预录 WAV 上传测试作为兜底。点击播放服务端生成的 TTS 通常不受麦克风安全上下文限制。
