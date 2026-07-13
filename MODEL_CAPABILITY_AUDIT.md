# 模型能力与外部服务清点报告

审计日期：2026-07-13  
审计范围：`customer-intelligence`、`ai-visit-training`  
审计方式：仅静态阅读源码、配置、依赖和部署文件；未启动业务服务，未调用任何真实模型、搜索、ASR 或 TTS 服务。  
本轮变更：仅生成本报告，并在两个项目的 `.env.example` 中预留默认关闭的 Embedding/Rerank 变量；未修改业务逻辑。

## 1. 结论摘要

1. 两个项目的主基模请求均采用 OpenAI Chat Completions 风格，接口地址、密钥和模型名均可由环境变量提供。情报助手直接使用 OpenAI Python SDK；陪练助手使用 `requests` 调用 `{base_url}/chat/completions`。
2. 当前工作区没有两个项目的有效 `.env`，因此无法从代码库判定任何真实模型凭据已配置。统一部署编排默认使用 Mock 模式，真实模型不会被调用。
3. 两个项目都没有实际 Embedding 调用，也没有向量数据库或独立 Rerank 模型调用。本轮只在 `.env.example` 预留相关变量，默认关闭；当前代码不会读取这些变量，不能通过把开关改为 `true` 来启用能力。
4. 情报助手主研究链路实际只注册了百度搜索适配器，并会继续抓取搜索结果网页正文。默认搜索地址是公网百度；内网部署若无可访问的搜索代理/镜像，将阻塞真实情报生成。
5. 陪练助手存在本地文件知识语料和轻量词法检索，但没有向量库。相关度为关键词、短语和字符 Jaccard 的规则加权，不是严格 BM25，也不是独立 Rerank。
6. 陪练前端同时保留 Web Speech API 和后端 ASR 路径。当前页面状态默认优先调用后端讯飞接口；Web Speech 是可切换/回退代码路径；FunASR 是可选完整模式，不是纯历史死依赖。关闭语音后，完整文字陪练不导入也不依赖 FunASR。

## 2. 模型与外部服务能力矩阵

| 项目 | 能力/服务 | 实现方式 | 当前代码是否实际使用 | 当前工作区/统一部署默认状态 | 内网部署阻塞性 |
|---|---|---|---|---|---|
| 情报助手 | 基模 | OpenAI Python SDK，Chat Completions | 是，真实研究报告必需 | 项目无 `.env`；统一部署默认 Mock | 需配置可达的 OpenAI 兼容网关，否则真实报告阻塞 |
| 情报助手 | 搜索 | 百度 HTML 搜索适配器或兼容搜索网关 | 是，真实研究主链路必需 | 项目默认公网百度；统一部署默认 Mock | 纯内网且不能访问公网时阻塞真实检索 |
| 情报助手 | 网页正文抓取 | Crawl4AI `scrape_url` | 是 | 真实研究时启用 | 目标网页不可达时结果降级/失败 |
| 情报助手 | Embedding | 无实现 | 否 | 默认关闭，仅预留配置 | 不阻塞；当前不需要 |
| 情报助手 | Rerank | 无模型实现；仅来源类型规则排序 | 否 | 默认关闭，仅预留配置 | 不阻塞；当前不需要 |
| 情报助手 | 知识库/向量库 | 静态产品能力表，不是向量库 | 仅产品目录参与 Prompt | 本地源码内可用 | 不阻塞 |
| 陪练助手 | 基模 | `requests` 调用 OpenAI 风格 `/chat/completions` | 是，非 Mock 对话、反转模式和开挂回答使用 | 项目无 `.env`；统一部署默认 Mock | 需配置可达的兼容网关，否则真实模型流程不可用 |
| 陪练助手 | DeepSeek | 变量和函数沿用 DeepSeek 命名；未绑定 DeepSeek SDK/固定域名 | 取决于环境变量指向 | 当前未配置，默认不调用 DeepSeek | 不阻塞，可直接指向内网兼容接口 |
| 陪练助手 | Embedding | 无实现 | 否 | 默认关闭，仅预留配置 | 不阻塞 |
| 陪练助手 | Rerank | 无独立模型；本地规则评分后排序 | 否 | 默认关闭，仅预留配置 | 不阻塞 |
| 陪练助手 | 本地知识语料 | `doc`/`knowcard_output` 文件解析后进入内存分块 | 是，按场景加载 | Docker 包含 `knowcard_output` | 不阻塞，但内容质量影响回答 |
| 陪练助手 | 浏览器 Web Speech | `SpeechRecognition || webkitSpeechRecognition` | 代码存在，当前默认不是首选录音提交路径 | 部署默认关闭语音 | 不阻塞文字流程；启用时有浏览器/HTTPS/公网依赖风险 |
| 陪练助手 | 讯飞 ASR | 浏览器采集 PCM，后端 WebSocket 调讯飞 | 当前前端语音路径默认优先 | 部署默认 `ASR_ENABLED=false`，且凭据为空 | 不阻塞文字流程；启用后依赖公网和凭据 |
| 陪练助手 | FunASR | 后端 `--full` 模式懒加载本地模型 | 条件启用，不是默认路径 | 轻量依赖不安装；部署默认关闭语音且不使用 `--full` | 不阻塞文字流程；完整语音模式会增加模型下载、内存和依赖风险 |
| 陪练助手 | Edge TTS | `edge-tts` | 条件启用 | 部署默认 `TTS_ENABLED=false` | 不阻塞文字流程；启用后通常依赖公网服务 |

