"""
Abstract base class for search engine implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResult:
    """A single search result entry."""
    title: str
    url: str
    snippet: str = ""
    rank: int = 0


@dataclass
class SearchResponse:
    """Response from a search engine."""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    engine: str = ""
    error: Optional[str] = None
    success: bool = True


class SearchEngine(ABC):
    """Interface that all search engine adapters must implement."""

    engine_name: str = "base"

    def __init__(self, proxy: str = "", timeout: int = 15, user_agent: str = ""):
        self.proxy = proxy
        self.timeout = timeout
        self.user_agent = user_agent

    @abstractmethod
    async def search(self, query: str, count: int = 10) -> SearchResponse:
        """
        Execute a search and return parsed results.

        Args:
            query: Search query string.
            count: Number of results requested (1-10, engine may return fewer).

        Returns:
            SearchResponse with parsed results.
        """
        ...

    def _build_headers(self) -> dict:
        """Build common HTTP headers for search requests."""
        return {
            "User-Agent": self.user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _build_client(self) -> dict:
        """Build kwargs for httpx.AsyncClient."""
        kwargs: dict = {
            "headers": self._build_headers(),
            "timeout": self.timeout,
            "follow_redirects": True,
        }
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs