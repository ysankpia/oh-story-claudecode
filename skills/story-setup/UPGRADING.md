# 升级指南

## 当前版本

- `setup_skill_version: 1.6.0`
- `agents_version: 23`

`.story-deployed` 缺失字段、`agents_version` 非整数或小于 `23` 时，都视为待更新部署。项目版本大于 `23` 时停止部署，先更新 oh-story-claudecode，不能用旧 skill 覆盖新部署。

## v0.11.0：Droid 正式适配

`story-setup` 新增 `droid` 目标，部署 `.factory/droids/*.md`、`.factory/hooks.json`、`.factory/hooks/` 和 Droid 专用 agent references。长拆文使用后台 Task + TaskOutput，并以 `_progress.md` 为跨会话权威断点；custom droid 不递归 spawn。

从旧版升级时，在小说项目根重新运行 `/story-setup`，选择 `droid` 或包含 Droid 的组合；setup 只合并自己管理的 Factory hooks，不删除用户已有配置。审核 `/hooks` 后新开 Droid 会话。

## v0.10.0：思想内核可执行化

所有文学流程改为强制调用 `story-tao` bundled runtime。旧 `status: confirmed` 长篇契约会迁移为 `active`，并补建 `追踪/思想进展.md`；旧正文不会被回写。升级后必须重新运行 setup 并新开会话，使 Claude/Codex/Droid agent 模板加载 `thought_contract_summary`、`thought_evidence` 和 `THOUGHT_GATE` 新契约。

## v0.8.0：Claude Code / Codex 双端收敛

从 v0.8.0 起，oh-story 只支持 Claude Code 与 Codex。14 个小说 skill、共享正文守卫和双端的 agent/hook 部署均保留。

旧版中其他 adapter 的目录和配置不会被 `/story-setup` 自动删除或改写。需要继续使用旧运行时的项目应固定在 v0.7.x；迁移到当前版本时，明确选择 Claude Code、Codex 或双端组合后重新部署。

## 文件所有权

### story-setup 管理，可替换

- `.claude/hooks/`、`.claude/agents/`、`.claude/rules/`
- `.claude/skills/story-setup/references/agent-references/`
- `.codex/agents/`、`.codex/hooks/`
- `.codex/skills/story-setup/references/agent-references/`
- `.factory/droids/`、`.factory/hooks/`
- `.factory/skills/story-setup/references/agent-references/`

### 用户与 story-setup 共同维护，只合并管理块

- `CLAUDE.md`
- `.claude/settings.local.json`
- `AGENTS.md`
- `.codex/hooks.json`
- `.factory/hooks.json`

### 用户状态，不覆盖

- `{书名}/正文/`、`正文.md`
- `{书名}/设定/`、`大纲/`、`追踪/`
- `.active-book`

## 升级步骤

1. 在项目根目录运行 `/story-setup`（Codex 使用 `$story-setup`）。
2. 选择 `claude-code`、`codex`、`droid` 或它们的组合。
3. 确认 `.story-deployed` 写入 `agents_version: 23` 和 `setup_skill_version: 1.6.0`。
4. 新开会话；Codex 需 trust 项目 `.codex/` 层，Codex 与 Droid 均需审核 `/hooks`。
5. 运行 `/story-review`。`Effective Mode: full/lean` 表示 agents 已加载；出现 fallback 时按报告提示重新部署或使用 solo。
