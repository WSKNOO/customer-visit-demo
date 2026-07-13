"""
Webpage scraper — extracts clean Markdown content from URLs.

Uses crawl4ai for robust, anti-detection web scraping:
1. LXMLWebScrapingStrategy (fast, no browser) for simple pages
2. Full browser crawl with stealth/magic for JS-heavy pages as fallback
3. Built-in anti-bot detection, random user-agents, and consent popup removal
"""

import asyncio
import sys
from dataclasses import dataclass
from typing import Optional

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy

# Safety limit: truncate extracted content to avoid blowing LLM context window
MAX_CONTENT_CHARS = 150_000


@dataclass
class ScrapedContent:
    """Result of scraping a webpage."""
    url: str
    title: str = ""
    content: str = ""
    language: str = ""
    description: str = ""
    success: bool = True
    error: Optional[str] = None
    word_count: int = 0


# ── Shared browser config (anti-detection) ──────────────────────────────────

def _make_browser_config(proxy: str = "", user_agent: str = "") -> BrowserConfig:
    """Build a BrowserConfig with anti-detection settings."""
    kwargs: dict = {
        "headless": True,
        "verbose": False,
        "enable_stealth": True,
        "light_mode": True,
        "ignore_https_errors": True,
    }
    if user_agent:
        kwargs["user_agent"] = user_agent
        kwargs["user_agent_mode"] = "custom"
    else:
        kwargs["user_agent_mode"] = "random"
    if proxy:
        kwargs["proxy"] = proxy
    return BrowserConfig(**kwargs)


def _make_lxml_run_config(timeout: int = 15) -> CrawlerRunConfig:
    """Build a lightweight CrawlerRunConfig using LXML strategy (no browser)."""
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48),
        options={"body_width": 0},
    )
    return CrawlerRunConfig(
        scraping_strategy=LXMLWebScrapingStrategy(),
        markdown_generator=md_generator,
        verbose=False,
        page_timeout=timeout * 1000,
        cache_mode="bypass",
    )


def _make_browser_run_config(timeout: int = 15) -> CrawlerRunConfig:
    """Build a full CrawlerRunConfig using real browser with anti-detection."""
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48),
        options={"body_width": 0},
    )
    return CrawlerRunConfig(
        markdown_generator=md_generator,
        verbose=False,
        page_timeout=timeout * 1000,
        cache_mode="bypass",
        # Anti-detection
        simulate_user=True,
        magic=True,
        remove_consent_popups=True,
        override_navigator=True,
        # Wait for content to settle
        delay_before_return_html=0.3,
        wait_until="domcontentloaded",
    )


def _extract_metadata(result, url: str) -> tuple:
    """
    Extract title, description, language from a CrawlResult.

    Returns (title, description, language).
    """
    title = ""
    description = ""
    language = ""

    # Try metadata first
    metadata = getattr(result, "metadata", None) or {}
    if isinstance(metadata, dict):
        title = metadata.get("title", "") or metadata.get("og:title", "") or ""
        description = metadata.get("description", "") or metadata.get("og:description", "") or ""

    # Fallback: extract from cleaned_html
    if not title or not description:
        cleaned = getattr(result, "cleaned_html", None)
        if cleaned:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(cleaned, "lxml")
            if not title and soup.title and soup.title.string:
                title = soup.title.string.strip()
            if not description:
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    description = meta_desc["content"].strip()
            if not language:
                html_tag = soup.find("html")
                if html_tag and html_tag.get("lang"):
                    language = html_tag["lang"]

    # Fallback: first line of markdown as title
    if not title:
        md = result.markdown
        if md:
            first_line = str(md).strip().split("\n")[0].strip()
            first_line = first_line.lstrip("#").strip()
            if first_line and len(first_line) < 200:
                title = first_line

    # Response headers for language
    if not language:
        resp_headers = getattr(result, "response_headers", None) or {}
        language = resp_headers.get("Content-Language", "")

    return title, description, language


def _extract_content(result) -> str:
    """
    Extract clean Markdown content from a crawl4ai CrawlResult.

    Tries multiple content sources in order of preference.
    """
    # result.markdown is a StringCompatibleMarkdown — str(result.markdown) works
    md = result.markdown
    if md:
        raw = str(md).strip()
        if raw:
            if len(raw) > MAX_CONTENT_CHARS:
                raw = raw[:MAX_CONTENT_CHARS] + "\n\n[... content truncated to prevent overflow ...]"
            return raw

    # Fallback: cleaned_html
    cleaned = getattr(result, "cleaned_html", None)
    if cleaned:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(cleaned, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        if text:
            if len(text) > MAX_CONTENT_CHARS:
                text = text[:MAX_CONTENT_CHARS] + "\n\n[... content truncated to prevent overflow ...]"
            return text

    return ""


# ── Main scrape function ────────────────────────────────────────────────────

async def scrape_url(
    url: str,
    proxy: str = "",
    timeout: int = 15,
    user_agent: str = "",
) -> ScrapedContent:
    """
    Scrape a webpage and return clean Markdown content.

    Uses crawl4ai with intelligent strategy selection:
    - LXMLWebScrapingStrategy for simple pages (instant, no browser launch)
    - Falls back to full browser crawl with anti-detection if LXML fails

    Args:
        url: Target URL to scrape.
        proxy: Optional proxy server URL (e.g. "http://127.0.0.1:7890").
        timeout: Request timeout in seconds.
        user_agent: Custom User-Agent string. If empty, uses random UA.

    Returns:
        ScrapedContent with extracted text in Markdown format.
    """
    browser_config = _make_browser_config(proxy=proxy, user_agent=user_agent)

    # ── Attempt 1: LXML strategy (fast, no browser) ──────────────────────
    lxml_config = _make_lxml_run_config(timeout=timeout)
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=lxml_config)

        if result and result.success:
            content = _extract_content(result)
            if content and len(content.strip()) > 50:
                title, description, language = _extract_metadata(result, url)
                return ScrapedContent(
                    url=url,
                    title=title,
                    content=content,
                    description=description,
                    language=language,
                    success=True,
                    word_count=len(content.split()),
                )
    except Exception as exc:
        print(f"[scraper] LXML strategy failed for {url}: {exc}", file=sys.stderr)

    # ── Attempt 2: Full browser crawl with anti-detection ────────────────
    browser_config = _make_browser_config(proxy=proxy, user_agent=user_agent)
    run_config = _make_browser_run_config(timeout=timeout)

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if result and result.success:
            content = _extract_content(result)
            if content and len(content.strip()) > 10:
                title, description, language = _extract_metadata(result, url)
                return ScrapedContent(
                    url=url,
                    title=title,
                    content=content,
                    description=description,
                    language=language,
                    success=True,
                    word_count=len(content.split()),
                )

        error_msg = result.error_message if result else "No result returned"
        return ScrapedContent(url=url, success=False, error=error_msg or "Unknown error")

    except Exception as exc:
        print(f"[scraper] Browser crawl failed for {url}: {exc}", file=sys.stderr)
        return ScrapedContent(url=url, success=False, error=str(exc))


# ── Convenience syncing for non-async contexts ──────────────────────────────

def scrape_url_sync(
    url: str,
    proxy: str = "",
    timeout: int = 15,
    user_agent: str = "",
) -> ScrapedContent:
    """Synchronous wrapper around scrape_url."""
    return asyncio.run(scrape_url(url, proxy, timeout, user_agent))