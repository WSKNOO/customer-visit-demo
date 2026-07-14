#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DEPLOY_DIR"
QUERY=${1:-中国电信 数字化 最新动态}
files=(-f docker-compose.yml)
if [[ "${USE_HOT_COMPOSE:-false}" == true ]]; then files+=(-f docker-compose.hot.yml); fi

docker compose "${files[@]}" exec -T customer-intelligence-api python3 - "$QUERY" <<'PY'
import asyncio
import json
import sys

from search_mcp.config import get_config
from search_mcp.engines.sogou import SogouSearch


async def main():
    cfg = get_config()["search"]
    engine = SogouSearch(
        proxy=cfg.get("proxy", ""),
        timeout=cfg.get("request_timeout", 15),
        user_agent=cfg.get("user_agent", ""),
        base_url=cfg.get("service_base_url", ""),
    )
    response = await engine.search(sys.argv[1], count=5)
    payload = {
        "success": response.success,
        "engine": response.engine,
        "count": len(response.results),
        "error": response.error,
        "results": [
            {"title": item.title, "url": item.url, "snippet_chars": len(item.snippet)}
            for item in response.results
        ],
    }
    print(json.dumps(payload, ensure_ascii=False))
    if not response.success or not response.results:
        raise SystemExit(1)


asyncio.run(main())
PY
