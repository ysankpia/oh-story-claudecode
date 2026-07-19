---
name: story-setup
version: 1.5.0
description: "网文写作工具集基础设施部署。仅支持 Claude Code 与 Codex，可单端或双端部署。触发方式：/story-setup、$story-setup、「准备写书」「帮我搭一下环境」「配置写作项目」。"
---
# story-setup：Claude/Codex 写作基础设施部署

你是写作基础设施部署器。只向用户项目部署 Claude Code、Codex 或二者组合所需的 hooks、agents、规则和参考资料。

**执行铁律：不覆盖用户已有配置，合并而非替换；不删除用户项目中的未知目录或旧工具配置。**

## 支持边界

- 合法 `target_cli` 只有 `claude-code`、`codex` 或 `claude-code,codex`。
- 14 个 story skill 保持完整；本 skill 不复制一套通用 skills 文件作为其他运行时的替代安装方式。
- 检测到旧版部署遗留的非双端 adapter 标记时，报告“该 adapter 已停止支持”，要求用户明确选择 Claude Code、Codex 或二者；不得修改或删除这些遗留文件。
- 自定义 agent 未部署、当前会话不能 spawn 或 Codex 返回 `unknown agent_type` 时，相关写作/审稿流程仍必须走 `solo/direct` fallback。

## Phase 1：检测与选择

1. 检查 `.story-deployed`：
   - `agents_version` 缺失、非整数或小于 `22`：标记为待更新。
   - `agents_version: 22`：确认是否重新部署。
   - `agents_version` 大于 `22`：停止，提示先更新本 skill，避免旧版本覆盖新部署。
2. 检查书名目录（含 `追踪/` 或用户明确指定的项目目录）和 `.active-book`，只用于展示当前写作状态。
3. 检查 `.claude/`、`CLAUDE.md`、`.codex/`、`.codex/hooks.json` 和根 `AGENTS.md` 的双端段落：
   - 只识别 Claude 标记：默认候选 `claude-code`。
   - 只识别 Codex 标记：默认候选 `codex`。
   - 两类都存在：默认候选 `claude-code,codex`。
   - 都不存在：用 AskUserQuestion 让用户选择 Claude Code、Codex 或两者。
4. 如发现旧 adapter 标记，先说明它们不会被自动清理；仍以用户本轮选择的双端目标继续，不把旧标记写入新的 `.story-deployed`。

## Phase 2：部署清单

仅在用户确认目标目录后执行。所有 `replace` 仅作用于 story-setup 管理的目标文件；用户自己的其他文件必须保留。

| Source path | Target path | Owner class | Merge mode | Validation check | 适用目标 |
|-------------|-------------|-------------|------------|------------------|----------|
| `references/templates/CLAUDE.md.tmpl` | `CLAUDE.md` | marker/section merge | claude-code |
| `references/templates/hooks/` | `.claude/hooks/` | replace managed directory | claude-code |
| `references/templates/rules/*.md` | `.claude/rules/*.md` | replace known files | claude-code |
| `references/templates/agents/*.md` | `.claude/agents/*.md` | replace managed directory | claude-code |
| `references/agent-references/` | `.claude/skills/story-setup/references/agent-references/` | replace managed directory | claude-code |
| `references/templates/settings-hooks.json` | `.claude/settings.local.json` | merge managed hook commands | claude-code |
| `references/templates/上下文.md.tmpl` | `{书名}/追踪/上下文.md` | create if absent | claude-code or codex |
| `references/codex/AGENTS.md.tmpl` | `AGENTS.md` | marker/section merge | codex |
| `references/codex/agents/` | `.codex/agents/` | replace managed directory | codex |
| `references/codex/hooks/hooks.json` | `.codex/hooks.json` | replace managed registrations | codex |
| `references/codex/hooks/` | `.codex/hooks/` | replace managed directory | codex |
| `scripts/merge-codex-hooks.py` | executed only | merge managed registrations | codex |
| `references/agent-references/` | `.codex/skills/story-setup/references/agent-references/` | replace managed directory | codex |
| generated sentinel | `.story-deployed` | replace managed file | all targets |

## Claude Code 部署

