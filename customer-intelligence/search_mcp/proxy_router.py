"""
Proxy Router — per-domain proxy routing with fallback to default.

Supports domain-specific proxy rules from config:
- Some domains can bypass proxy entirely (empty string)
- Some domains use the default proxy
- Some domains use a specific proxy

Usage:
    from search_mcp.proxy_router import get_proxy_for_url
    proxy = get_proxy_for_url("https://arxiv.org/abs/1234")
    # Returns "" (no proxy) if arxiv.org is in the bypass list
"""

import re
from typing import Dict, Optional
from urllib.parse import urlparse


def _get_rules() -> Dict[str, str]:
    """Fetch proxy rules from config."""
    from search_mcp.config import get_config
    cfg = get_config()
    proxy_cfg = cfg.get("search", {}).get("proxy", {})
    rules = proxy_cfg.get("rules", {}) if isinstance(proxy_cfg, dict) else {}
    return rules


def _get_default_proxy() -> str:
    """Fetch the default proxy from config."""
    from search_mcp.config import get_config
    cfg = get_config()
    proxy_cfg = cfg.get("search", {}).get("proxy", {})
    if isinstance(proxy_cfg, dict):
        return proxy_cfg.get("default", "")
    return proxy_cfg if isinstance(proxy_cfg, str) else ""


def get_proxy_for_url(url: str) -> str:
    """
    Determine the proxy to use for a given URL.

    Checks domain-specific rules first, falls back to default proxy.

    Args:
        url: The target URL to check.

    Returns:
        Proxy string (e.g. "http://127.0.0.1:12000") or "" for no proxy.
    """
    if not url:
        return _get_default_proxy()

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return _get_default_proxy()

    # Remove leading www. for matching
    domain = hostname.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    rules = _get_rules()
    if not rules:
        return _get_default_proxy()

    # Exact match on full domain first
    if domain in rules:
        return rules[domain]

    # Subdomain match: check if `domain` ends with any rule key
    # e.g. "scholar.google.com" -> matches rule for "google.com" if no exact match
    for rule_domain, rule_proxy in rules.items():
        if domain.endswith("." + rule_domain) or domain == rule_domain:
            return rule_proxy

    # Fall back to default
    return _get_default_proxy()


def should_use_proxy(url: str) -> bool:
    """Returns True if the URL should go through proxy."""
    return bool(get_proxy_for_url(url))


def resolve_proxy(
    url: str = "",
    engine_name: str = "",
) -> str:
    """
    Resolve proxy for a given URL or engine name.

    This is the main helper used by engines and scraper.
    - If url is given, applies domain rules.
    - If only engine_name is given, checks engine-level proxy rules.
    - Falls back to default proxy.

    Args:
        url: Target URL to check (optional).
        engine_name: Engine name for fallback (optional).

    Returns:
        Proxy string or "".
    """
    if url:
        return get_proxy_for_url(url)

    # Engine-level proxy (e.g. "google.com" needs proxy)
    from search_mcp.config import get_config
    cfg = get_config()
    proxy_cfg = cfg.get("search", {}).get("proxy", {})
    if isinstance(proxy_cfg, dict):
        rules = proxy_cfg.get("rules", {})
        default_proxy = proxy_cfg.get("default", "")
        # Check if engine name maps to a domain in rules
        engine_map = {
            "google": "google.com",
            "dblp": "dblp.org",
            "semantic_scholar": "semanticscholar.org",
            "bing_academic": "cn.bing.com",
            "bing": "",
            "baidu": "baidu.com",
            "sogou": "sogou.com",
        }
        mapped = engine_map.get(engine_name, "")
        if mapped in rules:
            return rules[mapped]
        return default_proxy
    return proxy_cfg if isinstance(proxy_cfg, str) else ""
