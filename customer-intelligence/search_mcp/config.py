"""
Configuration loader for search MCP server.

Loads config from:
1. config.yaml in the project root directory
2. Environment variable overrides (SEARCH_MCP_*)

Env vars take highest priority:
  SEARCH_MCP_ENGINE         -> search.default_engine
  SEARCH_MCP_PROXY          -> search.proxy
  SEARCH_MCP_TIMEOUT        -> search.request_timeout
  SEARCH_MCP_DEFAULT_COUNT  -> search.default_count
  SEARCH_MCP_SUMMARIZER_ENABLED -> summarizer.enabled
  SEARCH_MCP_SUMMARIZER_API_BASE -> summarizer.api_base
  SEARCH_MCP_SUMMARIZER_API_KEY  -> summarizer.api_key
  SEARCH_MCP_SUMMARIZER_MODEL    -> summarizer.model
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Default config ──────────────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    "search": {
        "default_engine": "sogou",
        "default_count": 10,
        "request_timeout": 15,
        "service_base_url": "https://www.sogou.com/web",
        "service_api_key": "",
        "max_fetch_pages": 20,
        "max_content_chars": 50000,
        "max_dimensions": 6,
        "max_keywords_per_dimension": 1,
        "fetch_content_enabled": False,
        "snippet_fallback_enabled": True,
        "proxy": {
            "default": "",
            "rules": {},
        },
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    },
    "summarizer": {
        "enabled": False,
        "api_base": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 2048,
        "max_input_chars": 100000,
        "context_limit": 20480,
        "max_input_tokens": 8000,
        "max_report_output_tokens": 4096,
        "token_safety_margin": 1024,
        "retry_input_tokens": 4500,
        "max_report_sources": 10,
        "max_source_chars": 500,
    },
}

# ── Env var map: (env_key, config_path_keys, type_cast) ─────────────────────

ENV_OVERRIDES = [
    ("SEARCH_MCP_ENGINE", ["search", "default_engine"], str),
    ("SEARCH_MCP_PROXY", ["search", "proxy"], str),
    ("SEARCH_MCP_TIMEOUT", ["search", "request_timeout"], int),
    ("SEARCH_MCP_DEFAULT_COUNT", ["search", "default_count"], int),
    ("SEARCH_SERVICE_BASE_URL", ["search", "service_base_url"], str),
    ("SEARCH_SERVICE_API_KEY", ["search", "service_api_key"], str),
    ("SEARCH_MAX_FETCH_PAGES", ["search", "max_fetch_pages"], int),
    ("SEARCH_MAX_CONTENT_CHARS", ["search", "max_content_chars"], int),
    ("SEARCH_MAX_DIMENSIONS", ["search", "max_dimensions"], int),
    ("SEARCH_MAX_KEYWORDS_PER_DIMENSION", ["search", "max_keywords_per_dimension"], int),
    ("SEARCH_FETCH_CONTENT_ENABLED", ["search", "fetch_content_enabled"], lambda v: v.lower() in ("1", "true", "yes")),
    ("SEARCH_SNIPPET_FALLBACK_ENABLED", ["search", "snippet_fallback_enabled"], lambda v: v.lower() in ("1", "true", "yes")),
    ("SEARCH_MCP_SUMMARIZER_ENABLED", ["summarizer", "enabled"], lambda v: v.lower() in ("1", "true", "yes")),
    ("SEARCH_MCP_SUMMARIZER_API_BASE", ["summarizer", "api_base"], str),
    ("SEARCH_MCP_SUMMARIZER_API_KEY", ["summarizer", "api_key"], str),
    ("SEARCH_MCP_SUMMARIZER_MODEL", ["summarizer", "model"], str),
    ("SEARCH_MCP_SUMMARIZER_TEMPERATURE", ["summarizer", "temperature"], float),
    ("SEARCH_MCP_SUMMARIZER_MAX_TOKENS", ["summarizer", "max_tokens"], int),
    ("SEARCH_MCP_SUMMARIZER_MAX_INPUT_CHARS", ["summarizer", "max_input_chars"], int),
    ("INTELLIGENCE_MODEL_CONTEXT_LIMIT", ["summarizer", "context_limit"], int),
    ("INTELLIGENCE_MODEL_MAX_INPUT_TOKENS", ["summarizer", "max_input_tokens"], int),
    ("INTELLIGENCE_MODEL_MAX_OUTPUT_TOKENS", ["summarizer", "max_report_output_tokens"], int),
    ("INTELLIGENCE_MODEL_TOKEN_SAFETY_MARGIN", ["summarizer", "token_safety_margin"], int),
    ("INTELLIGENCE_MODEL_RETRY_INPUT_TOKENS", ["summarizer", "retry_input_tokens"], int),
    ("INTELLIGENCE_REPORT_MAX_SOURCES", ["summarizer", "max_report_sources"], int),
    ("INTELLIGENCE_REPORT_SOURCE_MAX_CHARS", ["summarizer", "max_source_chars"], int),
]


def _find_config_file() -> Optional[Path]:
    """Walk up from cwd / script dir to find config.yaml."""
    candidates = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
        Path(__file__).resolve().parent.parent / "config.yaml",
        Path(__file__).resolve().parent.parent / "config.yml",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _deep_set(d: Dict[str, Any], keys: list, value: Any) -> None:
    """Set a nested dict value from a key path like ['search', 'proxy']."""
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _deep_get(d: Dict[str, Any], keys: list) -> Any:
    """Get a nested dict value, returning None if any key is missing."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return None
    return d


