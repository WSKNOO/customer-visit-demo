# AI中心服务器部署指南

## 1. 部署目标

推荐使用 `deploy/docker-compose.yml`，由 Nginx 对外提供一个端口：

- `/`：统一入口；
- `/intelligence/`：客户情报前端；
- `/intelligence-api/`：客户情报 API；
- `/training/`：AI陪练页面；
- `/api/`：AI陪练 API。

方案标准化助手不部署在本 Compose 中，只由统一入口读取外部 URL。

## 2. 环境要求

- Linux x86_64/arm64，推荐 Ubuntu 22.04 或兼容发行版；
- Docker Engine 24+、Docker Compose v2；
- 若不用 Docker：Python 3.11、Node.js 20、Nginx；
- 推荐至少 8GB 内存和 20GB 可用磁盘；真实网页抓取还需 Chromium 运行依赖；
- 主演示不需要 GPU、FunASR 或音频设备。

当前开发机没有 Docker，因此模板只完成了 YAML、服务、健康检查和路由静态校验；目标服务器必须实际构建。

## 3. 凭据前置条件

部署真实模式前必须完成 `CREDENTIAL_ROTATION_CHECKLIST.md`。不要复用曾写入源码、文档或部署脚本的旧 Key、SSH 密码或授权密钥。

```bash
cd /opt/customer-visit-demo/deploy
cp .env.example .env
chmod 600 .env
```

只在服务器 `.env` 或密钥管理系统填写真实值。不得把 `.env` 加入镜像、发布压缩包或 Git。

## 4. 关键环境变量

### 4.1 入口

- `GATEWAY_PORT`：统一对外端口，默认 8080。
- `PUBLIC_ORIGIN`：正式域名，例如 `https://visit.example.com`。
- `PORTAL_SOLUTION_URL`：已上线方案助手的正式外链。

### 4.2 情报助手

- `INTELLIGENCE_MOCK_MODE`
- `INTELLIGENCE_MODEL_BASE_URL/NAME/API_KEY`
- `SEARCH_SERVICE_BASE_URL/API_KEY`
- `SEARCH_MCP_TIMEOUT`
- `SEARCH_MAX_FETCH_PAGES`
- `SEARCH_MAX_CONTENT_CHARS`
- `INTELLIGENCE_RESEARCH_TIMEOUT_SECONDS`

### 4.3 AI陪练

- `TRAINING_MOCK_MODE`
- `TRAINING_MODEL_BASE_URL/NAME/API_KEY`
- `DEFAULT_TRAINING_ROUNDS`
- `MODEL_REQUEST_TIMEOUT_SECONDS`
- `MODEL_MAX_RETRIES`
- `SESSION_TTL_SECONDS`
- `ASR_ENABLED` 固定为 `false`

### 4.4 代理

- `HTTP_PROXY`、`HTTPS_PROXY`：公网搜索和抓取使用的统一代理。
- `NO_PROXY`：必须包含 Compose 服务名、localhost 和内部模型域名。

示例：

```env
NO_PROXY=127.0.0.1,localhost,ai-training,customer-intelligence-api,unified-portal,nginx,internal-model.example.com
```

不要把内部模型请求导向公网代理。

## 5. 首次部署：先 Mock

确认：

```env
INTELLIGENCE_MOCK_MODE=true
TRAINING_MOCK_MODE=true
```

执行：

```bash
cd /opt/customer-visit-demo/deploy
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

如果情报 API 镜像在 Crawl4AI/Chromium 阶段构建失败，先保持 Mock 模式定位 Python/浏览器系统依赖，不要临时删除抓取依赖并切换真实模式。

## 6. 健康检查

```bash
BASE_URL=http://127.0.0.1:8080 ./pre-demo-healthcheck.sh
```

脚本默认不访问真实模型、搜索或代理。只有人工确认后才能设置：

```bash
ALLOW_REAL_SERVICE_CHECKS=true \
MODEL_HEALTH_URL=https://internal-model.example.com/health \
SEARCH_HEALTH_URL=https://search.example.com/health \
PROXY_HEALTH_URL=https://approved-proxy-check.example.com/ \
./pre-demo-healthcheck.sh
```

健康地址必须是无计费、无业务数据的只读接口。

## 7. 受控真实模式验证

必须逐项切换，不要一次关闭两个 Mock：

1. 确认凭据已轮换，目标服务器可解析内部模型域名。
2. 在容器内检查 `NO_PROXY` 值，不打印 Key。
3. 先将 `TRAINING_MOCK_MODE=false`，用非敏感测试客户完成一轮文字对话。
4. 验证 401、429、5xx 和超时均显示可理解错误，再恢复 Mock。
5. 将 `INTELLIGENCE_MOCK_MODE=false`，使用批准的演示客户和代理测试搜索/抓取。
6. 检查至少客户官网、政府公开网站和新闻来源各一条。
7. 检查来源链接和失败降级，然后决定演示当天使用实时还是缓存结果。

禁止开启 ASR。任何真实调用前均需用户再次确认授权、模型账号、费用和客户数据边界。

## 8. 启动、停止和重启

```bash
# 启动
docker compose --env-file .env up -d

# 停止但保留报告卷
docker compose --env-file .env stop

# 重启单服务
docker compose --env-file .env restart ai-training

# 停止并移除容器，保留命名卷
docker compose --env-file .env down
```

不要使用 `down -v`，否则会删除情报报告卷。

## 9. 日志

应用日志输出到容器标准输出，不记录完整 Key 或 `visit_brief`：

```bash
docker compose logs --tail=200 nginx
docker compose logs --tail=200 customer-intelligence-api
docker compose logs --tail=200 ai-training
docker compose logs -f --since=10m
```

使用响应中的 `request_id` 关联情报任务和陪练初始化错误。报告保存在 Docker 卷 `intelligence_reports`。

## 10. HTTPS和访问控制

当前 Nginx 模板监听 8080。正式环境应由 AI 中心负载均衡/网关终止 HTTPS，或由运维补正式证书配置。公网开放前至少增加：

- 企业统一认证或反向代理认证；
- IP 白名单；
- 研究、会话初始化和聊天接口限流；
- 请求体和上游超时限制；
- 日志留存和敏感信息脱敏策略。

## 11. 回滚

部署前保存当前版本目录和镜像：

```bash
docker compose images
cp -a /opt/customer-visit-demo /opt/customer-visit-demo.backup-YYYYMMDD-HHMM
```

回滚步骤：

1. `docker compose --env-file .env down`；
2. 恢复上一发布目录及其 `.env` 权限；
3. 使用上一版本镜像或重新构建；
4. `docker compose --env-file .env up -d`；
5. 运行健康检查和缓存演示链路。

回滚不删除 `intelligence_reports` 卷。AI陪练内存会话在任何重启后都会失效，用户需从情报报告重新点击“开始AI陪练”。
