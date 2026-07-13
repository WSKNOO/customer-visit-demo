"""
Baidu search engine implementation.
Scrapes Baidu HTML search results (no official API required).
Supports Chinese-language queries and encoding.
"""

import sys
from typing import List, Optional
from urllib.parse import quote

import httpx
from lxml import html as lxml_html

from .base import SearchEngine, SearchResult, SearchResponse


class BaiduSearch(SearchEngine):
    """Search engine adapter for Baidu (www.baidu.com)."""

    engine_name: str = "baidu"

    def __init__(self, proxy: str = "", timeout: int = 15, user_agent: str = "", base_url: str = "", api_key: str = ""):
        super().__init__(proxy, timeout, user_agent)
        self._base_url = base_url or "https://www.baidu.com/s"
        self._api_key = api_key

    async def search(self, query: str, count: int = 10) -> SearchResponse:
        """
        Search Baidu and parse results.

        Args:
            query: Search terms (Chinese supported).
            count: Number of results to fetch (clamped 1-10).

        Returns:
            SearchResponse with parsed organic results.
        """
        response = SearchResponse(query=query, engine="baidu")
        count = max(1, min(count, 10))

        # Baidu uses 'wd' for query param, 'rn' for results per page
        params = {
            "wd": query,
            "rn": count,
            "ie": "utf-8",
            "oe": "utf-8",
        }

        client_kwargs = self._build_client()
        # Baidu needs Accept-Chinese
        headers = client_kwargs.setdefault("headers", {})
        headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(self._base_url, params=params)
                resp.raise_for_status()
                html_content = resp.text
        except httpx.HTTPStatusError as exc:
            response.success = False
            response.error = f"Baidu returned HTTP {exc.response.status_code}"
            return response
        except httpx.RequestError as exc:
            response.success = False
            response.error = f"Request to Baidu failed: {exc}"
            return response
        except Exception as exc:
            response.success = False
            response.error = f"Unexpected error querying Baidu: {exc}"
            return response

        # Parse HTML
        try:
            tree = lxml_html.fromstring(html_content)
            results = self._parse_results(tree, count)
            response.results = results
        except Exception as exc:
            response.success = False
            response.error = f"Failed to parse Baidu results: {exc}"

        return response

    def _parse_results(self, tree: lxml_html.HtmlElement, max_results: int) -> List[SearchResult]:
        """Extract organic search results from Baidu's HTML."""
        results: List[SearchResult] = []

        # Baidu organic results: div.c-container or div.result
        # Each result has h3.t > a (title+link) and span.content-right_8Zs40 or div.c-abstract
        containers = tree.cssselect("div.c-container, div.result")
        if not containers:
            # Fallback: more generic selectors
            containers = tree.cssselect(".result, .c-container")

        for container in containers:
            if len(results) >= max_results:
                break

            # Try multiple title/link selectors (Baidu A/B tests classes)
            link_el = (
                container.cssselect("h3.t a")
                or container.cssselect("h3 a")
                or container.cssselect(".t a")
                or container.cssselect("a[href^='http']")
            )
            if not link_el:
                continue

            link = link_el[0]
            title = link.text_content().strip()
            url = link.get("href", "")

            # Baidu may return intermediate redirect URLs — try to get real URL
            # from data attribute or use as-is (it'll redirect)
            if not url or url.startswith("javascript:") or url.startswith("#"):
                continue
            if url.startswith("//"):
                url = "https:" + url

            # Snippet: various Baidu positions
            snippet_el = (
                container.cssselect("span.content-right_8Zs40")
                or container.cssselect(".c-abstract")
                or container.cssselect(".c-span-last")
                or container.cssselect(".c-color-gray")
                or container.cssselect(".c-line-clamp1")
                or container.cssselect(".c-line-clamp2")
                or container.cssselect(".c-line-clamp3")
                or container.cssselect(".c-gap-bottom-small")
            )
            snippet = snippet_el[0].text_content().strip() if snippet_el else ""
            # Also try div with abstract class
            if not snippet:
                abstract = container.cssselect("div.c-abstract")
                if abstract:
                    snippet = abstract[0].text_content().strip()
            if not snippet:
                # Last resort: grab any text paragraph
                for p in container.cssselect("p"):
                    txt = p.text_content().strip()
                    if len(txt) > 10:
                        snippet = txt
                        break

            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                rank=len(results) + 1,
            ))

        # Deduplicate by URL
        seen_urls: set = set()
        deduped: List[SearchResult] = []
        for r in results:
            normalized = r.url.rstrip("/")
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                deduped.append(r)

        for idx, r in enumerate(deduped):
            r.rank = idx + 1

        return deduped
