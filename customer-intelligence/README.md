# 客户拜访情报助手

## 推荐环境

- Python 3.11
- Node.js 20

## 配置

```bash
cp .env.example .env
```

真实模型 Key 仅写入本地 `.env` 或部署平台密钥管理，不提交到代码库。离线验证使用 `INTELLIGENCE_MOCK_MODE=true`，不会调用搜索或模型。

阶段三新增的陪练集成配置：

```env
TRAINING_INTEGRATION_ENABLED=true
TRAINING_SERVICE_BASE_URL=http://127.0.0.1:5000
TRAINING_PUBLIC_URL=http://127.0.0.1:5000/
TRAINING_CONNECT_TIMEOUT_MS=2000
TRAINING_READ_TIMEOUT_MS=10000
```

`TRAINING_SERVICE_BASE_URL` 只供服务端访问；浏览器只会收到由 `TRAINING_PUBLIC_URL` 生成且仅包含 `session_id` 的跳转地址。

## 启动

后端 MCP/研究运行环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Web API（默认 `127.0.0.1:3001`）：

```bash
set -a; source .env; set +a
cd frontend
npm ci
npm run server
```

前端开发服务（默认 `0.0.0.0:8006`，`/api` 代理到 3001）：

```bash
cd frontend
npm run dev
```

访问 `http://localhost:8006`。健康检查：`GET http://127.0.0.1:3001/api/health`。

情报到陪练的接口：

```text
POST /api/visit-brief/start-training
Body: {"report_filename":"已生成的报告文件名.md"}
```

研究任务现在返回 `task_id`，可通过 `GET /api/research/:task_id` 查询生成中、成功、搜索异常、模型异常或超时状态。报告列表的“发起新研究”弹窗也可加载两个明确标注的缓存演示客户。

## 离线 Mock 验证

```bash
export INTELLIGENCE_MOCK_MODE=true
printf '%s' '{"company_name":"示例客户有限公司","visit_purpose":"了解数字化需求"}' | python research_cli.py
```

Mock 会在 `tmp/reports/` 生成本地报告和空来源文件。该数据只用于启动验证，不代表真实事实。

## 测试

```bash
python -m unittest discover -s tests -v
cd frontend && npm test && npm run build
```

生产前必须关闭 Mock、配置受控 CORS、接入鉴权/限流，并完成凭据轮换。阶段三提供 `Dockerfile.api` 和前端 `Dockerfile`；完整统一部署方式见工作区根目录 `DEPLOYMENT_GUIDE.md`。真实搜索容器仍需在目标服务器验证 Crawl4AI/Chromium 运行依赖。
