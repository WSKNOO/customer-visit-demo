"""Minimal Sogou HTML search adapter for Chinese customer research."""

import re
from typing import List
from urllib.parse import urljoin

import httpx
from lxml import html as lxml_html

from .base import SearchEngine, SearchResponse, SearchResult


class SogouSearch(SearchEngine):
    """Search Sogou through the configured outbound proxy without an API key."""

    engine_name = "sogou"

    def __init__(self, proxy: str = "", timeout: int = 15, user_agent: str = "", base_url: str = ""):
        super().__init__(proxy, timeout, user_agent)
        self._base_url = base_url or "https://www.sogou.com/web"

    async def search(self, query: str, count: int = 10) -> SearchResponse:
        response = SearchResponse(query=query, engine=self.engine_name)
        count = max(1, min(count, 10))
        try:
            async with httpx.AsyncClient(**self._build_client()) as client:
                raw = await client.get(self._base_url, params={"query": query, "num": count})
                raw.raise_for_status()
            tree = lxml_html.fromstring(raw.text)
            response.results = self._parse_results(tree, count)
            if not response.results:
                response.success = False
                response.error = "Sogou returned no parseable results"
        except httpx.HTTPStatusError as exc:
            response.success = False
            response.error = f"Sogou returned HTTP {exc.response.status_code}"
        except httpx.RequestError as exc:
            response.success = False
            response.error = f"Request to Sogou failed: {exc}"
        except Exception as exc:
            response.success = False
            response.error = f"Failed to parse Sogou results: {exc}"
        return response

    def _parse_results(self, tree: lxml_html.HtmlElement, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen = set()
        for card in tree.cssselect(".vrwrap"):
            links = card.cssselect("h3 a")
            if not links:
                continue
            link = links[0]
            title = re.sub(r"\s+", " ", link.text_content()).strip()
            href = (link.get("href") or "").strip()
            if not title or not href or href.startswith(("javascript:", "#")):
                continue
            url = urljoin("https://www.sogou.com", href)
            if url in seen:
                continue
            seen.add(url)
            text = re.sub(r"\s+", " ", card.text_content()).strip()
            if text.startswith(title):
                text = text[len(title):].strip(" -—|：:")
            results.append(SearchResult(title=title, url=url, snippet=text[:600], rank=len(results) + 1))
            if len(results) >= max_results:
                break
        return results
