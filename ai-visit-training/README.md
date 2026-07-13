# 🎙️ 语音对练 - 客户拜访AI对练系统

> Phase 2 启动基线：Python 3.11，默认端口 `127.0.0.1:5000`。纯文字为默认主链路，语音和 TTS 默认关闭。旧部署脚本仅兼容保留，所有连接信息必须通过 `DEPLOY_*` 环境变量提供。

## 安全启动（推荐）

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

离线 Mock 模式（不会调用模型、ASR 或 TTS）：

```bash
export MOCK_MODE=true
export ASR_ENABLED=false
export TTS_ENABLED=false
python app.py
```

访问 `http://127.0.0.1:5000`；健康检查为 `GET /api/health`。AI 陪练进程不加载语音模型：设置 `ASR_ENABLED=true`、`ASR_PROVIDER=http` 后代理到独立 `funasr-service`，设置 `TTS_ENABLED=true`、`TTS_PROVIDER=http` 后代理到独立 `tts-service`。

当前 Demo 语音链路为“浏览器 MediaRecorder 单次录音 → `/api/asr/transcribe` → 识别文本填入输入框（不自动发送）→ AI 陪练 → 用户点击 `/api/tts` 播放 WAV”。语音服务失败时文字输入和 AI 回复保持可用。模型只读外置、CPU 推理、不在启动时下载；完整 Compose 配置和部署步骤见 `deploy/DEPLOYMENT_RUNBOOK.md`。下文保留的早期全量设计说明不作为当前部署依据。

测试：

```bash
MOCK_MODE=true ASR_ENABLED=false TTS_ENABLED=false python -m unittest discover -s tests -v
```

陪练会话初始化：`POST /api/training/session/init`，请求体遵循工作区根目录 `visit_brief.schema.json`。返回的 `session_id` 可随后的 `/api/chat` 请求携带。`GET /api/training/session/:session_id` 返回前端安全的客户、角色、目标和开场问题；页面使用 `/?session_id=...` 可自动加载并开始纯文字陪练。会话仅保存在本进程内存，默认两小时过期。

真实模型模式通过 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_API_KEY` 配置；请求超时、重试和默认轮数分别由 `MODEL_REQUEST_TIMEOUT_SECONDS`、`MODEL_MAX_RETRIES`、`DEFAULT_TRAINING_ROUNDS` 控制。内部模型域名应加入 `NO_PROXY`。

Docker（轻量文字模式）：

```bash
docker build -t ai-visit-training .
docker run --rm -p 5000:5000 --env-file .env ai-visit-training
```

基于 **FunASR** 实时语音转写 + **DeepSeek V4** 模型的智能客户拜访对练Demo。

## ✨ 功能特点

- 🎤 **实时语音转写** - 使用FunASR进行高精度中文语音识别
- 🤖 **AI智能对练** - DeepSeek V4驱动，模拟真实客户场景
- 💼 **多场景支持** - 销售拜访、价格谈判、异议处理等多种场景
- 📚 **知识库集成** - 自动加载doc文件夹的行业领域资料
- 📊 **对话统计** - 实时记录练习时长和对话轮次
- 📥 **记录导出** - 支持导出对练记录用于复盘

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 (浏览器)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ 麦克风录音 │→ │ 语音显示  │  │    对话UI界面     │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/WebSocket
                      ▼
┌─────────────────────────────────────────────────────┐
│               后端服务 (Flask)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ FunASR   │  │ DeepSeek │  │  文档知识库加载   │   │
│  │ 语音转写  │→ │ API调用  │← │  (doc/目录)      │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## 📋 环境要求

- Python 3.9+
- Node.js 16+ (可选，如需额外功能)
- 麦克风设备

## 🚀 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# Windows激活
venv\Scripts\activate

# 安装Python依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件（已预设默认值）：

```env
# DeepSeek API配置
DEEPSEEK_API_KEY=<set-via-environment>
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# FunASR模型配置
FUNASR_MODEL=paraformer-zh

# 服务配置
HOST=127.0.0.1
PORT=5000

# 文档路径（相对或绝对路径）
DOC_PATH=./doc
```

### 3. 启动服务

```bash
python app.py
```

启动成功后会看到：
```
==================================================
🎙️ 语音联动Demo - 客户拜访AI对练系统
==================================================
📂 文档路径: ./doc
🤖 AI模型: deepseek-chat
🌐 访问地址: http://127.0.0.1:5000
==================================================

