"""End-to-end Mock integration check. Refuses to run unless both backends report Mock mode."""

from __future__ import annotations

import os
import re
import sys

import requests


PORTAL = os.getenv("PORTAL_URL", "http://127.0.0.1:8088")
INTELLIGENCE_FRONTEND = os.getenv("INTELLIGENCE_FRONTEND_URL", "http://127.0.0.1:8006")
INTELLIGENCE_API = os.getenv("INTELLIGENCE_API_URL", "http://127.0.0.1:3001/api")
TRAINING = os.getenv("TRAINING_URL", "http://127.0.0.1:5102")


def main() -> int:
    session = requests.Session()
    session.trust_env = False

    portal_page = session.get(f"{PORTAL}/", timeout=5)
    portal_page.raise_for_status()
    assert "政企客户智能拜访助手" in portal_page.text
    portal_config = session.get(f"{PORTAL}/config", timeout=5).json()
    assert portal_config.get("intelligence_url")
    assert portal_config.get("training_url")
    assert portal_config.get("solution_url")

    assert session.get(f"{INTELLIGENCE_FRONTEND}/", timeout=5).status_code == 200
    intelligence_health = session.get(f"{INTELLIGENCE_API}/health", timeout=5).json()
    training_health = session.get(f"{TRAINING}/api/health", timeout=5).json()
    if not intelligence_health.get("mock") or not training_health.get("mock"):
        raise RuntimeError("Refusing to run: both backends must be in Mock mode")

    demo = session.post(f"{INTELLIGENCE_API}/demo-reports/xinghai-manufacturing/load", json={}, timeout=5)
    demo.raise_for_status()
    filename = demo.json()["report_filename"]
    report = session.get(f"{INTELLIGENCE_API}/reports/{filename}", timeout=5)
    report.raise_for_status()
    assert "缓存演示结果" in report.json()["content"]

    init = session.post(
        f"{INTELLIGENCE_API}/visit-brief/start-training",
        json={"report_filename": filename}, timeout=8,
    )
    init.raise_for_status()
    initialized = init.json()
    assert re.fullmatch(r"[0-9a-f]{32}", initialized["session_id"])
    assert "session_id=" in initialized["training_url"]
    assert "visit_brief" not in initialized["training_url"]

    loaded = session.get(f"{TRAINING}/api/training/session/{initialized['session_id']}", timeout=5)
    loaded.raise_for_status()
    assert loaded.json()["customer_name"] == "星海智造演示客户"

    messages: list[dict[str, str]] = []
    last = ""
    for answer in (
        "先确认生产和质量数据的现状与影响。",
        "以数据口径、定位时长和闭环率作为评估基线。",
        "选择一个工厂和一种高频异常开展小范围试点。",
    ):
        messages.append({"role": "user", "content": answer})
        chat = session.post(
            f"{TRAINING}/api/chat",
            json={"session_id": initialized["session_id"], "messages": messages}, timeout=8,
        )
        chat.raise_for_status()
        data = chat.json()
        assert data.get("success")
        assert "<!--SCORE" in data["content"]
        last = data["content"]
        messages.append({"role": "assistant", "content": last})
    assert "<!--REPORT" in last

    print("Mock full chain passed: portal -> cached intelligence -> session -> 3 text rounds -> report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
