#!/usr/bin/env python3
"""Validate story-tao corpus, operator cards, and workflow integration."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ARTIFACT_FRONTMATTER_FIELDS = (
    "status",
    "mode",
    "primary_operator",
    "secondary_operator",
    "source_chapters",
)
ARTIFACT_SECTIONS = (
    "选择摘要",
    "核心命题",
    "反命题",
    "成立与失效条件",
    "人物初始立场",
    "三次命题检验",
    "结局",
    "读者契约兼容",
    "表达设计",
    "既有作品诊断",
    "未自动应用的补强建议",
)


@dataclass(frozen=True)
class TaoContract:
    chapter_count: int
    operator_count: int
    operator_sections: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: Path

    def detail(self, repo_root: Path) -> str:
        try:
            shown = self.path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            shown = self.path
        return "{}: {}".format(shown, self.message)


def load_contract(path: Path) -> TaoContract:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TaoContract(
        chapter_count=raw["tao_chapter_count"],
        operator_count=raw["tao_operator_count"],
        operator_sections=tuple(raw["tao_operator_sections"]),
    )


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def resource_findings(repo_root: Path, contract: TaoContract) -> list[Finding]:
    findings: list[Finding] = []
    skill_root = repo_root / "skills/story-tao"
    skill_file = skill_root / "SKILL.md"
    corpus_file = skill_root / "references/daodejing.md"
    operator_dir = skill_root / "references/operators"

    if not skill_file.is_file():
        findings.append(Finding("tao-skill-missing", "story-tao/SKILL.md is missing", skill_file))

    corpus = read_text(corpus_file)
    if corpus is None:
        findings.append(Finding("tao-corpus-missing", "Tao corpus is missing or unreadable", corpus_file))
    else:
        chapters = [int(value) for value in re.findall(r"^## 第([0-9]+)章\s*$", corpus, re.MULTILINE)]
        if chapters != list(range(1, contract.chapter_count + 1)):
            findings.append(
                Finding(
                    "tao-corpus-chapters",
                    "chapters must be exactly 1..{}; found {} headings".format(
                        contract.chapter_count, len(chapters)
                    ),
                    corpus_file,
                )
            )

    cards = sorted(operator_dir.glob("*.md"))
    if len(cards) != contract.operator_count:
        findings.append(
            Finding(
                "tao-operator-count",
                "expected {} operator cards, found {}".format(
                    contract.operator_count, len(cards)
                ),
                operator_dir,
            )
        )

    seen_ids: set[str] = set()
    for card in cards:
        text = read_text(card) or ""
        id_match = re.search(r"^id:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE)
        if id_match is None:
            findings.append(Finding("tao-operator-id", "missing a valid id", card))
        elif id_match.group(1) in seen_ids:
            findings.append(Finding("tao-operator-id", "operator id must be unique", card))
        else:
            seen_ids.add(id_match.group(1))

        chapter_match = re.search(r"^chapters:\s*\[([^]]+)\]\s*$", text, re.MULTILINE)
        if chapter_match is None:
            chapter_refs: list[int] = []
        else:
            try:
                chapter_refs = [int(value.strip()) for value in chapter_match.group(1).split(",")]
            except ValueError:
                chapter_refs = []
        if not chapter_refs or any(value < 1 or value > contract.chapter_count for value in chapter_refs):
            findings.append(
                Finding(
                    "tao-operator-chapters",
                    "chapter references must be within 1..{}".format(contract.chapter_count),
                    card,
                )
            )

        for section in contract.operator_sections:
            if re.search(r"^## {}\s*$".format(re.escape(section)), text, re.MULTILINE) is None:
                findings.append(
                    Finding(
                        "tao-operator-section",
                        "missing section: {}".format(section),
                        card,
                    )
                )
    return findings


def integration_findings(repo_root: Path) -> list[Finding]:
    checks = (
        ("skills/story/SKILL.md", r"/story-tao|\$story-tao", "tao-router", "router must expose story-tao"),
        ("skills/story-tao/SKILL.md", r"恰好输出三项", "tao-three-candidates", "must recommend exactly three candidates"),
        ("skills/story-long-write/SKILL.md", r"设定/思想命题\.md", "tao-long-write-artifact", "long writing must integrate the thought contract"),
        ("skills/story-long-write/SKILL.md", r"status:\s*confirmed", "tao-long-write-confirmed", "long writing must consume confirmed contracts only"),
        ("skills/story-long-write/references/workflow-daily.md", r"thought_alignment_conflict", "tao-daily-conflict", "daily writing must report thought conflicts"),
        ("skills/story-long-write/references/workflow-daily.md", r"不得新增细纲外事件|不新增细纲外事件", "tao-daily-outline", "thought guidance must not add outline events"),
        ("skills/story-review/SKILL.md", r"思想完整性", "tao-review-section", "review must expose thought-integrity advice"),
        ("skills/story-review/SKILL.md", r"不(?:改变|计入|影响).{0,30}(?:总分|严重级别|发布结论)", "tao-review-advisory", "thought review must remain advisory"),
    )
    findings: list[Finding] = []
    for relative, pattern, code, message in checks:
        path = repo_root / relative
        text = read_text(path)
        if text is None or re.search(pattern, text, re.MULTILINE) is None:
            findings.append(Finding(code, message, path))
    return findings


def artifact_findings(repo_root: Path) -> list[Finding]:
    path = repo_root / "skills/story-tao/references/thought-contract.md"
    text = read_text(path)
    if text is None:
        return [Finding("tao-artifact-missing", "thought-contract template is missing", path)]

    findings: list[Finding] = []
    if re.search(r"^status:\s*confirmed\s*$", text, re.MULTILINE) is None:
        findings.append(
            Finding(
                "tao-artifact-status",
                "thought-contract template status must be confirmed",
                path,
            )
        )
    for field in ARTIFACT_FRONTMATTER_FIELDS:
        if re.search(r"^{}:\s*.+$".format(re.escape(field)), text, re.MULTILINE) is None:
            findings.append(
                Finding(
                    "tao-artifact-frontmatter",
                    "thought-contract template is missing field: {}".format(field),
                    path,
                )
            )
    for section in ARTIFACT_SECTIONS:
        if re.search(r"^## {}\s*$".format(re.escape(section)), text, re.MULTILINE) is None:
            findings.append(
                Finding(
                    "tao-artifact-section",
                    "thought-contract template is missing section: {}".format(section),
                    path,
                )
            )
    return findings


def validate_repository(repo_root: Path, contract: TaoContract) -> list[Finding]:
    return (
        resource_findings(repo_root, contract)
        + artifact_findings(repo_root)
        + integration_findings(repo_root)
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().with_name("current-contract.json"))
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    contract = load_contract(args.manifest.resolve())
    findings = validate_repository(repo_root, contract)
    if findings:
        for finding in findings:
            print("[FAIL] {}: {}".format(finding.code, finding.detail(repo_root)))
        return 1
    print(
        "OK: story-tao contract ({} chapters, {} operators, routed writing/review integration)".format(
            contract.chapter_count, contract.operator_count
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