✅ FunASR模型加载成功
📚 已加载知识库:
...
```

### 4. 访问应用

打开浏览器访问：**http://127.0.0.1:5000**

## 🎯 使用指南

### 基本操作流程

1. **选择场景** - 在右侧面板选择练习场景（通用销售、技术产品、价格谈判等）
2. **开始对话**：
   - **文字输入**：在底部输入框输入内容，点击发送按钮或按回车
   - **语音输入**：按住麦克风按钮说话，松开后自动发送
3. **AI响应** - AI会根据选择的场景扮演相应角色进行互动
4. **查看转写** - 右侧面板实时显示语音识别结果
5. **导出记录** - 点击"导出记录"保存对练内容

### 场景说明

| 场景 | 描述 | 适用情况 |
|------|------|----------|
| 💼 通用销售拜访 | 标准销售流程演练 | 初学者入门 |
| 🔧 技术产品推介 | 技术型产品介绍 | 技术/SaaS产品 |
| 💰 价格谈判演练 | 价格相关攻防 | 销售进阶训练 |
| 🛡️ 异议处理训练 | 处理客户拒绝 | 提升应变能力 |
| ⚔️ 竞品对比攻防 | 竞争优势展示 | 竞争激烈的行业 |

## 📁 项目结构

```
demo2/
├── app.py              # Flask后端主程序
├── requirements.txt    # Python依赖列表
├── .env                # 环境变量配置
├── README.md           # 项目说明文档
├── static/
│   └── index.html      # 前端页面（包含CSS/JS）
└── doc/                # 行业资料知识库
    ├── 1/
    │   ├── 销售手册/
    │   ├── 培训资料/
    │   ├── Q&A/
    │   ├── 技术文档/
    │   ├── 竞品分析/
    │   └── ...
    ├── 2/
    └── 3/
```

## 🔧 API接口文档

### POST `/api/asr` - 语音转文字

**请求体：**
```json
{
  "audio": "base64编码的音频数据",
  "format": "wav"
}
```

**响应：**
```json
{
  "success": true,
  "text": "识别出的文字内容"
}
```

### POST `/api/chat` - AI对话

**请求体：**
```json
{
  "messages": [
    {"role": "user", "content": "用户消息"},
    ...
  ]
}
```

**响应：**
```json
{
  "success": true,
  "content": "AI回复内容",
  "usage": {"prompt_tokens": 100, "completion_tokens": 200}
}
```

### GET `/api/knowledge` - 获取知识库信息

**响应：**
```json
{
  "success": true,
  "knowledge": "知识库内容文本"
}
```

### GET `/api/health` - 健康检查

**响应：**
```json
{
  "status": "ok",
  "asr_model_loaded": true
}
```

## 🎨 自定义配置

### 修改AI角色设定

编辑 `app.py` 中的 `system_prompt` 变量：

```python
system_prompt = """你是一位专业的客户拜访AI对练教练...

## 对话规则
1. 首先询问用户要练习的产品/服务类型
2. 然后开始角色扮演...
"""
```

### 添加新的练习场景

编辑 `static/index.html` 中的场景选项：

```html
<div class="scene-option" data-scene="新场景">
    📌 新场景名称
</div>
```

### 扩展知识库

将文档放入 `doc/` 目录下的对应子文件夹：

```
doc/
├── 1/
│   ├── 销售手册/   # 放置销售话术文档
│   ├── 培训资料/   # 放置培训PPT/PDF
│   ├── Q&A/        # 放置常见问题解答
│   └── ...
```

支持的格式：`.docx`, `.pdf`, `.pptx`, `.xlsx`, `.txt`

## ⚠️ 注意事项

1. **麦克风权限**：首次使用需要允许浏览器访问麦克风权限
2. **网络连接**：需要能够访问DeepSeek API（可能需要代理）
3. **FunASR模型**：首次运行会自动下载模型文件（约2GB），请确保网络畅通
4. **浏览器兼容性**：推荐使用Chrome、Edge等现代浏览器

## 🐛 常见问题

### Q: FunASR模型加载失败怎么办？
A: 程序会自动降级为备用方案。检查网络连接，或手动安装依赖：
```bash
pip install funasr modelscope torch
```

### Q: 语音识别不准确？
A: 
- 确保环境安静，减少背景噪音
- 距离麦克风适当距离（20-30cm）
- 语速适中，发音清晰

### Q: DeepSeek API报错？
A: 
- 检查API Key是否正确
- 确认账户余额充足
- 查看是否需要开启API访问权限

### Q: 如何部署到生产环境？
A: 推荐使用Gunicorn+Nginx：
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 🔄 与Dify工作流集成

本Demo已内置DeepSeek API直接调用。如果需要接入Dify工作流：

1. 在Dify平台创建工作流，配置知识库（上传doc/目录文档）
2. 获取Dify工作流的API Endpoint和Key
3. 修改 `app.py` 中的 `call_deepseek()` 函数：

```python
def call_dify_workflow(messages):
    # Dify API调用示例
    url = "https://your-dify-instance.com/v1/chat-messages"
    headers = {
        "Authorization": "Bearer YOUR_DIFY_API_KEY",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {},
        "query": messages[-1]["content"],
        "response_mode": "blocking",
        "conversation_id": "",
        "user": "user-123"
    }
    # ...发送请求并处理响应
```

## 📊 性能优化建议

1. **FunASR加速**：安装CUDA版本的PyTorch以启用GPU加速
2. **模型缓存**：模型下载后会缓存在本地，无需重复下载
3. **音频压缩**：可考虑降低音频采样率减少传输大小
4. **对话缓存**：合理控制消息历史长度，避免token超限

## 📄 License

MIT License

## 👨‍💻 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Flask | 3.0+ |
| 语音识别 | FunASR | 1.1+ |
| AI模型 | DeepSeek V4 | - |
| 前端 | HTML5/CSS3/ES6+ | - |
| 音频采集 | Web Audio API | - |

---

**享受AI驱动的客户拜访对练体验！🚀**
