# 长篇思想契约

`设定/思想命题.md` 是长篇思想层唯一权威。状态只允许 `active | provisional`；旧 `confirmed` 迁移为 `active`。缺失或损坏时自动创建/修复，失败返回 `thought_contract_blocked`，不得忽略后继续写作。

```markdown
---
schema_version: 1
operator_manifest_version: 60
status: active
mode: long
primary_operator: tao-01-name-and-reality
secondary_operator: null
source_chapters: [1, 32]
evidence_basis: premise-and-reader-contract
---
# 思想命题

## 自动选择摘要
- 主命题卡：{名称 / ID / 章节}
- 辅命题卡：{名称 / ID / 章节；无则写无}
- 选择依据：{题材、读者契约、目标、冲突或正文证据}
- 待补证据：{active 写无；provisional 写具体缺口}

## 核心命题
{可被剧情反驳的陈述}

## 反命题
{有真实利益支撑的相反答案}

## 成立与失效条件
- 成立条件：{}
- 失效条件：{}

## 人物立场
- 主角：{初始立场 / 维护利益 / 底线 / 自我欺骗 / 改变条件}
- 核心反方：{同上}
- 关键配角：{同上}

## 长篇命题检验
- 开篇：{选择 / 代价 / 后果}
- 发展：{选择 / 代价 / 后果}
- 高潮：{选择 / 代价 / 后果}

## 结局回答
- 暂时回答：{}
- 保留疑问：{}

## 读者契约兼容
- 必须保留的代理权、核心收益和高光：{}
- 潜在冲突：{无 / thought_alignment_conflict: ...}

## 表达设计
- 贯穿意象或行为：{}
- 行动表达：{}
- 禁止说教、错误引文和古风腔污染：{}

## 迁移与诊断
{新书写自动创建；旧项目记录 confirmed -> active、证据和未回写正文范围}
```

全书大纲承载“结局回答”，卷纲承载阶段检验，细纲必须标记 `pressure | counterevidence | choice | consequence | recovery` 之一。思想层不得新增细纲外事件。