“当前启用”说明：源码中存在调用不等于运行时已经启用。当前两个项目根目录均无 `.env`；`deploy/docker-compose.yml` 对两项目均默认 Mock，并明确关闭陪练 ASR/TTS。

## 3. 客户拜访情报助手

项目目录：`/Users/neo/Desktop/customer-visit-demo/customer-intelligence`

### 3.1 基模调用位置

| 文件 | 函数/位置 | 作用 | 是否主链路 |
|---|---|---|---|
| `search_mcp/smart_search/report_generator.py` | `_call_ai()` | 构造 `OpenAI(base_url, api_key)`，调用 `client.chat.completions.create()` | 是 |
| `search_mcp/smart_search/report_generator.py` | `_generate_section()`、`generate_full_report()`、`generate_report_sequentially()` | 组织 Prompt，并通过 `_call_ai()` 生成整份或分段报告 | 是 |
| `search_mcp/smart_search/company_researcher.py` | `research_company()` | 真实研究统一入口；完成关键词、搜索、抓取、模型报告和文件保存 | 是 |
| `search_mcp/summarizer.py` | `summarize()` | 通用 MCP 搜索/抓取工具的可选摘要器，同样使用 OpenAI 兼容接口 | 否，非客户研究报告的直接主入口 |
| `search_mcp/server.py` | `maybe_summarize()` | MCP 工具启用摘要时调用 `summarize()` | 否，独立 MCP 工具路径 |

基模配置来自 `search_mcp/config.py`：

| 环境变量 | 用途 | 是否完整支持环境变量切换 |
|---|---|---|
| `SEARCH_MCP_SUMMARIZER_API_BASE` | OpenAI 兼容 API Base URL | 是 |
| `SEARCH_MCP_SUMMARIZER_API_KEY` | Bearer/API Key | 是 |
| `SEARCH_MCP_SUMMARIZER_MODEL` | 模型名 | 是 |
| `SEARCH_MCP_SUMMARIZER_ENABLED` | 通用摘要器开关 | 部分：MCP 的 `maybe_summarize()` 使用；客户报告 `_call_ai()` 不读取此开关 |
| `SEARCH_MCP_SUMMARIZER_TEMPERATURE` | 摘要器温度 | 通用摘要器使用；报告生成函数有自己的调用参数 |
| `SEARCH_MCP_SUMMARIZER_MAX_TOKENS` | 摘要器最大输出 | 通用摘要器使用；报告生成传入自己的 `max_tokens` |
| `SEARCH_MCP_SUMMARIZER_MAX_INPUT_CHARS` | 摘要器输入上限 | 通用摘要器使用 |

