"""
DBLP Computer Science Bibliography search engine.

Uses the official DBLP JSON API:
  https://dblp.org/search/publ/api?q=<query>&format=json&h=<count>

Returns structured publication results with title, authors, year, venue, DOI,
and links to PDF/DBLP entry.
"""

import re
from typing import List, Optional
from urllib.parse import quote_plus

import httpx

from .base import SearchEngine, SearchResult, SearchResponse


class DBLPSearch(SearchEngine):
    """
    Search engine adapter for DBLP Computer Science Bibliography.

    Uses the official DBLP JSON search API at dblp.org/search/publ/api.
    DBLP is accessible without proxy from most networks.
    """

    engine_name: str = "dblp"

    def __init__(self, proxy: str = "", timeout: int = 15, user_agent: str = ""):
        super().__init__(proxy, timeout, user_agent)
        self._api_url = "https://dblp.org/search/publ/api"

    async def search(self, query: str, count: int = 10) -> SearchResponse:
        """
        Search DBLP and return publication results.

        Args:
            query: Search terms.
            count: Number of results to fetch (clamped 1-20).

        Returns:
            SearchResponse with parsed publication results.
        """
        response = SearchResponse(query=query, engine="dblp")
        count = max(1, min(count, 20))

        params = {
            "q": query,
            "format": "json",
            "h": count,
            "c": 0,  # start offset
        }

        headers = {
            "User-Agent": self.user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        client_kwargs = {"headers": headers, "timeout": self.timeout, "follow_redirects": True}
        if self.proxy:
            client_kwargs["proxy"] = self.proxy

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(self._api_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            response.success = False
            response.error = f"DBLP API returned HTTP {exc.response.status_code}"
            return response
        except httpx.RequestError as exc:
            response.success = False
            response.error = f"Request to DBLP failed: {exc}"
            return response
        except Exception as exc:
            response.success = False
            response.error = f"DBLP search failed: {exc}"
            return response

        try:
            result = data.get("result", {})
            hits = result.get("hits", {})
            hit_list = hits.get("hit", [])

            for i, hit in enumerate(hit_list):
                info = hit.get("info", {})
                title = info.get("title", "")
                # DBLP sometimes HTML-encodes titles
                title = self._clean_html(title)

                # URL is the DBLP page URL, not necessarily PDF
                url = info.get("url", "")

                # Extract authors
                authors_data = info.get("authors", {}).get("author", [])
                if isinstance(authors_data, list):
                    authors = ", ".join(
                        a.get("text", "") for a in authors_data if isinstance(a, dict)
                    )
                else:
                    authors = authors_data.get("text", "") if isinstance(authors_data, dict) else ""

                year = info.get("year", "")
                venue = info.get("venue", "")
                doi = info.get("doi", "")

                # Build a rich snippet
                snippet_parts = []
                if authors:
                    snippet_parts.append(f"Authors: {authors}")
                if year:
                    snippet_parts.append(f"Year: {year}")
                if venue:
                    snippet_parts.append(f"Venue: {venue}")
                if doi:
                    snippet_parts.append(f"DOI: {doi}")

                response.results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=" | ".join(snippet_parts),
                    rank=i + 1,
                ))

        except Exception as exc:
            response.success = False
            response.error = f"Failed to parse DBLP results: {exc}"
            return response

        if not response.results:
            response.error = "No results found on DBLP"

        return response

    def _clean_html(self, text: str) -> str:
        """Remove HTML entities from DBLP titles."""
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()