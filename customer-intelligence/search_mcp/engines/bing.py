"""
Bing search engine implementation.
Scrapes Bing HTML search results (no official API required).
"""

import sys
import re
from typing import List, Optional

import httpx
from lxml import html as lxml_html

from .base import SearchEngine, SearchResult, SearchResponse


class BingSearch(SearchEngine):
    """Search engine adapter for Bing (www.bing.com)."""

    engine_name: str = "bing"

    def __init__(self, proxy: str = "", timeout: int = 15, user_agent: str = ""):
        super().__init__(proxy, timeout, user_agent)
        self._base_url = "https://www.bing.com/search"

    async def search(self, query: str, count: int = 10) -> SearchResponse:
        """
        Search Bing and parse results.

        Args:
            query: Search terms.
            count: Number of results to fetch (clamped 1-10).

        Returns:
            SearchResponse with parsed organic results.
        """
        response = SearchResponse(query=query, engine="bing")
        count = max(1, min(count, 10))

        params = {
            "q": query,
            "count": count + 2,  # request extra due to filtering
            "setlang": "en",
            "cc": "us",  # use international version to avoid CN content blocking
        }

        client_kwargs = self._build_client()
        html_content = ""
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(self._base_url, params=params)
                resp.raise_for_status()
                html_content = resp.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 503):
                response.error = f"Bing rate limited ({exc.response.status_code}), trying fallback"
            else:
                response.success = False
                response.error = f"Bing returned HTTP {exc.response.status_code}"
                return response
        except httpx.RequestError as exc:
            response.success = False
            response.error = f"Request to Bing failed: {exc}"
            return response
        except Exception as exc:
            response.success = False
            response.error = f"Unexpected error querying Bing: {exc}"
            return response

        if not html_content:
            # Try fallback via cn.bing.com with different params
            try:
                params2 = {"q": query, "count": count + 2}
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.get("https://www.bing.com/search", params=params2)
                    resp.raise_for_status()
                    html_content = resp.text
            except Exception:
                response.success = False
                response.error = "Bing search failed: all attempts blocked"
                return response

        # Parse HTML
        try:
            tree = lxml_html.fromstring(html_content)
            results = self._parse_results(tree, count)
            response.results = results
        except Exception as exc:
            response.success = False
            response.error = f"Failed to parse Bing results: {exc}"

        # If no results, try with cc=us to get international results
        if not response.results:
            try:
                params3 = {"q": query, "count": count + 2, "cc": "us", "setlang": "en"}
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.get(self._base_url, params=params3)
                    resp.raise_for_status()
                    tree = lxml_html.fromstring(resp.text)
                    results = self._parse_results(tree, count)
                    response.results = results
            except Exception:
                pass

        return response

    def _parse_results(self, tree: lxml_html.HtmlElement, max_results: int) -> List[SearchResult]:
        """Extract organic search results from Bing's HTML."""
        results: List[SearchResult] = []

        # Bing organic results are in <li class="b_algo"> elements
        for i, li in enumerate(tree.cssselect("li.b_algo")):
            if len(results) >= max_results:
                break

            # Title + URL from <h2><a>
            link_el = li.cssselect("h2 a")
            if not link_el:
                continue
            link = link_el[0]
            title = link.text_content().strip()
            url = link.get("href", "")

            # Skip if empty or if it's an ad (ads have different classes)
            if not title or not url:
                continue
            if url.startswith("javascript:") or url.startswith("#"):
                continue

            # ⚡ Block results with rdr=1 (Bing redirect tracking) — these are
            # usually low-quality or irrelevant results injected by Bing's redirect
            if "rdr=" in url.lower() or "&r=" in url.split("?")[0]:
                continue

            # Also skip bing.com internal links (adult filter, etc.)
            if url.startswith("https://www.bing.com/") and "/search?" not in url:
                continue

            # Skip known low-quality domains
            skip_domains = [
                "pinterest", "facebook.com", "instagram.com",
                "tiktok.com", "twitter.com", "x.com",
            ]
            if any(d in url.lower() for d in skip_domains):
                continue

            # Snippet from <p> or <div.b_caption><p>
            snippet_el = li.cssselect("p")
            if not snippet_el:
                snippet_el = li.cssselect(".b_caption p")
            snippet = snippet_el[0].text_content().strip() if snippet_el else ""

            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                rank=i + 1,
            ))

        # Fallback: try alternative selectors if b_algo missed
        if not results:
            for i, item in enumerate(tree.cssselect(".b_algo, .b_algo h2 a")):
                if len(results) >= max_results:
                    break

        # Deduplicate by URL
        seen_urls: set = set()
        deduped: List[SearchResult] = []
        for r in results:
            normalized = r.url.rstrip("/")
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                deduped.append(r)

        # Re-rank after dedup
        for idx, r in enumerate(deduped):
            r.rank = idx + 1

        return deduped