结论：模型地址、模型名和密钥都能由环境变量配置，且 SDK 接口通用。`config.yaml` 中模型地址、密钥、模型名为空，不包含可用凭据。客户研究报告路径不以 `SEARCH_MCP_SUMMARIZER_ENABLED` 作为总开关；是否进入真实研究主要由上层 `INTELLIGENCE_MOCK_MODE`/`MOCK_MODE` 决定，进入真实研究后模型密钥为空会失败。

### 3.2 搜索和网页抓取位置

| 文件 | 函数/位置 | 实际行为 |
|---|---|---|
| `search_mcp/smart_search/keyword_generator.py` | `generate_keywords()` | 用静态业务维度模板拼接客户名；不是模型生成关键词 |
| `search_mcp/smart_search/content_collector.py` | `ContentCollector.__init__()` | 客户研究主链路只注册 `BaiduSearch`；默认引擎列表虽含 Bing，但未注册项会跳过 |
| 同上 | `search_keyword()` | 调用搜索引擎并按 URL 去重 |
| 同上 | `fetch_content()` | 调用 `scrape_url()` 抓取正文，并按内容哈希去重 |
| 同上 | `search_dimensions()` | 并发搜索、按来源类型规则排序、按维度裁剪、并发抓取和过滤 |
| `search_mcp/engines/baidu.py` | `BaiduSearch.search()` | `httpx` GET `SEARCH_SERVICE_BASE_URL`，查询参数为 `wd/rn`；有密钥时发送 `X-API-Key` |
| `search_mcp/scraper.py` | `scrape_url()` | 使用 Crawl4AI 获取和清洗网页内容 |

搜索配置：

- `SEARCH_SERVICE_BASE_URL`：主链路实际搜索地址；未设置时默认 `https://www.baidu.com/s`。
- `SEARCH_SERVICE_API_KEY`：可选 `X-API-Key`。
- `SEARCH_MCP_TIMEOUT`、`SEARCH_MAX_FETCH_PAGES`、`SEARCH_MAX_CONTENT_CHARS`：超时和抓取限制。
- `SEARCH_MCP_ENGINE`：影响通用 MCP 搜索配置，但不改变客户研究 `ContentCollector` 当前只注册百度的事实。

内网风险：若内网禁止访问百度和目标网页，必须把 `SEARCH_SERVICE_BASE_URL` 指向协议兼容的内部搜索代理，并为网页抓取配置受控出口或接受只使用代理摘要的后续改造。仅更换搜索入口不能保证 Crawl4AI 能访问结果页正文。

### 3.3 Embedding、Rerank、知识库判断

- **Embedding：未使用。** Python 依赖和业务代码中没有 Embedding 客户端、向量生成或向量相似度计算。
- **Rerank：未使用独立模型。** `ContentCollector.search_dimensions()` 仅按“政府/官方、招标采购、百科、媒体、学术、其他”固定优先级排序。Google/Bing 适配器中“re-rank”注释实际只是 URL 去重后重编号，不是模型 Rerank，而且客户研究主链路未使用这些适配器。
- **知识库/向量库：不存在向量数据库。** `product_catalog.py` 是源码中的静态产品能力表，报告生成时被格式化并放入 Prompt；它不是可检索的向量知识库。抓取结果和报告保存在本地 `tmp/reports`，也不是向量存储。

## 4. AI 客户拜访陪练助手

项目目录：`/Users/neo/Desktop/customer-visit-demo/ai-visit-training`

