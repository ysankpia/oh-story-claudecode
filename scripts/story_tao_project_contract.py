#!/usr/bin/env python3
"""Validate story-tao artifacts inside a real writing project."""

from __future__ import annotations

import re
from pathlib import Path


ProjectError = tuple[str, str, Path]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    values: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1).strip()] = text[match.end() : end].strip()
    return result


def chapters(raw: str) -> list[int]:
    value = raw.strip().strip("[]")
    if not value:
        return []
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError:
        return []


def valid_operator_ids(repo_root: Path) -> set[str]:
    text = "\n".join(
        read_text(path)
        for path in (repo_root / "skills/story-tao/references/operators").glob("*.md")
    )
    return set(re.findall(r"^id:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE))


def operator_chapters(repo_root: Path) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for path in (repo_root / "skills/story-tao/references/operators").glob("*.md"):
        text = read_text(path)
        operator = re.search(r"^id:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE)
        raw_chapters = re.search(r"^chapters:\s*(\[[^]]*\])\s*$", text, re.MULTILINE)
        if operator and raw_chapters:
            result[operator.group(1)] = set(chapters(raw_chapters.group(1)))
    return result


def resolve_artifact(project_root: Path, mode: str, artifact: Path | None) -> tuple[Path | None, tuple[str, ...]]:
    if mode == "long":
        return artifact or project_root / "设定/思想命题.md", (
            "自动选择摘要", "核心命题", "反命题", "成立与失效条件", "人物立场", "长篇命题检验",
        )
    if mode == "short":
        return artifact or project_root / "思想命题.md", (
            "自动选择摘要", "核心命题与反命题", "短篇三步检验",
        )
    if mode == "deconstruction":
        candidates = sorted((project_root / "拆文库").glob("*/思想/命题张力.md"))
        chosen = artifact or (candidates[0] if len(candidates) == 1 else None)
        return chosen, (
            "作品实际命题", "实际反命题与反证", "人物立场", "关键选择、代价与后果", "章节证据", "三张命题卡映射",
        )
    return None, ()


def validate_project(
    repo_root: Path,
    project_root: Path,
    mode: str,
    chapter_count: int,
    schema_version: int,
    operator_manifest_version: int,
    artifact: Path | None = None,
) -> list[ProjectError]:
    if mode not in {"long", "short", "deconstruction"}:
        return [("tao-project-mode", "mode must be long, short, or deconstruction", project_root)]
    artifact, required = resolve_artifact(project_root, mode, artifact)
    if artifact is None or not artifact.is_file():
        return [("tao-project-artifact-missing", "project thought artifact is missing", artifact or project_root)]
    text = read_text(artifact)
    meta = frontmatter(text)
    body = sections(text)
    errors: list[ProjectError] = []
    if mode != "deconstruction":
        if meta.get("status") not in {"active", "provisional", "confirmed"}:
            errors.append(("tao-project-status", "project thought status is invalid", artifact))
        if meta.get("mode") != mode:
            errors.append(("tao-project-mode", "project thought mode does not match the workflow", artifact))
        if meta.get("schema_version") != str(schema_version):
            errors.append(("tao-project-schema", "project schema_version is stale or invalid", artifact))
        if meta.get("operator_manifest_version") != str(operator_manifest_version):
            errors.append(("tao-project-operator-manifest", "project operator_manifest_version is stale", artifact))
        card_chapters = operator_chapters(repo_root)
        ids = set(card_chapters)
        for field, code in (("primary_operator", "tao-project-primary-operator"), ("secondary_operator", "tao-project-secondary-operator")):
            operator_id = meta.get(field, "null")
            if operator_id not in {"", "null", "None"} and operator_id not in ids:
                errors.append((code, field.replace("_", " ") + " does not exist", artifact))
        primary = meta.get("primary_operator", "null")
        secondary = meta.get("secondary_operator", "null")
        if primary not in {"", "null", "None"} and primary == secondary:
            errors.append(("tao-project-secondary-operator", "primary and secondary operators must differ", artifact))
        source_chapters = chapters(meta.get("source_chapters", ""))
        if any(value < 1 or value > chapter_count for value in source_chapters):
            errors.append(("tao-project-source-chapters", "source chapters must be within 1..81", artifact))
        legal_chapters = set().union(*(card_chapters.get(item, set()) for item in (primary, secondary)))
        if source_chapters and not set(source_chapters) <= legal_chapters:
            errors.append(("tao-project-source-chapters", "source chapters must belong to the selected operators", artifact))
        if primary not in {"", "null", "None"} and not source_chapters:
            errors.append(("tao-project-source-chapters", "selected operators require source chapters", artifact))
    for section in required:
        if not body.get(section, "").strip():
            errors.append(("tao-project-section", "project artifact is missing section: " + section, artifact))
    if mode == "long" and not all(marker in body.get("长篇命题检验", "") for marker in ("开篇", "发展", "高潮")):
        errors.append(("tao-project-long-tests", "long thought contract must contain opening, development, and climax tests", artifact))
    if mode == "short" and not all(marker in body.get("短篇三步检验", "") for marker in ("初始信念", "反例冲击", "最终选择")):
        errors.append(("tao-project-short-tests", "short thought contract must contain all three thought steps", artifact))
    if mode == "deconstruction":
        evidence_count = len(re.findall(r"(?:第\d+章|第\d+节|小节\s*\d+|段落\s*\d+)", body.get("章节证据", "")))
        if evidence_count < 3:
            errors.append(("tao-project-evidence-count", "deconstruction mapping requires at least three located evidence items", artifact))
        mapped_ids = set(re.findall(r"tao-[a-z0-9-]+", body.get("三张命题卡映射", "")))
        if len(mapped_ids) != 3 or not mapped_ids <= valid_operator_ids(repo_root):
            errors.append(("tao-project-mapping-count", "deconstruction mapping requires exactly three existing operators", artifact))
    if mode == "long":
        progress = project_root / "追踪/思想进展.md"
        if not progress.is_file():
            errors.append(("tao-project-progress-missing", "long project thought progress is missing", progress))
        else:
            progress_chapters = list(map(int, re.findall(r"第(\d+)章", read_text(progress))))
            if any(value < 1 or value > chapter_count for value in progress_chapters):
                errors.append(("tao-project-progress-chapter", "progress references an invalid chapter", progress))
            context = read_text(project_root / "追踪/上下文.md")
            completed_match = re.search(r"最后完成章节[^\d]{0,8}第\s*(\d+)\s*章", context)
            if completed_match and any(value > int(completed_match.group(1)) for value in progress_chapters):
                errors.append(("tao-project-progress-future", "progress references a chapter beyond the completed manuscript", progress))
    return errors
