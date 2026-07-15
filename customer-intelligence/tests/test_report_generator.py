import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


if "search_mcp.scraper" not in sys.modules:
    scraper_stub = types.ModuleType("search_mcp.scraper")
    scraper_stub.scrape_url = None
    sys.modules["search_mcp.scraper"] = scraper_stub

from search_mcp.config import reload_config
from search_mcp.smart_search.content_collector import SourceItem
from search_mcp.smart_search import report_generator as generator


class _FakeCompletions:
    def __init__(self, fail_first=False):
        self.calls = []
        self.fail_first = fail_first

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError(
                "max_tokens is too large; this model's maximum context length is 20480 tokens"
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="生成成功"))]
        )


class ReportGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "SEARCH_MCP_SUMMARIZER_API_KEY": "test-placeholder",
            "INTELLIGENCE_MODEL_CONTEXT_LIMIT": "20480",
            "INTELLIGENCE_MODEL_MAX_INPUT_TOKENS": "8000",
            "INTELLIGENCE_MODEL_MAX_OUTPUT_TOKENS": "4096",
            "INTELLIGENCE_MODEL_TOKEN_SAFETY_MARGIN": "1024",
            "INTELLIGENCE_MODEL_RETRY_INPUT_TOKENS": "4500",
            "INTELLIGENCE_REPORT_MAX_SOURCES": "10",
            "INTELLIGENCE_REPORT_SOURCE_MAX_CHARS": "500",
        })
        self.env.start()
        reload_config()

    def tearDown(self):
        self.env.stop()
        reload_config()

    def test_dynamic_budget_compresses_and_retries_once(self):
        completions = _FakeCompletions(fail_first=True)
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with patch("openai.OpenAI", return_value=client):
            result = generator._call_ai(
                "大量客户公开资料。" * 5000,
                system_prompt="仅基于事实生成报告。" * 100,
                max_tokens=8192,
            )

        self.assertEqual(result, "生成成功")
        self.assertEqual(len(completions.calls), 2)
        self.assertLess(len(completions.calls[1]["messages"][-1]["content"]),
                        len(completions.calls[0]["messages"][-1]["content"]))
        for call in completions.calls:
            self.assertLessEqual(call["max_tokens"], 4096)
            estimated = sum(generator._estimate_tokens(m["content"]) for m in call["messages"]) + 16
            self.assertLessEqual(estimated, 8000)

    def test_sources_are_bounded(self):
        items = [
            SourceItem(title=f"来源{i}", url=f"https://example.com/{i}", content="资料" * 1000)
            for i in range(15)
        ]
        context = generator._format_sources_for_prompt(items)
        self.assertEqual(context.count("[来源 "), 10)
        self.assertNotIn("[来源 11]", context)
        self.assertLess(len(context), 9000)

    def test_kedaxunfei_large_search_context_generates_without_token_overflow(self):
        items = [
            SourceItem(
                title=f"科大讯飞公开动态{i}",
                url=f"https://example.com/iflytek/{i}",
                content="科大讯飞人工智能与数字化建设公开材料。" * 800,
                source_type="媒体",
            )
            for i in range(20)
        ]
        completions = _FakeCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with patch("openai.OpenAI", return_value=client):
            report = generator.generate_full_report(
                "科大讯飞", items, "了解人工智能合作机会", ["AI", "大模型"]
            )
        self.assertEqual(report, "生成成功")
        self.assertEqual(len(completions.calls), 1)
        call = completions.calls[0]
        estimated = sum(generator._estimate_tokens(m["content"]) for m in call["messages"]) + 16
        self.assertLessEqual(estimated, 8000)
        self.assertLessEqual(call["max_tokens"], 4096)

    def test_model_failure_returns_friendly_traceable_fallback(self):
        item = SourceItem(
            title="科大讯飞公开动态",
            url="https://example.com/news",
            snippet="公开信息摘要",
            source_type="媒体",
        )
        with patch.object(generator, "_call_ai", side_effect=RuntimeError("Error code 400 secret detail")):
            report = generator.generate_full_report("科大讯飞", [item])
        self.assertIn("系统已自动压缩信息后重新生成", report)
        self.assertIn("https://example.com/news", report)
        self.assertNotIn("Error code 400", report)
        self.assertNotIn("secret detail", report)

    def test_chinese_anchor_is_stable(self):
        self.assertEqual(generator._markdown_anchor("二、近期重点动态"), "二近期重点动态")


if __name__ == "__main__":
    unittest.main()