### 4.1 基模调用位置与 DeepSeek 判断

| 文件 | 函数/位置 | 模型调用 | 是否主运行入口 |
|---|---|---|---|
| `app.py` | `call_deepseek()` | 主陪练对话和评分；调用 `{DEEPSEEK_BASE_URL}/chat/completions` | 是 |
| `app.py` | `reverse_chat()` | 反转模式检索后生成销售答复 | 是，功能分支 |
| `app.py` | `cheat_answer()` | 本地检索后生成辅助答复，使用 `CHEAT_MODEL` | 是，功能分支 |
| `batch_generate_cards.py` | 模型请求代码 | 离线批量生成知识卡工具 | 否，不由 Web 服务启动 |
| `project/app.py`、`project/batch_generate_cards.py` | 与根目录文件相同的副本 | 同上 | 当前 Docker/启动说明不以此目录为入口，应视为遗留副本 |

当前代码**可能调用 DeepSeek API，但不必然调用 DeepSeek**：

- 命名仍为 `DEEPSEEK_*`，函数名仍为 `call_deepseek()`。
- 没有 DeepSeek SDK，也没有硬编码 DeepSeek 公网域名。
- 请求体使用 `model/messages/temperature/max_tokens`，响应读取 `choices[0].message.content`，属于常见 OpenAI Chat Completions 格式。
- 当 `MOCK_MODE=true` 时，`call_deepseek()` 直接返回固定 Mock，不发网络请求。
- 当 `MOCK_MODE=false` 且三个 `DEEPSEEK_*` 值齐全时，请求会发往环境变量指定地址；该地址若是 DeepSeek 就调用 DeepSeek，若是内部 OpenAI 兼容网关就调用内部模型。
- 当前项目无 `.env`，统一部署默认 `TRAINING_MOCK_MODE=true`，因此默认不会调用 DeepSeek 或其他真实模型。

相关环境变量：

- `DEEPSEEK_BASE_URL`：兼容网关 Base URL，代码会追加 `/chat/completions`。
- `DEEPSEEK_API_KEY`：Bearer Token。
- `DEEPSEEK_MODEL`：主对话和反转模式模型。
- `CHEAT_MODEL`：开挂/知识辅助模型；缺省回退到 `DEEPSEEK_MODEL`。
- `MOCK_MODE`：Mock 总开关。
- `MODEL_REQUEST_TIMEOUT_SECONDS`、`MODEL_MAX_RETRIES`：超时与重试控制；主调用包含重试，分支调用实现并不完全统一。

兼容性边界：内部网关需支持 `/chat/completions`、Bearer 认证、上述请求字段和 OpenAI 风格 `choices` 响应。若内部网关 Base URL 已经以 `/chat/completions` 结尾，当前代码会重复拼接，必须只配置到版本根路径（例如 `/v1`）。

### 4.2 Embedding、Rerank 和本地知识检索

- **Embedding：未使用。** 没有 Embedding API、向量生成、向量距离或相关依赖。
- **独立 Rerank：未使用。** 没有 Cross Encoder/Rerank API 或模型。
- **知识语料：存在。** `SimpleRAG.load_scene()` 从 `DOC_PATH`、`KNOWCARD_PATH` 加载场景卡、知识卡和 docx/pdf/pptx/xlsx/txt 文档，按段落形成内存块。
- **向量库：不存在。** 检索块仅保存在 Python 进程内存，未使用 FAISS、Chroma、Milvus、Qdrant、Elasticsearch 或数据库向量字段。
- **当前相关度算法：规则词法检索。** `SimpleRAG._compute_relevance()` 使用关键词命中 50%、连续短语匹配 35%、字符集合 Jaccard 15%；`search()` 按该分数排序并用文本前 50 字符去重。源码注释称 “BM25-like”，但实现没有 IDF、文档长度归一化等标准 BM25 计算，因此应准确归类为手工词法相关度，不是向量检索或独立 Rerank。