1. 读取并按 marker 合并 `references/templates/CLAUDE.md.tmpl` 到根 `CLAUDE.md`。
2. 递归复制完整目录树 `references/templates/hooks/` 到 `.claude/hooks/`，保留 `lib/common.sh`、`lib/sentinel.sh`、`story_hook_core.js` 和 `story_hook_cli.js`；对顶层 shell hooks 设置执行权限。
3. 复制规则、7 个 agent 和 agent references。agent 引用必须使用项目内 `.claude/skills/story-setup/references/agent-references/` 路径。
4. 将 `settings-hooks.json` 的 managed hook registrations 合并进 `.claude/settings.local.json`，保留用户 hooks 与未知字段。
5. 报告用户需要新开 Claude Code 会话，才能加载更新后的 agents。

## Codex 部署

1. 合并 `references/codex/AGENTS.md.tmpl` 到根 `AGENTS.md`。
2. 复制 `references/codex/agents/*.toml` 到 `.codex/agents/`；每个 TOML 必须含 `name`、`description` 和 `developer_instructions`。只读职责 agent 必须保留 `sandbox_mode = "read-only"`。
3. 复制 Codex hooks，并通过 `scripts/merge-codex-hooks.py` 合并 `.codex/hooks.json`：替换本 skill 管理的 registrations，保留用户 hooks 和未知顶层字段。
4. 复制 agent references 到 `.codex/skills/story-setup/references/agent-references/`。
5. 报告用户需要 trust 项目 `.codex/` 层、在 `/hooks` 审核 hooks，并新开 Codex 会话。运行时没有 custom-agent registry 时必须使用 `solo/direct`。

## 共享 hook 契约

- Claude 的 Node core `references/templates/hooks/story_hook_core.js` 是正文网、字数、路径抽取、提交识别和连续性检查的唯一 JavaScript 权威实现。
- Codex 的 `references/codex/hooks/story_codex_hook.py` 保持同一对外行为；由回归测试验证正文网、连续性、提交提示和大纲守卫的结果一致。
- 不保留为其他 adapter 服务的副本、runner 或 parity 分支。

### 创建部署标记

部署完成后写入以下字段：

```yaml
deployed_at: 2026-07-19T00:00:00Z
agents_version: 22
setup_skill_version: 1.5.0
target_cli: claude-code | codex | claude-code,codex
resolver_strategy: project-local
references_dir: .claude/skills/story-setup/references/agent-references | .codex/skills/story-setup/references/agent-references
```

`target_cli` 为双端组合时，`references_dir` 用逗号分隔两个项目内路径。旧 sentinel 中的非双端值只用于给出迁移提示，不能作为新部署目标。

## 验证安装

### Claude Code

- `.claude/hooks/` 包含完整 hook 树，`node --check` 能解析 `story_hook_core.js` 与 `story_hook_cli.js`。
- `.claude/agents/` 有 7 个 agent，`.claude/rules/` 每个文件有 `paths` frontmatter。
- `.claude/settings.local.json` 有效，managed hook commands 不重复。
- `.claude/skills/story-setup/references/agent-references/` 的每个被引用文件都存在。

### Codex

- `.agents/skills` 保持指向 `../skills` 的相对 symlink，仓库发现 14 个 skill。
- `.codex/agents/` 的 7 个 TOML 均可解析；`.codex/hooks.json` 有当前 6 个 managed registrations，用户 hooks 未被移除。
- `.codex/hooks/` 同时包含 Python、shell 和 Windows launcher；Python/Node 源文件均可解析。
- `.codex/skills/story-setup/references/agent-references/` 的每个被引用文件都存在。

### 双端组合

- 两套目录同时存在时，`CLAUDE.md` 与 `AGENTS.md` 各自只保留所属端的 managed section。
- `.story-deployed` 的 `target_cli` 为 `claude-code,codex`，两个 reference 路径均可读。

## 输出安装报告

报告必须说明：实际 `target_cli`、写入或合并的路径、保留的用户配置、需要重新打开的会话，以及任何不支持的旧 adapter 标记。不得声称已删除用户项目中的旧配置。

## 资源索引

| 目录 | 用途 |
|------|------|
| `references/templates/` | Claude Code 的 hooks、rules、agents、CLAUDE 模板与上下文模板 |
| `references/codex/` | Codex 的 AGENTS、agent TOML 和 hook 配置 |
| `references/agent-references/` | 两端 agent 读取的项目内参考资料 |
| `scripts/` | Codex hooks 合并与 agent 生成工具 |

调用语法：Claude Code 使用 `/story-*`；Codex 使用 `$story-*` 或 `/skills`。
