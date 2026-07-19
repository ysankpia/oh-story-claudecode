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
    require(contract.operator_count == 15, "contract must declare 15 operators")
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

        first.write_text(original_first.replace("## 反命题", "## 缺失反命题"), encoding="utf-8")
        require(
            "tao-operator-section" in codes(validator.resource_findings(root, contract)),
            "missing operator sections must fail",
        )

        thought_contract = target / "references/thought-contract.md"
        original_thought_contract = thought_contract.read_text(encoding="utf-8")
        thought_contract.write_text(
            original_thought_contract.replace("## 三次命题检验", "## 缺失三次命题检验"),
            encoding="utf-8",
        )
        require(
            "tao-artifact-section" in codes(validator.artifact_findings(root)),
            "missing thought-contract sections must fail",
        )

        thought_contract.write_text(
            original_thought_contract.replace("status: confirmed", "status: draft"),
            encoding="utf-8",
        )
        require(
            "tao-artifact-status" in codes(validator.artifact_findings(root)),
            "unconfirmed thought-contract templates must fail",
        )

    print("OK: story-tao contract rejects chapter, id, reference, and artifact drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
