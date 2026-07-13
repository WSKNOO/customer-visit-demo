# RAG 技术实现方案深度解读

> 全称：Retrieval-Augmented Generation（检索增强生成）  
> 本项目：自研轻量级 RAG，零外部依赖，纯 Python 实现

---

## 一、核心设计理念

### 1.1 要解决什么问题

传统 LLM 对话有两个致命缺陷：

| 缺陷 | 具体表现 | RAG 如何解决 |
|------|----------|-------------|
| **知识盲区** | ChatGPT 不知道你们公司云电脑的 GPU 虚拟化性能参数 | 把公司产品文档注入 System Prompt |
| **编造幻觉** | AI 会自行编造不存在的客户案例 | 强制 AI 只引用检索到的数据，否则说"我需要确认" |

### 1.2 为什么不用现成的向量数据库？

| 方案 | 问题 |
|------|------|
| ChromaDB / Milvus | 需要安装向量数据库服务 |
| sentence-transformers | 需要下载 500MB+ 的 embedding 模型 |
| OpenAI Embedding API | 每次检索都调 API，延迟+成本 |

**本项目的选择**：关键词 + 短语 + Jaccard 混合检索，纯 Python 实现，零安装，启动即用。

---

## 二、数据结构设计

### 2.1 检索块（Chunk） 的标准化格式

```python
chunk = {
    'scene': 'knowcard/AI/合同审查大模型',  # 所属场景
    'source': '文档/产品介绍.docx#chunk3',   # 来源文件 + 分块编号
    'text': '合同审查大模型支持30+合同类型...', # 检索文本
    'keywords': ['合同审查', '大模型', ...],   # 预提取的关键词列表
    'card_type': 'raw_doc'                  # 块类型
}
```

### 2.2 三种块类型（数据来源）

```
                                    knowcard/{场景}/
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            scene_card.json      knowledge_cards.json     原始文档
               场景卡                 知识卡片              .docx/.pdf等
                │                      │                     │
            add_scene_card()    add_knowledge_cards()  add_raw_doc()
                │                      │                     │
                ▼                      ▼                     ▼
          1个 chunk            每张卡1个 chunk        每5段1个 chunk
     card_type='scene_card'   card_type=产品/案例   card_type='raw_doc'
```

---

## 三、文档加载流程

### 3.1 入口：`load_scene(scene_id)`

```python
def load_scene(self, scene_id, max_chunks=100):
    # 1. 防重复加载
    if scene_id in self.loaded_scenes:
        return
    
    # 2. 解析路径 → 确定目标目录
    if scene_id.startswith('knowcard/'):
        target = KNOWCARD_PATH / scene_id.replace('knowcard/', '')
    else:
        target = DOC_PATH / scene_id.replace('doc/', '')
    
    # 3. 按优先级加载
    # Step 1: 场景卡（单个 JSON）
    if (target / 'scene_card.json').exists():
        add_scene_card(json_data, scene_id)
    
    # Step 2: 知识卡片（JSON 数组）
    if (target / 'knowledge_cards.json').exists():
        add_knowledge_cards(json_array, scene_id)
    
    # Step 3: 原始文档（递归遍历）
    for ext in ['*.docx', '*.pdf', '*.pptx', '*.xlsx', '*.txt']:
        for file in target.rglob(ext):
            text = _extract_text(file)          # 文档解析
            add_raw_doc(text, file.name, scene_id)  # 分块入库
```

### 3.2 场景卡加载：`add_scene_card()`

```python
def add_scene_card(self, scene_card, scene_name):
    # 从 JSON 中提取所有有意义的字段 → 拼接为长文本
    parts = [
        scene_card.get('scenario_name', ''),
        client_profile.get('role', ''),      # 例如 "CTO"
        client_profile.get('personality', ''), # 例如 "谨慎、技术导向"
        client_profile.get('current_situation', ''),
    ]
    # 痛点
    for pp in scene_card.get('pain_points', []):
        parts.append(pp.get('point', ''))
    # 产品匹配
    for pm in scene_card.get('product_match', []):
        parts.append(pm.get('product', ''))
    # 常见异议
    for ob in scene_card.get('objections', []):
        parts.append(ob.get('objection', ''))
    
    full_text = ' '.join(parts)
    keywords = self._extract_keywords(full_text)
    self.chunks.append({...})
```

