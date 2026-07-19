---
name: story-tao
description: "Oh Story 的强制《道德经》思想内核。自动匹配叙事命题、生成或修复长短篇思想契约、拆文命题张力和长篇思想进展；/story-tao、$story-tao、/道德经创作可用于重新校准，但启用不依赖命令。"
---
# story-tao：强制思想内核

本 skill 是所有文学流程共用的深模块。《道德经》提供可被剧情反驳的冲突方法，不是固定道德答案、文风模板或古风装饰。扫榜、拆文、导入、写作、审稿、去 AI 味和封面由各自流程自动调用本接口；公开命令只用于作者主动更换命题。

## 不变量

- 每个文学项目恰好一个主命题，最多一个辅命题；作者可以覆盖选择，但不能关闭思想内核。
- 优先级：作者明确要求、读者契约和锁定大纲 > 思想契约 > 题材取舍与文风。冲突时保留原纲并报告 `thought_alignment_conflict`。
- 正文只用行动、关系、选择、代价和后果表达，不讲解原典、不自动引用、不模仿古文。
- 反命题必须聪明且有现实利益；人物不得成为证明老子正确的工具。
- 其他 skill 只消费本模块生成的短摘要，不自行解释六十张卡，不加载八十一章全文。

## 参考加载

- 自动匹配先读 [references/operator-index.md](references/operator-index.md)；需要核对章节归属时再读 [references/coverage-matrix.md](references/coverage-matrix.md)，只读取入选卡片。
- 维护自动匹配或检查评分漂移时读 [references/matching-fixtures.md](references/matching-fixtures.md)；正常创作不加载校准样例。
- 原文核对或引文争议才读 [references/daodejing.md](references/daodejing.md) 的对应章。
- 创建或修复四类产物时按需读取 [references/thought-contract.md](references/thought-contract.md)、[references/short-thought-contract.md](references/short-thought-contract.md)、[references/deconstruction-thought-contract.md](references/deconstruction-thought-contract.md) 和 [references/thought-progress-contract.md](references/thought-progress-contract.md)。

## 唯一接口

所有流程必须通过 bundled runtime 执行，不以本文件的自然语言说明代替实际调用。运行时位于 `scripts/story_tao_runtime.py`，独立安装使用 [references/runtime-contract.json](references/runtime-contract.json)，仓库开发使用根 `scripts/current-contract.json`。调用统一采用 JSON stdin/stdout：

```bash
for PYBIN in python3 python py; do "$PYBIN" -c "" 2>/dev/null && break; done
"$PYBIN" scripts/story_tao_runtime.py match
"$PYBIN" scripts/story_tao_runtime.py ensure --project-root "{项目目录}" --mode long
"$PYBIN" scripts/story_tao_runtime.py summarize --project-root "{项目目录}" --mode long
"$PYBIN" scripts/story_tao_runtime.py map-evidence
"$PYBIN" scripts/story_tao_runtime.py advance --project-root "{项目目录}"
```

实际执行时从当前已加载的 `story-tao` skill 根目录解析脚本；Windows 同样按上述顺序探测可用解释器。业务错误输出结构化错误码并以状态码 2 退出。

### `match`

输入题材、平台、读者契约、主角目标、核心冲突和可用文本证据。先按索引中的 `domain` 轻量过滤，再按人物必须作出的选择自动选一个主命题；所有卡片都可参与评分，`risk_level` 只降低误配和说教风险，不屏蔽治理、战争或社会主题。只有能补充而不建立第二条哲学主线时才选辅命题。只读入选卡片；核对引文时才读原典对应章。

材料足以支持人物立场和反命题时返回 `active`；材料不足仍返回 `provisional`，列出待补证据。不得输出三个候选后等待确认。

### `ensure`

按调用场景创建或校验权威产物：

| 场景 | 权威产物 | 模板 |
|---|---|---|
| 长篇 | `设定/思想命题.md` | `references/thought-contract.md` |
| 短篇 | `思想命题.md` | `references/short-thought-contract.md` |
| 长短篇拆文 | `拆文库/{书名}/思想/命题张力.md` | `references/deconstruction-thought-contract.md` |
| 长篇运行状态 | `追踪/思想进展.md` | `references/thought-progress-contract.md` |

文件缺失就自动创建。`status: confirmed` 自动迁移为 `status: active`；缺段落或合法来源时，根据项目证据和命题卡当轮修复。修复失败返回 `thought_contract_blocked` 并阻断后续文学创作，不得静默跳过。旧正文不回写。

### `summarize`

只向调用者返回场景所需的短摘要：命题/反命题、相关人物立场、当前思想功能或检验、选择/代价/后果、表达禁区和冲突标记。不得传入原典全文、卡片释义或无关历史状态。

### `map-evidence`

拆文先从作品证据归纳实际命题、反命题、人物立场、关键选择、代价、后果和反证，再映射最接近的三张命题卡。每项必须带章节或小节证据，并固定声明：这是分析映射，不证明原作者受老子影响。

### `advance`

长篇每章完成后更新 `追踪/思想进展.md`：记录本章思想功能、人物最新立场、新反证、已付代价和下一检验。只能记录正文已发生事实，不得借更新追踪新增剧情。

## 自动匹配原则

1. 匹配人物选择，不匹配题材表面关键词。
2. 主角、反方和关键配角至少形成两个可辩护立场。
3. 只有行动过度导致反噬时才选“反者道之动”；只有撤除妄为或重设条件时才选“无为”。
4. 自动选择必须写明成立条件、失效条件和说教风险。
5. 作者要求重校准时覆盖契约选择并保留迁移说明；不需要再次确认“是否启用”。

## 输出

报告调用场景、产物路径、状态、主/辅命题、证据强弱、修复或迁移动作，以及任何 `thought_alignment_conflict` / `thought_contract_blocked`。不在对话中粘贴完整原典。
