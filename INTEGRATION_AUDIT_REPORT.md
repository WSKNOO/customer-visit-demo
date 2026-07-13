# 客户拜访情报助手与 AI 客户拜访陪练助手集成审计报告

> 审计日期：2026-07-13（Asia/Shanghai）  
> 审计范围：静态代码、配置、依赖、目录、Git 状态与无外部调用的语法检查  
> 审计限制：未安装/升级依赖，未启动服务，未调用大模型、搜索、ASR、TTS 或云端接口，未修改任何业务文件。报告中的凭据、密码、Token、主机地址均不展示具体值。

## 1. 执行摘要

### 1.1 核心结论

- **可做演示级轻量集成，但不能原样直接上线。** 两套系统的前后端边界清晰，陪练的纯文字主链路已经存在；主要工作不是重构，而是补一个很薄的“会话初始化适配层”，把情报摘要转换为陪练上下文。
- **推荐方式：保持两个后端独立，由情报助手前端作为统一入口；浏览器调用陪练后端的会话初始化接口，再跳转/嵌入陪练页面。** 统一服务器上用 Nginx 同域反向代理，例如 `/intelligence-api/`、`/training-api/`、`/training/`。不建议两后端互相同步调用生成任务，也不建议为演示引入 Redis/数据库。
- **两天内有条件可完成。** 条件是第一日上午先完成密钥轮换、运行时统一、两项目独立启动和一条真实但受控的模型调用验证；若公网模型/搜索接口不可用，则必须启用预生成情报与固定陪练场景作为演示兜底。
- **当前工作区状态下，两个项目都不能判定为“可直接独立运行”。** 静态语法通过，但客户情报项目缺 Python 依赖且本机 Node.js 15.9.0 不满足已安装 Vite 5.4.21 的 Node 版本要求；陪练项目当前 Python 环境缺 Flask 等依赖，附带 `.venv` 没有可执行解释器，且实际加载目录 `knowcard/` 为空，生成卡片在 `knowcard_output/`。
- **最大风险不是 UI 集成，而是安全与外部服务稳定性。** 两项目存在多处明文凭据；客户情报 Web 研究接口存在命令注入风险；陪练存在任意文件下载风险、开放 CORS、无限制音频请求及调试音频持久化。

### 1.2 审计证据边界

- Python：使用 AST 对 48 个 Python 文件做了只读解析，全部可解析；发现 `app.py:70` 的无效转义 `SyntaxWarning`，不阻断解析。
- Node：`customer-intelligence/frontend/server/index.js` 通过 `node --check`。
- 未运行构建：构建会改写 `dist/`，不符合本轮“仅新增报告”的约束。
- 未运行应用健康检查：启动会创建目录、加载/下载模型或可能触发外部服务。
- 两个目录均未检测到可用 Git 仓库元数据，因此无法确认 `.env` 是否曾被提交或查看提交历史；只能确认敏感文件当前存在于工作区。

## 2. 两个项目目录与技术栈

### 2.1 总览

| 项目 | 目录 | 前端 | 后端 | 运行时 | 默认端口 | README | Docker / Compose |
|---|---|---|---|---|---|---|---|
| 客户拜访情报助手 | `/Users/neo/Desktop/customer-visit-demo/customer-intelligence` | Vue 3、Vite 5、TypeScript、Pinia、Ant Design Vue、Axios、Marked、Highlight.js | Python MCP（FastMCP）+ Node.js Express Web API | Python `>=3.11`；Vite 5 实际要求 Node `^18 || >=20` | 前端开发 8006；Express API 3001；MCP 为 stdio、无 TCP 端口 | 无 | 无 / 无 |
| AI 客户拜访陪练助手 | `/Users/neo/Desktop/customer-visit-demo/ai-visit-training` | 单文件 HTML/CSS/原生 JavaScript，ECharts CDN/浏览器语音 API | Python Flask + requests + 本地轻量 RAG；可选 FunASR/讯飞 ASR/Edge TTS | README 声明 Python 3.9+；遗留缓存显示曾用 Python 3.11 | Flask 5000；部署脚本另含 443/80 方案 | 有（另有 `project/README.md`） | 无 / 无 |

### 2.2 客户情报助手基本情况

- **用途**：输入企业名、拜访目的和关注方向；生成多维关键词；百度搜索；抓取正文；调用 OpenAI 兼容模型生成十模块 Markdown 客户拜访简报；保存报告和来源元数据。
- **主要依赖**：`mcp>=1.0.0`、PyYAML、OpenAI Python SDK、`crawl4ai[pdf]>=0.8`；前端依赖见 `frontend/package.json`，后端 Web API 使用 Express、CORS。
- **入口与命令**：
  - MCP：`python run_server.py` 或安装包后的 `search-mcp`，入口 `search_mcp.server:main`，stdio transport。
  - Express API：在 `frontend/` 下执行 `npm run server`，端口 3001。
  - Vue 开发端：在 `frontend/` 下执行 `npm run dev`，端口 8006，`/api` 代理到 3001。
  - 前端构建：`npm run build`；本轮未执行。
- **启动入口文件**：`run_server.py`、`search_mcp/server.py`、`frontend/server/index.js`、`frontend/src/main.ts`。
- **数据库/缓存**：无数据库、Redis 或服务端缓存。收集器仅在单次进程内用集合做 URL/内容去重。
- **本地存储**：默认写入 `tmp/reports/*.md` 和 `*_sources.json`；当前 `tmp/` 不存在。Express 启动时会自动创建目录。
- **外部服务**：百度搜索；代码还实现 Bing、Google、DBLP、Semantic Scholar；Crawl4AI 网页抓取；OpenAI 兼容模型服务；Google 可选本地 SOCKS5 代理。
- **导出能力**：实际只生成/保存 Markdown；未实现 Word/PDF 导出。PDF 解析是独立 MCP 工具能力，不在 `research_company()` 主流程中。

### 2.3 AI 陪练助手基本情况

