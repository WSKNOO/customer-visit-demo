"""Shared safeguards for OpenAI-compatible training model calls."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


PLACEHOLDER_PREFIXES = ("replace-with-", "your-", "changeme", "example-")
THINK_OPEN_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>[\s\S]*?</think\s*>", re.IGNORECASE)
THINK_CLOSE_RE = re.compile(r"</think\s*>", re.IGNORECASE)
COACH_RE = re.compile(r"<!--COACH\s*([\s\S]*?)\s*-->", re.IGNORECASE)
SCORE_RE = re.compile(r"<!--SCORE\s*(\{[\s\S]*?\})\s*(?:SCORE_END)?\s*-->", re.IGNORECASE)
HIDDEN_RE = re.compile(r"<!--(?:COACH|SCORE|REPORT|FINAL_REPORT)[\s\S]*?-->", re.IGNORECASE)
REPORT_RE = re.compile(r"<!--(?:REPORT|FINAL_REPORT)\b[\s\S]*?-->", re.IGNORECASE)

DEFAULT_SCORE = {
    "professionalism": 60,
    "communication": 60,
    "needs_analysis": 60,
    "objection_handling": 60,
    "closing": 60,
    "mood": "neutral",
    "mood_reason": "模型未返回完整评分，已使用安全兜底值",
}


@dataclass(frozen=True)
class ModelConfigStatus:
    configured: bool
    error_code: str | None


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_bounded_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None and value.strip() else default
    except (TypeError, ValueError):
        parsed = default
    return min(maximum, max(minimum, parsed))


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return (
        not lowered
        or lowered.startswith(PLACEHOLDER_PREFIXES)
        or "example.com" in lowered
        or lowered in {"sk-your-key-here", "api-key", "model-name"}
    )


def validate_model_config(base_url: str, api_key: str, model: str) -> ModelConfigStatus:
    values = (base_url.strip(), api_key.strip(), model.strip())
    if any(_is_placeholder(value) for value in values):
        return ModelConfigStatus(False, "MODEL_CONFIG_INVALID")
    parsed = urlparse(values[0])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ModelConfigStatus(False, "MODEL_CONFIG_INVALID")
    if values[0].rstrip("/").endswith("/chat/completions"):
        return ModelConfigStatus(False, "MODEL_CONFIG_INVALID")
    return ModelConfigStatus(True, None)


def add_chat_template_kwargs(payload: dict[str, Any], enable_thinking: bool) -> dict[str, Any]:
    result = dict(payload)
    result["chat_template_kwargs"] = {"enable_thinking": bool(enable_thinking)}
    return result


def strip_think_content(content: str | None) -> str:
    """Remove complete, repeated, stray, and unterminated think blocks."""
    text = str(content or "")
    previous = None
    while previous != text:
        previous = text
        text = THINK_BLOCK_RE.sub("", text)
    open_match = THINK_OPEN_RE.search(text)
    if open_match:
        text = text[: open_match.start()]
    text = THINK_CLOSE_RE.sub("", text)
    return text.strip()


def _normalize_score(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    score = dict(DEFAULT_SCORE)
    for key in ("professionalism", "communication", "needs_analysis", "objection_handling", "closing"):
        number = value.get(key)
        if not isinstance(number, (int, float)):
            return None
        score[key] = max(0, min(100, round(number)))
    if value.get("mood") in {"happy", "neutral", "angry"}:
        score["mood"] = value["mood"]
    if isinstance(value.get("mood_reason"), str) and value["mood_reason"].strip():
        score["mood_reason"] = value["mood_reason"].strip()[:300]
    return score


def parse_training_content(content: str | None, finish_reason: str | None = None) -> dict[str, Any]:
    cleaned = strip_think_content(content)
    if not cleaned:
        raise ValueError("MODEL_OUTPUT_EMPTY_AFTER_THINK_FILTER")

    coach_match = COACH_RE.search(cleaned)
    coach = coach_match.group(1).strip()[:1000] if coach_match else "本轮暂无完整教练点评，请结合客户追问继续澄清需求。"

    score = None
    score_valid = False
    score_match = SCORE_RE.search(cleaned)
    if score_match:
        try:
            score = _normalize_score(json.loads(score_match.group(1)))
            score_valid = score is not None
        except (TypeError, ValueError, json.JSONDecodeError):
            score = None
    score = score or dict(DEFAULT_SCORE)

    customer_reply = HIDDEN_RE.sub("", cleaned).strip()
    if not customer_reply:
        customer_reply = "我需要再确认一下。请先说明您建议优先验证的业务问题和成功标准。"

    missing = []
    if not coach_match:
        missing.append("coach")
    if not score_valid:
        missing.append("score")
    if finish_reason == "length":
        missing.append("truncated")
    parse_status = "ok" if not missing else "fallback_" + "_".join(dict.fromkeys(missing))

    report_blocks = REPORT_RE.findall(cleaned)
    normalized = (
        f"{customer_reply}\n"
        f"<!--COACH\n{coach}\n-->\n"
        f"<!--SCORE\n{json.dumps(score, ensure_ascii=False, separators=(',', ':'))}\n-->"
    )
    if report_blocks:
        normalized += "\n" + "\n".join(report_blocks)
    return {
        "customer_reply": customer_reply,
        "coach_feedback": coach,
        "score": score,
        "raw_content": cleaned,
        "content": normalized,
        "parse_status": parse_status,
        "finish_reason": finish_reason,
    }
