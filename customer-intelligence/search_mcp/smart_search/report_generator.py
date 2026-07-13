"""
Report Generator — 基于收集到的内容，使用AI生成结构化客户拜访简报。

核心原则：
1. 只使用搜索材料中出现的信息，不得编造
2. 事实和推测严格分开标注
3. 关键结论必须带来源链接
4. 不确定时明确说明
5. 生成不少于5万字的详实报告
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from search_mcp.config import get_config
from search_mcp.smart_search.content_collector import SourceItem
from search_mcp.smart_search.product_catalog import format_catalog_text, search_products


# ── 报告系统 Prompt ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一名政企客户售前分析专家，请基于提供的联网检索材料，生成一份结构化的客户拜访前情报简报。

## 核心约束（必须遵守）

1. **只使用材料中出现的信息作为事实，不得编造**
2. **潜在需求、产品匹配、商机判断必须明确标注为"推测"**
3. **重要事实后标注来源编号，格式如 [1][2]**
4. **如果材料不足，请写明"未检索到明确证据"，不要强行下结论**
5. **输出必须是完整的中文Markdown格式**
6. **每个模块内容必须详尽充实，整体不少于5万字**
7. **各模块按分析逻辑展开，写足细节，不能只列要点**

## 输出结构

简报必须包含以下十个模块：

### 一、客户基本画像
- 企业全称、简称、企业性质（央企/国企/民企等）
- 所属行业、主营业务详情
- 上级单位、集团关系、下属子公司
- 组织架构与领导班子（标注信息获取时间）
- 企业规模（员工数、营收等，标注发布时间）
- 区域布局与分支机构

### 二、近期重点动态（按时间倒序）
- 近一年重大新闻、公告、事件
- 战略合作与签约项目
- 会议、论坛、领导调研
- 项目建设与项目验收
- 表彰、荣誉、资质获取
- 每条动态标注时间和来源

### 三、数字化/智能化线索
- AI、大模型、人工智能相关动向
- 大数据、数据治理、数据中台建设
- 云计算、云平台、算力部署
- 网络安全、数据安全、合规需求
- 5G、物联网、工业互联网
- 信创替代、国产化、自主可控
- 信息化系统建设与升级
- 每条线索标注来源和置信度

### 四、潜在业务痛点（推测，标注置信度）
- 基于行业特点分析可能痛点
- 基于公开信息推断潜在问题
- 区分"明确提及"和"推测可能"
- 每个痛点标注依据来源

### 五、可能匹配的产品能力
- 根据分析出的需求匹配产品
- 参考提供的产品能力目录
- 说明匹配理由和切入方式
- 列出建议推荐的具体产品ID

### 六、拜访切入点建议
- 开场话题设计（基于客户动态）
- 沟通切入方式
- 避免提及的敏感话题
- 建议展示的案例或方案

### 七、建议提问清单
- 面向客户不同角色的提问
- 用于确认需求和痛点的关键问题
- 问题应具有针对性和可操作性

### 八、后续商机判断
- 可跟进的业务方向
- 优先级排序
- 预计时间窗口
- 注意事项与风险

### 九、风险与不确定性
- 说明哪些内容证据不足
- 指出需要人工确认的关键信息
- 标注信息的时间敏感性

### 十、信息来源（完整列表）
- 按编号列出所有引用来源
- 包含标题、链接、来源类型
- 方便人工核验

## 格式要求
- 使用Markdown格式
- 适当使用标题层级（# ## ### ####）
- 使用表格呈现结构化数据
- 使用列表呈现要点
- 重要数据加粗标注
- 每个大节内容不少于2000字"""


def _truncate_text(text: str, max_chars: int = 80000) -> str:
    """截断过长的文本，保留开头和结尾。"""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half]}\n\n[... 中间内容已截断，共 {len(text)} 字符 ...]\n\n{text[-half:]}"


def _format_sources_for_prompt(items: List[SourceItem]) -> str:
    """将搜索到的内容格式化为模型可用的上下文。"""
    parts = []
    for i, item in enumerate(items):
        source_type = item.source_type
        dim = item.dimension
        content_preview = item.content[:5000] if item.content else item.snippet
        parts.append(
            f"[来源 {i+1}] 标题: {item.title}\n"
            f"链接: {item.url}\n"
            f"类型: {source_type} | 维度: {dim}\n"
            f"内容:\n{content_preview}\n"
            f"---\n"
        )
    return "\n".join(parts)


