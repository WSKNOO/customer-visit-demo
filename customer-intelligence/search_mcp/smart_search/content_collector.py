"""
Content Collector — 多引擎搜索 + 网页抓取 + 内容清洗去重。

对每个关键词，使用多个搜索引擎（bing/baidu/dblp）进行检索，
抓取返回的网页内容，按来源优先级排序，过滤无关内容。
"""

import asyncio
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from search_mcp.config import get_config
from search_mcp.engines.bing import BingSearch
from search_mcp.engines.baidu import BaiduSearch
from search_mcp.scraper import scrape_url
from search_mcp.proxy_router import resolve_proxy


@dataclass
class SourceItem:
    """一条搜索到的信息来源。"""
    title: str
    url: str
    snippet: str = ""
    content: str = ""
    source_type: str = ""  # 官网/政府/招标/媒体/学术/其他
    dimension: str = ""    # 所属搜索维度
    keyword: str = ""      # 使用的搜索词
    _engine: str = ""
    score: float = 0.0
    content_hash: str = ""
    fetch_success: bool = False
    fetch_error: str = ""


# ── 来源类型判断 ────────────────────────────────────────────────────────────

OFFICIAL_DOMAINS = [
    "gov.cn", "sasac.gov.cn", "ndrc.gov.cn", "miit.gov.cn",
    "mof.gov.cn", "mofcom.gov.cn", "most.gov.cn",
]

BID_DOMAINS = [
    "bidcenter.com", "chinabidding.com", "cib.com", "bidchance.com",
    "zhaobiao.cn", "ccgp.gov.cn", "采购.cn",
]

MEDIA_DOMAINS = [
    "people.com.cn", "xinhuanet.com", "chinanews.com",
    "cctv.com", "china.com.cn", "163.com", "sina.com.cn",
    "sohu.com", "ifeng.com", "thepaper.cn", "36kr.com",
    "huxiu.com", "cs.com.cn", "stcn.com",
]

ACADEMIC_DOMAINS = [
    "arxiv.org", "cnki.net", "wanfangdata.com", "dblp.org",
    "semanticscholar.org", "ieee.org", "acm.org",
]


def classify_source(url: str, title: str = "") -> str:
    """根据URL判断来源类型。"""
    domain = urlparse(url).netloc.lower()
    for d in OFFICIAL_DOMAINS:
        if d in domain or domain.endswith("." + d):
            return "政府/官方"
    if any(d in domain for d in BID_DOMAINS):
        return "招标采购"
    for d in ACADEMIC_DOMAINS:
        if d in domain or domain.endswith("." + d):
            return "学术"
    for d in MEDIA_DOMAINS:
        if d in domain or domain.endswith("." + d):
            return "媒体"

    # 检测关键词
    title_lower = title.lower()
    if any(k in title_lower for k in ["招标", "中标", "采购", "投标"]):
        return "招标采购"
    if any(k in domain for k in ["baike", "wiki"]):
        return "百科知识"

    return "其他"


# ── 内容收集器 ──────────────────────────────────────────────────────────────

