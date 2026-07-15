"""
Report Generator — 基于收集到的内容，使用AI生成结构化客户拜访简报。

核心原则：
1. 只使用搜索材料中出现的信息，不得编造
2. 事实和推测严格分开标注
3. 关键结论必须带来源链接
4. 不确定时明确说明
5. 在模型上下文预算内生成适合拜访准备的精炼报告
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
6. **优先保留可核验事实、业务判断和建议，不为追求篇幅重复扩写**
7. **各模块按分析逻辑展开，内容清晰、具体、便于现场阅读**

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
- 全文建议控制在3000至6000字，材料不足时宁可简短并明确说明"""


def _truncate_text(text: str, max_chars: int = 80000) -> str:
    """截断过长的文本，保留开头和结尾。"""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half]}\n\n[... 中间内容已截断，共 {len(text)} 字符 ...]\n\n{text[-half:]}"


def _estimate_tokens(text: str) -> int:
    """Conservative dependency-free estimate for mixed Chinese/ASCII prompts."""
    cjk = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    other = max(0, len(text) - cjk)
    return cjk + (other + 3) // 4 + 16


def _truncate_to_token_budget(text: str, token_budget: int) -> str:
    """Bound text to an estimated token budget while preserving both ends."""
    token_budget = max(128, token_budget)
    candidate = text
    for _ in range(4):
        estimated = _estimate_tokens(candidate)
        if estimated <= token_budget:
            return candidate
        target_chars = max(256, int(len(candidate) * token_budget / estimated * 0.9))
        candidate = _truncate_text(text, target_chars)
    return candidate


def _positive_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(maximum, max(minimum, int(value)))
    except (TypeError, ValueError):
        return default


