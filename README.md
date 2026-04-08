# web-prime-search

## 里程碑 Milestone


### v0.3.1 (2026-04-08)
- 修复 `.env` 只在当前目录下查找导致 key 读取为空的问题，现支持从任意子目录启动自动向上查找
- `get_settings()` 现在会在 `.env` 或 `WPS_*` 环境变量变更时自动重载，避免缓存脏值

### v0.3.0 (2026-04-08)
- 移除 `.env` 和 `.env.example` 敏感信息及历史，安全合规
- 运行时仅加载 `.env`，不再回退 `.env.example`
- 新增 `.env.template`，一键复制后填写即可本地运行
- README 配置说明与模板同步，提升开箱体验
- 相关测试、文档、CI 全面更新

### v0.2.0 (2026-04-03)
- 移除 Google API Key 相关配置与文档，避免混淆
- `google_html` 搜索引擎优先级调整为最后
- 文档、测试、配置同步更新

给龙虾开发的基于本地网络代理，使用自动路由 google、duckduckgo、douyin、baidu、x、google_html 的网络搜索工具

---

## 搜索能力

支持的搜索引擎：`google`、`duckduckgo`、`douyin`、`baidu`、`x`、`google_html`。

- 默认情况下，搜索会按配置中的优先级依次聚合结果；当前默认顺序为 `google`、`duckduckgo`、`douyin`、`baidu`、`x`、`google_html`。
- 单次请求可以显式指定一个或多个搜索引擎，覆盖默认优先级。
- 如果传入的引擎名全部无效，会自动回退到默认优先级继续搜索。
- `google_html` 引擎优先尝试直接抓取 Google 搜索结果页 HTML；若静态页面被 Google 的 JS/反爬机制拦住，会继续尝试 Playwright 浏览器 fallback。
- `google_html` 的浏览器 fallback 现默认启用持久化 profile，会把浏览器状态保存在用户缓存目录下的稳定路径中；你也可以通过环境变量显式指定 profile 目录或 cookie 文件，以便复用已有状态。
- `google_html` 属于 best-effort 引擎；如果静态 HTML 和浏览器 fallback 都遇到反爬、同意页或 `enablejs` 页面，会记录失败并自动降级到其他更可靠的引擎。默认优先级中它位于最后。
- `google` 引擎现已改为基于 Google Programmable Search Element 的 CSE 浏览器方案，只需要配置 `WPS_GOOGLE_CX`。
- `douyin` 引擎现通过火山方舟 Ark Responses API 的联网搜索工具实现，不再直接抓取抖音网页。
- `duckduckgo` 引擎通过 `ddgs` 包接入 DuckDuckGo 文本搜索，不需要单独的 API Key。
- `douyin` 结果会优先返回较短的引用摘要；如果模型本身生成了热点概述，会额外放在 `summary` 字段里，便于直接展示。

### 配置说明