- **用途**：选择场景、难度、拜访阶段，由模型模拟客户；用户文字或语音作答；模型每轮返回客户回复、教练建议、五维评分，前端展示趋势和总结。
- **主要依赖**：Flask、Flask-CORS、requests、python-dotenv；完整版另含 FunASR、ModelScope、PyTorch、Torchaudio、NumPy、Pydub、websocket-client；轻量版另含 Edge TTS。代码还按需导入 `python-docx`、PyPDF2、`python-pptx`、openpyxl，但这些未完整列入根 requirements。
- **入口与命令**：`python app.py` 为轻量模式；`python app.py --full` 加载 FunASR；README 建议生产用 Gunicorn。入口固定监听 `127.0.0.1:5000`，未读取 `.env` 中的 HOST/PORT。
- **前端**：Flask 直接托管 `static/index.html`；`/v2` 托管 `index_v2.html`。两文件当前内容相同。
- **数据库/缓存**：无数据库/Redis。RAG 块保存在进程全局内存；对话状态在浏览器 JS 内存；最多 20 条消息、评分和历史摘要写入浏览器 `localStorage`。
- **本地文件**：读取 `doc/`、`knowcard/`；支持 txt/docx/pdf/pptx/xlsx。当前 `doc/` 缺失、`knowcard/` 为空；119 个生成文件在 `knowcard_output/`，不会被当前主程序读取。另有 `card/` 6 个文件。
- **外部服务**：OpenAI 兼容的模型 API（当前默认指向第三方平台）；浏览器 Web Speech API；可选本地 FunASR；讯飞 WebSocket ASR；Edge TTS 在线服务；前端 ECharts CDN。
- **Docker/Compose**：无。存在大量面向旧公网服务器的 SSH/SFTP/Nginx/systemd 部署脚本，不应直接复用到统一服务器。

## 3. 客户拜访情报助手审计

### 3.1 业务流程与搜索实现

1. `research_company()` 调用 `generate_keywords()`，按最多 12 个维度生成固定模板关键词。
2. `ContentCollector.search_dimensions()` 并发搜索、按来源类型排序、按维度裁剪。
3. `ContentCollector.fetch_content()` 使用 Crawl4AI 抓取网页正文，并用 URL 与正文前 1000 字 MD5 去重。
4. `generate_full_report()` 单次调用模型，或 `generate_report_sequentially()` 分九个模块调用模型；最后拼接来源表。
5. `research_company()` 将 Markdown 和精简来源元数据写入 `tmp/reports/`。

关键文件：

- 搜索入口：`search_mcp/smart_search/company_researcher.py:27`
- 关键词：`search_mcp/smart_search/keyword_generator.py:13,138`
- 搜索与抓取：`search_mcp/smart_search/content_collector.py:94,114,148,175`
- 搜索引擎实现：`search_mcp/engines/*.py`
- 网页清洗：`search_mcp/scraper.py`
- PDF：`search_mcp/pdf_parser.py`、`search_mcp/server.py:325`
- 报告与 Prompt：`search_mcp/smart_search/report_generator.py:24,139,191,299`
- MCP 工具：`search_mcp/server.py:538`
- Web 接口：`frontend/server/index.js:36,67,111`

### 3.2 搜索专项判断

| 检查项 | 判断 | 证据/说明 |
|---|---|---|
| 实际主流程搜索服务 | 百度 | `ContentCollector.__init__()` 实际只注册 `baidu`；默认参数虽写 `bing, baidu`，未注册的 Bing 被跳过。独立 MCP 工具支持更多引擎。 |
| 关键词生成 | 固定模板 | 企业画像、数字化、AI、云、网络安全、5G/IoT、招投标、战略合作、年报、新闻、行业、信创，共 12 维。不是模型动态生成。 |
| 网页正文抓取 | 有 | Crawl4AI 两级策略，提取 Markdown/清洗正文，不仅使用摘要。 |
| 搜索摘要 | 有 | `SourceItem.snippet` 保留，但主报告优先使用抓取正文。 |
| PDF/附件 | 独立工具有，主流程无 | `fetch_pdf`/`download_papers` 可解析或下载 PDF；`ContentCollector.fetch_content()` 未识别并路由到 PDF 解析器，因此企业研究主链路对 PDF 不可靠。其他附件不处理。 |
| 正文清洗 | 有 | `scraper.py` 使用 Crawl4AI 的 Markdown 提取与降级策略。 |
| 来源链接 | 有 | 报告上下文和第十模块带 URL；来源 JSON 保存 title/url/type/dimension/content_length。 |
| 引用溯源 | 部分 | Prompt 强制 `[n]` 和来源表，但没有程序化验证编号是否存在、事实是否真的由对应来源支持。 |
| 时间过滤 | 弱 | 关键词含“最新/年报”等，Prompt 要求近一年和倒序；搜索请求本身无日期范围参数，也无结果日期解析/过滤。 |
| 客户名称消歧 | 无 | 未基于官网、统一社会信用代码、地区、行业做实体确认；同名企业可能混入。 |
| 结果去重 | 有但基础 | URL 精确去重 + 正文前 1000 字哈希；未做 canonical URL、相似度/转载聚类。 |
| 来源可信度排序 | 有但粗粒度 | 政府/官方 > 招标 > 百科 > 媒体 > 学术 > 其他，仅按域名/标题规则；企业官网未被单独可靠识别。 |
| 事实/推测区分 | Prompt 层支持 | Prompt 要求“明确提及/推测可能”、置信度；无结构化字段或后处理校验，模型仍可能不遵守。 |
| 保存历史/缓存 | 文件历史 | 报告按时间戳落盘并可列表查看；没有任务表、状态机、缓存命中或过期策略。 |
| 导出 | Markdown | 无 Word/PDF 导出按钮或后端转换。 |

### 3.3 最终输出结构

内部 `research_company()` 返回：

```text
success, company, report, report_path, source_count, total_chars,
elapsed_seconds, error, source_data_path（成功时）
```

其中 `report` 是一整段 Markdown，十模块仅靠标题表达结构，**不是 JSON 字段**。`*_sources.json` 仅保存来源元数据，不保存正文、摘要、发布时间、可信度或实际引用关系。

