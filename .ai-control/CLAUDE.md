# CLAUDE.md — Project Instructions (web-prime-search)

本项目目标：
- 基于本地网络代理，自动路由和聚合 X、Google、抖音、百度等主流平台的搜索请求。
- 当前仓库为初始化状态，仅有 README，无业务代码、无构建/测试/部署命令。

## 技术栈与命令约定
- 技术栈、依赖、构建、测试、部署命令需由 Orchestrator 在首次任务分解时补充。
- Executor/Tester 不得假设任何未在本文件明确声明的命令或工具。
- 所有新任务、分支、worktree、验证命令等，需在 session.json 和 task card 中显式指定。

## 目录结构约定
- 以 `.ai-control/README.md` 为准。
- 业务代码、配置、测试等目录需在后续任务中逐步建立。

## 其他说明
- 本文件内容仅反映当前仓库实际状态，后续如有变更需由 Orchestrator 维护。
- Copilot Chat agent/skill 工作流说明见 `.github/copilot-instructions.md`、`.copilot/skills/multi-agent-orchestrator/SKILL.md`。