主要调用点：`call_deepseek()` 的 Prompt 构造、`reverse_chat()` 和 `cheat_answer()` 都会调用 `rag.search()`，将检索结果拼入模型上下文。

## 5. 浏览器 ASR 专项检查

### 5.1 前端文件与函数

主文件 `static/index.html`，另有内容相同的 `static/index_v2.html`。关键函数：

- `initSpeechRecognition()`：读取后端语音开关、检测浏览器 API、请求麦克风权限并显示状态。
- `startRecording()`：`useXFYun=false` 时创建浏览器 Speech Recognition 实例。
- `startXFRecording()` / `stopXFRecording()`：采集 16 kHz PCM，并 POST 到 `/api/xfyun-asr`。
- `detectBackendMode()`：读取 `/api/mode` 的 `voice_enabled`；关闭时禁用录音按钮，文字输入保持可用。
- `checkXFYun()`：存在用于失败后切换 Web Speech 的函数，但 `init()` 当前没有调用它。

API 选择方式为：

```javascript
window.SpeechRecognition || window.webkitSpeechRecognition
```

即同时兼容标准名称和 Chromium/WebKit 前缀名称。

### 5.2 实际路径与回退能力

1. 页面状态 `useXFYun` 默认是 `true`，所以点击录音首先进入 `startXFRecording()`，音频发送到后端 `/api/xfyun-asr`，不是首先交给浏览器 Web Speech。
2. `checkXFYun()` 未在初始化中执行，因此后端讯飞不可用时不会在录音前自动把 `useXFYun` 改为 `false`。当前“讯飞失败自动回退 Web Speech”并不完整。
3. 浏览器不支持 `SpeechRecognition` 和 `webkitSpeechRecognition` 时，页面显示“麦克风：不支持”。但检测逻辑会提前返回，即使后端讯飞路径理论上可用，也会被该浏览器 API 检测影响状态显示。
4. 麦克风权限被拒绝时显示“麦克风：未授权”。文字输入框和发送按钮是独立控件，不因权限拒绝被禁用，因此可以回退到纯文字。
5. Web Speech 的 `not-allowed`、`service-not-allowed`、`network` 等错误有可理解提示；非网络错误会停止录音。文字入口仍可继续使用。

### 5.3 HTTPS、公网和浏览器风险

- `getUserMedia()` 在普通远程 HTTP 页面通常不可用，只在 HTTPS 安全上下文或 localhost 例外。前端计算了 `isSecure`，但最终权限仍由浏览器强制执行；生产启用语音必须使用 HTTPS。
- Web Speech API 支持度不一致，`webkitSpeechRecognition` 主要依赖 Chromium 系浏览器。不能把它当作所有国产浏览器、Firefox 和受限终端上的稳定能力。
- 浏览器 Web Speech 的识别实现可能使用浏览器厂商的云端服务，不能保证离线，也不能保证只在内网传输。网络受限时可能触发 `network` 或 `service-not-allowed`。
- 默认后端讯飞路径明确依赖讯飞公网 WebSocket 和 `XF_APPID`/`XF_API_KEY`/`XF_API_SECRET`；纯内网环境不可将其视为可用。
- 前端状态文案把后端录音路径标成 “FunASR”，但实际 POST 的是 `/api/xfyun-asr`；这会造成运维和验收误判，建议后续只修正文案/状态判断，不改变本阶段逻辑。

### 5.4 如何关闭语音

- 服务端设置 `ASR_ENABLED=false`。旧变量 `VOICE_ENABLED=false` 仍兼容，但 `ASR_ENABLED` 优先。
- `/api/mode` 返回 `voice_enabled=false` 后，`detectBackendMode()` 会禁用录音按钮并显示“ASR/麦克风已关闭”。
- `deploy/docker-compose.yml` 已固定 `ASR_ENABLED: "false"`，同时 `TTS_ENABLED: "false"`。
- 会话初始化中的 `voice_enabled` 只能进一步收紧会话能力，不能越过服务端总开关开启语音。
- 当前没有独立的 Vite/前端环境变量控制语音入口；由后端环境变量和 `/api/mode` 统一控制，已经满足部署时关闭需求。