### 3.3 知识卡片加载：`add_knowledge_cards()`

**5 种卡片类型，每种提取策略不同**：

```python
def add_knowledge_cards(self, cards, scene_name):
    for card in cards:
        ct = card.get('card_type')  # product/case/objection/solution/parameter
        
        if ct == 'product':   # 产品卡
            text = 产品名 + 定位 + 核心能力 + 竞争优势
        
        elif ct == 'case':    # 案例卡
            text = 案例名 + 背景 + 方案 + "准确率=99.5% 响应时间<3ms"
        
        elif ct == 'objection':  # 异议卡
            text = 异议类别 + 异议原文 + 根本顾虑 + 回应框架
        
        elif ct == 'solution':   # 方案卡
            text = 方案名 + 适用场景
        
        elif ct == 'parameter':  # 参数卡
            text = "GPU虚拟化 99.5% 3ms"
```

### 3.4 原始文档加载：`add_raw_doc()`

```python
def add_raw_doc(self, text, file_name, scene_name):
    # 按段落分块（每 5 段合并）
    paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 20]
    
    for i in range(0, len(paragraphs), 5):
        chunk_text = ' '.join(paragraphs[i:i+5])  # 5段合并
    
        keywords = self._extract_keywords(chunk_text)  # 预提取关键词
        self.chunks.append({
            'source': f'文档/{file_name}#chunk{i//5}',
            'text': chunk_text,
            'keywords': keywords
        })
```

### 3.5 文档解析：`_extract_text()`

```python
def _extract_text(file_path):
    suffix = file_path.suffix.lower()
    
    if suffix == '.docx':
        doc = Document(file_path)            # python-docx
        return '\n'.join(p.text for p in doc.paragraphs)
    
    elif suffix == '.pdf':
        reader = PdfReader(file_path)        # PyPDF2
        return '\n'.join(p.extract_text() for p in reader.pages)
    
    elif suffix == '.pptx':
        prs = Presentation(file_path)        # python-pptx
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    texts.append(shape.text)
        return '\n'.join(texts)
    
    elif suffix == '.xlsx':
        wb = load_workbook(file_path)        # openpyxl
        return '\n'.join(str(cell.value) for row in ws for cell in row)
    
    elif suffix == '.txt':
        return file_path.read_text(encoding='utf-8')
```

---

## 四、检索打分算法（核心）

### 4.1 总分公式

```
相关性分数 = 关键词命中 × 0.50 + 短语匹配 × 0.35 + Jaccard × 0.15
```

### 4.2 维度 1：关键词命中（权重 50%）

```python
def _compute_relevance(query_tokens, chunk_text, chunk_keywords):
    kw_hits = 0
    for qt in query_tokens:          # 遍历用户的每个关键词
        if qt in chunk_keywords:     # ① 精确命中关键词表
            kw_hits += 1.0           #    满分 1.0
        elif any(qt in ck for ck in chunk_keywords):
            kw_hits += 0.5           # ② 部分匹配（如"云电脑"匹配到"云省分-云电脑"）
        elif qt in chunk_text:       # ③ 在全文出现
            kw_hits += 0.3           #    兜底 0.3
    
    kw_score = min(kw_hits / len(query_tokens), 1.0)  # 归一化到 [0,1]
    score += kw_score * 0.5
```

**举例**：
- 用户问："云电脑价格"
- 分词 → `['云电脑', '价格']`
- 找 chunk 的 keywords：`['云电脑', 'GPU虚拟化', '价格体系', '套餐']`
- `'云电脑'` → 精确命中 → +1.0
- `'价格'` → 部分匹配 `'价格体系'` → +0.5
- 总分 = (1.0 + 0.5) / 2 = 0.75 × 0.5 = **0.375**