MCP `research_company_tool()` 返回 JSON 字符串：`success`、`company`、`report_path`、`source_data_path`、`source_count`、`total_chars`、`elapsed_seconds`、`error`、`report_preview`、`summary`。

Express `POST /api/research` 只立即返回：`success`、`message`、`note`；没有 task_id、状态查询、结果 URL 或失败信息回传。前端只能刷新报告列表猜测任务是否完成。

### 3.4 “生成客户情报”统一入口判断

- **现有最佳内部入口**：`search_mcp.smart_search.company_researcher.research_company()`。
- **输入**：
  - `company_name: str`（必填）
  - `visit_purpose: str = ""`
  - `focus_areas: List[str] | None`
  - `output_dir: str = ""`
  - `max_items: int = 80`
  - `sequential_mode: bool = False`
- **返回**：见 3.3。
- **是否适合另一系统直接调用**：**不适合直接跨系统调用，但适合包装。** 原因是它是 Python 内部函数、同步等待时间长、会产生文件写入、依赖公网搜索与模型、输出为大段 Markdown、没有稳定的结构化摘要。建议保留它不动，在情报侧新增一个只读结果适配 API：按报告 ID 解析/提取最小 JSON；演示时陪练只消费已完成结果，不等待搜索生成。
- **现有 Web 入口 `POST /api/research` 不应作为集成入口**：存在命令注入、无任务 ID、无状态、无结构化返回。

### 3.5 不稳定点

- 目标“5 万字”与单次模型 token、响应时长、成本和上下文限制冲突；逐模块模式需多次调用，3–5 分钟提示过于乐观。
- 百度页面结构/反爬、Crawl4AI 浏览器依赖、超时和网页 JS 渲染会导致抓取波动。
- 主流程只实际用百度；搜索覆盖面和外部可用性单点明显。
- `focus_areas` 在 Express 中以字符串传给期望 `List[str]` 的内部函数，Python 会逐字符迭代，造成关注方向筛选异常。
- Express 后台进程输出被累积但不消费结果，无任务管理；服务重启后任务不可追踪。
- 报告文件名仅替换空格和中文括号，未限制 `/`、`..` 等路径字符，内部函数被直接调用时存在路径问题。
- 来源引用、日期、事实/推测均靠 Prompt，无校验器。
- 当前没有任何报告样本目录，无法离线验证报告解析与 UI 展示。

## 4. AI 陪练助手审计

### 4.1 交互流程

1. 页面加载 `/api/scenes`、`/api/mode`，初始化语音/TTS，并从 `localStorage` 读取历史。
2. 用户选择知识场景、难度（简单 5 轮/中等 8 轮/困难 10 轮）和阶段（初次接触、需求深挖、方案呈现、异议处理、促成收尾）。
3. 点击“开始对练”后，前端清空本地状态，以“对练开始！”作为首条用户消息调用 `/api/chat`。
4. 后端按阶段固定人设、难度角色、知识库检索结果和最近 12 条消息拼接系统 Prompt，调用 OpenAI 兼容 `/chat/completions`。
5. 模型每轮需返回客户口语、`<!--COACH ...-->` 和 `<!--SCORE {...}-->`。前端解析评分并显示趋势。
6. 达到轮数或模型返回 REPORT 标记后，前端生成最终报告弹层并保存摘要到 `localStorage`。

### 4.2 客户角色与问题生成

- **角色生成**：不是独立 API，也不是结构化角色对象。`call_deepseek()` 依据难度、阶段配置、固定痛点故事和场景 RAG 内容动态拼接 Prompt。
- **问题生成**：模型在同一 `/api/chat` 回复中扮演客户并继续提问；无独立问题列表/题库生成接口。
- **与目标客户的适配现状**：`/api/chat` 只接受 `messages`、`difficulty`、`scene`、`phase`；客户名称、客户背景、潜在需求、拜访目标不会进入 Prompt。必须新增可控上下文字段或会话初始化接口。
- **RAG**：自研关键词/字符相似度检索，非 LangChain/LangGraph；数据来自 `doc/`、`knowcard/`。目前实际目录错位导致动态场景为 0。

### 4.3 对话、状态和评分

- **用户提交**：前端把完整 `state.messages` POST 到 `/api/chat`；后端不持有会话。
- **会话状态**：当前活动会话在浏览器内存；历史在 `localStorage` 的 `voice_practice_history_v3`。服务端无 session_id、数据库、Redis、鉴权或并发隔离问题，但也无法恢复跨设备会话。
- **后端返回**：`success`、`content`、`usage`；评分隐藏在 `content` 注释中，不是稳定 API 字段。
- **评分维度**：专业度 `professionalism`、表达沟通 `communication`、需求洞察 `needs_analysis`、异议处理 `objection_handling`、成交引导 `closing`；另有客户情绪 `mood` 和原因。
- **最终评分**：前端对最后一次解析到的五维分数做简单平均，不使用阶段页面定义的权重；最终总结优先截取模型 REPORT，否则拼接模板。评分完全由同一个扮演客户的模型自评，缺少独立评审调用和确定性规则。
- **流式输出**：无，全部是阻塞 HTTP 请求。

### 4.4 文字与语音

| 能力 | 判断 |
|---|---|
| 文字输入 | 完整支持，输入框 + Enter/发送按钮，可完成全流程。 |
| 浏览器 ASR | 轻量模式使用 Web Speech API；依赖浏览器和网络实现。 |
| 本地 ASR | `python app.py --full` 懒加载 FunASR（paraformer-zh、FSMN VAD、标点模型，可选 CAM++）。首次可能下载大模型。 |
| 公网 ASR | `/api/xfyun-asr` 调用讯飞 WebSocket IAT；凭据目前硬编码兜底。 |
| 音频处理 | `/api/asr` 接收 Base64；Torchaudio 转 16kHz 单声道 WAV；临时文件处理。讯飞路径由前端采集并下采样 PCM。 |
| ASR 文本可修改 | 浏览器语音转写停止后约 500ms 自动调用 `sendMessage()`，没有确认/编辑步骤。讯飞成功结果也直接发送；不满足“先修订再提交”。 |
| ASR 失败兜底 | 文字输入始终存在，语音失败不阻断文字主链路。 |
| 关闭语音 | 无统一“关闭 ASR”开关，但可完全不用麦克风；TTS 有开关。 |
| 纯文字完整陪练 | 支持，推荐作为演示主链路。 |
| 固定演示模式 | 无显式固定模型响应模式；有固定阶段配置和本地知识卡生成物，但当前目录未接通。 |

