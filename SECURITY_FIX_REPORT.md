# 第二阶段安全整改报告

## 1. 范围与结论

本轮仅修改以下两个项目及工作区交付文档：

- `/Users/neo/Desktop/customer-visit-demo/customer-intelligence`
- `/Users/neo/Desktop/customer-visit-demo/ai-visit-training`

未修改已上线的方案标准化助手，未执行 Git 提交、推送、重置、清理或历史重写，未调用真实模型、搜索、ASR 或其他付费接口。

审计报告中的两个 P0 代码风险已完成最小修复：情报助手不再把客户输入拼入 Shell；陪练助手不再接受可逃逸资源目录的任意文件路径。现有明文凭据和旧服务器连接信息已从运行代码、脚本与文档示例中移除，改为环境变量读取。

## 2. 已修复问题

### 2.1 凭据与配置

| 问题 | 处理 | 主要文件 |
|---|---|---|
| 模型、ASR、部署凭据写在代码或配置中 | 改为环境变量；示例仅保留占位符 | `customer-intelligence/config.yaml`、`search_mcp/config.py`、`ai-visit-training/app.py`、`batch_generate_cards.py`、各部署脚本 |
| 旧服务器地址和 SSH 登录信息散落在部署脚本 | 新增统一 `deploy_env.py`，脚本读取 `DEPLOY_HOST/PORT/USER/PASSWORD` | `ai-visit-training/deploy_env.py`、`deploy*.py`、`deploy.sh`、`check_*.py`、`upload_*.py` |
| 文档包含可直接复制的旧凭据示例 | 替换为变量名或安全占位符 | AI 陪练项目 README、设计、评审和技术说明文档 |
| `.env`、证书、私钥缺少统一忽略规则 | 两项目补充 `.gitignore` | 两项目 `.gitignore` |
| 配置样例不完整 | 两项目新增/补全 `.env.example` | 两项目 `.env.example` |
| 健康检查可能暴露 Key 片段 | 只返回是否配置，不返回任何 Key 内容 | `ai-visit-training/app.py` |

前端未加入任何服务端密钥。`.env.example` 中只有变量名、安全占位符和本地默认地址。

### 2.2 情报助手命令注入

主要改动：

- `frontend/server/index.js` 使用 `spawn(executable, [scriptPath], { shell: false })`，通过标准输入传入 JSON。
- 新增 `research_cli.py`，统一校验客户名称、拜访目的和关注方向，并在 Mock 模式直接调用内部 Python 逻辑。
- 客户名称仅允许中英文、数字及有限业务标点，限制长度；拒绝 Shell 元字符、换行、路径分隔符和路径跳转。
- 输出文件名经过净化并再次校验位于报告目录内。
- 子进程输出设置上限；接口错误不返回服务器路径或调用栈。
- `tests/test_security.py` 和 `frontend/server/validation.test.mjs` 覆盖 `;`、`&&`、`|`、`$()`、反引号、换行、`../` 和 Windows 路径。

### 2.3 AI 陪练任意文件读取

主要改动：

- `app.py` 的资源下载统一经过 `resolve_resource_file()`。
- 拒绝绝对路径、Windows 盘符/设备路径、UNC 路径、单次及多次 URL 编码穿越、`..` 和空字节。
- 使用解析后的真实路径校验文件仍位于允许的文档或知识卡目录中，软链接逃逸会被拒绝。
- 限制扩展名、MIME 类型和文件大小；非法或不存在文件统一返回 `Resource not available`。
- `tests/test_phase2.py` 覆盖 `/etc/passwd`、Windows 绝对路径、URL 编码穿越、软链接逃逸和不允许格式。

### 2.4 其他安全加固

- 两个 Web 服务的 CORS 改为环境变量 allowlist，不再默认全开放。
- 陪练服务增加请求体和音频大小限制、音频格式/Base64 校验。
- 语音默认关闭；关闭时 ASR 接口返回 503，纯文字主链路不受影响。
- ASR 默认不落调试音频，不记录完整转写文本和临时文件路径。
- 调试模型接口仅在 `MOCK_MODE=true` 时可用。
- Flask 增加统一 413/500 响应，避免返回内部堆栈。
- `visit_brief` 来源 URL 拒绝环回、私网、链路本地和未指定 IP 地址。

