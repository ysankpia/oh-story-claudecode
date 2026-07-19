#!/usr/bin/env python3
"""Regression tests for the focused story-tao contract validator."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import story_tao_contract as validator


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def codes(findings: list[validator.Finding]) -> set[str]:
    return {finding.code for finding in findings}


def main() -> int:
    contract = validator.load_contract(SCRIPT_DIR / "current-contract.json")
    require(contract.chapter_count == 81, "contract must declare 81 chapters")
    require(contract.operator_count == 60, "contract must declare 60 operators")
    require(contract.required_chapter_count == 81, "all chapters must require primary coverage")
    require(len(contract.original_operator_ids) == 15, "the original 15 ids must remain stable")
    require(
        not validator.validate_repository(REPO_ROOT, contract),
        "shipped story-tao resources and integrations must pass",
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "skills/story-tao"
        shutil.copytree(REPO_ROOT / "skills/story-tao", target)

        corpus = target / "references/daodejing.md"
        original_corpus = corpus.read_text(encoding="utf-8")
        corpus.write_text(original_corpus.replace("## 第81章", "## 第82章"), encoding="utf-8")
        require(
            "tao-corpus-chapters" in codes(validator.resource_findings(root, contract)),
            "non-contiguous chapters must fail",
        )
        corpus.write_text(original_corpus, encoding="utf-8")

        corpus.write_text(
            original_corpus.replace("反者道之动；弱者道之用。天下万物生于有，有生于无。", ""),
            encoding="utf-8",
        )
        require(
            "tao-corpus-empty-chapter" in codes(validator.resource_findings(root, contract)),
            "empty chapter bodies must fail",
        )
        corpus.write_text(original_corpus, encoding="utf-8")

        first = target / "references/operators/01-name-and-reality.md"
        second = target / "references/operators/02-mutual-arising.md"
        original_first = first.read_text(encoding="utf-8")
        original_second = second.read_text(encoding="utf-8")

        second.write_text(
            original_second.replace("id: tao-02-mutual-arising", "id: tao-01-name-and-reality"),
            encoding="utf-8",
        )
        require(
            "tao-operator-id" in codes(validator.resource_findings(root, contract)),
            "duplicate operator ids must fail",
        )

        second.write_text(original_second.replace("chapters: [2]", "chapters: [82]"), encoding="utf-8")
        require(
            "tao-operator-chapters" in codes(validator.resource_findings(root, contract)),
            "out-of-range chapter references must fail",
        )
        second.write_text(original_second, encoding="utf-8")

        second.write_text(
            original_second.replace("domain: identity-relationship\n", ""),
            encoding="utf-8",
        )
        require(
            "tao-operator-frontmatter" in codes(validator.resource_findings(root, contract)),
            "missing operator frontmatter must fail",
        )
        second.write_text(original_second, encoding="utf-8")

        second.write_text(
            original_second.replace("id: tao-02-mutual-arising", "id: tao-02-renamed"),
            encoding="utf-8",
        )
        require(
            "tao-operator-filename" in codes(validator.resource_findings(root, contract)),
            "operator ids must match their stable filenames",
        )
        require(
            "tao-original-operator-id" in codes(validator.resource_findings(root, contract)),
            "renaming an original operator id must fail",
        )
        second.write_text(original_second, encoding="utf-8")

        first.write_text(original_first.replace("## 反命题", "## 缺失反命题"), encoding="utf-8")
        require(
            "tao-operator-section" in codes(validator.resource_findings(root, contract)),
            "missing operator sections must fail",
        )
        first.write_text(original_first, encoding="utf-8")

        first.write_text(
            original_first.replace(
                "## 历史语境\n涉及名与道的认识、秩序和治理语境，不等于现代身份政治的单一结论。",
                "## 历史语境\n",
            ),
            encoding="utf-8",
        )
        require(
            "tao-operator-section-empty" in codes(validator.resource_findings(root, contract)),
            "empty operator sections must fail",
        )
        first.write_text(original_first, encoding="utf-8")

        matrix = target / "references/coverage-matrix.md"
        original_matrix = matrix.read_text(encoding="utf-8")
        matrix.write_text(
            original_matrix.replace("| 81 | tao-60-plain-truth", "| 82 | tao-60-plain-truth"),
            encoding="utf-8",
        )
        require(
            "tao-coverage-chapters" in codes(validator.resource_findings(root, contract)),
            "coverage matrix must contain exactly chapters 1..81",
        )
        matrix.write_text(original_matrix, encoding="utf-8")

        operator_index = target / "references/operator-index.md"
        original_operator_index = operator_index.read_text(encoding="utf-8")
        operator_index.write_text(
            original_operator_index.replace(
                "| tao-16-esteem-and-control | 尚贤与欲望治理 | 3 | governance-desire | high |",
                "| tao-16-esteem-and-control | 尚贤与欲望治理 | 3 | wrong-domain | low |",
            ),
            encoding="utf-8",
        )
        require(
            "tao-operator-index-metadata" in codes(validator.resource_findings(root, contract)),
            "operator index metadata must match card frontmatter",
        )
        operator_index.write_text(original_operator_index, encoding="utf-8")

        matrix.write_text(
            original_matrix.replace("| 75 | tao-56-extraction-and-hunger", "| 75 | tao-missing-card"),
            encoding="utf-8",
        )
        require(
            "tao-coverage-operator" in codes(validator.resource_findings(root, contract)),
            "coverage matrix must reject missing cards",
        )
        matrix.write_text(original_matrix, encoding="utf-8")

        card_56 = target / "references/operators/56-extraction-and-hunger.md"
        card_56.unlink()
        require(
            "tao-operator-count" in codes(validator.resource_findings(root, contract)),
            "deleting a new card must fail the declared count",
        )
        require(
            "tao-coverage-operator" in codes(validator.resource_findings(root, contract)),
            "deleting a new card must expose its coverage gap",
        )

        matching_fixtures = target / "references/matching-fixtures.md"
        original_matching_fixtures = matching_fixtures.read_text(encoding="utf-8")
        matching_fixtures.write_text(
            original_matching_fixtures.replace(
                "tao-46-small-fish-governance",
                "tao-99-missing-governance",
            ),
            encoding="utf-8",
        )
        require(
            "tao-matching-fixture-operator" in codes(validator.resource_findings(root, contract)),
            "matching fixtures must reject unknown operators",
        )

        thought_contract = target / "references/thought-contract.md"
        original_thought_contract = thought_contract.read_text(encoding="utf-8")
        thought_contract.write_text(
            original_thought_contract.replace("## 长篇命题检验", "## 缺失长篇命题检验"),
            encoding="utf-8",
        )
        require(
            "tao-artifact-section" in codes(validator.artifact_findings(root)),
            "missing thought-contract sections must fail",
        )

        thought_contract.write_text(
            original_thought_contract.replace("status: active", "status: disabled"),
            encoding="utf-8",
        )
        require(
            "tao-artifact-status" in codes(validator.artifact_findings(root)),
            "disabled thought-contract templates must fail",
        )

        short_contract = target / "references/short-thought-contract.md"
        short_contract.unlink()
        require(
            "tao-short-artifact-missing" in codes(validator.artifact_findings(root)),
            "missing short-form contract must fail",
        )

        deconstruction = target / "references/deconstruction-thought-contract.md"
        deconstruction.write_text(
            deconstruction.read_text(encoding="utf-8").replace("章节证据", "无证据"),
            encoding="utf-8",
        )
        require(
            "tao-deconstruction-section" in codes(validator.artifact_findings(root)),
            "deconstruction mapping without chapter evidence must fail",
        )

        progress = target / "references/thought-progress-contract.md"
        progress.write_text(
            progress.read_text(encoding="utf-8").replace("## 下一检验", "## 缺失下一检验"),
            encoding="utf-8",
        )
        require(
            "tao-progress-section" in codes(validator.artifact_findings(root)),
            "runtime state without the next test must fail",
        )

        project = root / "project"
        (project / "设定").mkdir(parents=True)
        (project / "追踪").mkdir(parents=True)
        project_contract = project / "设定/思想命题.md"
        project_contract.write_text(
            """---