### 4.5 “创建陪练会话”统一入口判断

- **现有最佳入口**：没有服务端创建会话接口。最接近的是前端 `startBtn.onclick`（`static/index.html:1734`）初始化本地状态，随后调用 `POST /api/chat`。
- **现有 `/api/chat` 输入**：`messages[]`、`difficulty`、`scene`、`phase`。
- **现有返回**：`success`、`content`、`usage`；会话状态全部由浏览器保存。
- **目标字段传入现状**：无法直接传 `customer_name`、`customer_background`、`potential_needs`、`visit_goal`；即使塞进第一条用户消息，也容易被当作销售话术，且每轮裁剪最近 12 条后会丢失。
- **建议的最薄入口**：新增 `POST /api/training/sessions`，接受本报告第 8 节的 `handoff`，返回 `session_id`、标准化 `scenario_context`、`opening_message`、`difficulty`、`phase`、`round_limit`。演示版可将上下文放在签名的短期 token 或浏览器 `sessionStorage`，并在每次 `/api/chat` 请求中显式携带；若允许后端内存 TTL 存储，则以 `session_id` 查上下文。**不建议 URL 直接携带完整情报。**
- **会话状态建议**：两天演示优先 `sessionStorage` + 每次请求携带摘要；需要多实例时再引入 Redis。现有 `localStorage` 只用于历史展示，不应存完整敏感客户原文。

### 4.6 不稳定点

- README 称 DeepSeek V4/DeepSeek API，代码实际将模型硬编码为第三方平台上的 DeepSeek V3 标识；环境变量 `DEEPSEEK_MODEL` 被忽略。
- `max_tokens=400` 同时要求客户回复、COACH、SCORE、结束 REPORT，容易截断标记，前端解析失败。
- 前端按 REPORT 关键词判断结束；后端不计算轮数，完全依赖模型遵守“最近 12 条消息”中的提示。
- 模型输出 HTML 注释格式不是稳定协议；评分和总结可能缺失或 JSON 不合法。
- 动态场景目录错位：代码读 `knowcard/`，数据在 `knowcard_output/`。
- 启动时 argparse 在模块导入阶段解析参数，Gunicorn 等宿主参数可能冲突。
- TTS 使用 Edge 在线能力且前端默认开启，会增加外部依赖；演示建议默认关闭。
- ECharts 依赖 CDN，离线或受限网络下评分图表可能不显示。

## 5. 外部服务与环境变量清单

### 5.1 客户情报助手

| 变量/配置 | 用途 | 当前支持环境变量 | 风险/建议 |
|---|---|---|---|
| `SEARCH_MCP_ENGINE` | 默认搜索引擎 | 是 | 企业研究主流程仍实际固定百度。 |
| `SEARCH_MCP_PROXY` | 默认代理 | 是 | `config.yaml` 另含 Google 本地代理地址。 |
| `SEARCH_MCP_TIMEOUT` | 请求超时 | 是 | 建议统一为有边界的整数。 |
| `SEARCH_MCP_DEFAULT_COUNT` | 默认结果数 | 是 | 主研究流程有自己的限制。 |
| `SEARCH_MCP_SUMMARIZER_ENABLED` | 模型开关 | 是 | 报告生成实际仍要求模型 Key。 |
| `SEARCH_MCP_SUMMARIZER_API_BASE` | OpenAI 兼容基地址 | 是 | 当前配置文件硬编码内网地址。 |
| `SEARCH_MCP_SUMMARIZER_API_KEY` | 模型凭据 | 是 | 当前配置文件存在明文值，必须轮换。 |
| `SEARCH_MCP_SUMMARIZER_MODEL` | 模型名 | 是 | 可切换；默认/配置值不同。 |
| `SEARCH_MCP_SUMMARIZER_TEMPERATURE` | 温度 | 是 | 报告生成函数部分调用会覆盖。 |
| `SEARCH_MCP_SUMMARIZER_MAX_TOKENS` | 最大输出 | 是 | 报告生成函数使用自有更大值。 |
| `SEARCH_MCP_SUMMARIZER_MAX_INPUT_CHARS` | 最大输入字符 | 是 | 报告生成函数也有独立截断。 |

模型调用使用 OpenAI Python SDK `OpenAI(base_url=..., api_key=...)` 和 `chat.completions.create()`，因此**接口协议兼容 OpenAI Chat Completions，容易替换为统一模型网关**。无流式输出，无 Agent/LangChain/LangGraph/Dify；MCP 只用于工具暴露和 stdio 运行。

### 5.2 AI 陪练助手

| 变量 | 用途 | 实际读取情况 | 风险/建议 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 对话模型 Key | 读取，但代码带明文兜底 | 移除兜底、轮换。 |
| `DEEPSEEK_BASE_URL` | OpenAI 兼容地址 | 读取 | 可统一到同一模型网关。 |
| `DEEPSEEK_MODEL` | 模型名 | `.env` 有，主代码忽略 | 改为真正读取；`CHEAT_MODEL` 同步配置。 |
| `FUNASR_MODEL` | 本地 ASR 模型 | `.env` 有，主代码未使用 | 模型名在代码内固定。 |
| `HOST` / `PORT` | 服务监听 | `.env` 有，主代码未使用 | 入口固定 `127.0.0.1:5000`。 |
| `DOC_PATH` | 文档目录 | `.env` 有，主代码未使用 | 代码按脚本目录固定。 |
| `XF_APPID` / `XF_API_KEY` / `XF_API_SECRET` | 讯飞 ASR | 读取，但代码带明文兜底 | 立即轮换，演示主链路关闭。 |
| `TTS_VOICE` / `TTS_RATE` / `TTS_VOLUME` | Edge TTS | 读取 | 建议演示默认关闭 TTS。 |

