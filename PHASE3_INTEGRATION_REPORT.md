# 第三阶段轻量集成报告

> 执行日期：2026-07-13  
> 范围：轻量集成、Mock 全链路、真实环境配置准备、部署模板。  
> 安全边界：未调用真实模型、搜索、代理、ASR 或方案助手正式地址；未修改方案标准化助手代码。

## 1. 执行结论

“客户情报 → 开始AI陪练 → 自动加载客户上下文 → 三轮纯文字问答 → 最终评分与建议”的完整 Mock 链路已经打通，并通过真实浏览器和自动化脚本验证。

采用的集成方式是：**两个后端保持独立，情报助手 Express 后端通过 HTTP 调用 AI 陪练 Flask 初始化接口；浏览器只接收短 `session_id` 并跳转。** 完整 `visit_brief` 不进入 URL、浏览器本地存储或前端日志。

当前具备部署到 AI 中心服务器并先运行 Mock 演示的条件。真实服务模式仍需完成凭据轮换、目标服务器 Python 3.11/Node.js 20 冒烟、代理确认和受控接口验证。

## 2. 集成架构

```text
统一入口 /
  ├─ /intelligence/       情报助手 Vue 前端
  ├─ /intelligence-api/   情报助手 Express API
  ├─ /training/           AI陪练页面
  └─ /api/                AI陪练 Flask API

情报报告详情
  -> POST /api/visit-brief/start-training
  -> Express 读取报告并映射 visit_brief
  -> POST AI陪练 /api/training/session/init
  -> 返回 session_id + /training/?session_id=...
  -> AI陪练 GET /api/training/session/:session_id
  -> POST /api/chat 完成文字对练
```

未引入 Redis、数据库、消息队列或新的前端框架。会话继续使用单进程、有限数量、短 TTL 内存存储。

## 3. 新增和修改内容

### 3.1 客户拜访情报助手

- 新增 `server/trainingIntegration.js`：
  - 二次校验和收敛 `visit_brief`；
  - 服务端 HTTP 调用；
  - 连接/读取超时；
  - 不重试、不打印完整情报；
  - 内网服务地址与前端跳转地址分离；
  - 返回请求编号和稳定错误码。
- 新增 `POST /api/visit-brief/start-training`。
- `GET /api/reports/:filename/visit-brief` 复用同一映射和校验器。
- 研究任务增加 `task_id` 和 `GET /api/research/:task_id` 状态接口。
- 状态包含：`generating`、`success`、`search_error`、`model_error`、`generation_error`、`service_error`、`timeout`。
- 报告详情增加“开始AI陪练”按钮、加载状态和失败提示。
- 报告列表增加研究进度、Mock/缓存标识、请求编号和缓存演示客户入口。
- 新增两个虚构演示客户：星海智造、云岭交通。
- 搜索服务地址、可选 API Key、代理、最大抓取页数和正文长度均可由环境变量控制。

### 3.2 AI 客户拜访陪练助手

- 新增 `GET /api/training/session/:session_id`，只返回前端所需的安全摘要。
- 陪练页面读取 `session_id`，自动加载：
  - 客户名称；
  - 客户角色；
  - 拜访目标；
  - 开场问题；
  - 难度、阶段和轮数。
- 后续 `/api/chat` 自动携带 `session_id`，每轮读取固定会话上下文。
- ASR 使用 `ASR_ENABLED=false` 作为主开关，并兼容旧 `VOICE_ENABLED`。
- 增加模型请求超时、有限重试、默认轮数和会话 TTL 环境变量。
- 修正 `objection` 阶段前后端命名不一致。
- 页面按后端能力显示 Mock、模型配置、纯文字和 TTS 状态，不再静态宣称模型在线或语音完整模式。
- Docker 使用单 Gunicorn worker，避免内存会话在多个 worker 间不一致。

### 3.3 统一入口与部署

- 新增无第三方依赖的 `unified-portal/` 单页入口和健康检查。
- 三个入口均从环境变量读取；方案助手只使用外链。
- 新增最小 Docker Compose、Nginx 同域反代、健康检查和 `.env.example`。
- 对外只需暴露 Nginx 统一端口；其他服务只在 Docker 网络互访。
- 新增演示前健康检查脚本和部署模板静态校验脚本。

## 4. 接口说明

### 4.1 开始陪练

```http
POST /api/visit-brief/start-training
Content-Type: application/json

{"report_filename":"星海智造演示客户_YYYYMMDD_HHMMSS.md"}
```

成功响应：

```json
{
  "request_id": "UUID",
  "session_id": "32位随机十六进制ID",
  "customer_name": "星海智造演示客户",
  "opening_question": "...",
  "training_url": "/training/?session_id=...",
  "status": "ready"
}
```

主要错误码：

| HTTP | `error_code` | 页面提示 |
|---:|---|---|
| 422 | `VISIT_BRIEF_INVALID` / `VISIT_BRIEF_REJECTED` | 客户情报数据校验失败 |
| 503 | `TRAINING_INTEGRATION_DISABLED` | 陪练集成功能暂未启用 |
| 503 | `TRAINING_SERVICE_UNAVAILABLE` | 陪练服务暂不可用 |
| 504 | `TRAINING_CONNECT_TIMEOUT` / `TRAINING_READ_TIMEOUT` | 创建会话超时，可稍后重试 |
| 404 | `REPORT_NOT_FOUND` | 客户情报报告不存在 |

