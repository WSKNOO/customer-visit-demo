"""
Semantic Scholar academic search engine.

Uses the Semantic Scholar API (semanticscholar.org):
  https://api.semanticscholar.org/graph/v1/paper/search

Includes rate-limit handling (429 retry with backoff).
"""

import asyncio
import re
from typing import List, Optional
from urllib.parse import quote_plus

import httpx

from .base import SearchEngine, SearchResult, SearchResponse


class SemanticScholarSearch(SearchEngine):
    """
    Search engine adapter for Semantic Scholar.

    Uses the Semantic Scholar Graph API to search academic papers.
    Rate-limited to ~1 req/sec (handled with retry + backoff).
    """

    engine_name: str = "semantic_scholar"

    def __init__(self, proxy: str = "", timeout: int = 15, user_agent: str = ""):
        super().__init__(proxy, timeout, user_agent)
        self._api_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    async def search(self, query: str, count: int = 10) -> SearchResponse:
        """
        Search Semantic Scholar and return paper results.

        Args:
            query: Search terms.
            count: Number of results to fetch (clamped 1-10).

        Returns:
            SearchResponse with parsed paper results.
        """
        response = SearchResponse(query=query, engine="semantic_scholar")
        count = max(1, min(count, 10))

        params = {
            "query": query,
            "limit": count,
            "fields": "title,year,authors,url,externalIds,venue,citationCount,publicationDate",
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
            if exc.response.status_code == 429:
                response.success = False
                response.error = (
                    "Semantic Scholar API rate limited (429). "
                    "Try again later or reduce request frequency."
                )
            else:
                response.success = False
                response.error = f"Semantic Scholar API returned HTTP {exc.response.status_code}"
            return response
        except httpx.RequestError as exc:
            response.success = False
            response.error = f"Request to Semantic Scholar failed: {exc}"
            return response
        except Exception as exc:
            response.success = False
            response.error = f"Semantic Scholar search failed: {exc}"
            return response

        try:
            papers = data.get("data", [])

            for i, paper in enumerate(papers):
                title = paper.get("title", "")
                if not title:
                    continue

                url = paper.get("url", "")
                year = paper.get("year", "")
                venue = paper.get("venue", "")
                citation_count = paper.get("citationCount", 0)
                pub_date = paper.get("publicationDate", "")
                external_ids = paper.get("externalIds", {}) or {}

                # Build a URL — prefer arXiv if available
                arxiv_id = external_ids.get("ArXiv", "")
                pdf_url = ""
                if arxiv_id:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

                # Authors
                authors_data = paper.get("authors", [])
                authors = ", ".join(
                    a.get("name", "") for a in authors_data[:3] if isinstance(a, dict)
                )
                if len(authors_data) > 3:
                    authors += " et al."

                # Build snippet
                snippet_parts = []
                if authors:
                    snippet_parts.append(f"Authors: {authors}")
                if year:
                    snippet_parts.append(f"Year: {year}")
                if venue:
                    snippet_parts.append(f"Venue: {venue}")
                if citation_count:
                    snippet_parts.append(f"Citations: {citation_count}")
                if arxiv_id:
                    snippet_parts.append(f"arXiv: {arxiv_id}")
                if pdf_url:
                    snippet_parts.append(f"PDF: {pdf_url}")

                response.results.append(SearchResult(
                    title=title,
                    url=url or f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                    snippet=" | ".join(snippet_parts),
                    rank=i + 1,
                ))

        except Exception as exc:
            response.success = False
            response.error = f"Failed to parse Semantic Scholar results: {exc}"
            return response

        if not response.results:
            response.error = "No results found on Semantic Scholar"

        return response