- 先复制 [.env.template](.env.template) 为 `.env`，再填写真实配置；应用运行时只会自动加载 `.env`。
- 可直接执行：`cp .env.template .env`
- `google_html` 引擎默认复用 `WPS_PROXY_URL` 和 `WPS_ENGINE_TIMEOUT_SECONDS`；第三阶段额外支持 `WPS_GOOGLE_HTML_PERSIST_PROFILE`、`WPS_GOOGLE_HTML_PROFILE_DIR`、`WPS_GOOGLE_HTML_COOKIE_FILE` 与 `WPS_GOOGLE_HTML_STEALTH`。
- 当 `WPS_GOOGLE_HTML_PERSIST_PROFILE=true` 且未显式指定 `WPS_GOOGLE_HTML_PROFILE_DIR` 时，程序会自动选择用户缓存目录下的 `web-prime-search/google-html-profile` 作为持久化 profile 目录。
- `WPS_GOOGLE_HTML_COOKIE_FILE` 为可选项，仅在你想显式导入或回写 Google cookie 时才需要配置；文件损坏或不可写时会跳过，不会阻塞搜索。
- `WPS_GOOGLE_HTML_STEALTH` 默认开启，会在 Playwright context 上追加额外 header 和浏览器指纹伪装；关闭后便于排查 live 问题。
- `WPS_GOOGLE_CX`：`google` CSE 引擎必填，用于指定 Programmable Search Engine 的 `cx`。
- `WPS_VOLCENGINE_API_KEY`：火山方舟 API Key，`douyin` 引擎必填。
- `WPS_VOLCENGINE_WEB_SEARCH_MODEL`：用于联网搜索的火山模型 ID，`douyin` 引擎必填。
- `WPS_VOLCENGINE_RESPONSES_URL`：可选，默认值为 `https://ark.cn-beijing.volces.com/api/v3/responses`。
- `duckduckgo` 引擎默认复用 `WPS_PROXY_URL` 和 `WPS_ENGINE_TIMEOUT_SECONDS`，无需额外环境变量。
- `WPS_DOUYIN_COOKIE`：已废弃，新的 `douyin` 实现不会再使用该配置。

### MCP 工具调用

MCP 工具名为 `web_search`，支持传入 `engines` 参数：

```python
await web_search(query="opc", engines=["x", "baidu"], max_results=5)

await web_search(query="最近一周的热点新闻", engines=["google_html"], max_results=5)

await web_search(query="今天有什么热点新闻？", engines=["duckduckgo"], max_results=5)
```

### 命令行调用

默认命令仍然启动 MCP server：

```bash
web-prime-search
web-prime-search serve
python -m web_prime_search
```

直接执行一次搜索时，使用 `search` 子命令：

```bash
web-prime-search search --query "opc" --engines x,baidu --max-results 5
web-prime-search search --query "geo china" --engine google --max-results 5
web-prime-search search --query "最近一周的热点新闻" --engines google_html --max-results 5
web-prime-search search --query "今天有什么热点新闻？" --engines duckduckgo --max-results 5

WPS_GOOGLE_HTML_PROFILE_DIR=~/Library/Caches/web-prime-search/google-html-profile \
WPS_GOOGLE_HTML_COOKIE_FILE=~/Library/Caches/web-prime-search/google-cookies.json \
web-prime-search search --query "本月热点新闻" --engines google_html --max-results 5
```

也可以直接调试单个引擎模块：

```bash
python -m web_prime_search.engines.google "coding plan"
python -m web_prime_search.engines.duckduckgo "coding plan"
python -m web_prime_search.engines.baidu "coding plan"
python -m web_prime_search.engines.douyin "coding plan"
python -m web_prime_search.engines.x "coding plan"
```

命令行结果会以 JSON 输出，便于脚本消费。

## Copilot 多 Agent 工作流说明

本仓库已集成 VS Code Copilot Chat 多 agent 协作协议，支持如下 agent/skill：

- **@Orchestrator**：主控 agent，负责任务分解、分派、会话持久化
- **@Planner**：只做任务规划和依赖分析
- **@Executor**：只实现单一任务，受限于 task card 的 allowed_paths
- **@Tester**：只做测试和 evidence 报告，不修复业务代码
- **multi-agent-orchestrator skill**：支持多 agent 并行、任务隔离、bug 重派等高级工作流

### 如何使用
1. 在 VS Code Copilot Chat 中选择对应 agent 模式（如 @Orchestrator）
2. 按照提示描述你的需求，Orchestrator 会自动分解并分派任务
3. 所有工作流状态、任务卡、bug 卡、handoff 记录均持久化于 `.ai-control/` 目录
4. 技术栈、构建/测试命令等需在首次任务分解时由 Orchestrator 明确

详细协议见 `.github/copilot-instructions.md`、`.copilot/skills/multi-agent-orchestrator/SKILL.md`、`.ai-control/README.md`。
