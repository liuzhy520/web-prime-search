# web-prime-search

## 里程碑 Milestone

### v0.3.9 (2026-04-28)
- 根目录新增 launch.py shim，Hermes/agent 可直接发现 launcher，无需指定嵌套路径
- 所有主流搜索引擎（baidu、cli、douyin、duckduckgo、google_html、google、x）测试全部通过
- SKILL.md、README、__init__.py、pyproject.toml 版本号和里程碑同步

### v0.3.8 (2026-04-27)
- 搜索引擎鲁棒性升级：
	- DuckDuckGo 增加 backend fallback（duckduckgo→lite），支持 region/safesearch 参数
	- Baidu 增加 User-Agent 随机轮换、Referer 头、429 重试（指数退避）
	- Google HTML 明确 429 检测，Playwright 浏览器回退支持自动重试
- 新增 7 个配置项，详见 config.py
- 测试用例新增 12 项，全部通过
- 版本号、SKILL.md、__init__.py、README 里程碑同步
---
### v0.3.7 (2026-04-23)
...existing code...

### v0.3.6 (2026-04-10)
- 里程碑、版本号同步：OpenClaw 技能定义、launcher、测试、文档全部切换为仓库根目录为技能根。
- 仅保留根目录 SKILL.md，移除旧 skill 文件，所有环境变量和 discover 逻辑已对齐。
- launcher、测试、README 全面更新，确保 OpenClaw 能正确发现和执行本地技能。
- 通过定向测试验证 launcher 环境变量、解释器选择、MCP 工具注册和配置发现。

### v0.3.5 (2026-04-10)
- 新增 OpenClaw skill 包装层，根目录提供 SKILL.md，repo-local launcher 位于 openclaw/web-prime-search/launch.py，免系统级安装。
- launcher 自动设置 WPS_ENV_ROOT、OPENCLAW_SKILL_DIR、OPENCLAW_SKILL_ROOT 到仓库根目录，并注入 PYTHONPATH，确保 OpenClaw 场景下配置和源码可用。
- README 增加 OpenClaw 部署与使用说明。
- 新增定向测试，验证 launcher 环境变量、解释器选择、MCP 工具注册和配置发现。


### v0.3.4 (2026-04-09)
- `.env` 配置发现顺序增强，支持 OpenClaw 技能目录、cwd、入口路径多重兜底，重启/切换上下文后依然能稳定找到正确配置
- 回归测试覆盖 OpenClaw 场景、cwd 变化、包目录 fallback、入口路径 fallback 等多种启动方式
- 文档同步说明 `.env` 解析优先级和推荐用法
- 兼容原有 `.env` 持久化配置方式，未引入新存储模型
- `douyin` 引擎新增独立超时配置 `WPS_DOUYIN_TIMEOUT_SECONDS`，默认 60 秒
- 其余引擎继续使用 `WPS_ENGINE_TIMEOUT_SECONDS`，默认 35 秒

### v0.3.2 (2026-04-08)
- `google` 引擎通过 CSE AJAX 路径（无需浏览器）优先拉取结果，失败时回退 Playwright；**不需要任何 API Key**，只需配置 `WPS_GOOGLE_CX`
- OpenClaw 无需反复询问 Google API Key，该字段已从对外接口中移除

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
- `google` 引擎基于 Google Programmable Search Element（CSE），**不需要 API Key**，只需配置 `WPS_GOOGLE_CX`。搜索时优先走轻量 AJAX 路径（无浏览器启动），仅在被拦截时回退到 Playwright；OpenClaw 无需为此询问任何 API Key。
- `douyin` 引擎现通过火山方舟 Ark Responses API 的联网搜索工具实现，不再直接抓取抖音网页。
- `douyin` 引擎默认单独使用 60 秒超时窗口；其他引擎继续使用全局默认 35 秒超时。
- `duckduckgo` 引擎通过 `ddgs` 包接入 DuckDuckGo 文本搜索，不需要单独的 API Key。
- `douyin` 结果会优先返回较短的引用摘要；如果模型本身生成了热点概述，会额外放在 `summary` 字段里，便于直接展示。

### 配置说明

