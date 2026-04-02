# web-prime-search
给龙虾开发的基于本地网络代理，使用自动路由 google、douyin、duckduckgo、baidu、x 的网络搜索工具

---

## 搜索能力

支持的搜索引擎：`google`、`douyin`、`duckduckgo`、`baidu`、`x`。

- 默认情况下，搜索会按配置中的优先级依次聚合结果；当前默认顺序为 `duckduckgo`、`douyin`、`baidu`、`google`、`x`。
- 单次请求可以显式指定一个或多个搜索引擎，覆盖默认优先级。
- 如果传入的引擎名全部无效，会自动回退到默认优先级继续搜索。
- `douyin` 引擎现通过火山方舟 Ark Responses API 的联网搜索工具实现，不再直接抓取抖音网页。
- `duckduckgo` 引擎通过 `ddgs` 包接入 DuckDuckGo 文本搜索，不需要单独的 API Key。
- `douyin` 结果会优先返回较短的引用摘要；如果模型本身生成了热点概述，会额外放在 `summary` 字段里，便于直接展示。

### 配置说明

- 应用会优先自动加载仓库根目录下的 `.env`；如果 `.env` 不存在，会回退读取 `.env.example`。
- `WPS_VOLCENGINE_API_KEY`：火山方舟 API Key，`douyin` 引擎必填。
- `WPS_VOLCENGINE_WEB_SEARCH_MODEL`：用于联网搜索的火山模型 ID，`douyin` 引擎必填。
- `WPS_VOLCENGINE_RESPONSES_URL`：可选，默认值为 `https://ark.cn-beijing.volces.com/api/v3/responses`。
- `duckduckgo` 引擎默认复用 `WPS_PROXY_URL` 和 `WPS_ENGINE_TIMEOUT_SECONDS`，无需额外环境变量。
- `WPS_DOUYIN_COOKIE`：已废弃，新的 `douyin` 实现不会再使用该配置。

### MCP 工具调用

MCP 工具名为 `web_search`，支持传入 `engines` 参数：

```python
await web_search(query="opc", engines=["x", "baidu"], max_results=5)

await web_search(query="今天有什么热点新闻？", engines=["duckduckgo"], max_results=5)
```

### 命令行调用

默认命令仍然启动 MCP server：

```bash
web-prime-search
web-prime-search serve
```

直接执行一次搜索时，使用 `search` 子命令：

```bash
web-prime-search search --query "opc" --engines x,baidu --max-results 5
web-prime-search search --query "今天有什么热点新闻？" --engines duckduckgo --max-results 5
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
