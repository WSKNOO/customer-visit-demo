import asyncio
import sys
import types
import unittest

from lxml import html as lxml_html

from search_mcp.config import reload_config
from search_mcp.engines.baidu import BaiduSearch
from search_mcp.engines.sogou import SogouSearch


class SearchRuntimeTests(unittest.TestCase):
    def test_sogou_parser_keeps_summary_and_absolute_source_url(self):
        tree = lxml_html.fromstring(
            '<div class="vrwrap"><h3><a href="/link?url=abc">中国电信数字化动态</a></h3>'
            '<div>中国电信发布新的数字化建设成果和行业解决方案。</div></div>'
        )
        results = SogouSearch()._parse_results(tree, 5)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].url.startswith("https://www.sogou.com/link?"))
        self.assertIn("数字化建设成果", results[0].snippet)

    def test_standard_https_proxy_is_inherited(self):
        import os

        previous = {name: os.environ.get(name) for name in ("SEARCH_MCP_PROXY", "HTTPS_PROXY", "HTTP_PROXY")}
        try:
            os.environ["SEARCH_MCP_PROXY"] = ""
            os.environ["HTTPS_PROXY"] = "http://proxy.example:8080"
            os.environ.pop("HTTP_PROXY", None)
            self.assertEqual(reload_config()["search"]["proxy"], "http://proxy.example:8080")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            reload_config()

    def test_baidu_unknown_summary_class_keeps_card_text(self):
        tree = lxml_html.fromstring(
            '<div class="c-container"><h3><a href="https://example.com/news">示例标题</a></h3>'
            '<div class="new-summary-class">这是百度新版结果卡片中的实时搜索摘要，应该被保留下来。</div></div>'
        )
        results = BaiduSearch()._parse_results(tree, 5)
        self.assertEqual(len(results), 1)
        self.assertIn("实时搜索摘要", results[0].snippet)

    def test_disabled_page_fetch_falls_back_to_search_snippet(self):
        scraper_stub = types.ModuleType("search_mcp.scraper")
        scraper_stub.scrape_url = None
        previous = sys.modules.get("search_mcp.scraper")
        sys.modules["search_mcp.scraper"] = scraper_stub
        try:
            sys.modules.pop("search_mcp.smart_search.content_collector", None)
            from search_mcp.smart_search.content_collector import ContentCollector, SourceItem

            collector = ContentCollector.__new__(ContentCollector)
            collector.fetch_content_enabled = False
            collector.snippet_fallback_enabled = True
            collector.max_content_chars = 50000
            item = SourceItem(title="标题", url="https://example.com", snippet="这是一段来自实时搜索结果的有效摘要，可在网页抓取失败时继续使用。")
            result = asyncio.run(collector.fetch_content(item))
            self.assertTrue(result.fetch_success)
            self.assertIn("实时搜索结果", result.content)
        finally:
            if previous is None:
                sys.modules.pop("search_mcp.scraper", None)
            else:
                sys.modules["search_mcp.scraper"] = previous


if __name__ == "__main__":
    unittest.main()
