#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
ALLOW_REAL_SERVICE_CHECKS="${ALLOW_REAL_SERVICE_CHECKS:-false}"

check() {
  name="$1"
  url="$2"
  if curl --fail --silent --show-error --max-time 8 "$url" >/dev/null; then
    printf '%s: OK\n' "$name"
  else
    printf '%s: FAILED\n' "$name"
    return 1
  fi
}

check "统一入口" "$BASE_URL/"
check "网关" "$BASE_URL/gateway-health"
check "情报前端" "$BASE_URL/intelligence/"
check "情报后端" "$BASE_URL/intelligence-api/health"
check "陪练前端" "$BASE_URL/training/"
check "陪练后端" "$BASE_URL/api/health"

if [ -n "${PORTAL_SOLUTION_URL:-}" ]; then check "方案助手" "$PORTAL_SOLUTION_URL"; else printf '%s\n' "方案助手: SKIPPED (未配置)"; fi

if [ "$ALLOW_REAL_SERVICE_CHECKS" = "true" ]; then
  [ -n "${MODEL_HEALTH_URL:-}" ] && check "内部大模型" "$MODEL_HEALTH_URL" || printf '%s\n' "内部大模型: SKIPPED (无健康地址)"
  [ -n "${SEARCH_HEALTH_URL:-}" ] && check "搜索服务" "$SEARCH_HEALTH_URL" || printf '%s\n' "搜索服务: SKIPPED (无健康地址)"
  [ -n "${PROXY_HEALTH_URL:-}" ] && check "公网代理" "$PROXY_HEALTH_URL" || printf '%s\n' "公网代理: SKIPPED (无健康地址)"
else
  printf '%s\n' "真实模型/搜索/代理: SKIPPED (尚未获得受控验证确认)"
fi
