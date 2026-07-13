"""
PDF parser — extracts content from PDF URLs and returns Markdown.

Uses crawl4ai's PDFContentScrapingStrategy for robust PDF parsing with
native Markdown output. Falls back to PyMuPDF if crawl4ai PDF fails.
"""

import re
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai import PDFContentScrapingStrategy


@dataclass
class PDFContent:
    """Result of parsing a PDF file."""
    url: str
    title: str = ""
    content: str = ""
    page_count: int = 0
    success: bool = True
    error: Optional[str] = None


# ── Detection ────────────────────────────────────────────────────────────────

PDF_URL_PATTERN = re.compile(r"\.pdf(\?|#|$)", re.I)


def is_pdf_url(url: str) -> bool:
    """Quick check if URL likely points to a PDF by its extension."""
    return bool(PDF_URL_PATTERN.search(url))


async def check_pdf_remote(url: str, proxy: str = "", timeout: int = 10) -> bool:
    """
    Perform a lightweight HEAD request to check if the remote resource is a PDF.
    Uses crawl4ai's infrastructure minimally.

    Returns True if Content-Type indicates application/pdf.
    """
    try:
        import httpx
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }
        client_kwargs: dict = {
            "headers": headers,
            "timeout": timeout,
            "follow_redirects": True,
        }
        if proxy:
            client_kwargs["proxy"] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.head(url)
            content_type = resp.headers.get("content-type", "")
            return "pdf" in content_type.lower()
    except Exception:
        # Fall back to URL-based detection
        return is_pdf_url(url)


# ── Main PDF parsing function ────────────────────────────────────────────────

async def parse_pdf_url(
    url: str,
    proxy: str = "",
    timeout: int = 30,
) -> PDFContent:
    """
    Download a PDF from a URL and parse it into Markdown content.

    Uses crawl4ai's PDFContentScrapingStrategy which handles:
    - PDF text extraction
    - Table detection and rendering
    - Layout preservation

    Falls back to PyMuPDF if crawl4ai PDF processing fails.

    Args:
        url: PDF URL.
        proxy: Optional proxy server URL.
        timeout: Download timeout in seconds.

    Returns:
        PDFContent with extracted text in Markdown format.
    """
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        light_mode=True,
    )
    if proxy:
        browser_config.proxy = proxy

    run_config = CrawlerRunConfig(
        scraping_strategy=PDFContentScrapingStrategy(),
        verbose=False,
        page_timeout=timeout * 1000,
        cache_mode="bypass",
    )

    # ── Attempt 1: crawl4ai PDF strategy ─────────────────────────────────
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if result and result.success:
            md = result.markdown
            md_str = str(md).strip() if md else ""

            # Try to extract title from metadata or first line
            title = ""
            metadata = getattr(result, "metadata", None) or {}
            if isinstance(metadata, dict):
                title = metadata.get("title", "")
            if not title and md_str:
                first_line = md_str.split("\n")[0].strip()
                first_line = re.sub(r"^#+\s*", "", first_line)
                if first_line and len(first_line) < 200:
                    title = first_line

            # Estimate page count from content
            page_count = 0
            if md_str:
                # Count page markers or approximate by content length
                pages = re.findall(r"(?i)(?:page\s*\d+|\[page\s*\d+\])", md_str)
                page_count = len(pages) if pages else max(1, len(md_str) // 3000)

            return PDFContent(
                url=url,
                title=title,
                content=md_str or "",
                page_count=page_count,
                success=True,
            )
        else:
            error_msg = result.error_message if result else "No result from crawl4ai"
            # Fall through to fallback

    except ImportError:
        # crawl4ai[pdf] not installed — fall through to fallback
        print("[pdf_parser] crawl4ai PDF requires 'pip install crawl4ai[pdf]'. Falling back to PyMuPDF.", file=sys.stderr)
    except Exception as exc:
        print(f"[pdf_parser] crawl4ai PDF failed: {exc}. Falling back to PyMuPDF.", file=sys.stderr)

    # ── Attempt 2: PyMuPDF fallback ──────────────────────────────────────
    try:
        return await _parse_pdf_pymupdf(url, proxy, timeout)
    except Exception as exc:
        return PDFContent(
            url=url,
            success=False,
            error=f"Failed to parse PDF: {exc}",
        )


async def _parse_pdf_pymupdf(url: str, proxy: str = "", timeout: int = 30) -> PDFContent:
    """
    Fallback PDF parser using PyMuPDF + pdfplumber.

    Used when crawl4ai PDF strategy fails or isn't available.
    """
    import fitz  # PyMuPDF

    # Download PDF bytes
    pdf_bytes = await _download_pdf_bytes(url, proxy, timeout)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(doc)

    title = ""
    metadata = doc.metadata
    if metadata and metadata.get("title"):
        title = metadata["title"]
    if not title and page_count > 0:
        first_page = doc[0]
        first_text = first_page.get_text()[:200].strip()
        if first_text:
            for line in first_text.split("\n"):
                line = line.strip()
                if line and len(line) < 200:
                    title = line
                    break

    all_pages = []

    # Try pdfplumber for tables
    import pdfplumber
    import io

    try:
        pdf_plumb = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception:
        pdf_plumb = None

    for page_num in range(page_count):
        page = doc[page_num]
        page_text = page.get_text()

        # Get tables from pdfplumber
        page_tables = []
        if pdf_plumb and page_num < len(pdf_plumb.pages):
            try:
                plumb_page = pdf_plumb.pages[page_num]
                extracted = plumb_page.extract_tables()
                if extracted:
                    page_tables = extracted
            except Exception:
                pass

        lines = page_text.split("\n")
        processed = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                processed.append("")
                continue
            if re.match(r"^\d+$", stripped) and len(stripped) <= 5:
                continue
            processed.append(stripped)

        page_md = "\n".join(processed)
        if page_tables:
            table_md = _render_tables_as_markdown(page_tables)
            if table_md:
                page_md = page_md.strip() + "\n\n" + table_md

        all_pages.append(f"## Page {page_num + 1}\n\n{page_md.strip()}")

    doc.close()
    if pdf_plumb:
        pdf_plumb.close()

    return PDFContent(
        url=url,
        title=title,
        content="\n\n---\n\n".join(all_pages),
        page_count=page_count,
        success=True,
    )


async def _download_pdf_bytes(url: str, proxy: str = "", timeout: int = 30) -> bytes:
    """Download PDF bytes from a URL."""
    import httpx
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*;q=0.8",
    }
    client_kwargs = {"headers": headers, "timeout": timeout, "follow_redirects": True}
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _render_tables_as_markdown(tables: list) -> str:
    """Convert pdfplumber tables to GitHub-flavored Markdown pipe tables."""
    sections = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        clean = []
        for row in table:
            clean_row = [
                (cell or "").replace("\n", " ").replace("|", "\\|").strip()
                for cell in row
            ]
            clean.append(clean_row)

        max_cols = max(len(r) for r in clean)
        clean = [r + [""] * (max_cols - len(r)) for r in clean]

        lines = []
        lines.append("| " + " | ".join(clean[0]) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        for row in clean[1:]:
            lines.append("| " + " | ".join(row) + " |")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)