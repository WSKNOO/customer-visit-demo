# AI 客户拜访模拟对练系统

> 让 AI 扮演真实客户，售前人员在零风险环境中无限次实战对练。

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key

# 3. 启动
python app.py
# 打开 http://127.0.0.1:5000/v2
```

## 项目结构

```
├── app.py                # Flask 后端主程序
├── static/
│   ├── index_v2.html     # 前端页面（源文件）
│   └── index.html        # 同步副本
├── knowcard/             # 知识库（场景 JSON + 原始文档）
├── requirements.txt      # Python 依赖
├── .env.example          # 配置模板
└── .gitignore
```

## 核心功能

- **五阶段对练**：初次接触 → 需求深挖 → 方案呈现 → 异议谈判 → 促成收尾
- **RAG 知识检索**：自研轻量级三维度打分算法（关键词+短语+Jaccard）
- **实时评分**：五维能力评分 + AI 教练点评 + ECharts 雷达图
- **双模式切换**：常规训练模式 + 反转学习模式
- **语音交互**：支持 Web Speech API 和讯飞实时转写
- **开挂模式**：实时知识库话术辅助

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3 + Flask |
| AI 模型 | DeepSeek-V3 (SiliconFlow API) |
| RAG 检索 | 自研 SimpleRAG（纯 Python） |
| 语音识别 | Web Speech API / 讯飞 API |
| 语音合成 | edge-tts（微软免费 TTS） |
| 前端 | HTML5 + CSS3 + Vanilla JS + ECharts 5 |
