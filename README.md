# web-prime-search
给龙虾开发的基于本地网络代理，使用自动路由x、google、抖音、百度的网络搜索工具

---

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
