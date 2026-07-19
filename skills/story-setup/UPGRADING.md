# 升级指南

## 当前版本

- `setup_skill_version: 1.5.0`
- `agents_version: 22`

`.story-deployed` 缺失字段、`agents_version` 非整数或小于 `22` 时，都视为待更新部署。项目版本大于 `22` 时停止部署，先更新 oh-story-claudecode，不能用旧 skill 覆盖新部署。

## v0.10.0：思想内核可执行化

所有文学流程改为强制调用 `story-tao` bundled runtime。旧 `status: confirmed` 长篇契约会迁移为 `active`，并补建 `追踪/思想进展.md`；旧正文不会被回写。升级后必须重新运行 setup 并新开会话，使 Claude/Codex agent 模板加载 `thought_contract_summary`、`thought_evidence` 和 `THOUGHT_GATE` 新契约。

## v0.8.0：Claude Code / Codex 双端收敛

从 v0.8.0 起，oh-story 只支持 Claude Code 与 Codex。14 个小说 skill、共享正文守卫和双端的 agent/hook 部署均保留。

旧版中其他 adapter 的目录和配置不会被 `/story-setup` 自动删除或改写。需要继续使用旧运行时的项目应固定在 v0.7.x；迁移到当前版本时，明确选择 Claude Code、Codex 或双端组合后重新部署。

## 文件所有权

### story-setup 管理，可替换

- `.claude/hooks/`、`.claude/agents/`、`.claude/rules/`
- `.claude/skills/story-setup/references/agent-references/`
- `.codex/agents/`、`.codex/hooks/`
- `.codex/skills/story-setup/references/agent-references/`

### 用户与 story-setup 共同维护，只合并管理块

- `CLAUDE.md`
- `.claude/settings.local.json`
- `AGENTS.md`
- `.codex/hooks.json`

### 用户状态，不覆盖

- `{书名}/正文/`、`正文.md`
- `{书名}/设定/`、`大纲/`、`追踪/`
- `.active-book`

## 升级步骤

1. 在项目根目录运行 `/story-setup`（Codex 使用 `$story-setup`）。
2. 选择 `claude-code`、`codex` 或 `claude-code,codex`。
3. 确认 `.story-deployed` 写入 `agents_version: 22` 和 `setup_skill_version: 1.5.0`。
4. 新开会话；Codex 还需 trust 项目 `.codex/` 层并审核 `/hooks`。
5. 运行 `/story-review`。`Effective Mode: full/lean` 表示 agents 已加载；出现 fallback 时按报告提示重新部署或使用 solo。