def _model_budget() -> Dict[str, int]:
    cfg = get_config().get("summarizer", {})
    context_limit = _positive_int(cfg.get("context_limit"), 20480, 2048, 1000000)
    safety_margin = _positive_int(cfg.get("token_safety_margin"), 1024, 256, context_limit // 2)
    max_input = _positive_int(cfg.get("max_input_tokens"), 8000, 512, context_limit - safety_margin - 256)
    retry_input = _positive_int(cfg.get("retry_input_tokens"), 4500, 512, max_input)
    max_output = _positive_int(cfg.get("max_report_output_tokens"), 4096, 256, context_limit // 2)
    return {
        "context_limit": context_limit,
        "safety_margin": safety_margin,
        "max_input": max_input,
        "retry_input": retry_input,
        "max_output": max_output,
    }


def _format_sources_for_prompt(items: List[SourceItem]) -> str:
    """将搜索到的内容格式化为模型可用的上下文。"""
    cfg = get_config().get("summarizer", {})
    max_sources = _positive_int(cfg.get("max_report_sources"), 10, 1, 30)
    max_source_chars = _positive_int(cfg.get("max_source_chars"), 500, 100, 2000)
    parts = []
    for i, item in enumerate(items[:max_sources]):
        source_type = item.source_type
        dim = item.dimension
        content_preview = (item.content or item.snippet or "")[:max_source_chars]
        parts.append(
            f"[来源 {i+1}] 标题: {item.title}\n"
            f"链接: {item.url}\n"
            f"类型: {source_type} | 维度: {dim}\n"
            f"内容:\n{content_preview}\n"
            f"---\n"
        )
    return "\n".join(parts)


def _is_context_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in (
        "maximum context", "max_tokens", "max_completion_tokens",
        "context length", "context_length", "token limit",
    ))


def _call_ai(prompt: str, system_prompt: str = None,
             max_tokens: int = 4096, temperature: float = 0.1) -> str:
    """Call an OpenAI-compatible model with a bounded, dynamic token budget."""
    cfg = get_config()
    sum_cfg = cfg.get("summarizer", {})
    api_key = sum_cfg.get("api_key", "")
    api_base = sum_cfg.get("api_base", "https://api.openai.com/v1")
    model = sum_cfg.get("model", "gpt-4o-mini")

    if not api_key:
        raise RuntimeError("AI summarizer not configured: api_key is empty")

    from openai import OpenAI
    client = OpenAI(base_url=api_base, api_key=api_key)

    budget = _model_budget()
    last_error: Optional[Exception] = None
    for attempt, input_budget in enumerate((budget["max_input"], budget["retry_input"]), start=1):
        system_text = system_prompt or ""
        system_tokens = _estimate_tokens(system_text) if system_text else 0
        user_budget = max(256, input_budget - system_tokens - 32)
        user_text = _truncate_to_token_budget(prompt, user_budget)
        messages = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

        input_tokens = sum(_estimate_tokens(message["content"]) for message in messages) + 16
        available_tokens = budget["context_limit"] - input_tokens - budget["safety_margin"]
        output_tokens = min(max_tokens, budget["max_output"], max(256, available_tokens))
        if available_tokens < 256:
            last_error = RuntimeError("模型输入在安全压缩后仍超过上下文预算")
            continue

        print(
            f"[report_gen] 模型预算: input≈{input_tokens}, output={output_tokens}, "
            f"context={budget['context_limit']}, attempt={attempt}",
            file=sys.stderr,
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=output_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_error = exc
            if attempt == 1 and _is_context_limit_error(exc):
                print("[report_gen] 上下文超限，已自动压缩信息并重试一次", file=sys.stderr)
                continue
            raise
    raise last_error or RuntimeError("模型调用失败")


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
- 内容具体，按逻辑展开分析，避免重复扩写
- 本模块控制在300至800字
"""
    return _call_ai(prompt, system_prompt=SYSTEM_PROMPT,
                    max_tokens=4096, temperature=0.3)


def _markdown_anchor(title: str) -> str:
    """Generate the same compact Chinese-safe anchor used by the frontend."""
    cleaned = title.replace("**", "").lower()
    return "".join(char for char in cleaned if char.isalnum() or "\u3400" <= char <= "\u9fff") or "section"


def _build_fallback_report(company_name: str, items: List[SourceItem],
                           visit_purpose: str = "", focus_areas: List[str] = None) -> str:
    """Return a presentable, source-traceable report when the model is unavailable."""
    sources = items[:10]
    source_lines = [
        f"- [{i}] [{item.title[:100]}]({item.url})：{(item.snippet or item.content or '暂无摘要')[:500]}"
        for i, item in enumerate(sources, start=1)
    ]
    source_summary = "\n".join(source_lines) or "- 暂无可用公开信息。"
    source_table = [
        "| 编号 | 标题 | 来源类型 | 链接 |",
        "|---|---|---|---|",
    ]
    for i, item in enumerate(sources, start=1):
        title = item.title.replace("|", "\\|")[:100]
        source_table.append(f"| [{i}] | {title} | {item.source_type} | {item.url} |")

    return f"""# {company_name} 客户拜访情报简报

**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}
**拜访目的**：{visit_purpose or '客户拜访前准备'}
**关注方向**：{', '.join(focus_areas) if focus_areas else '全面分析'}

> 由于客户公开信息较多，系统已自动压缩信息后重新生成。当前模型服务暂不可用，以下先展示可核验的搜索摘要；推测性结论请在拜访前人工确认。

## 一、客户基本画像

当前公开材料摘要如下，企业性质、主营业务和组织信息需结合来源进一步核验：

{source_summary}

## 二、近期重点动态

请优先核验上述来源中的发布日期、签约、项目建设及领导活动信息。

## 三、数字化/智能化线索

可围绕公开材料中出现的云、网、数、智、安等关键词进一步确认建设现状。

## 四、潜在业务痛点

当前未由模型生成推测性痛点，建议通过现场访谈确认，避免将公开信息直接等同于客户需求。

## 五、可能匹配的产品能力

待确认客户建设现状、预算、时间窗口和决策链后再进行产品匹配。

## 六、拜访切入点建议

可从近期公开动态切入，先核实事实，再询问相关建设目标和实施难点。

## 七、建议提问清单

1. 贵单位当前最优先推进的数字化建设目标是什么？
2. 现有系统在数据协同、运营效率或安全方面有哪些主要难点？
3. 本轮建设的预期时间窗口和决策流程是什么？

## 八、后续商机判断

当前证据不足，需在拜访后结合客户明确反馈更新商机优先级。

## 九、风险与不确定性

- 搜索摘要可能存在时效性或语境缺失。
- 公开信息不等同于客户正式需求。
- 重要事实应通过来源链接及客户沟通再次核验。

## 十、信息来源

{chr(10).join(source_table)}
"""


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
{source_context}

## 产品能力目录（用于模块五匹配）
{_truncate_text(product_catalog_text, 2000)}

## 已匹配产品
{', '.join([p.name for p in matched_products[:8]]) if matched_products else '（待分析后匹配）'}

## 输出要求
请严格按照系统指令中的10个模块结构，生成完整的客户拜访简报。

每个模块应优先呈现与本次拜访直接相关的事实、判断和行动建议。
整体报告建议控制在3000至6000字，不要重复扩写。
**十、信息来源**应保留完整的链接列表。
对于材料中提供的数据，请展开分析其含义和影响。
对于推测性内容，请标注理由和置信度。
"""
    # ── 调用AI生成完整报告 ───────────────────────────────────────────────
    print(f"[report_gen] 正在调用AI生成报告（{company_name}）...", file=sys.stderr)
    print(f"[report_gen] 共 {len(items)} 条来源，{sum(len(i.content or '') for i in items)} 字符内容",
          file=sys.stderr)

    try:
        report = _call_ai(prompt, system_prompt=SYSTEM_PROMPT,
                          max_tokens=4096, temperature=0.3)
    except Exception as exc:
        print(f"[report_gen] AI生成不可用，返回搜索摘要兜底: {type(exc).__name__}", file=sys.stderr)
        report = _build_fallback_report(company_name, items, visit_purpose, focus_areas)

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

    # 与完整报告共用同一份有界来源上下文，避免分模块模式重新放大输入。
    main_context = source_context

    print(f"[report_gen] 准备逐模块生成，主上下文 {len(main_context)} 字符", file=sys.stderr)

    # 定义各模块的生成指令
    module_defs = [
        ("一、客户基本画像",
         "整理企业全称、简称、企业性质、所属行业、主营业务、上级单位、组织架构、领导班子、企业规模、区域布局等内容。"
         "注意标注信息获取时间，内容精炼、可核验。"),
        ("二、近期重点动态",
         "按时间倒序整理近一年重大新闻、公告、战略合作、签约项目、会议论坛、领导调研、项目建设、表彰荣誉等。"
         "每条动态简要说明背景和意义。"),
        ("三、数字化/智能化线索",
         "从材料中提取AI、大数据、云、算力、安全、5G、物联网、信创、信息化建设等相关信息。"
         "每条线索说明其对客户的意义和可能的项目机会。"),
        ("四、潜在业务痛点",
         "基于行业特点和公开信息归纳可能痛点。区分'明确提及'和'推测可能'。"
         "每个痛点简要分析影响。"),
        ("五、可能匹配的产品能力",
         "基于识别的需求和痛点，匹配产品能力目录中的产品。说明匹配理由和切入方式。"
         "可列出多个产品方向。"),
        ("六、拜访切入点建议",
         "设计开场话题、沟通切入方式，基于客户最新动态设计交流角度。"
         "同时指出应避免提及的敏感话题。"),
        ("七、建议提问清单",
         "面向不同角色（领导层、业务部门、技术部门）的提问建议。"
         "问题应具体、有针对性。"),
        ("八、后续商机判断",
         "判断可跟进方向、优先级、时间窗口、预期规模。"
         "区分短期和长期机会。"),
        ("九、风险与不确定性",
         "说明证据不足的内容、需要人工确认的关键信息、信息时效性。"
         "明确标注推测项。"),
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
            sections.append(f"\n\n## {section_name}\n\n该模块暂未生成，请参考信息来源并稍后重试。\n\n")

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
        report_parts.append(f"- [{section_name}](#{_markdown_anchor(section_name)})\n")
    report_parts.append(f"- [十、信息来源](#{_markdown_anchor('十、信息来源')})\n\n---\n\n")

    report_parts.extend(sections)

    final_report = "".join(report_parts)
    total_chars = len(final_report)
    print(f"[report_gen] 报告总字数: {total_chars} 字", file=sys.stderr)

    return final_report