### 4.3 维度 2：短语匹配（权重 35%）

```python
    phrase_hits = 0
    for i in range(len(query_tokens)):
        for win in [2, 3, 4]:               # 2字/3字/4字滑动窗口
            if i + win <= len(query_tokens):
                phrase = ''.join(query_tokens[i:i+win])  # 连续拼接
                if phrase in chunk_text:
                    phrase_hits += win        # 越长匹配，权重越高
    phrase_score = min(phrase_hits / 10.0, 1.0)
    score += phrase_score * 0.35
```

**举例**：
- 用户问："云电脑价格"
- tokens = `['云电脑', '价格']`
- 2字滑动 = `'云电脑价格'` (4字)
- 3字滑动 = `'云电脑价格'` (超出，跳过)
- 4字滑动 = 超出，跳过
- 如果 `'云电脑价格'` 出现在 chunk_text 中 → phrase_hits = 4
- phrase_score = 4/10 = 0.4 × 0.35 = **0.14**

**为什么越长权重越高**？因为"云电脑价格"比单独"云电脑"更精确，说明这个 chunk 更相关。

### 4.4 维度 3：Jaccard 兜底（权重 15%）

```python
    q_chars = set(''.join(query_tokens))     # 用户问题字符集
    c_chars = set(chunk_text[:500])           # chunk 前 500 字字符集
    jaccard = len(q_chars & c_chars) / len(q_chars | c_chars)  # 交集/并集
    score += jaccard * 0.15
```

**为什么需要 Jaccard**？前两个维度都依赖"分词是否准确"。Jaccard 在字符级别做兜底——即使分词错了，只要 chunk 里有足够多相同的汉字，就能被召回。

### 4.5 综合示例

用户问："云电脑 GPU 虚拟化性能"

| 维度 | 计算过程 | 得分 |
|------|----------|:--:|
| 关键词 (0.50) | '云电脑'命中 + 'GPU'命中 + '虚拟化'部分匹配 + '性能'全文出现 → (1+1+0.5+0.3)/4 × 0.5 | **0.35** |
| 短语 (0.35) | '云电脑GPU'+'GPU虚拟化'+'虚拟化性能' → 6 × 0.35/10 | **0.21** |
| Jaccard (0.15) | 交集/并集 ≈ 0.6 × 0.15 | **0.09** |
| **总分** | | **0.65** |

---

## 五、检索流程

### 5.1 主流程：`search(query, scene_id, top_k)`

```python
def search(self, query, scene_id=None, top_k=8):
    # Step 1: 对用户问题分词 + 提取关键词
    query_tokens = self._extract_keywords(query)
    # "你们云电脑的GPU虚拟化性能怎么样" 
    # → ['云电脑', 'GPU', '虚拟化', '性能']
    
    # Step 2: 遍历所有 chunk，计算相关性
    scored = []
    for chunk in self.chunks:
        if scene_id and chunk['scene'] != scene_id:
            continue                    # 场景过滤：只搜当前场景
        score = self._compute_relevance(query_tokens, chunk['text'], chunk['keywords'])
        if score > 0:
            scored.append((score, chunk))
    
    # Step 3: 排序
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Step 4: 去重（同一文档的前 50 字相同 → 合并）
    deduped = []
    seen = set()
    for score, chunk in scored[:top_k]:
        fingerprint = chunk['text'][:50]   # 前 50 字做指纹
        if fingerprint not in seen:
            deduped.append((score, chunk))
            seen.add(fingerprint)
    
    return deduped[:top_k]
```

### 5.2 中文分词：`_tokenize()`

```python
def _tokenize(self, text):
    # 步骤1：按标点切分
    tokens = re.split(r'[，。！？；、：\n\r\t\s,\.!\?;:]+', text)
    tokens = [t for t in tokens if len(t) >= 2 and not t.isdigit()]
    
    # 步骤2：对长词做 bigram 拆解
    #   "合同审查大模型" → 补充 ['合同审查', '审查大', '大模型', '模型']
    extra = []
    for t in tokens:
        if len(t) >= 4:
            for i in range(len(t)-1):
                bigram = t[i:i+2]
                extra.append(bigram)
    tokens.extend(extra)
    return tokens
```