陪练通过 `requests.post(BASE_URL + '/chat/completions')` 手工实现 OpenAI Chat Completions 协议，**可替换统一模型接口**。Prompt 集中但与业务逻辑高度耦合在 `app.py`：阶段规则、角色、RAG、评分协议和调用重试在一个函数中；两天集成只应增加上下文槽位，不应拆分重构。

## 6. 安全风险清单

> 风险值均已脱敏。由于无 Git 元数据，“被提交”状态无法证实；当前工作区明文存在已足以构成泄露风险。

| 等级 | 项目/位置 | 变量或代码位置 | 风险说明 | 后续建议 |
|---|---|---|---|---|
| 严重 | `customer-intelligence/config.yaml` | `summarizer.api_key` | 明文模型 API Key。 | 立即吊销轮换；配置仅留空值，从密钥管理/环境变量注入。 |
| 高 | `customer-intelligence/config.yaml` | `summarizer.api_base` | 硬编码内网模型服务地址，暴露拓扑且统一服务器未必可达。 | 环境变量化，部署前做无敏感值连通性检查。 |
| 严重 | `customer-intelligence/frontend/server/index.js:123-143` | `company_name`、`visit_purpose`、`focus_areas` 拼入 `bash -c`，且 `shell:true` | 单引号替换不足以防命令替换、双引号/换行等注入；公网开放时可执行任意命令。 | P0：不经 shell；使用固定 Python 程序和参数/JSON stdin；修复前不要暴露接口。 |
| 高 | `customer-intelligence/frontend/server/index.js:14` | `cors()` | CORS 全开放且无鉴权，可从任意站点发起高成本研究任务。 | 同域部署、白名单、鉴权/限流。 |
| 中 | `customer-intelligence/frontend/server/index.js:15` | JSON 50MB | 研究接口只需小 JSON，却允许 50MB，易 DoS。 | 降到 64–256KB，并限制字段长度。 |
| 高 | `customer-intelligence/search_mcp/smart_search/company_researcher.py:100-125` | `output_dir`、`safe_name` | 企业名未过滤路径分隔符，可能越界写文件；输出目录可由调用方指定。 | 白名单文件名、固定输出根目录、解析后校验 `is_relative_to`。 |
| 中 | `customer-intelligence/search_mcp/server.py` 抓取工具 | 任意 URL | `fetch_url`/`fetch_pdf` 可访问调用者提供的 URL，若暴露为网络服务有 SSRF 风险。 | 限制 scheme、阻止环回/私网/元数据地址，保留 stdio 信任边界。 |
| 严重 | `ai-visit-training/app.py:44`、`project/app.py:44`、README | `DEEPSEEK_API_KEY` | 源码和文档含明文模型 Key 兜底/示例。 | 立即轮换；示例用占位符；Key 缺失时拒绝启动。 |
| 严重 | `ai-visit-training/app.py:1780-1782` 及副本 | `XF_APPID`、`XF_API_KEY`、`XF_API_SECRET` | 讯飞凭据硬编码。 | 立即轮换；仅环境变量注入；语音可选时不配置。 |
| 严重 | `ai-visit-training/.env`、`.env.backup` | 上述模型变量 | 实际 `.env` 和备份同时存在于工作区；根目录无 `.gitignore` 证据。 | 轮换、移出交付包；根目录补 `.gitignore`（实施阶段）。 |
| 严重 | 多个 `deploy*.py`、`do_https.py`、`update_cloud.py` 等 | `SERVER/HOST/H/P/U/USER/PW/PWD/PASSWORD`、`ssh.connect(...)` | 多个旧服务器 IP、root 用户和明文 SSH 密码硬编码。 | 全部视为已泄露并轮换；统一部署禁止复用这些脚本。 |
| 高 | `ai-visit-training/app.py:1464-1475` | `/api/download/<path:filepath>` | 将用户路径与项目根拼接后未做归一化边界校验；`../` 可读取项目外任意服务账号可读文件。 | 仅允许知识库根下的文件 ID；`resolve()` 后做根目录包含校验。 |
| 高 | `ai-visit-training/app.py:33` | `CORS(app)` | CORS 全开放、所有成本接口无鉴权/CSRF/限流。 | 同域白名单、反向代理鉴权和速率限制。 |
| 高 | `ai-visit-training/app.py:1157-1246,1977-1988` | Base64 `audio` | 无请求体/音频大小、时长、格式白名单；可导致内存、磁盘、CPU 和付费 ASR 滥用。 | Flask/Nginx 限制体积；校验格式/时长；并发和频率限制。 |
| 高 | `ai-visit-training/app.py:1208-1214` | `debug_asr_*.wav` | 每次 FunASR 都复制一份调试音频到项目目录，永久保留客户语音，且日志打印路径/转写片段。 | 默认禁用；临时加密/短期清理；日志脱敏。 |
| 中 | `ai-visit-training/app.py:1672-1683` | `/api/health`、`api_key_preview` | 健康接口返回 Key 前缀和内部 ASR 错误。 | 只返回布尔状态，不返回任何 Key 片段/内部错误。 |
| 中 | `ai-visit-training/app.py:1685-1692` | `/api/test` | 无鉴权调试接口会真实调用模型并产生费用。 | 生产禁用或管理员鉴权。 |
| 中 | `ai-visit-training/app.py:1139-1143` | `/test_cache` | 指向当前不存在的调试文件，暴露调试路由。 | 生产移除/关闭。 |
| 中 | `ai-visit-training/static/index*.html:870-886` | `localStorage` 历史 | 客户对话和评分长期存浏览器，任何同源脚本/XSS 可读；无过期策略。 | 演示仅存摘要、加清空按钮/TTL；敏感客户不存完整原文。 |
| 中 | `ai-visit-training/app.py:1041-1066` | API 错误日志 | 日志输出模型 URL、错误响应和请求元信息，可能包含供应商细节；ASR 日志打印转写片段。 | 结构化脱敏日志，不记录用户原文/音频路径/Key 片段。 |
| 中 | `ai-visit-training/https_server.py`、部署脚本 | 自签名证书/私钥生成 | 工作区当前未发现 `.key/.pem/.crt` 文件，但脚本会生成长期自签名私钥并放在固定目录。 | 统一服务器用正式证书管理，不运行遗留脚本。 |
| 中 | 两项目 | 无认证/授权 | 报告、知识库下载、对话与付费接口均公开。 | 演示至少加统一入口口令或反向代理 Basic/OIDC。 |