schema_version: 1
operator_manifest_version: 60
status: active
mode: long
primary_operator: tao-10-self-knowledge
secondary_operator: null
source_chapters: [33]
evidence_basis: test
---
# 思想命题

## 自动选择摘要
测试摘要
## 核心命题
测试命题
## 反命题
测试反命题
## 成立与失效条件
测试条件
## 人物立场
测试立场
## 长篇命题检验
- 开篇：测试检验
- 发展：测试检验
- 高潮：测试检验
""",
            encoding="utf-8",
        )
        (project / "追踪/思想进展.md").write_text("# 思想进展\n", encoding="utf-8")
        require(
            not validator.project_artifact_findings(REPO_ROOT, project, contract, "long"),
            "valid project thought artifacts must pass",
        )
        project_contract.write_text(
            project_contract.read_text(encoding="utf-8").replace("primary_operator: tao-10-self-knowledge", "primary_operator: tao-99-missing"),
            encoding="utf-8",
        )
        require(
            "tao-project-primary-operator" in codes(validator.project_artifact_findings(REPO_ROOT, project, contract, "long")),
            "real project artifacts must reject unknown operators",
        )
        project_contract.write_text(
            project_contract.read_text(encoding="utf-8").replace("primary_operator: tao-99-missing", "primary_operator: tao-10-self-knowledge").replace("source_chapters: [33]", "source_chapters: [82]"),
            encoding="utf-8",
        )
        require(
            "tao-project-source-chapters" in codes(validator.project_artifact_findings(REPO_ROOT, project, contract, "long")),
            "real project artifacts must reject invalid source chapters",
        )

    print("OK: story-tao contract rejects chapter, id, reference, and artifact drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