- 先复制 [.env.template](.env.template) 为 `.env`，再填写真实配置；应用运行时只会自动加载 `.env`。
- 可直接执行：`cp .env.template .env`
- `.env` 仍然是推荐的持久化配置方式。运行时会按固定优先级选择一个 `.env` 文件并只加载这一份，避免在不同启动方式之间漂移到别的父目录配置。
- `.env` 解析优先级如下：`WPS_ENV_FILE` 指向的文件；`WPS_ENV_ROOT` 或 OpenClaw 技能目录提示下的 `.env`；当前工作目录向上查找的 `.env`；启动入口附近向上查找的 `.env`；安装包目录向上查找的 `.env`。
- 如果你通过 OpenClaw 部署，建议让技能启动路径稳定地落在技能目录内；如运行时支持，也可以只传递 `.env` 所在目录给 `WPS_ENV_ROOT`，配置内容本身依旧保存在 `.env` 文件中。
- `google_html` 引擎默认复用 `WPS_PROXY_URL` 和 `WPS_ENGINE_TIMEOUT_SECONDS`；第三阶段额外支持 `WPS_GOOGLE_HTML_PERSIST_PROFILE`、`WPS_GOOGLE_HTML_PROFILE_DIR`、`WPS_GOOGLE_HTML_COOKIE_FILE` 与 `WPS_GOOGLE_HTML_STEALTH`。
- 当 `WPS_GOOGLE_HTML_PERSIST_PROFILE=true` 且未显式指定 `WPS_GOOGLE_HTML_PROFILE_DIR` 时，程序会自动选择用户缓存目录下的 `web-prime-search/google-html-profile` 作为持久化 profile 目录。
- `WPS_GOOGLE_HTML_COOKIE_FILE` 为可选项，仅在你想显式导入或回写 Google cookie 时才需要配置；文件损坏或不可写时会跳过，不会阻塞搜索。
- `WPS_GOOGLE_HTML_STEALTH` 默认开启，会在 Playwright context 上追加额外 header 和浏览器指纹伪装；关闭后便于排查 live 问题。
- `WPS_GOOGLE_CX`：`google` CSE 引擎必填，用于指定 Programmable Search Engine 的 `cx`。
- `WPS_VOLCENGINE_API_KEY`：火山方舟 API Key，`douyin` 引擎必填。
- `WPS_VOLCENGINE_WEB_SEARCH_MODEL`：用于联网搜索的火山模型 ID，`douyin` 引擎必填。
- `WPS_VOLCENGINE_RESPONSES_URL`：可选，默认值为 `https://ark.cn-beijing.volces.com/api/v3/responses`。
- `WPS_ENGINE_TIMEOUT_SECONDS`：除 `douyin` 外的引擎统一超时时间，默认 35 秒。
- `WPS_DOUYIN_TIMEOUT_SECONDS`：`douyin` 引擎专用超时时间，默认 60 秒。
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

### OpenClaw 技能接入

- OpenClaw 技能定义文件位于仓库根目录 [SKILL.md](SKILL.md)。
- 仓库内 launcher 位于 [openclaw/web-prime-search/launch.py](openclaw/web-prime-search/launch.py)，启动时使用：`python3 openclaw/web-prime-search/launch.py serve`。根目录也提供了快捷入口 [launch.py](launch.py)，`python3 launch.py serve` 效果完全相同，方便从默认工作目录直接调用。
- 这个 launcher 会优先复用仓库根目录下的 `.venv`，并自动设置 `WPS_ENV_ROOT`、`OPENCLAW_SKILL_DIR`、`OPENCLAW_SKILL_ROOT` 到仓库根目录，确保应用稳定读取仓库根目录 `.env`。
- launcher 同时会把仓库 `src/` 注入 `PYTHONPATH`，因此 OpenClaw 可以直接运行当前源码，不需要把本项目重新打包到系统 Python。
- 如果仓库内 `.venv` 还不存在，可在仓库根目录执行 `python3 -m venv .venv && .venv/bin/pip install -e .`；这仍然是 repo-local 安装，不会写入系统级 site-packages。
- OpenClaw 场景下依然使用 MCP 工具名 `web_search`。

---

> **注（针对 Agent）**：以下章节介绍本仓库的 VS Code Copilot 多 agent 协作工具链，是**开发内部工具**，与 `web_search` MCP 搜索功能无关。

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