### 5.3 关键词提取：`_extract_keywords()`

```python
def _extract_keywords(self, text, top_n=20):
    stopwords = {'的','了','在','是','我','有','和','就','不','人','都',...}  # 30+ 停用词
    
    tokens = self._tokenize(text)
    
    # 词频统计（过滤停用词）
    freq = {}
    for t in tokens:
        if t not in stopwords:
            freq[t] = freq.get(t, 0) + 1
    
    # 取频次最高的 top_n 个
    sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [kw for kw, _ in sorted_kw]
```

---

## 六、检索结果格式化

### 6.1 `format_context(results, max_chars)`

```python
def format_context(self, results, max_chars=4000):
    lines = []
    total = 0
    for score, chunk in results:
        prefix = '★' if score > 0.3 else '·'    # 高分标记
        src = chunk['source']
        if '/chunk' in src:
            src = src.split('/chunk')[0]          # 去掉 chunk 编号
        
        line = f"{prefix} 出处: {src}\n   {chunk['text'][:350]}"
        if total + len(line) > max_chars:
            break                                 # 总量不超过 max_chars
        lines.append(line)
        total += len(line)
    
    return '\n'.join(lines)
```

输出示例：
```
★ 出处: 知识卡/product/云电脑-GPU虚拟化
   GPU虚拟化性能损耗<3%，支持NVIDIA全系列GPU...
· 出处: 文档/竞品分析.docx
   与阿里云无影对比：阿里云GPU虚拟化通过直通模式...
```

### 6.2 注入 System Prompt

```python
# 在 call_deepseek() 中
knowledge = rag.format_context(results, max_chars=3500)

system_prompt = f"""
...
## 知识库参考
{knowledge}
...
"""
```

---

## 七、在不同场景中的 RAG 使用

### 7.1 常规对练模式（`/api/chat`）

```
用法: 辅助 AI 客户"刁难"销售
  
  提取 messages 中最近一条 assistant 消息
    → rag.search(问题, scene_id=当前场景, top_k=12)
    → 注入 System Prompt 的"知识库参考"段落
  
  效果: AI 客户能抛出具体的竞品名、参数、案例
        例如："你们GPU虚拟化损耗<3%？阿里云无影也是<3%，优势在哪？"
```

### 7.2 反转模式（`/api/reverse-chat`）

```
用法: 辅助 AI 售前经理"回答"客户

  步骤1: 关键词匹配场景名（如"云电脑"→ 找到"标品/云省分-云电脑"）
  步骤2: 优先加载名称匹配的场景，RAG 检索 top_k=5
  步骤3: 不够再随机加载其他场景补充
  
  效果: AI 售前经理的回答有数据、有案例、有来源
        底部显示"参考文档"列表 + 下载链接
```

### 7.3 开挂模式（`/api/cheat`）

```
用法: 实时辅助销售回答

  双路检索:
    路1: 用"完整对话上下文"搜索 → 召回相关产品/方案
    路2: 用"客户最后一条消息"搜索 → 召回精准异议回应
  
  效果: 两条检索结果合并 → LLM 生成最优答复
        销售看到精确话术 + 客户潜在顾虑分析
```

---

## 八、完整数据流

