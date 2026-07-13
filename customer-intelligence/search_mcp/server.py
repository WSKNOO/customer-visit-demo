"""
AI4Search MCP Server — Search, Fetch, Parse, and Download tools for LLM agents.

Provides six MCP tools:
  - search_and_fetch: search engine + scrape top N results
  - fetch_url: scrape a single URL
  - fetch_pdf: parse a PDF URL
  - download_papers: batch download PDF files

Supports configurable search engines (bing/baidu/google/dblp/semantic_scholar),
smart per-domain proxy routing, and optional AI summarization.
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import FastMCP

from search_mcp.config import get_config
from search_mcp.engines.baidu import BaiduSearch
from search_mcp.engines.bing import BingSearch
from search_mcp.engines.dblp import DBLPSearch
from search_mcp.engines.google import GoogleSearch
from search_mcp.engines.semantic_scholar import SemanticScholarSearch
from search_mcp.proxy_router import resolve_proxy
from search_mcp.scraper import ScrapedContent, scrape_url
from search_mcp.pdf_parser import PDFContent, is_pdf_url, parse_pdf_url
from search_mcp.smart_search.company_researcher import research_company

# ── Logging helper (stderr, safe for stdio MCP) ─────────────────────────────

def log(msg: str) -> None:
    """Emit a log message to stderr (won't interfere with stdio MCP)."""
    print(f"[ai4search] {msg}", file=sys.stderr, flush=True)


# ── Proxy resolution helper ─────────────────────────────────────────────────

def _resolve_proxy(search_cfg: dict, url: str = "", engine_name: str = "") -> str:
    """
    Resolve proxy for a URL or engine using per-domain rules.

    If a URL is provided, uses domain-based routing.
    If only engine_name, uses engine-to-domain mapping.
    Falls back to the default proxy.

    The config.proxy can be:
      - A string (old format): used as-is for everything
      - A dict with 'default' + 'rules' (new format): per-domain routing
    """
    proxy_raw = search_cfg.get("proxy", "")
    if isinstance(proxy_raw, str):
        return proxy_raw

    # Dict format: use proxy_router
    if url:
        return resolve_proxy(url=url)
    if engine_name:
        return resolve_proxy(engine_name=engine_name)
    return proxy_raw.get("default", "") if isinstance(proxy_raw, dict) else ""


# ── MCP Server ───────────────────────────────────────────────────────────────

mcp = FastMCP("ai4search")


# ── Engine factory ──────────────────────────────────────────────────────────

def _get_engine_proxy(search_cfg: dict, engine_name: str) -> str:
    """Get the right proxy for a given engine using domain rules."""
    engine_domains = {
        "bing": "bing.com",
        "baidu": "baidu.com",
        "google": "google.com",
        "dblp": "dblp.org",
        "semantic_scholar": "semanticscholar.org",
    }
    domain = engine_domains.get(engine_name, "")
    return _resolve_proxy(search_cfg, engine_name=engine_name)


def get_engine(engine_name: str):
    """Get a search engine instance configured from the global config."""
    cfg = get_config()
    search_cfg = cfg.get("search", {})
    timeout = search_cfg.get("request_timeout", 15)
    ua = search_cfg.get("user_agent", "")

    def _proxy(name: str) -> str:
        return _get_engine_proxy(search_cfg, name)

    engines = {
        "bing": BingSearch(proxy=_proxy("bing"), timeout=timeout, user_agent=ua),
        "baidu": BaiduSearch(proxy=_proxy("baidu"), timeout=timeout, user_agent=ua),
        "google": GoogleSearch(proxy=_proxy("google"), timeout=timeout, user_agent=ua),
        "dblp": DBLPSearch(proxy=_proxy("dblp"), timeout=timeout, user_agent=ua),
        "semantic_scholar": SemanticScholarSearch(proxy=_proxy("semantic_scholar"), timeout=timeout, user_agent=ua),
    }
    engine = engines.get(engine_name)
    if engine is None:
        raise ValueError(
            f"Unknown engine: {engine_name}. "
            f"Choose from: {', '.join(engines.keys())}"
        )
    return engine


# ── Summarization helper ────────────────────────────────────────────────────

def maybe_summarize(text: str, summarize_flag: bool) -> str:
    """Summarize text if flag is True and summarizer is configured."""
    if not summarize_flag:
        return text

    cfg = get_config()
    sum_cfg = cfg.get("summarizer", {})
    if not sum_cfg.get("enabled", False):
        return text

    from search_mcp.summarizer import summarize as ai_summarize

    return ai_summarize(
        text=text,
        api_base=sum_cfg.get("api_base", "https://api.openai.com/v1"),
        api_key=sum_cfg.get("api_key", ""),
        model=sum_cfg.get("model", "gpt-4o-mini"),
        temperature=sum_cfg.get("temperature", 0.3),
        max_tokens=sum_cfg.get("max_tokens", 2048),
        max_input_chars=sum_cfg.get("max_input_chars", 100000),
    )


# ── MCP Tools ────────────────────────────────────────────────────────────────

AVAILABLE_ENGINES = ["bing", "baidu", "google", "dblp", "semantic_scholar"]


@mcp.tool(
    name="search_and_fetch",
    description="Search the web and fetch content from top result pages. "
                "Supports Bing, Baidu, Google, DBLP (academic), and Semantic Scholar. "
                "Returns title, URL, snippet, and full extracted Markdown content "
                "for each search result. Optionally summarize using AI.",
)
async def search_and_fetch(
    query: str,
    engine: str = "bing",
    count: int = 10,
    summarize: bool = False,
) -> str:
    """
    Search with the specified engine, fetch each result URL, return content.

    For academic engines (dblp, semantic_scholar), the result URLs are
    publication pages or DBLP pages, not necessarily full articles — use
    the snippet metadata to find specific PDF links.

    Args:
        query: Search query string.
        engine: Search engine — "bing" (default), "baidu", "google",
                "dblp" (academic), or "semantic_scholar".
        count: Number of results to fetch and parse (1-10, default 10).
        summarize: Whether to AI-summarize each result (requires config).

    Returns:
        JSON string with results or error.
    """
    log(f"search_and_fetch: engine={engine}, query={query!r}, count={count}")

    cfg = get_config()
    search_cfg = cfg.get("search", {})
    timeout = search_cfg.get("request_timeout", 15)
    count = max(1, min(count, 10))

    # ── Run search ───────────────────────────────────────────────────────
    try:
        engine_obj = get_engine(engine)
        search_resp = await engine_obj.search(query, count)
    except ValueError as exc:
        return json.dumps({"success": False, "data": [], "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        log(f"Search failed: {exc}")
        fallback_engine = "bing" if engine != "bing" else "baidu"
        try:
            log(f"Falling back to {fallback_engine}")
            engine_obj = get_engine(fallback_engine)
            search_resp = await engine_obj.search(query, count)
        except Exception as exc2:
            return json.dumps({
                "success": False,
                "data": [],
                "error": f"Primary engine ({engine}) failed. Fallback ({fallback_engine}) also failed: {exc2}",
            }, ensure_ascii=False)

    if not search_resp.success:
        return json.dumps({"success": False, "data": [], "error": search_resp.error}, ensure_ascii=False)
    if not search_resp.results:
        return json.dumps({"success": True, "data": [], "error": "No results found"}, ensure_ascii=False)

    # ── Fetch each result URL concurrently (max 3 at a time) ───────────────
    semaphore = asyncio.Semaphore(3)

    async def fetch_single(result) -> Optional[Dict[str, Any]]:
        async with semaphore:
            item: Dict[str, Any] = {
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "rank": result.rank,
                "content": "",
                "error": None,
            }
            if not result.url:
                return item

            try:
                proxy = _resolve_proxy(search_cfg, url=result.url)
                scraped = await scrape_url(result.url, proxy=proxy, timeout=timeout)
                if scraped.success:
                    content = (
                        f"# {scraped.title or result.title}\n"
                        f"> Source: {result.url}\n"
                        f"> Description: {scraped.description or result.snippet}\n\n"
                        f"{scraped.content}"
                    )
                    if summarize:
                        content = maybe_summarize(content, summarize_flag=True)
                    item["content"] = content
                    item["title"] = scraped.title or result.title
                else:
                    item["content"] = ""
                    item["error"] = scraped.error
            except Exception as exc:
                item["error"] = str(exc)
            return item

    tasks = [fetch_single(r) for r in search_resp.results[:count]]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    fetched_data: List[Dict[str, Any]] = []
    for res in results_list:
        if isinstance(res, Exception):
            log(f"Fetch task exception: {res}")
            fetched_data.append({
                "title": "", "url": "", "snippet": "", "rank": 0,
                "content": "", "error": str(res),
            })
        elif res is not None:
            fetched_data.append(res)

    return json.dumps({"success": True, "data": fetched_data, "error": None}, ensure_ascii=False, indent=2)


@mcp.tool(
    name="fetch_url",
    description="Fetch and extract readable content from any webpage URL. "
                "Returns clean Markdown with title and metadata. "
                "Optionally summarize using AI. Proxy is auto-resolved per domain.",
)
async def fetch_url(
    url: str,
    summarize: bool = False,
) -> str:
    """
    Fetch and extract content from a single webpage URL.

    Proxy is automatically resolved based on domain rules in config.

    Args:
        url: Webpage URL to fetch.
        summarize: Whether to AI-summarize the content (requires config).

    Returns:
        JSON string with extracted content or error.
    """
    log(f"fetch_url: {url}")

    cfg = get_config()
    search_cfg = cfg.get("search", {})
    timeout = search_cfg.get("request_timeout", 15)
    proxy = _resolve_proxy(search_cfg, url=url)

    try:
        scraped = await scrape_url(url, proxy=proxy, timeout=timeout)
        if scraped.success:
            content = (
                f"# {scraped.title}\n"
                f"> Source: {url}\n"
                f"> Description: {scraped.description}\n\n"
                f"{scraped.content}"
            )
            if summarize:
                content = maybe_summarize(content, summarize_flag=True)

            return json.dumps({
                "success": True,
                "data": {
                    "url": scraped.url,
                    "title": scraped.title,
                    "content": content,
                    "language": scraped.language,
                    "word_count": scraped.word_count,
                },
                "error": None,
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({"success": False, "data": None, "error": scraped.error}, ensure_ascii=False)
    except Exception as exc:
        log(f"fetch_url error: {exc}")
        return json.dumps({"success": False, "data": None, "error": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="fetch_pdf",
    description="Download a PDF from a URL and extract its content as Markdown with LaTeX for math. "
                "Extracts text, tables (as pipe tables), and mathematical expressions. "
                "Optionally summarize using AI. Proxy is auto-resolved per domain.",
)
async def fetch_pdf(
    url: str,
    summarize: bool = False,
) -> str:
    """
    Fetch and parse a PDF from a URL.

    Proxy is automatically resolved based on domain rules.

    Args:
        url: PDF URL to fetch and parse.
        summarize: Whether to AI-summarize the content (requires config).

    Returns:
        JSON string with parsed PDF content or error.
    """
    log(f"fetch_pdf: {url}")

    cfg = get_config()
    search_cfg = cfg.get("search", {})
    timeout = search_cfg.get("request_timeout", 15)
    proxy = _resolve_proxy(search_cfg, url=url)

    # If it's not obviously a PDF, do a HEAD check first
    if not is_pdf_url(url):
        try:
            from search_mcp.pdf_parser import check_pdf_remote
            is_pdf = await check_pdf_remote(url, proxy=proxy, timeout=timeout)
            if not is_pdf:
                return json.dumps({
                    "success": False,
                    "data": None,
                    "error": f"URL does not appear to be a PDF: {url}",
                }, ensure_ascii=False)
        except Exception as exc:
            log(f"PDF check failed, trying anyway: {exc}")

    try:
        result = await parse_pdf_url(url, proxy=proxy, timeout=timeout)
        if result.success:
            content = (
                f"# {result.title or 'PDF Document'}\n"
                f"> Source: {url}\n"
                f"> Pages: {result.page_count}\n\n"
                f"{result.content}"
            )
            if summarize:
                content = maybe_summarize(content, summarize_flag=True)

            return json.dumps({
                "success": True,
                "data": {
                    "url": result.url,
                    "title": result.title,
                    "content": content,
                    "page_count": result.page_count,
                },
                "error": None,
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({"success": False, "data": None, "error": result.error}, ensure_ascii=False)
    except Exception as exc:
        log(f"fetch_pdf error: {exc}")
        traceback.print_exc(file=sys.stderr)
        return json.dumps({"success": False, "data": None, "error": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="download_papers",
    description="Batch download PDF files (typically academic papers) to a local directory. "
                "Accepts a list of PDF URLs. Supports arxiv, any PDF URL. "
                "Proxy is auto-resolved per domain using config rules. "
                "Returns download status for each URL.",
)
async def download_papers(
    urls: List[str],
    output_dir: str = "",
) -> str:
    """
    Download multiple PDFs to a local directory.

    Args:
        urls: List of PDF URLs to download (e.g. ["https://arxiv.org/pdf/2604.09439v1", ...]).
        output_dir: Directory to save files. Defaults to "./tmp/papers/".
                    Created automatically if it doesn't exist.

    Returns:
        JSON string with download results for each URL.
    """
    log(f"download_papers: {len(urls)} files")

    # Resolve output directory
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "tmp", "papers")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cfg = get_config()
    search_cfg = cfg.get("search", {})
    timeout = search_cfg.get("request_timeout", 15)

    import httpx

    results: List[Dict[str, Any]] = []
    semaphore = asyncio.Semaphore(3)  # max 3 concurrent downloads

    async def download_single(url: str) -> Dict[str, Any]:
        async with semaphore:
            proxy = _resolve_proxy(search_cfg, url=url)
            # Generate filename from URL
            url_clean = url.rstrip("/")
            # Extract the last meaningful path segment
            path_parts = [p for p in url_clean.split("/") if p and not p.startswith("?")]
            filename_base = path_parts[-1] if path_parts else "paper"
            # Remove query params from filename
            filename_base = filename_base.split("?")[0]
            if not filename_base.endswith(".pdf"):
                filename_base += ".pdf"

            # Handle arxiv IDs differently: use the ID as filename
            if "arxiv.org" in url:
                import re
                arxiv_match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", url)
                if arxiv_match:
                    filename_base = arxiv_match.group(1) + ".pdf"

            filepath = output_path / filename_base

            # Skip if already downloaded
            if filepath.exists():
                return {
                    "url": url,
                    "status": "skipped",
                    "filename": filename_base,
                    "size_kb": filepath.stat().st_size // 1024,
                    "error": None,
                }

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            }

            client_kwargs = {
                "headers": headers,
                "timeout": min(timeout * 2, 120),
                "follow_redirects": True,
            }
            if proxy:
                client_kwargs["proxy"] = proxy

            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    filepath.write_bytes(resp.content)
                    return {
                        "url": url,
                        "status": "downloaded",
                        "filename": filename_base,
                        "size_kb": len(resp.content) // 1024,
                        "error": None,
                    }
            except Exception as exc:
                return {
                    "url": url,
                    "status": "failed",
                    "filename": filename_base,
                    "size_kb": 0,
                    "error": str(exc),
                }

    tasks = [download_single(u) for u in urls]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    for outcome in outcomes:
        if isinstance(outcome, Exception):
            results.append({
                "url": "",
                "status": "failed",
                "filename": "",
                "size_kb": 0,
                "error": str(outcome),
            })
        elif outcome is not None:
            results.append(outcome)

    downloaded = sum(1 for r in results if r["status"] == "downloaded")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")

    return json.dumps({
        "success": True,
        "output_dir": str(output_path.resolve()),
        "summary": {
            "total": len(results),
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
        },
        "files": results,
    }, ensure_ascii=False, indent=2)


@mcp.tool(
    name="research_company",
    description="对一家企业进行全面的联网情报研究，自动多维度搜索、收集内容、AI分析，"
                "生成详实的客户拜访情报简报（不少于5万字）。"
                "支持央企/国企/民企。返回一份结构化报告带来源链接。",
)
async def research_company_tool(
    company_name: str,
    visit_purpose: str = "",
    focus_areas: str = "",
    max_items: int = 80,
    sequential_mode: bool = False,
) -> str:
    """
    对企业进行全面的联网情报研究，生成结构化报告。

    Args:
        company_name: 客户企业名称（如\"中国石油天然气集团有限公司\"）。
        visit_purpose: 拜访目的描述（如\"了解数字化转型需求，推荐AI解决方案\"）。
        focus_areas: 关注的领域方向，用逗号分隔（如\"AI,云,大数据,安全\"）。
                     留空则进行全面分析。
        max_items: 最大收集的网页条目数（10-150，默认80）。
        sequential_mode: 是否使用逐模块生成模式。设为true可以生成更详细的报告，
                         但耗时更长（默认false）。

    Returns:
        JSON with research results including report path and stats.
    """
    log(f"research_company: {company_name}")

    # Parse focus areas
    focus_list = None
    if focus_areas and focus_areas.strip():
        focus_list = [a.strip() for a in focus_areas.split(",") if a.strip()]

    max_items = max(10, min(max_items, 150))

    result = await research_company(
        company_name=company_name,
        visit_purpose=visit_purpose,
        focus_areas=focus_list,
        max_items=max_items,
        sequential_mode=sequential_mode,
    )

    # For the report content, return a summary + first/last portion
    # (the full report is saved to disk)
    report = result.get("report", "")
    report_preview = ""
    if report:
        lines = report.split("\n")
        preview_lines = lines[:min(80, len(lines))]
        report_preview = "\n".join(preview_lines)
        if len(lines) > 80:
            report_preview += "\n\n... (报告完整内容已保存至文件) ...\n\n"
            report_preview += "\n".join(lines[-20:])

    return json.dumps({
        "success": result.get("success", False),
        "company": company_name,
        "report_path": result.get("report_path", ""),
        "source_data_path": result.get("source_data_path", ""),
        "source_count": result.get("source_count", 0),
        "total_chars": result.get("total_chars", 0),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "error": result.get("error"),
        "report_preview": report_preview,
        "summary": (
            f"研究完成！共检索到 {result.get('source_count', 0)} 条有效来源，"
            f"生成报告 {result.get('total_chars', 0)} 字。"
            f"报告已保存至: {result.get('report_path', '')}"
        ),
    }, ensure_ascii=False, indent=2)


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    """Run the MCP server with stdio transport."""
    log("AI4Search MCP Server starting...")
    cfg = get_config()
    proxy_cfg = cfg.get("search", {}).get("proxy", "")
    proxy_desc = "routing" if isinstance(proxy_cfg, dict) and proxy_cfg.get("rules") else ("set" if proxy_cfg else "none")
    log(f"Config loaded: engine={cfg['search']['default_engine']}, "
        f"proxy={proxy_desc}, "
        f"summarizer={'enabled' if cfg['summarizer']['enabled'] else 'disabled'}")
    log("Ready for connections via stdio.")

    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        log("Server shutdown by user")
    except Exception as exc:
        log(f"Server error: {exc}")
        raise


if __name__ == "__main__":
    main()