def _merge_proxy_config(config: Dict[str, Any], file_cfg: Dict[str, Any]) -> None:
    """Merge proxy config (handles both old string format and new dict format)."""
    file_proxy = file_cfg.get("proxy")
    if file_proxy is None:
        return
    if isinstance(file_proxy, str):
        # Old format: proxy as a plain string
        config["proxy"] = file_proxy
    elif isinstance(file_proxy, dict):
        # New format: proxy as {default: ..., rules: {...}}
        current = config["proxy"]
        if isinstance(current, dict):
            if "default" in file_proxy:
                current["default"] = file_proxy["default"]
            if "rules" in file_proxy and isinstance(file_proxy["rules"], dict):
                current["rules"].update(file_proxy["rules"])
        else:
            config["proxy"] = file_proxy


def load_config() -> Dict[str, Any]:
    """
    Load config from file then overlay env-var overrides.

    Returns a fully-populated config dict (every key from DEFAULT_CONFIG is
    guaranteed to exist).
    """
    config: Dict[str, Any] = {}
    for section, values in DEFAULT_CONFIG.items():
        if isinstance(values, dict):
            config[section] = dict(values)
        else:
            config[section] = values

    # 1. File override
    cfg_path = _find_config_file()
    if cfg_path is not None:
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                file_cfg = yaml.safe_load(fh) or {}
            # Merge file values into defaults (only known keys)
            for section, values in file_cfg.items():
                if section in config:
                    if section == "search" and isinstance(values, dict):
                        _merge_search_config(config["search"], values)
                    elif isinstance(values, dict) and isinstance(config[section], dict):
                        for key, val in values.items():
                            if val is not None and key in config[section]:
                                config[section][key] = val
                    elif not isinstance(values, dict):
                        config[section] = values
        except Exception as exc:
            print(f"[config] Warning: could not read {cfg_path}: {exc}", file=sys.stderr)

    # 2. Env-var override (only for simple string/int/float/bool values)
    for env_key, keys, cast in ENV_OVERRIDES:
        raw = os.environ.get(env_key)
        if raw is not None:
            try:
                _deep_set(config, keys, cast(raw))
            except (ValueError, TypeError) as exc:
                print(f"[config] Warning: cannot parse {env_key}={raw!r}: {exc}", file=sys.stderr)

    # A single explicit search proxy is easiest to deploy. If it is omitted,
    # inherit the standard outbound proxy used by the container.
    if not os.environ.get("SEARCH_MCP_PROXY"):
        inherited_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if inherited_proxy:
            config["search"]["proxy"] = inherited_proxy

    return config


def _merge_search_config(config: Dict[str, Any], file_values: Dict[str, Any]) -> None:
    """Merge search config section, with special handling for proxy."""
    for key, val in file_values.items():
        if val is None:
            continue
        if key == "proxy":
            _merge_proxy_config(config, file_values)
        elif key in config:
            config[key] = val


def _legacy_proxy(config: Dict[str, Any]) -> Any:
    """
    Backward-compatible accessor for proxy config.

    Returns the proxy string if proxy is a simple string,
    or the default proxy if configured as dict.
    """
    proxy = config.get("search", {}).get("proxy", "")
    if isinstance(proxy, dict):
        return proxy.get("default", "")
    return proxy if isinstance(proxy, str) else ""


# ── Singleton (loaded once on first import) ─────────────────────────────────

_config: Optional[Dict[str, Any]] = None


def get_config() -> Dict[str, Any]:
    """Return the singleton config, loading it on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Dict[str, Any]:
    """Force-reload config from disk and env vars."""
    global _config
    _config = load_config()
    return _config