未发现应用层数据库密码、Redis 密码、云存储密钥、默认管理员账号或测试账号；但部署脚本中的 root SSH 口令属于严重基础设施凭据风险。前端源码未直接暴露模型 Key，Key 位于后端/配置/文档。

## 7. 当前可运行性判断

### 7.1 客户情报助手

**判断：代码结构基本完整，但当前环境不能直接运行，且安全修复前不能对外提供研究接口。**

- 当前 Python 3.12.7 满足 `>=3.11`，但缺 `mcp`、`crawl4ai`；未做安装。
- 当前 Node 15.9.0，而已安装 Vite 5.4.21 声明 Node `^18.0.0 || >=20.0.0`，前端开发/构建不具备受支持环境。
- `node_modules` 和 `dist/` 存在，Express 入口语法通过，但没有报告目录/样本。
- 无 README、Dockerfile、Compose、健康接口或任务状态接口。
- 模型地址为内网地址，统一服务器是否可达未知；搜索和浏览器依赖未验证。
- 静态检查不能证明真实搜索、抓取和模型输出可用。

### 7.2 AI 陪练助手

**判断：纯文字代码链路完整，理论上比情报助手更容易启动；当前环境仍不能直接运行。**

- 当前全局 Python 缺 Flask、Flask-CORS、FunASR、PyTorch、Edge TTS 等；`.venv` 没有可执行的 Unix Python，疑似从其他系统/不完整复制。
- 根 `app.py` 与 `project/app.py` 完全相同；两个 `index_v2.html` 也完全相同，存在重复副本带来的发布歧义。
- 纯文字轻量模式不需要 FunASR，但仍需要 Flask、requests、dotenv 和有效模型接口。
- 动态知识场景当前为 0：代码读取 `knowcard/`，而数据在 `knowcard_output/`。
- 无 Dockerfile/Compose；遗留部署脚本与目标统一服务器强耦合且含敏感信息，不能作为可用部署基线。

## 8. 集成接口与数据结构分析

### 8.1 推荐最小交接结构

建议以一个版本化 `visit_brief` 作为情报到陪练的交接载荷。它比直接传整篇 Markdown 稳定，也保留事实、推测和来源边界：

```json
{
  "schema_version": "1.0",
  "brief_id": "ci_20260713_xxx",
  "customer": {
    "name": "客户企业全称",
    "aliases": [],
    "industry": "",
    "profile_summary": "",
    "key_facts": [
      {
        "text": "",
        "as_of": "2026-07-01",
        "source_ids": ["src_1"]
      }
    ]
  },
  "visit": {
    "goal": "",
    "focus_areas": [],
    "target_role": "",
    "suggested_questions": []
  },
  "signals": {
    "recent_events": [
      {
        "title": "",
        "date": "2026-06-20",
        "summary": "",
        "source_ids": ["src_2"]
      }
    ],
    "digital_clues": [
      {
        "summary": "",
        "confidence": "high",
        "source_ids": ["src_3"]
      }
    ],
    "potential_needs": [
      {
        "summary": "",
        "basis": "fact|inference",
        "confidence": "medium",
        "source_ids": ["src_3"]
      }
    ],
    "recommended_solutions": [
      {
        "name": "",
        "reason": "",
        "priority": "P1"
      }
    ]
  },
  "sources": [
    {
      "id": "src_1",
      "title": "",
      "url": "https://example.invalid/",
      "publisher_type": "official|government|media|tender|other",
      "published_at": null
    }
  ],
  "training_options": {
    "difficulty": "中等",
    "phase": "discovery",
    "round_limit": 6,
    "voice_enabled": false
  }
}
```

### 8.2 字段兼容性

| 字段 | 情报助手现状 | 陪练可用性 | 处理建议 |
|---|---|---|---|
| `customer.name` | 已有 `company_name/company` | 可直接用于角色 Prompt | 必填，1–120 字符。 |
| `customer.profile_summary` | Markdown 第一模块中有 | 可直接作为角色背景 | 需从 Markdown 提取/模型结构化；建议 ≤2,000 字。 |
| `customer.key_facts` | 报告中有，未结构化 | 用于角色事实约束 | 每项 ≤300 字，最多 20 项，保留 source_ids。 |
| `visit.goal` | 已有 `visit_purpose` | 可直接用于陪练目标 | 必填，≤500 字。 |
| `visit.focus_areas` | 已有 | 可映射阶段/知识检索 | 字符串数组，最多 10 项。 |
| `visit.target_role` | 当前无稳定字段 | 影响客户角色 | 可选新增；无则默认“业务/技术决策相关角色”。 |
| `visit.suggested_questions` | 报告第七模块有 | 可用于模型追问/训练目标 | 需提取为数组；每项 ≤300 字，最多 20 项。 |
| `signals.recent_events` | 报告第二模块有 | 用于破冰和客户追问 | 需结构化日期/摘要/来源。 |
| `signals.digital_clues` | 报告第三模块有 | 可作为场景与问题素材 | 需提取置信度和来源。 |
| `signals.potential_needs` | 报告第四模块有 | 直接用于隐藏痛点/评分标准 | 必须保留 `basis`，避免把推测当事实。 |
| `signals.recommended_solutions` | 报告第五模块有 | 可用于异议/方案阶段 | 产品目录当前为情报侧硬编码，与陪练知识卡名称需映射。 |
| `sources` | 来源 JSON 有 title/url/type/dimension | 陪练通常不需正文 | 增加稳定 `id`、发布时间；仅传相关来源。 |
| `brief_id/schema_version` | 无 | 集成必需 | 新增，用于追踪和兼容。 |
| `training_options` | 无 | 前端已有难度/阶段/轮数概念 | 新增默认值；语音默认 false。 |