错误响应包含请求编号，不包含内网地址、绝对路径或调用栈。

### 4.2 陪练会话加载

```http
GET /api/training/session/:session_id
```

返回 `customer_name`、`role_profile`、`training_goal`、`opening_question`、`difficulty`、`phase`、`round_limit`、`voice_enabled` 和剩余有效时间，不返回完整 Prompt 上下文。

### 4.3 研究任务状态

```http
GET /api/research/:task_id
```

返回状态、用户可理解的信息、报告文件名、结果模式、错误编号和请求编号。任务状态仍为单进程内存数据，服务重启后失效，但已生成报告不受影响。

## 5. 配置项

情报侧集成：

- `TRAINING_INTEGRATION_ENABLED`
- `TRAINING_SERVICE_BASE_URL`
- `TRAINING_PUBLIC_URL`
- `TRAINING_CONNECT_TIMEOUT_MS`
- `TRAINING_READ_TIMEOUT_MS`

真实服务准备：

- 情报：`MOCK_MODE`、`SEARCH_MCP_SUMMARIZER_API_BASE/MODEL/API_KEY`、`SEARCH_SERVICE_BASE_URL/API_KEY`、代理、超时、抓取页数、正文长度。
- 陪练：`MOCK_MODE`、`DEEPSEEK_BASE_URL/MODEL/API_KEY`、`ASR_ENABLED=false`、默认轮数、模型超时/重试、会话 TTL。
- 统一入口：`PORTAL_INTELLIGENCE_URL`、`PORTAL_TRAINING_URL`、`PORTAL_SOLUTION_URL`。

所有示例仅包含占位符。内部模型域名必须加入 `NO_PROXY`；公网搜索和抓取按 AI 中心要求使用统一代理。

## 6. 测试结果

| 检查 | 结果 |
|---|---|
| `visit_brief` 映射、空字段、超长字段 | 通过 |
| 情报后端调用陪练初始化 | 通过 |
| 陪练不可用 | 通过，返回 503 和稳定错误码 |
| 读取超时 | 通过，返回 504 |
| 情报任务状态 | 通过，Mock 从 generating 进入 success |
| 前端按钮可用状态 | 浏览器验证通过 |
| 情报详情到陪练跳转 | 浏览器验证通过，URL 只含 `session_id` |
| 客户/角色/目标/开场问题加载 | 浏览器验证通过 |
| 三轮纯文字陪练与最终报告 | 浏览器及自动脚本均通过 |
| 两个缓存演示客户 | 通过，页面明确标识缓存结果 |
| 统一入口三个运行时链接 | 配置测试通过；方案助手正式地址待提供 |
| 情报 Python 测试 | 3/3 通过 |
| AI陪练 Python 测试 | 6/6 通过 |
| Node 集成测试 | 全部通过 |
| 前端 TypeScript/Vite 生产构建 | 通过，生产基路径 `/intelligence/` |
| Python `pip check` | 两项目通过 |
| Python AST / JSON Schema | 通过 |
| 部署模板静态检查 | 通过 |
| Docker Compose 实际构建 | 未执行：本机无 Docker 命令 |
| `git diff --check` | 无法执行：工作区无 Git 元数据 |

完整自动 Mock 测试：`tests/mock_full_chain.py`。该脚本在两个健康接口未同时声明 Mock 时会拒绝运行。

## 7. 真实服务验证状态

未执行。没有使用任何现存或未知授权状态的真实凭据，也没有访问真实模型、搜索、ASR、代理或正式方案助手。

人工配置并明确确认后，按 `DEPLOYMENT_GUIDE.md` 依次验证：

1. 内部模型网络路径和 `NO_PROXY`；
2. 情报模型；
3. 陪练模型；
4. 公网代理；
5. 搜索、客户官网、政府网站和新闻来源；
6. 抓取失败和超时提示。

ASR 不进入主演示，也不应在本轮受控验证中自动开启。

## 8. 未解决问题

1. 已曝光凭据仍需人工吊销，原始 Git 仓库仍需历史扫描。
2. 目标服务器 Python 3.11、Node.js 20 和 Docker 构建尚未实际验证。
3. Crawl4AI/Chromium 在最终容器中的系统依赖尚需目标服务器构建验证。
4. 内存会话和研究任务不支持多实例；AI陪练必须保持单 worker。
5. 公网开放前仍需由统一网关增加身份认证、IP 白名单和限流。
6. Vite/esbuild 保留 2 个 moderate 公告；修复需要跨主版本，演示部署只使用静态构建，不暴露开发服务器。
7. 方案助手正式 URL、域名和 HTTPS 终止方式尚未提供。
8. 报告标题解析仍依赖既有 Markdown 结构，真实模型输出偏离标题时字段可能为空。

## 9. 是否可进入部署

**可以进入 AI 中心服务器的 Mock 部署和受控验证准备，不应直接切换真实模式。** 最先应完成凭据轮换和原始 Git 历史扫描，然后在目标服务器执行 Compose 配置检查、镜像构建和 Mock 冒烟。