```
┌─────────────────────────────────────────────────────────────┐
│                    knowcard/ 知识库                           │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ scene_card   │  │ knowledge_cards  │  │ 原始文档      │  │
│  │ 场景卡 1个    │  │ 知识卡 N张        │  │ .docx/.pdf等  │  │
│  └──────┬───────┘  └────────┬─────────┘  └──────┬───────┘  │
│         │                   │                    │          │
│         ▼                   ▼                    ▼          │
│    提取关键字段          按类型提取语义       按段落分块       │
│    构建长文本            构建文本块           5段合并          │
│         │                   │                    │          │
│         ▼                   ▼                    ▼          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SimpleRAG.chunks[]                       │   │
│  │  [{scene, source, text, keywords, card_type}, ...]    │   │
│  └──────────────────────┬───────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      用户提问                                │
│            "你们云电脑的GPU虚拟化性能怎么样？"                  │
└──────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               _extract_keywords()                            │
│         分词 → 去停用词 → 词频排序 → top 20                   │
│         ['云电脑', 'GPU', '虚拟化', '性能']                   │
└──────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              _compute_relevance()                            │
│                                                             │
│   关键词命中(50%): '云电脑'+1, 'GPU'+1, '虚拟化'+0.5,         │
│                    '性能'+0.3 → (2.8/4) × 0.5 = 0.35        │
│   短语匹配(35%):   '云电脑GPU'+'GPU虚拟化'+'虚拟化性能'       │
│                    → 6/10 × 0.35 = 0.21                     │
│   Jaccard(15%):    字符交集/并集 ≈ 0.6 × 0.15 = 0.09        │
│                                                             │
│   总分: 0.65                                                │
└──────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              search()                                        │
│   遍历所有 chunk → 打分 → 排序 → 去重 → top_k=8              │
└──────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              format_context(max_chars=3500)                  │
│   ★ 出处: 知识卡/product/云电脑-GPU虚拟化                    │
│      GPU虚拟化性能损耗<3%...                                 │
│   · 出处: 文档/竞品分析.docx                                 │
│      与阿里云无影对比...                                     │
└──────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              call_deepseek()                                 │
│   System Prompt = 场景 + 阶段 + 规则 + {检索结果}             │
│   → DeepSeek-V3                                             │
│   → "你们GPU虚拟化损耗<3%？阿里云无影也是<3%，优势在哪？"       │
└─────────────────────────────────────────────────────────────┘
```

---

## 九、优劣势 & 升级路线

### 当前方案的优缺点

| 优点 | 缺点 |
|------|------|
| ✅ 零外部依赖，pip 装完就能跑 | ❌ 语义理解弱于向量检索 |
| ✅ 关键词+短语在结构化场景下精度高 | ❌ 无法处理同义词（"便宜"≠"低价"） |
| ✅ 启动即用，不需要下载模型 | ❌ 长文本检索慢（O(n) vs O(logn)） |
| ✅ 来源可追溯，精确到文档名 | ❌ 无跨语言能力 |

### 升级路线

```
当前 (v1): 关键词 + 短语 + Jaccard
         ↓  升级成本: ~3 天
升级 (v2): BM25 + 向量混合检索
         ├── BM25: 替代当前的关键词匹配（更科学的 TF-IDF）
         └── 向量: sentence-transformers → 512维向量 → ChromaDB
         ↓  升级成本: ~5 天
升级 (v3): HyDE (Hypothetical Document Embeddings)
         └── 先让 LLM 生成"理想答案" → 用理想答案做向量检索
            效果: 召回率提升 30%+
```

---

## 十、答辩时怎么讲 RAG

### 30 秒版本

> "我们自研了一套轻量级 RAG 检索系统，纯 Python 实现，不需要向量数据库。核心是三维度混合打分：关键词占 50%、短语匹配占 35%、字符级 Jaccard 占 15%。在这个场景下，关键词匹配精度已经够用，因为我们把文档拆成了结构化的原子知识卡。"

### 如果被追问"为什么不用向量数据库"

> "这是成本收益权衡。向量检索需要 embedding 模型（500MB+ 下载）或 API 调用（每次+0.5 秒延迟）。我们的场景特殊——知识卡是结构化的，产品名、参数值都是精确关键词，关键词匹配在这个场景下精度已够。Demo 阶段追求『秒级启动、零依赖』。"

### 如果被追问"准确率怎么样"

> "定性评估：能精准匹配到对应产品的竞品分析和参数卡。定量评估的话，下一步计划用『AI 回答中引用的数据是否与原文一致』作为准确率指标。目前估计，关键词+短语命中率约 70-80%，纯口语化表达约 50-60%，升级向量检索后可提升到 85%+。"
