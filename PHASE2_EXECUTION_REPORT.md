# 第二阶段执行报告

## 1. 执行结论

| 项目 | 独立启动 | Mock 模式 | 核心链路 | 当前判断 |
|---|---|---|---|---|
| 客户拜访情报助手 | 通过 | 通过 | 提交客户 → 生成 Mock 报告 → 展示/读取 → 映射 `visit_brief` | 可用于下一阶段轻量集成 |
| AI 客户拜访陪练助手 | 通过 | 通过 | 初始化会话 → 三轮纯文字回答 → 每轮评分 → 第三轮总结 | 可用于下一阶段轻量集成 |

这里的“通过”指本机 Mock 和无付费外部调用条件下通过。真实模型、搜索和 ASR 的供应商连通性、配额、模型权限与输出质量未测试。

## 2. 推荐运行环境与端口

目标环境：Python 3.11、Node.js 20。

| 服务 | 默认端口 | 启动入口 |
|---|---:|---|
| 情报助手 API | 3001 | `customer-intelligence/frontend/server/index.js` |
| 情报助手前端 | 8006 | `customer-intelligence/frontend` 的 Vite 预览/静态服务 |
| AI 陪练前后端一体 Flask 服务 | 5000 | `ai-visit-training/app.py` |

端口无冲突。当前机器没有可直接使用的 Python 3.11，本轮在隔离的 Python 3.12.7 虚拟环境完成验证；依赖元数据已声明支持 Python 3.11，部署到目标服务器后仍需做一次 3.11 冒烟测试。Node 构建使用工作区提供的 Node.js 24 完成；`package.json` 已声明 Node.js 20 及以上。

## 3. 启动说明

完整命令、环境变量和 Mock 启动方式已写入：

- `customer-intelligence/README.md`
- `ai-visit-training/README.md`
- 两项目各自的 `.env.example`

陪练项目新增轻量 `Dockerfile`，默认 Mock、关闭语音并由 Gunicorn 启动。情报助手由 Node API 调用 Python 研究模块，当前分层较清楚；本轮未为容器化强行合并两个运行时。

## 4. Mock 验证结果

### 4.1 情报助手

- API 健康检查：通过，`GET /api/health` 返回 `status=ok`。
- 提交客户：通过，`POST /api/research` 接受合法客户和拜访目标。
- Mock 报告：通过，在报告目录生成 Markdown 和空来源元数据，不调用搜索或模型。
- 报告读取：通过，详情接口返回 200。
- `visit_brief` 映射：通过；验证客户名、拜访目标和 3 条建议问题可读。
- 输入安全：Python 3 个测试与 Node 输入测试全部通过。
- 外部服务失败：Mock 与真实入口隔离；模型/搜索未配置时不会影响健康检查，研究子进程失败也不会使 API 进程退出。当前异步任务失败只写入脱敏后的服务端日志，页面级任务状态提示尚未补齐，列为下一阶段前的 P1 事项。
- 前端构建：通过；Vue 类型检查与 Vite 生产构建成功。

### 4.2 AI 陪练

- 页面：Flask 静态首页返回 200。
- 健康检查：通过，Mock 开启、语音关闭。
- 会话初始化：`POST /api/training/session/init` 返回 201 和 `ready`。
- 三轮文字陪练：通过；三轮均产生评分标记，第三轮产生总结标记。
- ASR 兜底：语音关闭时 ASR 返回 503，但文字会话完整可用；前端麦克风入口禁用且不主动申请权限。
- 模型不可用：Mock 模式不调用模型；真实模式缺少 Key 时返回明确错误，不导致服务崩溃。
- 路径穿越与接口测试：6 个测试全部通过。
- Python 依赖检查：通过，无缺失或冲突。

## 5. `visit_brief` 与初始化接口

### 5.1 数据模型

规范文件：工作区根目录 `visit_brief.schema.json`。AI 陪练的运行时校验和上下文映射位于 `ai-visit-training/visit_brief.py`。

主要约束：

