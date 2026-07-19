#!/usr/bin/env python3
"""Validate story-tao corpus, operator cards, and workflow integration."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from story_tao_project_contract import validate_project


LONG_FRONTMATTER_FIELDS = (
    "schema_version",
    "operator_manifest_version",
    "status",
    "mode",
    "primary_operator",
    "secondary_operator",
    "source_chapters",
    "evidence_basis",
)
LONG_SECTIONS = (
    "自动选择摘要",
    "核心命题",
    "反命题",
    "成立与失效条件",
    "人物立场",
    "长篇命题检验",
    "结局回答",
    "读者契约兼容",
    "表达设计",
    "迁移与诊断",
)

ARTIFACT_SPECS = (
    (
        "references/short-thought-contract.md",
        "tao-short-artifact",
        ("自动选择摘要", "核心命题与反命题", "短篇三步检验", "读者契约兼容", "表达设计"),
    ),
    (
        "references/deconstruction-thought-contract.md",
        "tao-deconstruction",
        ("作品实际命题", "实际反命题与反证", "人物立场", "关键选择、代价与后果", "章节证据", "三张命题卡映射", "说教与误读风险"),
    ),
    (
        "references/thought-progress-contract.md",
        "tao-progress",
        ("当前人物立场", "已出现反证", "已付代价", "章节思想功能日志", "下一检验", "冲突与修复"),
    ),
)


@dataclass(frozen=True)
class TaoContract:
    chapter_count: int
    operator_count: int
    schema_version: int
    operator_manifest_version: int
    required_chapter_count: int
    coverage_matrix: str
    card_frontmatter_fields: tuple[str, ...]
    card_sections: tuple[str, ...]
    original_operator_ids: tuple[str, ...]


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
        schema_version=raw.get("tao_schema_version", 1),
        operator_manifest_version=raw.get("tao_operator_manifest_version", raw["tao_operator_count"]),
        required_chapter_count=raw["tao_required_chapter_count"],
        coverage_matrix=raw["tao_coverage_matrix"],
        card_frontmatter_fields=tuple(raw["tao_card_frontmatter_fields"]),
        card_sections=tuple(raw["tao_card_sections"]),
        original_operator_ids=tuple(raw["tao_original_operator_ids"]),
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
        headings = list(re.finditer(r"^## 第([0-9]+)章\s*$", corpus, re.MULTILINE))
        empty_chapters = []
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(corpus)
            body = corpus[heading.end() : end].strip()
            if not body:
                empty_chapters.append(int(heading.group(1)))
        if empty_chapters:
            findings.append(
                Finding(
                    "tao-corpus-empty-chapter",
                    "chapter bodies must not be empty: {}".format(empty_chapters),
                    corpus_file,
                )
            )
        for marker in ("底本：", "交叉核对：", "引用规则："):
            if marker not in corpus:
                findings.append(
                    Finding(
                        "tao-corpus-source-metadata",
                        "corpus version metadata is missing: {}".format(marker),
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
    card_meta: dict[str, tuple[set[int], str, str, str]] = {}
    for card in cards:
        text = read_text(card) or ""
        id_match = re.search(r"^id:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE)
        if id_match is None:
            findings.append(Finding("tao-operator-id", "missing a valid id", card))
        elif id_match.group(1) in seen_ids:
            findings.append(Finding("tao-operator-id", "operator id must be unique", card))
        else:
            seen_ids.add(id_match.group(1))

        operator_id = id_match.group(1) if id_match else ""
        expected_id = "tao-" + card.stem
        if operator_id and operator_id != expected_id:
            findings.append(
                Finding(
                    "tao-operator-filename",
                    "operator id {} must match filename {}".format(operator_id, card.name),
                    card,
                )
            )

        frontmatter: dict[str, str] = {}
        for field in contract.card_frontmatter_fields:
            match = re.search(r"^{}:\s*(.+?)\s*$".format(re.escape(field)), text, re.MULTILINE)
            if match is None:
                findings.append(
                    Finding(
                        "tao-operator-frontmatter",
                        "missing frontmatter field: {}".format(field),
                        card,
                    )
                )
            else:
                frontmatter[field] = match.group(1).strip()

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

        coverage_role = frontmatter.get("coverage_role", "")
        risk_level = frontmatter.get("risk_level", "")
        domain = frontmatter.get("domain", "")
        if coverage_role not in {"primary", "secondary"}:
            findings.append(Finding("tao-operator-role", "coverage_role must be primary or secondary", card))
        if risk_level not in {"low", "medium", "high"}:
            findings.append(Finding("tao-operator-risk", "risk_level must be low, medium, or high", card))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", domain):
            findings.append(Finding("tao-operator-domain", "domain must be a lowercase slug", card))
        if operator_id:
            card_meta[operator_id] = (set(chapter_refs), domain, risk_level, coverage_role)

        for section in contract.card_sections:
            section_match = re.search(
                r"^## {}\s*\n(.*?)(?=^## |\Z)".format(re.escape(section)),
                text,
                re.MULTILINE | re.DOTALL,
            )
            if section_match is None:
                findings.append(
                    Finding(
                        "tao-operator-section",
                        "missing section: {}".format(section),
                        card,
                    )
                )
            elif not section_match.group(1).strip():
                findings.append(
                    Finding(
                        "tao-operator-section-empty",
                        "section must contain text: {}".format(section),
                        card,
                    )
                )
    for original_id in contract.original_operator_ids:
        if original_id not in seen_ids:
            findings.append(
                Finding(
                    "tao-original-operator-id",
                    "original operator id must remain stable: {}".format(original_id),
                    operator_dir,
                )
            )

    index_path = skill_root / "references/operator-index.md"
    index_text = read_text(index_path) or ""
    indexed_ids = set(re.findall(r"^\|\s*(tao-[a-z0-9-]+)\s*\|", index_text, re.MULTILINE))
    if indexed_ids != seen_ids:
        missing = sorted(seen_ids - indexed_ids)
        unknown = sorted(indexed_ids - seen_ids)
        findings.append(
            Finding(
                "tao-operator-index",
                "index/card mismatch; missing={}, unknown={}".format(missing, unknown),
                index_path,
            )
        )
    for line in index_text.splitlines():
        if re.match(r"^\|\s*tao-[a-z0-9-]+\s*\|", line) is None:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            findings.append(Finding("tao-operator-index-row", "operator index row must contain six columns", index_path))
            continue
        operator_id, _, _, domain, risk, file_cell = cells
        if operator_id not in card_meta:
            continue
        _, card_domain, card_risk, _ = card_meta[operator_id]
        expected_file = "`operators/{}.md`".format(operator_id.removeprefix("tao-"))
        if domain != card_domain or risk != card_risk or file_cell != expected_file:
            findings.append(
                Finding(
                    "tao-operator-index-metadata",
                    "operator index metadata must match card: {}".format(operator_id),
                    index_path,
                )
            )

    matrix_path = repo_root / contract.coverage_matrix
    matrix_text = read_text(matrix_path)
    if matrix_text is None:
        findings.append(Finding("tao-coverage-missing", "coverage matrix is missing", matrix_path))
        return findings

    rows: list[tuple[int, str, list[str], str, str, str, str]] = []
    for line in matrix_text.splitlines():
        if re.match(r"^\|\s*[0-9]+\s*\|", line) is None:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            findings.append(Finding("tao-coverage-row", "coverage row must contain seven columns", matrix_path))
            continue
        try:
            chapter = int(cells[0])
        except ValueError:
            findings.append(Finding("tao-coverage-row", "coverage chapter must be an integer", matrix_path))
            continue
        secondary = [value.strip() for value in cells[2].split(",") if value.strip()]
        rows.append((chapter, cells[1], secondary, cells[3], cells[4], cells[5], cells[6]))

    matrix_chapters = [row[0] for row in rows]
    expected_chapters = list(range(1, contract.required_chapter_count + 1))
    if matrix_chapters != expected_chapters:
        findings.append(
            Finding(
                "tao-coverage-chapters",
                "coverage chapters must be exactly 1..{}".format(contract.required_chapter_count),
                matrix_path,
            )
        )

    matrix_operator_ids = {
        operator_id
        for _, primary, secondary, _, _, _, _ in rows
        for operator_id in [primary] + secondary
    }
    orphan_ids = sorted(seen_ids - matrix_operator_ids)
    if orphan_ids:
        findings.append(
            Finding(
                "tao-coverage-orphan",
                "operators must appear in the coverage matrix: {}".format(orphan_ids),
                matrix_path,
            )
        )

    for chapter, primary, secondary, domain, risk, auto_match, deconstruction in rows:
        referenced = [primary] + secondary
        if any(operator_id not in card_meta for operator_id in referenced):
            findings.append(
                Finding(
                    "tao-coverage-operator",
                    "chapter {} references a missing operator".format(chapter),
                    matrix_path,
                )
            )
            continue
        primary_chapters, primary_domain, primary_risk, primary_role = card_meta[primary]
        if chapter not in primary_chapters or primary_role != "primary":
            findings.append(
                Finding(
                    "tao-coverage-primary",
                    "chapter {} primary card must claim the chapter with coverage_role primary".format(chapter),
                    matrix_path,
                )
            )
        if domain != primary_domain or risk != primary_risk:
            findings.append(
                Finding(
                    "tao-coverage-metadata",
                    "chapter {} domain/risk must match its primary card".format(chapter),
                    matrix_path,
                )
            )
        for secondary_id in secondary:
            if chapter not in card_meta[secondary_id][0]:
                findings.append(
                    Finding(
                        "tao-coverage-secondary",
                        "chapter {} secondary card must cite the chapter".format(chapter),
                        matrix_path,
                    )
                )
        if auto_match != "yes" or deconstruction != "yes":
            findings.append(
                Finding(
                    "tao-coverage-eligibility",
                    "all chapter cards must support automatic matching and deconstruction",
                    matrix_path,
                )
            )

    fixture_path = skill_root / "references/matching-fixtures.md"
    fixture_text = read_text(fixture_path)
    if fixture_text is None:
        findings.append(Finding("tao-matching-fixture-missing", "matching fixtures are missing", fixture_path))
        return findings
    required_fixture_sections = (
        "个人成长：惯常胜法造成自我欺骗",
        "治理：频繁改规则导致执行混乱",
        "战争复仇：胜利制造战后责任",
        "高风险政治解释：知识垄断",
        "证据不足：只有题材标签",
        "辅命题边界",
    )
    for section in required_fixture_sections:
        if re.search(r"^## {}\s*$".format(re.escape(section)), fixture_text, re.MULTILINE) is None:
            findings.append(
                Finding(
                    "tao-matching-fixture-section",
                    "matching fixture section is missing: {}".format(section),
                    fixture_path,
                )
            )
    fixture_ids = set(re.findall(r"tao-[a-z0-9-]+", fixture_text))
    unknown_fixture_ids = sorted(fixture_ids - seen_ids)
    if unknown_fixture_ids:
        findings.append(
            Finding(
                "tao-matching-fixture-operator",
                "matching fixtures reference unknown operators: {}".format(unknown_fixture_ids),
                fixture_path,
            )
        )
    statuses = re.findall(r"^- expected_status:\s*(\S+)\s*$", fixture_text, re.MULTILINE)
    if set(statuses) != {"active", "provisional"}:
        findings.append(
            Finding(
                "tao-matching-fixture-status",
                "matching fixtures must cover active and provisional outcomes",
                fixture_path,
            )
        )
    if re.search(r"^- required_risk:\s*high\s*$", fixture_text, re.MULTILINE) is None:
        findings.append(
            Finding(
                "tao-matching-fixture-risk",
                "matching fixtures must cover a high-risk operator",
                fixture_path,
            )
        )
    return findings


def integration_findings(repo_root: Path) -> list[Finding]:
    checks = (
        ("skills/story-tao/scripts/story_tao_runtime.py", r"def match_cards", "tao-runtime-match", "story-tao runtime must implement match"),
        ("skills/story-tao/scripts/story_tao_runtime.py", r"def ensure", "tao-runtime-ensure", "story-tao runtime must implement ensure"),
        ("skills/story-tao/scripts/story_tao_runtime.py", r"def summarize", "tao-runtime-summarize", "story-tao runtime must implement summarize"),
        ("skills/story-tao/scripts/story_tao_runtime.py", r"def map_evidence", "tao-runtime-map", "story-tao runtime must implement map-evidence"),
        ("skills/story-tao/scripts/story_tao_runtime.py", r"def advance", "tao-runtime-advance", "story-tao runtime must implement advance"),
        ("skills/story/SKILL.md", r"/story-tao|\$story-tao", "tao-router", "router must expose story-tao"),
        ("skills/story-tao/SKILL.md", r"不得输出三个候选后等待确认", "tao-auto-match", "automatic matching must not wait for confirmation"),
        ("skills/story-tao/SKILL.md", r"thought_contract_blocked", "tao-fail-closed", "irreparable contracts must block literary work"),
        ("skills/story-long-scan/SKILL.md", r"思想冲突潜力", "tao-long-scan", "long scan must include thought potential"),
        ("skills/story-short-scan/SKILL.md", r"思想冲突潜力", "tao-short-scan", "short scan must include thought potential"),
        ("skills/story-long-analyze/SKILL.md", r"思想/命题张力\.md", "tao-long-analyze", "long deconstruction must emit thought evidence"),
        ("skills/story-short-analyze/SKILL.md", r"思想/命题张力\.md", "tao-short-analyze", "short deconstruction must emit thought evidence"),
        ("skills/story-import/SKILL.md", r"思想/命题张力\.md", "tao-import", "import must consume or derive thought evidence"),
        ("skills/story-long-write/SKILL.md", r"追踪/思想进展\.md", "tao-long-write-state", "long writing must keep thought runtime state"),
        ("skills/story-long-write/SKILL.md", r"pressure\s*\|\s*counterevidence\s*\|\s*choice\s*\|\s*consequence\s*\|\s*recovery", "tao-chapter-role", "chapter outlines must carry a thought role"),
        ("skills/story-short-write/SKILL.md", r"初始信念.{0,20}反例冲击.{0,20}最终选择", "tao-short-write", "short writing must use the short thought structure"),
        ("skills/story-long-write/references/workflow-daily.md", r"thought_alignment_conflict", "tao-daily-conflict", "daily writing must report thought conflicts"),
        ("skills/story-long-write/references/workflow-daily.md", r"不得新增细纲外事件|不新增细纲外事件", "tao-daily-outline", "thought guidance must not add outline events"),
        ("skills/story-review/SKILL.md", r"Thought Gate:\s*pass\s*\|\s*revise\s*\|\s*blocked", "tao-review-gate", "review must expose a mandatory thought gate"),
        ("skills/story-review/SKILL.md", r"商业数值评分.{0,40}(?:独立|不计入)", "tao-review-score", "thought gate must remain separate from numeric scoring"),
        ("skills/story-deslop/SKILL.md", r"思想契约", "tao-deslop", "deslop must preserve thought intent"),
        ("skills/story-cover/SKILL.md", r"核心对立", "tao-cover", "cover must consume the thought opposition"),
        ("skills/story-setup/references/templates/agents/story-architect.md", r"thought_contract_summary", "tao-agent-architect", "architect must consume the thought summary"),
        ("skills/story-setup/references/templates/agents/character-designer.md", r"维护利益", "tao-agent-character", "character design must carry thought positions"),
        ("skills/story-setup/references/templates/agents/chapter-extractor.md", r"thought_evidence", "tao-agent-extractor", "chapter extraction must expose thought evidence"),
        ("skills/story-setup/references/templates/agents/narrative-writer.md", r"本章思想功能", "tao-agent-writer", "prose writing must consume the chapter thought role"),
        ("skills/story-setup/references/templates/agents/consistency-checker.md", r"THOUGHT_GATE", "tao-agent-checker", "consistency review must expose the thought gate"),
        ("skills/story-setup/references/templates/agents/story-explorer.md", r"thought_context_load", "tao-agent-explorer", "explorer must load compact thought context"),
        ("skills/story-setup/references/templates/CLAUDE.md.tmpl", r"强制思想内核", "tao-claude-root", "Claude root template must require the thought core"),
        ("skills/story-setup/references/codex/AGENTS.md.tmpl", r"强制思想内核", "tao-codex-root", "Codex root template must require the thought core"),
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
    if re.search(r"^status:\s*(?:active|provisional)\s*$", text, re.MULTILINE) is None:
        findings.append(
            Finding(
                "tao-artifact-status",
                "thought-contract template status must be active or provisional",
                path,
            )
        )
    for field in LONG_FRONTMATTER_FIELDS:
        if re.search(r"^{}:\s*.+$".format(re.escape(field)), text, re.MULTILINE) is None:
            findings.append(
                Finding(
                    "tao-artifact-frontmatter",
                    "thought-contract template is missing field: {}".format(field),
                    path,
                )
            )
    for section in LONG_SECTIONS:
        if re.search(r"^## {}\s*$".format(re.escape(section)), text, re.MULTILINE) is None:
            findings.append(
                Finding(
                    "tao-artifact-section",
                    "thought-contract template is missing section: {}".format(section),
                    path,
                )
            )
    skill_root = repo_root / "skills/story-tao"
    for relative, code_prefix, sections in ARTIFACT_SPECS:
        artifact = skill_root / relative
        artifact_text = read_text(artifact)
        if artifact_text is None:
            findings.append(Finding(code_prefix + "-missing", "artifact template is missing", artifact))
            continue
        for section in sections:
            if re.search(r"^## {}\s*$".format(re.escape(section)), artifact_text, re.MULTILINE) is None:
                findings.append(
                    Finding(
                        code_prefix + "-section",
                        "artifact template is missing section: {}".format(section),
                        artifact,
                    )
                )
    return findings


def project_artifact_findings(
    repo_root: Path,
    project_root: Path,
    contract: TaoContract,
    mode: str,
    artifact: Path | None = None,
) -> list[Finding]:
    return [
        Finding(code, message, path)
        for code, message, path in validate_project(
            repo_root,
            project_root,
            mode,
            contract.chapter_count,
            contract.schema_version,
            contract.operator_manifest_version,
            artifact,
        )
    ]


def validate_repository(
    repo_root: Path,
    contract: TaoContract,
    project_root: Path | None = None,
    project_mode: str | None = None,
    project_artifact: Path | None = None,
) -> list[Finding]:
    project_findings: list[Finding] = []
    if project_root is not None:
        if project_mode is None:
            project_findings.append(Finding("tao-project-mode", "project mode is required when validating a project", project_root))
        else:
            project_findings.extend(
                project_artifact_findings(repo_root, project_root, contract, project_mode, project_artifact)
            )
    return (
        resource_findings(repo_root, contract)
        + artifact_findings(repo_root)
        + integration_findings(repo_root)
        + project_findings
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().with_name("current-contract.json"))
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--project-mode", choices=("long", "short", "deconstruction"), default=None)
    parser.add_argument("--project-artifact", type=Path, default=None)
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    contract = load_contract(args.manifest.resolve())
    findings = validate_repository(
        repo_root,
        contract,
        args.project_root.resolve() if args.project_root else None,
        args.project_mode,
        args.project_artifact.resolve() if args.project_artifact else None,
    )
    if findings:
        for finding in findings:
            print("[FAIL] {}: {}".format(finding.code, finding.detail(repo_root)))
        return 1
    print(
        "OK: story-tao mandatory core ({} chapters, {} operators, full coverage, four artifacts)".format(
            contract.chapter_count, contract.operator_count
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