class ContentCollector:
    """多引擎搜索+网页抓取+内容清洗去重。"""

    def __init__(self, proxy: str = ""):
        cfg = get_config()
        search_cfg = cfg.get("search", {})
        self.proxy = proxy or resolve_proxy(engine_name="bing")
        self.timeout = search_cfg.get("request_timeout", 15)
        self.user_agent = search_cfg.get("user_agent", "")
        self.max_content_chars = min(200000, max(1000, int(search_cfg.get("max_content_chars", 50000))))

        # 搜索引擎实例（只使用百度，Bing CN返回大量无关门户首页）
        self.engines = {
            "baidu": BaiduSearch(proxy=resolve_proxy(engine_name="baidu") if not proxy else proxy,
                                 timeout=self.timeout, user_agent=self.user_agent,
                                 base_url=search_cfg.get("service_base_url", ""),
                                 api_key=search_cfg.get("service_api_key", "")),
        }

        # 去重缓存
        self._seen_urls: set = set()
        self._seen_hashes: set = set()

    async def search_keyword(self, keyword: str, dimension: str = "",
                             engines: List[str] = None) -> List[SourceItem]:
        """用一个关键词在多个引擎上搜索，返回合并结果。"""
        items = []
        if engines is None:
            engines = ["bing", "baidu"]

        for engine_name in engines:
            engine = self.engines.get(engine_name)
            if not engine:
                continue
            try:
                resp = await engine.search(keyword, count=8)
                if resp.success and resp.results:
                    for r in resp.results:
                        url_clean = r.url.rstrip("/")
                        if url_clean in self._seen_urls:
                            continue
                        self._seen_urls.add(url_clean)
                        items.append(SourceItem(
                            title=r.title,
                            url=r.url,
                            snippet=r.snippet,
                            source_type=classify_source(r.url, r.title),
                            dimension=dimension,
                            keyword=keyword,
                            _engine=engine_name,
                            content_hash=hashlib.md5(r.url.encode()).hexdigest()[:12],
                        ))
            except Exception as exc:
                print(f"[collector] Search error [{engine_name}] {keyword}: {exc}", file=sys.stderr)

        return items

    async def fetch_content(self, item: SourceItem) -> SourceItem:
        """抓取单个SourceItem的页面内容。"""
        try:
            scraped = await scrape_url(
                item.url,
                proxy=resolve_proxy(url=item.url),
                timeout=self.timeout,
            )
            if scraped.success and scraped.content:
                item.content = scraped.content[:self.max_content_chars]
                item.fetch_success = True

                # 去重检查（基于内容哈希）
                content_hash = hashlib.md5(item.content[:1000].encode()).hexdigest()
                if content_hash in self._seen_hashes:
                    item.content = ""  # 重复内容，清空
                    item.fetch_success = False
                    item.fetch_error = "重复内容"
                else:
                    self._seen_hashes.add(content_hash)

            else:
                item.fetch_error = scraped.error or "抓取失败"
        except Exception as exc:
            item.fetch_error = str(exc)
        return item

    async def search_dimensions(self, keywords_by_dim: List[Dict],
                                max_per_dim: int = 5,
                                max_fetch: int = 80) -> List[SourceItem]:
        """
        多维度搜索，返回所有收集到的内容。

        Args:
            keywords_by_dim: keyword_generator 生成的维度关键词列表。
            max_per_dim: 每个维度最多保留的有效条目数。
            max_fetch: 最大抓取数量。

        Returns:
            清洗后的 SourceItem 列表。
        """
        all_items: List[SourceItem] = []

        # ── 阶段1: 搜索所有关键词 ─────────────────────────────────────────
        search_tasks = []
        for dim in keywords_by_dim:
            for kw in dim["keywords"]:
                search_tasks.append(self.search_keyword(kw, dim.get("dimension", dim.get("name", ""))))

        search_results = await asyncio.gather(*search_tasks)
        for items in search_results:
            all_items.extend(items)

        print(f"[collector] 搜索阶段完成，共 {len(all_items)} 条原始结果", file=sys.stderr)

        # ── 阶段2: 按优先级排序 ───────────────────────────────────────────
        priority_order = {"政府/官方": 0, "招标采购": 1, "百科知识": 2, "媒体": 3, "学术": 4, "其他": 5}
        all_items.sort(key=lambda x: priority_order.get(x.source_type, 5))

        # ── 阶段3: 按维度取top ────────────────────────────────────────────
        dim_count: Dict[str, int] = {}
        filtered: List[SourceItem] = []
        for item in all_items:
            d = item.dimension
            if dim_count.get(d, 0) < max_per_dim * 2:  # 余量，等抓取后再裁
                filtered.append(item)
                dim_count[d] = dim_count.get(d, 0) + 1

        print(f"[collector] 筛选阶段完成，保留 {len(filtered)} 条", file=sys.stderr)

        # ── 阶段4: 抓取内容（并发限制）───────────────────────────────────
        semaphore = asyncio.Semaphore(5)
        fetch_targets = filtered[:max_fetch]

        async def fetch_with_limit(item):
            async with semaphore:
                return await self.fetch_content(item)

        fetch_tasks = [fetch_with_limit(item) for item in fetch_targets]
        fetched = await asyncio.gather(*fetch_tasks)

        # ── 阶段5: 最终过滤 ───────────────────────────────────────────────
        final: List[SourceItem] = []
        dim_final_count: Dict[str, int] = {}
        for item in fetched:
            if not item.fetch_success or not item.content:
                continue
            # 内容太短的过滤
            if len(item.content.strip()) < 100:
                continue
            d = item.dimension
            if dim_final_count.get(d, 0) < max_per_dim:
                final.append(item)
                dim_final_count[d] = dim_final_count.get(d, 0) + 1

        print(f"[collector] 最终保留 {len(final)} 条有效内容", file=sys.stderr)
        return final
