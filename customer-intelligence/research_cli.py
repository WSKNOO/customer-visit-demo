"""Safe JSON-stdin entry point for customer research jobs."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMPANY_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9（）()·&＆.\-\s]{1,120}$")
MAX_PURPOSE_LENGTH = 500
MAX_FOCUS_LENGTH = 200


def _clean_single_line(value: Any, field: str, max_length: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if "\n" in value or "\r" in value or len(value) > max_length:
        raise ValueError(f"{field} is invalid or too long")
    return value


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request body must be an object")
    company_name = _clean_single_line(payload.get("company_name"), "company_name", 120)
    if not company_name or "&&" in company_name or not COMPANY_RE.fullmatch(company_name):
        raise ValueError("company_name contains unsupported characters")
    visit_purpose = _clean_single_line(payload.get("visit_purpose"), "visit_purpose", MAX_PURPOSE_LENGTH)
    focus_raw = _clean_single_line(payload.get("focus_areas"), "focus_areas", MAX_FOCUS_LENGTH)
    focus_areas = [item.strip() for item in re.split(r"[,，]", focus_raw) if item.strip()][:10]
    return {
        "company_name": company_name,
        "visit_purpose": visit_purpose,
        "focus_areas": focus_areas,
    }


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9._-]+", "_", value).strip("._")
    cleaned = re.sub(r"\.{2,}", "_", cleaned)
    if not cleaned:
        raise ValueError("company_name cannot be converted to a safe filename")
    return cleaned[:80]


def create_mock_report(data: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{_safe_filename(data['company_name'])}_{timestamp}.md"
    report_path = (output_dir / filename).resolve()
    if output_dir.resolve() not in report_path.parents:
        raise ValueError("invalid report path")
    goal = data["visit_purpose"] or "了解客户需求并准备首次拜访"
    focus = "、".join(data["focus_areas"]) or "数字化建设"
    report = f"""# {data['company_name']} 客户拜访情报简报（Mock）

**拜访目的**: {goal}

**关注方向**: {focus}

## 一、客户基本画像

这是离线 Mock 数据，用于验证本地启动和页面展示，不代表真实客户事实。

## 二、近期重点动态

- 暂无联网数据；演示模式未调用搜索服务。

## 三、数字化/智能化线索

- 关注方向：{focus}（Mock，需人工核验）。

## 四、潜在业务痛点

- 可能需要提升数据协同效率（推测，Mock）。

## 五、可能匹配的产品能力

- 建议先做需求澄清，再选择方案（Mock）。

## 六、拜访切入点建议

- 围绕“{goal}”确认现状、约束和成功标准。

## 七、建议提问清单

1. 当前最希望优先解决的业务问题是什么？
2. 现有系统和数据协同的主要障碍是什么？
3. 本次项目的决策流程和时间窗口是什么？

## 八、后续商机判断

- 需在真实访谈后判断（Mock）。

## 九、风险与不确定性

- 本报告为离线验证数据，不可用于真实决策。

## 十、信息来源

- 本地 Mock 数据，无外部来源。
"""
    report_path.write_text(report, encoding="utf-8")
    sources_path = report_path.with_name(f"{report_path.stem}_sources.json")
    sources_path.write_text("[]\n", encoding="utf-8")
    return {
        "success": True,
        "company": data["company_name"],
        "report_path": str(report_path),
        "source_data_path": str(sources_path),
        "source_count": 0,
        "total_chars": len(report),
        "elapsed_seconds": 0.0,
        "error": None,
        "mock": True,
    }


async def run(payload: Any) -> dict[str, Any]:
    data = validate_payload(payload)
    output_dir = Path(__file__).resolve().parent / "tmp" / "reports"
    mock_value = os.getenv("INTELLIGENCE_MOCK_MODE", os.getenv("MOCK_MODE", ""))
    if mock_value.lower() in {"1", "true", "yes"}:
        return create_mock_report(data, output_dir)

    from search_mcp.smart_search.company_researcher import research_company

    return await research_company(
        company_name=data["company_name"],
        visit_purpose=data["visit_purpose"],
        focus_areas=data["focus_areas"] or None,
        output_dir=str(output_dir),
        max_items=min(100, max(1, int(os.getenv("SEARCH_MAX_FETCH_PAGES", "80")))),
        sequential_mode=True,
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = asyncio.run(run(payload))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("success") else 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception:
        print(json.dumps({"success": False, "error": "research job failed"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
