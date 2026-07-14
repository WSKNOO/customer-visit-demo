"""
Company Researcher — 智能企业情报研究主编排器。

整合关键词生成、内容收集、AI报告生成的全流程。
对外提供统一的 research_company() 接口供 MCP 工具调用。
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from search_mcp.config import get_config
from search_mcp.smart_search.keyword_generator import generate_keywords
from search_mcp.smart_search.content_collector import ContentCollector, SourceItem
from search_mcp.smart_search.report_generator import (
    generate_full_report,
    generate_report_sequentially,
)
from search_mcp.smart_search.product_catalog import format_catalog_text


def _safe_company_filename(company_name: str) -> str:
    """Create a bounded filename component without path separators."""
    safe_name = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9._-]+", "_", company_name).strip("._")
    safe_name = re.sub(r"\.{2,}", "_", safe_name)
    if not safe_name:
        raise ValueError("企业名称无法转换为安全文件名")
    return safe_name[:80]


async def research_company(
    company_name: str,
    visit_purpose: str = "",
    focus_areas: List[str] = None,
    output_dir: str = "",
    max_items: int = 80,
    sequential_mode: bool = False,
) -> Dict[str, Any]:
    """
    对企业进行全面的联网情报研究，生成结构化报告。

    Args:
        company_name: 客户企业名称。
        visit_purpose: 拜访目的描述。
        focus_areas: 关注方向（如 ['AI', '云', '安全']），全部为全维度。
        output_dir: 报告输出目录，默认 ./tmp/reports/。
        max_items: 最大收集条目数。
        sequential_mode: 是否使用逐模块生成模式（适合长报告）。

    Returns:
        Dict: {
            "success": bool,
            "company": str,
            "report": str (Markdown),
            "report_path": str (文件路径),
            "source_count": int,
            "total_chars": int,
            "elapsed_seconds": float,
            "error": str or None,
        }
    """
    start_time = time.time()
    result: Dict[str, Any] = {
        "success": False,
        "company": company_name,
        "report": "",
        "report_path": "",
        "source_count": 0,
        "total_chars": 0,
        "elapsed_seconds": 0.0,
        "error": None,
    }

    try:
        print(f"[researcher] 开始研究: {company_name}", file=sys.stderr)
        if visit_purpose:
            print(f"[researcher] 拜访目的: {visit_purpose}", file=sys.stderr)
        if focus_areas:
            print(f"[researcher] 关注方向: {focus_areas}", file=sys.stderr)

        # ── 阶段1: 生成搜索关键词 ────────────────────────────────────────
        print(f"[researcher] 阶段1/4: 生成搜索关键词...", file=sys.stderr)
        keywords_by_dim = generate_keywords(company_name, focus_areas)
        search_cfg = get_config().get("search", {})
        max_dimensions = min(12, max(1, int(search_cfg.get("max_dimensions", 6))))
        max_keywords = min(5, max(1, int(search_cfg.get("max_keywords_per_dimension", 1))))
        keywords_by_dim = sorted(
            keywords_by_dim,
            key=lambda item: 0 if item.get("priority") == "high" else 1,
        )[:max_dimensions]
        for dimension in keywords_by_dim:
            dimension["keywords"] = dimension.get("keywords", [])[:max_keywords]
        total_keywords = sum(len(d["keywords"]) for d in keywords_by_dim)
        print(f"[researcher] 生成 {len(keywords_by_dim)} 个维度, "
              f"{total_keywords} 个关键词", file=sys.stderr)

        # ── 阶段2: 搜索与内容收集 ────────────────────────────────────────
        print(f"[researcher] 阶段2/4: 联网搜索与内容收集...", file=sys.stderr)
        collector = ContentCollector()
        items = await collector.search_dimensions(
            keywords_by_dim,
            max_per_dim=8,
            max_fetch=max_items,
        )
        print(f"[researcher] 收集到 {len(items)} 条有效内容", file=sys.stderr)

        if not items:
            result["error"] = "未搜索到任何有效内容，请确认企业名称是否正确"
            result["elapsed_seconds"] = time.time() - start_time
            return result

        # ── 阶段3: 设置输出目录 ───────────────────────────────────────────
        if not output_dir:
            output_dir = os.path.join(os.getcwd(), "tmp", "reports")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # ── 阶段4: 生成报告 ───────────────────────────────────────────────
        print(f"[researcher] 阶段3/4: 生成AI分析报告...", file=sys.stderr)
        if sequential_mode:
            report = generate_report_sequentially(
                company_name, items, visit_purpose, focus_areas
            )
        else:
            report = generate_full_report(
                company_name, items, visit_purpose, focus_areas
            )

        total_chars = len(report)

        # ── 阶段5: 保存报告 ───────────────────────────────────────────────
        print(f"[researcher] 阶段4/4: 保存报告...", file=sys.stderr)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = _safe_company_filename(company_name)
        filename = f"{safe_name}_{timestamp}.md"
        report_path = (output_path / filename).resolve()
        if output_path.resolve() not in report_path.parents:
            raise ValueError("报告输出路径非法")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"[researcher] 报告已保存: {report_path}", file=sys.stderr)

        # 同时保存搜索到的原始材料（便于调试）
        data_path = output_path / f"{safe_name}_{timestamp}_sources.json"
        source_data = []
        for item in items:
            source_data.append({
                "title": item.title,
                "url": item.url,
                "source_type": item.source_type,
                "dimension": item.dimension,
                "content_length": len(item.content or ""),
            })
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(source_data, f, ensure_ascii=False, indent=2)

        result["success"] = True
        result["report"] = report
        result["report_path"] = str(report_path)
        result["source_count"] = len(items)
        result["total_chars"] = total_chars
        result["source_data_path"] = str(data_path)

    except Exception as exc:
        print(f"[researcher] 研究过程出错: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        result["error"] = str(exc)

    result["elapsed_seconds"] = round(time.time() - start_time, 1)
    return result