## 3. Git 历史检查

工作区根目录及两个项目目录均不存在 `.git` 元数据，因此无法执行历史提交扫描，也无法列出“涉及文件与提交号”。本轮没有伪造历史结论，也没有执行历史重写。

必须在两个项目的原始 Git 仓库中继续执行：

1. 使用凭据扫描工具扫描全部分支、标签和提交；
2. 记录命中文件、提交号和凭据类型，不复制凭据原值；
3. 先吊销凭据，再评估是否由仓库管理员执行历史清理；
4. 同步清理 CI/CD 变量、制品、镜像层、发布压缩包和聊天记录中的副本。

## 4. 尚未解决的风险

| 等级 | 风险 | 当前状态与建议 |
|---|---|---|
| 高 | 已曝光凭据可能仍有效 | 删除代码中的值不能使旧凭据失效，必须完成 `CREDENTIAL_ROTATION_CHECKLIST.md`。 |
| 中 | 原始 Git 历史未知 | 当前副本无 Git 元数据；必须回到原始仓库扫描。 |
| 中 | 陪练会话保存在单进程内存 | 满足演示和最小集成；多进程/重启会丢失。正式部署前再评估共享存储，本轮不引入 Redis。 |
| 中 | 接口暂无登录、授权和限流 | 统一服务器部署时应限制网络边界；正式开放公网前补认证和速率限制。 |
| 中 | Vite/esbuild 有 2 个 moderate 公告 | 修复建议跨 Vite 主版本，可能扩大改动。本轮不升级；演示时不要对公网暴露 Vite 开发服务器。生产使用已构建静态文件。 |
| 中 | 部分遗留安装脚本仍使用 `shell=True` 执行固定维护命令 | 参数不是用户输入，不属于当前可利用的业务命令注入；建议后续改成参数数组，并限制仅管理员离线执行。涉及 `install_env.py`、`install_funasr.py`、`install_onnx.py`、`install_torch.py`。 |
| 中 | 遗留 SSH 脚本采用宽松主机密钥策略 | 演示部署前应固定服务器指纹并优先使用 SSH Key。 |
| 低 | Flask 自带开发服务器不适合生产 | Docker 已使用 Gunicorn；非容器部署也应采用 WSGI 服务。 |
| 低 | 情报研究异步失败尚无页面级任务状态 | 失败会写入脱敏服务端日志且不影响 API 存活；下一阶段增加轻量任务状态查询或前端轮询。 |
| 低 | 前端构建产物有大分块警告 | 不阻塞演示，后续可做代码分包，本轮不重构。 |

## 5. 涉及文件概览

### 客户拜访情报助手

- 配置与说明：`.env.example`、`.gitignore`、`README.md`、`config.yaml`、`pyproject.toml`、`search_mcp/config.py`
- 后端与映射：`research_cli.py`、`search_mcp/smart_search/company_researcher.py`、`frontend/server/index.js`、`validation.js`、`visitBrief.js`
- 测试：`tests/test_security.py`、`frontend/server/validation.test.mjs`、`visitBrief.test.mjs`
- 前端依赖锁定：`frontend/package.json`、`frontend/package-lock.json`

### AI 客户拜访陪练助手

- 配置与说明：`.env.example`、`.gitignore`、`README.md`、`requirements*.txt`、`Dockerfile`
- 核心：`app.py`、`visit_brief.py`、`static/index.html`、`static/index_v2.html`
- 兼容副本：`project/app.py`、`project/visit_brief.py`、对应静态文件和依赖说明
- 凭据整改：`batch_generate_cards.py`、`deploy_env.py`、遗留部署/检查/上传脚本及相关文档
- 测试：`tests/test_phase2.py`

## 6. 人工操作

请按工作区根目录的 `CREDENTIAL_ROTATION_CHECKLIST.md` 在各供应商和服务器后台完成吊销、轮换与访问日志检查。新凭据只应配置在部署环境，不应提交到仓库或写入前端。