结论：关闭语音后，用户可通过 `textInput`、发送按钮和 `sendMessage()` 完成陪练；`FULL_MODE = args.full and VOICE_ENABLED` 为假，`get_asr_model()` 不执行，FunASR 不导入。文字陪练对 FunASR、讯飞和 Web Speech 均无运行时依赖。

## 6. FunASR 依赖处置建议

FunASR 不是纯历史代码：`app.py` 的 `/api/asr` 和 `get_asr_model()` 仍提供本地完整模式。但它不是默认部署路径，也不是纯文字流程依赖。

当前依赖拆分已经基本合理：

- `requirements.txt`：轻量 Web 服务依赖，不含 `funasr`、`modelscope`、`torch`、`torchaudio`。
- `requirements-full.txt`：额外包含 `funasr`、`modelscope`、`torch`、`torchaudio`、`websocket-client`、`numpy`、`pydub`。
- Dockerfile 仅安装 `requirements.txt`，默认镜像不会安装 FunASR 重依赖。

建议：

1. 内网纯文字演示和常规部署只安装 `requirements.txt`，保持 `ASR_ENABLED=false`，不下载 FunASR 模型。
2. `requirements-full.txt` 保留为可选语音扩展，不建议现在删除，因为代码仍有明确入口；若产品确认永久不提供本地 ASR，再单独删除完整模式代码和依赖。
3. `requirements-full.txt` 中的 `websocket-client` 当前未被 `app.py` 导入；讯飞实现使用标准库 `socket` 手写 WebSocket 帧。启用语音前应通过依赖审计确认它是否可删除，当前不必调整。
4. `FUNASR_MODEL` 已在 `.env.example` 中出现，但当前 `get_asr_model()` 仍硬编码 `paraformer-zh`，没有读取该变量。后续若要启用本地 ASR，应做一次小范围配置一致性修复。

## 7. 切换 AI 中心内部模型的最小步骤

### 7.1 情报助手

无需修改业务代码，先按以下方式受控验证：

1. 设置 `INTELLIGENCE_MOCK_MODE=false`。
2. 设置 `SEARCH_MCP_SUMMARIZER_API_BASE` 为 AI 中心 OpenAI 兼容网关版本根路径。
3. 设置 `SEARCH_MCP_SUMMARIZER_API_KEY` 和 `SEARCH_MCP_SUMMARIZER_MODEL`。
4. 确认网关支持 OpenAI Python SDK 的 Chat Completions 请求及较大的 `max_tokens`；当前长报告配置可能超过内部模型限制，应先用小客户/非分段链路验证限制。
5. 将内部模型域名加入 `NO_PROXY`，或按网络策略显式配置代理。
6. 搜索侧另行设置内部 `SEARCH_SERVICE_BASE_URL`；模型切换不会解决公网搜索和网页抓取可达性。

### 7.2 陪练助手

当前无需重命名变量即可切换：

1. 设置 `TRAINING_MOCK_MODE=false`（Compose）或 `MOCK_MODE=false`（项目直接启动）。
2. 将 AI 中心版本根路径填入 Compose 的 `TRAINING_MODEL_BASE_URL`，最终映射到 `DEEPSEEK_BASE_URL`。
3. 将内部模型名和密钥填入 `TRAINING_MODEL_NAME`、`TRAINING_MODEL_API_KEY`，最终映射到 `DEEPSEEK_MODEL`、`DEEPSEEK_API_KEY`。
4. 如开挂模式需不同模型，直接启动时可设置 `CHEAT_MODEL`；当前 Compose 未单独映射该变量，未设置时自动复用主模型。
5. 保持 `ASR_ENABLED=false`、`TTS_ENABLED=false`，先验证纯文字三轮和评分输出。
6. 确认内部网关支持 `/chat/completions` 和 OpenAI 风格响应，再逐步验证反转/开挂分支。