def _call_ai(prompt: str, system_prompt: str = None,
             max_tokens: int = 16384, temperature: float = 0.1) -> str:
    """调用AI生成内容。"""
    cfg = get_config()
    sum_cfg = cfg.get("summarizer", {})
    api_key = sum_cfg.get("api_key", "")
    api_base = sum_cfg.get("api_base", "https://api.openai.com/v1")
    model = sum_cfg.get("model", "gpt-4o-mini")

    if not api_key:
        raise RuntimeError("AI summarizer not configured: api_key is empty")

    from openai import OpenAI
    client = OpenAI(base_url=api_base, api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _generate_section(section_name: str, section_instruction: str,
                      context: str, prev_content: str = "") -> str:
    """生成报告的一个模块。"""
    prompt = f"""请基于以下检索材料，撰写报告模块「{section_name}」。

{section_instruction}

检索材料如下：
{_truncate_text(context, 60000)}

已完成的上一模块内容（供参考，请勿重复）：
{prev_content[:3000] if prev_content else "（无）"}

要求：
- 只使用材料中出现的信息
- 事实带来源编号
- 内容详实，按逻辑展开分析
- 不少于3000字
"""
    return _call_ai(prompt, system_prompt=SYSTEM_PROMPT,
                    max_tokens=8192, temperature=0.3)


def generate_full_report(company_name: str,
                          items: List[SourceItem],
                          visit_purpose: str = "",
                          focus_areas: List[str] = None) -> str:
    """
    基于收集到的内容，生成完整的客户拜访简报。

    Args:
        company_name: 客户企业名称。
        items: 收集到的 SourceItem 列表。
        visit_purpose: 拜访目的描述。
        focus_areas: 关注方向列表。

    Returns:
        完整的 Markdown 格式报告。
    """
    # ── 准备上下文 ───────────────────────────────────────────────────────
    source_context = _format_sources_for_prompt(items)

    # 统计各类型来源
    type_count: Dict[str, int] = {}
    for item in items:
        t = item.source_type
        type_count[t] = type_count.get(t, 0) + 1

    # 提取关键词用于产品匹配
    all_keywords = []
    for item in items:
        all_keywords.append(item.title)
        if item.snippet:
            all_keywords.append(item.snippet)

    # 产品匹配
    product_catalog_text = format_catalog_text()
    matched_products = search_products(all_keywords)

    # ── 构建综合 Prompt ──────────────────────────────────────────────────
    prompt = f"""# 客户拜访情报简报生成任务

## 客户信息
- **企业名称**: {company_name}
- **拜访目的**: {visit_purpose or '客户拜访前准备'}
- **关注方向**: {', '.join(focus_areas) if focus_areas else '全面分析'}
- **报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 搜索概况
- 共检索到 {len(items)} 条有效信息来源
- 来源分布：{json.dumps(type_count, ensure_ascii=False)}

## 检索材料（请逐一阅读分析）
{_truncate_text(source_context, 80000)}

## 产品能力目录（用于模块五匹配）
{_truncate_text(product_catalog_text, 5000)}

## 已匹配产品
{', '.join([p.name for p in matched_products[:8]]) if matched_products else '（待分析后匹配）'}

## 输出要求
请严格按照系统指令中的10个模块结构，生成完整的客户拜访简报。

每个模块要求：
- **一、客户基本画像**: 4000字以上
- **二、近期重点动态**: 8000字以上，每条动态详细描述
- **三、数字化/智能化线索**: 8000字以上，每个线索展开分析
- **四、潜在业务痛点**: 5000字以上
- **五、可能匹配的产品能力**: 5000字以上
- **六、拜访切入点建议**: 4000字以上
- **七、建议提问清单**: 3000字以上
- **八、后续商机判断**: 5000字以上
- **九、风险与不确定性**: 3000字以上
- **十、信息来源**: 完整的链接列表

**整体报告总字数不少于50000字（50,000字）**。
每个模块请深入分析，不要停留在表面要点罗列。
对于材料中提供的数据，请展开分析其含义和影响。
对于推测性内容，请标注理由和置信度。
"""
    # ── 调用AI生成完整报告 ───────────────────────────────────────────────
    print(f"[report_gen] 正在调用AI生成报告（{company_name}）...", file=sys.stderr)
    print(f"[report_gen] 共 {len(items)} 条来源，{sum(len(i.content or '') for i in items)} 字符内容",
          file=sys.stderr)

    try:
        report = _call_ai(prompt, system_prompt=SYSTEM_PROMPT,
                          max_tokens=65536, temperature=0.3)
    except Exception as exc:
        print(f"[report_gen] AI生成失败: {exc}", file=sys.stderr)
        # 尝试用更小的上下文重试
        try:
            print(f"[report_gen] 尝试缩短上下文后重试...", file=sys.stderr)
            report = _call_ai(
                f"请为{company_name}生成一份客户拜访简报。\n\n"
                f"搜索材料摘要如下（共{len(items)}条来源）：\n"
                + _truncate_text(source_context, 40000)
                + f"\n\n产品目录：\n{_truncate_text(product_catalog_text, 3000)}",
                system_prompt=SYSTEM_PROMPT,
                max_tokens=65536, temperature=0.3,
            )
        except Exception as exc2:
            report = f"# 报告生成失败\n\nAI生成报告时出错：{exc}\n重试也失败：{exc2}"

    total_chars = len(report)
    print(f"[report_gen] 报告生成完成，共 {total_chars} 字", file=sys.stderr)

    return report


def generate_report_sequentially(company_name: str,
                                  items: List[SourceItem],
                                  visit_purpose: str = "",
                                  focus_areas: List[str] = None) -> str:
    """
    逐模块生成报告（适合长报告，避免单次调用超长）。

    每个模块独立调用AI，最后拼接为完整报告。
    """
    sections = []
    source_context = _format_sources_for_prompt(items)

    # 提取前2000条目的完整内容作为主上下文
    main_context = ""
    for i, item in enumerate(items):
        content_length = len(item.content or "")
        snippet = item.content[:3000] if item.content else item.snippet
        main_context += (
            f"\n[来源{i+1}] {item.title}\n"
            f"URL: {item.url}\n"
            f"{snippet}\n"
        )

    print(f"[report_gen] 准备逐模块生成，主上下文 {len(main_context)} 字符", file=sys.stderr)

    # 定义各模块的生成指令
    module_defs = [
        ("一、客户基本画像",
         "整理企业全称、简称、企业性质、所属行业、主营业务、上级单位、组织架构、领导班子、企业规模、区域布局等内容。"
         "注意标注信息获取时间。展开分析4000字以上。"),
        ("二、近期重点动态",
         "按时间倒序整理近一年重大新闻、公告、战略合作、签约项目、会议论坛、领导调研、项目建设、表彰荣誉等。"
         "每条动态详细描述背景和意义。8000字以上。"),
        ("三、数字化/智能化线索",
         "从材料中提取AI、大数据、云、算力、安全、5G、物联网、信创、信息化建设等相关信息。"
         "每条线索展开分析其对客户的意义和可能的项目机会。8000字以上。"),
        ("四、潜在业务痛点",
         "基于行业特点和公开信息归纳可能痛点。区分'明确提及'和'推测可能'。"
         "每个痛点分析其影响。5000字以上。"),
        ("五、可能匹配的产品能力",
         "基于识别的需求和痛点，匹配产品能力目录中的产品。说明匹配理由和切入方式。"
         "可列出多个产品方向。5000字以上。"),
        ("六、拜访切入点建议",
         "设计开场话题、沟通切入方式，基于客户最新动态设计交流角度。"
         "避免提及的敏感话题。4000字以上。"),
        ("七、建议提问清单",
         "面向不同角色（领导层、业务部门、技术部门）的提问建议。"
         "问题应具体、有针对性。3000字以上。"),
        ("八、后续商机判断",
         "判断可跟进方向、优先级、时间窗口、预期规模。"
         "区分短期和长期机会。5000字以上。"),
        ("九、风险与不确定性",
         "说明证据不足的内容、需要人工确认的关键信息、信息时效性。"
         "明确标注推测项。3000字以上。"),
    ]

    prev_content = ""
    for section_name, instruction in module_defs:
        print(f"[report_gen] 正在生成模块: {section_name}...", file=sys.stderr)
        try:
            section_content = _generate_section(
                section_name, instruction, main_context, prev_content
            )
            sections.append(section_content)
            prev_content = section_content
        except Exception as exc:
            print(f"[report_gen] 模块生成失败 [{section_name}]: {exc}", file=sys.stderr)
            sections.append(f"\n\n## {section_name}\n\n（该模块生成过程中出现错误: {exc}）\n\n")

        # 避免API限流，短延迟
        import time
        time.sleep(0.5)

    # ── 生成来源列表（模块十）───────────────────────────────────────────
    print(f"[report_gen] 正在生成模块: 十、信息来源...", file=sys.stderr)
    source_section = "## 十、信息来源\n\n"
    source_section += "以下为本报告引用的所有信息来源，按编号排列，方便人工核验。\n\n"
    source_section += "| 编号 | 标题 | 来源类型 | 链接 |\n"
    source_section += "|------|------|----------|------|\n"
    for i, item in enumerate(items):
        title_escaped = item.title.replace("|", "\\|")[:50]
        source_section += f"| [{i+1}] | {title_escaped} | {item.source_type} | {item.url} |\n"
    sections.append(source_section)

    # ── 拼接完整报告 ─────────────────────────────────────────────────────
    report_parts = [
        f"# {company_name} 客户拜访情报简报\n\n",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
        f"**拜访目的**: {visit_purpose or '客户拜访前准备'}\n\n",
        f"**关注方向**: {', '.join(focus_areas) if focus_areas else '全面分析'}\n\n",
        f"**信息来源**: 共检索 {len(items)} 条有效来源\n\n",
        "---\n\n",
    ]

    # 加入目录
    report_parts.append("## 目录\n\n")
    for section_name, _ in module_defs:
        report_parts.append(f"- [{section_name}](#{section_name.split('、')[1] if '、' in section_name else section_name})\n")
    report_parts.append("- [十、信息来源](#十信息来源)\n\n---\n\n")

    report_parts.extend(sections)

    final_report = "".join(report_parts)
    total_chars = len(final_report)
    print(f"[report_gen] 报告总字数: {total_chars} 字", file=sys.stderr)

    return final_report