- `customer.name` 必填，最多 120 字符；客户简介最多 2,000 字符。
- 拜访目标最多 1,000 字符；建议问题最多 12 条、每条最多 300 字符。
- 各类信号数组设置 8～12 条上限，条目只传摘要和可选依据，不传网页全文。
- 总 JSON 文本限制为 20,000 字符；陪练上下文再压缩到 6,000 字符。
- 缺失数组默认为空；角色、难度、阶段、轮数和语音开关有安全默认值。
- 来源链接可选，陪练不依赖它们；仅接受公网 HTTP(S) URL。

情报助手映射位于 `frontend/server/visitBrief.js`，接口为：

`GET /api/reports/:filename/visit-brief`

### 5.2 陪练初始化接口

接口：

`POST /api/training/session/init`

输入为 `visit_brief`，输出包含：

- `session_id`
- `customer_name`
- `role_profile`
- `training_goal`
- `opening_question`
- `status`
- `difficulty`、`phase`、`round_limit`、`voice_enabled`

会话上下文目前保存在进程内存，默认两小时过期并限制会话数量。`POST /api/chat` 可携带 `session_id` 读取上下文；不传 `session_id` 时保留原有陪练流程。

## 6. 验证命令与结果摘要

| 检查 | 结果 |
|---|---|
| Python 全量 AST 语法检查 | 通过，0 个错误 |
| 情报助手 Python 安全测试 | 3/3 通过 |
| 情报助手 Node 安全/映射测试 | 通过 |
| AI 陪练阶段测试 | 6/6 通过 |
| 两项目 Python `pip check` | 通过，无破损依赖 |
| 前端 Vue 类型检查 + Vite 构建 | 通过 |
| JSON Schema 语法检查 | 通过 |
| 进程级健康检查 | 两项目通过 |
| Mock 情报生成 | 通过 |
| 三轮纯文字陪练和总结 | 通过 |
| 路径穿越/命令注入输入 | 全部按预期拒绝 |
| `git diff --check` | 无法执行：工作区不含 Git 元数据 |

为弥补 `git diff --check` 无法运行，已完成所有 Python 文件 AST 检查、JSON Schema 解析、前端类型检查/生产构建和敏感模式扫描；未发现冲突标记或业务源码中的密钥形态。

## 7. 验证过程中遇到的问题

| 现象 | 根因 | 措施 | 是否阻塞 |
|---|---|---|---|
| 系统 `/usr/bin/python3` 返回退出码 69 | 本机 Xcode 许可未接受 | 不修改系统状态，改用隔离的现有 Python 运行时 | 否 |
| 首次 `npm run build` 的 `.bin/vue-tsc` 无执行权限 | 原项目复制的 `node_modules` 可执行位异常 | 修正项目内依赖入口权限后，标准 `npm run build` 已通过；业务代码未变 | 否 |
| 首次 Vite 构建缺少 Rollup 平台可选包 | 依赖目录不完整 | 按锁文件补装可选依赖后构建成功 | 否 |
| Python `urllib` 访问 localhost 返回代理 502 | 环境代理拦截本地请求 | 验证客户端禁用代理后进程接口全部通过 | 否 |
| Vite/esbuild 有 2 个 moderate 公告 | 当前 Vite 版本受开发服务器公告影响 | 未跨主版本升级；演示使用生产构建且不公网暴露开发服务器 | 否，但需后续处理 |

## 8. 是否具备进入轻量集成阶段的条件

结论：**具备，限 Mock/纯文字演示链路。**

下一阶段可以由情报助手取得 `visit_brief` 后，以服务端 HTTP 请求调用陪练初始化接口，再将返回的 `session_id` 交给陪练页面。无需合并框架或引入 Redis。

进入真实外部服务联调前仍需完成：

1. 人工吊销并轮换全部已曝光凭据；
2. 在原始 Git 仓库执行历史凭据扫描；
3. 在 Python 3.11 / Node.js 20 的目标服务器做一次安装和启动冒烟；
4. 通过受控测试账号分别验证模型、搜索和可选 ASR；
5. 对统一服务器设置网络访问控制、日志脱敏和费用限额。

## 9. 本轮未做范围

未增加统一入口前端、Nginx 正式配置、情报页跳转按钮、视觉统一、正式模型/搜索/ASR、登录权限、Redis/新数据库、复杂 Agent 改造或方案标准化助手变更。