最小代码改造建议（本轮未实施）：在 `app.py` 增加通用变量别名，例如 `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` 优先，`DEEPSEEK_*` 作为兼容回退；同时把请求封装成一个内部函数，供主对话、反转模式、开挂模式和批处理复用。该改造不是接入内部模型的前置条件，可在真实验证稳定后进行。

## 8. 预留的 Embedding/Rerank 配置

两个项目的 `.env.example` 已新增以下变量：

```dotenv
EMBEDDING_ENABLED=false
EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
RERANK_ENABLED=false
RERANK_BASE_URL=
RERANK_API_KEY=
RERANK_MODEL=
RERANK_TOP_N=5
```

这些变量仅为配置契约预留：

- 默认关闭，不改变当前检索行为。
- 当前业务代码没有读取或调用它们。
- 不应在现阶段安装 Embedding/Rerank SDK、创建向量库或强行改写检索链路。
- 后续只有在词法检索质量有可复现瓶颈、内部服务已明确可用且完成数据安全评估后，才应单独立项启用。

## 9. 内网部署阻塞项与建议优先级

| 优先级 | 项目 | 问题 | 是否阻塞 | 最小处理 |
|---|---|---|---|---|
| P0 | 情报助手 | 默认真实搜索指向公网百度，正文抓取还需访问目标站点 | 阻塞纯内网真实情报 | 配置内部搜索代理，并明确受控网页出口或接受摘要-only 方案 |
| P0 | 两项目 | AI 中心协议、模型上下文/输出限制尚未做受控实测 | 阻塞真实模型验收 | 使用脱敏测试数据验证 Chat Completions、超时和长度限制 |
| P1 | 陪练助手 | 三个模型调用分支重复实现，错误/重试行为不完全一致 | 不阻塞首轮演示 | 先只验证主文字分支；后续做小范围统一封装 |
| P1 | 陪练助手 | 前端默认讯飞路径，Web Speech 自动回退函数未接入初始化 | 不阻塞文字流程，阻塞可靠语音演示 | 当前保持语音关闭；不要把语音列为演示主链路 |
| P1 | 陪练助手 | Web Speech 可能依赖厂商云服务且浏览器兼容性有限 | 不阻塞文字流程 | HTTPS + 指定受支持浏览器；仍保留文字兜底 |
| P2 | 陪练助手 | `FUNASR_MODEL` 配置未被代码读取，语音状态文案与实际讯飞路径不一致 | 不阻塞 | 真正启用语音前修正 |
| P2 | 两项目 | Embedding/Rerank 当前不存在 | 不阻塞 | 保持关闭，不接入 |

## 10. 最终判断

- **模型接口统一可行：** 两项目均可指向 AI 中心的 OpenAI 兼容 Chat Completions 网关，情报助手无需改业务代码，陪练助手无需立即重命名 `DEEPSEEK_*`。
- **Embedding/Rerank 不应成为当前集成前置条件：** 目前没有实际能力，也没有必要为演示强行引入。
- **内网真实验证的主要阻塞不是基模，而是情报搜索和网页正文出口。** 搜索代理只解决结果列表，正文抓取网络策略仍需确认。
- **语音不应作为当前部署主链路：** 浏览器 Web Speech、讯飞和 FunASR 各有不同约束；保持服务端语音关闭即可保证纯文字陪练不依赖任何 ASR。
- **可进入受控真实模型验证：** 前提是提供 AI 中心兼容网关的受控测试配置，并继续保持搜索/ASR/TTS 为 Mock 或关闭，逐服务放开，避免一次同时排查多条外部链路。
