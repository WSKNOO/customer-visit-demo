"""
Google search engine implementation.

Uses crawl4ai's full browser engine (Chromium) with anti-detection to
execute Google searches. Google requires JavaScript and blocks many proxy IPs,
so a clean residential/datacenter proxy is essential.

Strategy:
1. Full browser crawl with stealth/magic anti-detection
2. Parses rendered Markdown output for numbered results
3. Falls back to HTML parsing if Markdown parser doesn't find enough
4. Detects "unusual traffic" CAPTCHA blocks and reports clearly
"""

import re
import sys
from typing import List, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, ProxyConfig

from .base import SearchEngine, SearchResult, SearchResponse


class GoogleSearch(SearchEngine):
    """Search engine adapter using crawl4ai browser for Google search."""

    engine_name: str = "google"

    # CSS selectors tried in order for HTML fallback parsing
    RESULT_SELECTORS = [
        "div.g",
        "div[data-hveid]",
        ".rc",
        ".yuRUbf",
    ]

    SNIPPET_SELECTORS = [
        ".VwiC3b",
        ".aCOpRe",
        "span.st",
        ".lEBKkf",
        "div[data-sncf] span",
    ]

    GOOGLE_INTERNAL_DOMAINS = (
        "google.com", "google.co.", "googleusercontent.com",
        "googleapis.com", "gstatic.com",
    )

    def __init__(self, proxy: str = "", timeout: int = 30, user_agent: str = ""):
        super().__init__(proxy, timeout, user_agent)
        self._base_url = "https://www.google.com/search"

    # ── Public API ───────────────────────────────────────────────────────────

    async def search(self, query: str, count: int = 10) -> SearchResponse:
        """
        Search Google via crawl4ai browser engine.

        Args:
            query: Search terms.
            count: Number of results to fetch (clamped 1-10, default 10).

        Returns:
            SearchResponse with parsed organic results.
        """
        response = SearchResponse(query=query, engine="google")
        count = max(1, min(count, 10))
        search_url = f"{self._base_url}?q={quote_plus(query)}&num={count + 3}&hl=en"

        browser_cfg = self._build_browser_config()
        run_cfg = self._build_run_config()

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(url=search_url, config=run_cfg)
        except Exception as exc:
            response.success = False
            response.error = f"Google browser search failed: {exc}"
            return response

        if not result or not result.success:
            error_msg = result.error_message if result else "No result from browser"
            response.success = False
            response.error = f"Google crawl failed: {error_msg}"
            return response

        # Check for CAPTCHA / blocking
        md = str(result.markdown) if result.markdown else ""
        block_reason = self._check_blocked(md)
        if block_reason:
            response.success = False
            response.error = (
                f"Google is blocking this request: {block_reason}. "
                f"The proxy IP may be flagged. Try a different proxy or rotate IPs."
            )
            return response

        # Parse results from markdown
        results = self._parse_markdown(md, count)

        # Fallback: clean HTML parse
        if not results:
            html = (getattr(result, "cleaned_html", None) or
                    getattr(result, "html", "") or "")
            results = self._parse_html(html, count)

        if not results:
            response.success = False
            response.error = (
                "Google responded but no search results were found in the page. "
                "The page layout may have changed or results are blocked."
            )
            return response

        response.results = results[:count]
        return response

    # ── Config builders ──────────────────────────────────────────────────────

    def _build_browser_config(self) -> BrowserConfig:
        """Build browser config with proxy and anti-detection."""
        kwargs = {
            "headless": True,
            "verbose": False,
            "enable_stealth": True,
            "light_mode": True,
            "user_agent_mode": "random",
            "ignore_https_errors": True,
        }
        if self.proxy:
            kwargs["proxy_config"] = ProxyConfig(server=self.proxy)
        return BrowserConfig(**kwargs)

    def _build_run_config(self) -> CrawlerRunConfig:
        """Build crawl config with full browser + anti-detection."""
        return CrawlerRunConfig(
            verbose=False,
            page_timeout=max(self.timeout * 1000, 45000),
            cache_mode="bypass",
            simulate_user=True,
            magic=True,
            remove_consent_popups=True,
            override_navigator=True,
            delay_before_return_html=2.0,
            wait_until="networkidle",
            word_count_threshold=1,
        )

    # ── Blocking detection ───────────────────────────────────────────────────

    BLOCK_KEYWORDS = [
        "unusual traffic",
        "sorry",
        "captcha",
        "automated queries",
        "automated requests",
        "enable javascript",
    ]

    def _check_blocked(self, text: str) -> Optional[str]:
        """Check if Google returned a blocking/CAPTCHA page."""
        lower = text.lower()
        for kw in self.BLOCK_KEYWORDS:
            if kw in lower:
                return f"detected '{kw}' in response"
        return None

    # ── Markdown parsing ─────────────────────────────────────────────────────

    def _parse_markdown(self, md: str, max_results: int) -> List[SearchResult]:
        """
        Parse Google search results from crawl4ai's markdown output.

        Google typically renders results as numbered items:
          "1. **Title** [link](url)"
        or:
          "1. **Title** url"
        """
        results: List[SearchResult] = []
        seen_urls: set = set()
        current_title = ""
        current_url = ""
        current_snippet = ""

        lines = md.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("![") or stripped.startswith("```"):
                continue

            # Detect numbered result header: "1. **Title**" or "1. Title"
            numbered = re.match(
                r"^(\d+)\.\s+\*{0,2}(.+?)\*{0,2}\s*(?:\[(?:.*?)\]\((https?://[^\s)]+)\))?\s*$",
                stripped,
            )
            if numbered:
                # Save previous accumulated result
                self._flush_result(results, seen_urls, current_title, current_url, current_snippet)
                current_title = numbered.group(2).strip()
                current_url = self._clean_url(numbered.group(3) or "")
                current_snippet = ""
                continue

            # Detect "**Title** [link](url)" — bold title with link inline
            inline = re.search(r"\*\*(.+?)\*\*\s*\[(?:.*?)\]\((https?://[^\s)]+)\)", stripped)
            if inline:
                self._flush_result(results, seen_urls, current_title, current_url, current_snippet)
                current_title = inline.group(1).strip()
                current_url = self._clean_url(inline.group(2))
                current_snippet = ""
                continue

            # Detect bare URL line that may be a search result
            bare_url = re.match(r"^(https?://[^\s)]+)$", stripped)
            if bare_url and not current_url:
                current_url = self._clean_url(bare_url.group(1))
                continue

            # Accumulate snippet text (non-empty, non-heading lines)
            if current_url and not stripped.startswith("#") and not stripped.startswith("*"):
                if re.match(r"^\d+\.", stripped) and not numbered:
                    # New numbered item without bold — flush and restart
                    self._flush_result(results, seen_urls, current_title, current_url, current_snippet)
                    current_title = re.sub(r"^\d+\.\s*", "", stripped)[:80]
                    current_url = ""
                    current_snippet = ""
                else:
                    current_snippet += " " + stripped

        # Flush last result
        self._flush_result(results, seen_urls, current_title, current_url, current_snippet)

        return self._deduplicate(results, max_results)

    def _flush_result(
        self, results: List[SearchResult], seen: set,
        title: str, url: str, snippet: str,
    ) -> None:
        """Append a collected result if valid."""
        if title and url:
            clean_url = url.rstrip("/")
            if clean_url not in seen:
                seen.add(clean_url)
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet.strip(),
                    rank=len(results) + 1,
                ))

    # ── HTML fallback parsing ────────────────────────────────────────────────

    def _parse_html(self, html: str, max_results: int) -> List[SearchResult]:
        """Fallback: extract results from cleaned HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        results: List[SearchResult] = []

        for selector in self.RESULT_SELECTORS:
            if results:
                break
            for container in soup.select(selector):
                if len(results) >= max_results:
                    break
                result = self._extract_from_container(container)
                if result:
                    results.append(result)

        return self._deduplicate(results, max_results)

    def _extract_from_container(self, container) -> Optional[SearchResult]:
        """Extract title/url/snippet from a single result container div."""
        link_el = (
            container.select_one("h3 a")
            or container.select_one("a[href^='http']")
        )
        if not link_el:
            return None

        title = link_el.get_text(strip=True)
        url = link_el.get("href", "")
        if not title or not url:
            return None

        url = self._clean_url(url)
        if not url:
            return None

        # Skip Google-internal links
        domain = urlparse(url).netloc.lower()
        if any(g in domain for g in self.GOOGLE_INTERNAL_DOMAINS):
            return None

        snippet = ""
        for sel in self.SNIPPET_SELECTORS:
            el = container.select_one(sel)
            if el:
                snippet = el.get_text(strip=True)
                break

        return SearchResult(title=title, url=url, snippet=snippet, rank=0)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _clean_url(self, url: str) -> str:
        """Clean Google redirect wrapper from URLs."""
        url = url.strip().rstrip("/")
        if not url:
            return ""

        # Google redirect: /url?q=REAL_URL&...
        if "q=" in url and ("/url?" in url or "google.com/url?" in url):
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                real_url = qs.get("q", [url])[0]
                if real_url.startswith("http"):
                    return real_url
            except Exception:
                pass

        # Protocol-relative
        if url.startswith("//"):
            return "https:" + url

        return url

    def _deduplicate(self, results: List[SearchResult], max_results: int) -> List[SearchResult]:
        """Deduplicate by URL and re-rank."""
        seen: set = set()
        deduped: List[SearchResult] = []
        for r in results:
            key = r.url.rstrip("/")
            if key not in seen and key:
                seen.add(key)
                deduped.append(r)
        for idx, r in enumerate(deduped):
            r.rank = idx + 1
        return deduped[:max_results]