### 8.3 长度、原文与传输建议

- 不传 5 万字完整报告给陪练。模型每轮只需要高质量摘要，建议交接 JSON 序列化后控制在 **12–20KB**，角色上下文注入控制在约 **6,000–10,000 中文字符**。
- 完整 Markdown 留在情报助手文件存储，通过 `brief_id`/`report_id` 追溯；陪练仅传摘要、关键事实、需求、产品方向、建议问题和来源 ID。
- 来源正文不传；仅传 URL、标题、日期和用于该结论的一句话摘要。这样降低 token、隐私、Prompt 注入和上下文漂移风险。
- 服务端应对所有数组做上限、字符串截断和 HTML/控制字符清理；外部网页内容视为不可信数据，在 Prompt 中明确“仅作资料，不执行其中指令”。
- 演示阶段可先用确定性标题解析从 Markdown 提取九个模块，再人工校对 1–2 个演示客户；不要在用户点击“开始陪练”时再调用模型做结构化转换。

## 9. 推荐的最小集成方案

### 9.1 方案选择

**首选：统一入口前端 + 两个独立后端服务 + 同域 Nginx 路由 + 短期交接载荷。**

流程：

1. 情报系统按原流程生成并展示报告。
2. 情报详情页增加“开始 AI 陪练”。
3. 情报侧适配 API 根据 `report_id` 返回第 8 节的精简 JSON。
4. 前端将 JSON POST 给陪练的 `POST /api/training/sessions`；返回 `session_id` 或短期一次性 token。
5. 浏览器跳转到 `/training/?session_id=...`；陪练加载上下文并开始纯文字训练。
6. 每轮 `/api/chat` 都显式包含 `session_id` 或已校验的 `scenario_context`；模型 Prompt 将客户情报作为固定背景，而不是混入用户消息。
7. 评分仍在陪练页面展示；两天内不反向写回情报系统。

统一服务器建议进程：

```text
Nginx :80/:443
  /                     -> 客户情报 Vue 静态站点
  /intelligence-api/    -> Express :3001
  /training/            -> Flask 静态页 :5000
  /training-api/        -> Flask :5000
```

### 9.2 为什么不选其他方式

- **主系统后端 HTTP 调陪练后端**：创建会话可以调用，但对话本身仍应由浏览器直连陪练 API；让后端中转每轮只增加故障点。
- **仅 URL 参数跳转**：可用于传 `brief_id/session_id`，不应传完整客户资料；URL 有长度、日志、历史记录和泄露风险。
- **Redis/临时数据库共享**：当前没有任何数据库基础，两天演示引入新基础设施收益低。只有多实例、跨设备恢复或审计要求出现时再用 Redis。
- **把陪练模块嵌入情报助手代码**：会把 Flask 单页和 Vue 工程强行合并，改动大、回归面大，不符合两天目标。
- **同一前端深度改写两个页面**：长期合理，短期不必要。先统一视觉入口和同域导航即可。

### 9.3 P0 前置条件

1. 轮换所有已暴露模型、ASR、SSH 凭据，并确认旧服务器凭据失效。
2. 修复/隔离 Express `/api/research` 命令注入和 Flask 任意文件下载；修复前仅绑定回环地址且由受控反代访问。
3. 统一 Python 3.11、Node 20 LTS；锁定实际依赖，确认 FFmpeg/浏览器依赖是否需要。
4. 将陪练演示设为文字优先、TTS/ASR 默认关闭。
5. 准备至少 1 个经过人工校验的预生成情报 JSON 和固定陪练场景。

## 10. 两天实施计划

> 下表是后续实施计划，本轮未执行。工作量按一名熟悉代码的全栈工程师估算。

### 第一天：独立可运行与数据打通

| 优先级 | 任务 | 预计工作量 | 涉及文件 | 主要风险 | 验收方式 |
|---|---|---:|---|---|---|
| P0 | 轮换凭据、隔离旧部署脚本、建立统一 `.env.example` 变量表 | 1.0h | 两项目配置、`.env.example`、部署清单 | 旧 Key 仍有效；误用旧服务器 | 日志/源码不含真实值；缺 Key 时安全失败；旧 Key 已吊销证明。 |
| P0 | 统一运行时并独立启动 | 1.5h | `pyproject.toml`、requirements、`package.json`、启动说明 | Crawl4AI/FunASR 重依赖；Node 版本 | Python 3.11、Node 20；两个健康页可访问；不加载语音模型。 |
| P0 | 修复或反代隔离两个致命入口 | 1.0h | `frontend/server/index.js`、`app.py`、Nginx | 命令注入、任意文件读取 | 注入/`../` 请求被拒绝；研究接口不可匿名公网调用。 |
| P0 | 确认情报内部入口与已完成报告读取接口 | 1.0h | `company_researcher.py`、`frontend/server/index.js` | 长任务无状态、Markdown 不稳定 | 用离线样本获得 `report_id` 和报告内容；不触发公网。 |
| P0 | 确认陪练纯文字模式 | 0.75h | `app.py`、`static/index.html` | 模型输出格式截断 | 用受控测试账号完成 3 轮；无麦克风也能结束并评分。 |
| P0 | 定稿 `visit_brief v1` 和映射器 | 1.25h | 新增适配模块/接口文件（实施时） | 标题解析失败、推测混作事实 | 1–2 个样本通过 JSON Schema；每个事实有来源/或明确为空。 |
| P0 | 增加陪练会话初始化薄接口 | 1.0h | `app.py` 或独立 adapter | 上下文丢失、过长 | POST brief 返回 session/token；首轮 Prompt 可见客户名、目标、需求。 |
| P1 | 基础跳转打通 | 0.5h | `ReportDetail.vue`、前端 API | URL 泄露 | URL 只含短 ID；陪练页面正确加载客户标题。 |

### 第二天：统一入口、部署与演示加固

| 优先级 | 任务 | 预计工作量 | 涉及文件 | 主要风险 | 验收方式 |
|---|---|---:|---|---|---|
| P0 | 情报详情增加“开始 AI 陪练”并传递摘要 | 1.0h | `ReportDetail.vue`、`frontend/src/api/index.ts` | 重复点击、会话过期 | 单击创建一次会话，失败可重试；不传完整 Markdown。 |
| P0 | 陪练 Prompt 注入固定客户上下文 | 1.0h | `app.py:call_deepseek`、会话适配 | Prompt 注入、12 条裁剪丢背景 | 每轮均保持同一客户/目标；来源数据被视为资料而非指令。 |
| P0 | 评分结果稳定展示与无 REPORT 兜底 | 0.75h | `app.py`、`static/index.html` | SCORE JSON 缺失 | 正常、缺字段、截断三种响应都能显示可理解结果。 |
| P0 | 同域部署脚本/容器化最小基线 | 1.5h | 新 Dockerfile/Compose/Nginx（实施时）或 systemd 单元 | 浏览器依赖体积、监听地址、CORS | 一条命令/脚本启动；仅 Nginx 暴露端口；健康检查通过。 |
| P0 | 演示客户数据与离线兜底 | 0.75h | `demo-data/*.json`（实施时） | 现场搜索/模型失败 | 断开搜索后仍可从预生成 brief 开始固定陪练。 |
| P0 | 异常与超时兜底 | 0.75h | 两后端 API、前端提示 | 90 秒阻塞、重复计费 | 超时、429、5xx、空 SCORE 都有提示；按钮可恢复，不重复提交。 |
| P1 | 文字模式默认、TTS/ASR 显式可选 | 0.5h | `static/index.html`、配置 | 浏览器权限弹窗干扰 | 首次打开不请求麦克风、不调用 TTS；用户主动开启才调用。 |
| P1 | 演示脚本与检查清单 | 0.5h | `DEMO_RUNBOOK.md`（实施时） | 操作顺序不一致 | 非开发人员按脚本 10 分钟完成全流程。 |
| P1 | 备用录屏与关键截图 | 0.75h | 演示资产目录（实施时） | 现场网络/模型故障 | 本地可播放；覆盖情报、跳转、3 轮、评分四节点。 |
| P2 | Word/PDF 导出、语音完善、结果回写 | 不纳入两天 | 多模块 | 扩大范围 | 后续迭代单独验收。 |

## 11. 演示风险与兜底方案

| 风险 | 触发信号 | 主方案 | 现场兜底 |
|---|---|---|---|
| 搜索/抓取失败 | 无来源、百度验证码、超时 | 预先生成并人工校验 1–2 个客户 brief | 直接选择“演示客户”，跳过实时搜索。 |
| 模型网关不可达/余额不足 | 401/429/5xx/90 秒超时 | 演示前健康检查和额度确认；统一网关 | 固定 3 轮脚本响应 + 标识“演示模式”；播放录屏。 |
| 报告过长/生成超时 | 5 分钟仍未完成 | 演示只展示已完成报告，不现场生成 5 万字 | 展示预生成 Markdown 和来源。 |
| SCORE/REPORT 格式损坏 | 评分面板为空 | 把评分改为独立 JSON 字段或强校验重试一次 | 前端使用最近有效评分和模板总结。 |
| 动态场景为空 | `/api/scenes total=0` | 修正部署数据目录/显式配置知识库路径 | 使用内置通用场景 + brief 上下文。 |
| 语音权限/ASR/TTS/CDN | 权限弹窗、无声音、图表空白 | 默认文字、关闭 TTS；ECharts 本地化 | 纯文字完成；评分用数字/条形图，无 CDN 也可读。 |
| 同名客户信息污染 | 来源跨公司 | 演示客户预校验；增加行业/地区确认 | 显示“请确认客户实体”，切换预生成样本。 |
| 安全漏洞被利用 | 异常命令/文件请求 | 修复后才对外；Nginx 鉴权/限流 | 仅内网/本机演示，关闭公网入口。 |
| 服务重启丢会话 | 页面刷新后上下文缺失 | brief token/sessionStorage；短 TTL | 重新从情报详情点击开始，过程不写回。 |

建议演示顺序：打开已完成情报 → 展示来源与“事实/推测” → 点击开始陪练 → 纯文字完成 3–5 轮 → 展示五维评分和改进建议。实时搜索、语音和 TTS 只作为可选加分项，不进入主链路。

## 12. 待我确认的问题

1. 统一服务器的操作系统、CPU/内存、是否有 GPU、是否允许 Docker，以及预定域名/HTTPS 方式是什么？
2. 统一大模型接口最终使用哪个网关、模型名、并发/限额？客户数据是否允许发送到该公网模型？
3. 客户情报当前硬编码的内网模型地址在统一服务器是否可达？若不可达，是否统一替换到陪练所用网关？
4. 实际演示必须“现场联网生成情报”，还是允许使用预生成客户报告？建议允许预生成作为主演示，实时生成作为备用展示。
5. 演示客户是哪 1–2 家？是否有同名风险、敏感信息或必须排除的来源？
6. AI 陪练应模拟哪类客户角色（业务负责人、技术负责人、采购、领导）？是否需要在开始前由用户选择？
7. 两天范围是否允许新增两个很薄的接口（情报摘要读取、陪练会话初始化）和 Nginx/Docker 文件？这是推荐方案的最小必要改动。
8. 陪练结果是否需要回写情报助手？本报告建议两天内不回写，只在陪练页展示与本地导出。
9. 是否要求账号登录/企业内网访问？即使是演示，也建议至少反向代理口令、IP 白名单和速率限制。
10. 对话与客户情报的留存要求是什么？建议演示默认不在服务器持久化，浏览器历史只保留摘要并可一键清空。

---

### 最终建议一句话

先把两个项目分别在统一的 Python 3.11 / Node 20 环境中安全启动，轮换并移除所有明文凭据，封堵命令注入和任意文件读取；随后用“精简 `visit_brief` + 陪练会话初始化接口 + 同域跳转”的方式集成，主演示坚持预生成情报与纯文字陪练，两天内完成的概率最高。
