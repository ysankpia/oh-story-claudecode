#!/usr/bin/env python3
"""Deterministic local runtime for the mandatory story-tao thought core."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


VALID_FUNCTIONS = {"pressure", "counterevidence", "choice", "consequence", "recovery"}
LONG_SECTIONS = (
    "自动选择摘要", "核心命题", "反命题", "成立与失效条件", "人物立场",
    "长篇命题检验", "结局回答", "读者契约兼容", "表达设计", "迁移与诊断",
)
SHORT_SECTIONS = (
    "自动选择摘要", "核心命题与反命题", "短篇三步检验", "读者契约兼容", "表达设计",
)


class TaoRuntimeError(RuntimeError):
    """A stable, machine-readable story-tao runtime failure."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class Card:
    operator_id: str
    title: str
    chapters: tuple[int, ...]
    domain: str
    risk_level: str
    sections: dict[str, str]


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    result: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _sections(text: str) -> dict[str, str]:
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    result: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        result[heading.group(1)] = text[heading.end():end].strip()
    return result


def _chapter_list(raw: str) -> tuple[int, ...]:
    try:
        return tuple(int(value.strip()) for value in raw.strip().strip("[]").split(",") if value.strip())
    except ValueError as exc:
        raise TaoRuntimeError("thought_contract_blocked", "invalid source_chapters") from exc


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        skill_root = Path(__file__).resolve().parent.parent
        candidates = (Path.cwd() / "scripts/current-contract.json", skill_root / "references/runtime-contract.json")
        path = next((candidate for candidate in candidates if candidate.is_file()), candidates[-1])
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaoRuntimeError("manifest_invalid", "cannot read story-tao manifest", {"path": str(path)}) from exc
    required = ("tao_chapter_count", "tao_operator_count", "tao_schema_version", "tao_operator_manifest_version")
    if any(not isinstance(manifest.get(field), int) for field in required):
        raise TaoRuntimeError("manifest_invalid", "story-tao manifest is missing integer contract fields")
    return manifest


def _operator_dir(resource_root: Path) -> Path:
    candidates = (
        resource_root / "skills/story-tao/references/operators",
        resource_root / "references/operators",
        resource_root / "operators",
    )
    return next((candidate for candidate in candidates if candidate.is_dir()), candidates[0])


def load_cards(resource_root: Path, manifest: dict[str, Any]) -> dict[str, Card]:
    cards: dict[str, Card] = {}
    directory = _operator_dir(Path(resource_root))
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = _frontmatter(text)
        operator_id = meta.get("id", "")
        chapters = _chapter_list(meta.get("chapters", ""))
        if not operator_id or not chapters or any(chapter < 1 or chapter > manifest["tao_chapter_count"] for chapter in chapters):
            raise TaoRuntimeError("operator_invalid", "operator metadata is invalid", {"path": str(path)})
        if operator_id in cards:
            raise TaoRuntimeError("operator_invalid", "duplicate operator id", {"operator": operator_id})
        cards[operator_id] = Card(
            operator_id=operator_id,
            title=meta.get("title", operator_id), chapters=chapters,
            domain=meta.get("domain", ""), risk_level=meta.get("risk_level", "medium"),
            sections=_sections(text),
        )
    if len(cards) != manifest["tao_operator_count"]:
        raise TaoRuntimeError(
            "operator_manifest_mismatch", "operator count does not match the manifest",
            {"expected": manifest["tao_operator_count"], "actual": len(cards)},
        )
    return cards


def _as_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    return value if isinstance(value, list) else ([value] if value else [])


def _score(card: Card, payload: dict[str, Any]) -> dict[str, int]:
    domains = {str(value) for value in _as_list(payload, "domains")}
    selection = 3 if card.domain in domains else 0
    counter = 2 if _as_list(payload, "counterevidence") else 0
    reader = 2 if payload.get("reader_contract") else 1 if domains else 0
    evidence = 2 if _as_list(payload, "evidence") else 0
    risk = {"low": 0, "medium": -1, "high": -2}.get(card.risk_level, -2)
    return {
        "character_choice": selection, "counter_thesis": counter,
        "reader_contract": reader, "evidence": evidence, "preaching_risk": risk,
        "total": selection + counter + reader + evidence + risk,
    }


def match_cards(payload: dict[str, Any], cards: dict[str, Card]) -> dict[str, Any]:
    preferred = payload.get("preferred_operator")
    requested_secondary = payload.get("secondary_operator")
    for operator_id in (preferred, requested_secondary):
        if operator_id and operator_id not in cards:
            raise TaoRuntimeError("unknown_operator", "operator does not exist", {"operator": operator_id})
    if preferred and requested_secondary and cards[preferred].domain == cards[requested_secondary].domain:
        raise TaoRuntimeError("same_axis_secondary", "secondary operator must use a different conflict axis")

    domains = _as_list(payload, "domains")
    if not preferred and not domains:
        return {
            "status": "provisional", "primary_operator": None, "secondary_operator": None,
            "score_breakdown": {}, "conditions": [], "failure_conditions": [],
            "missing_evidence": ["人物的具体选择", "至少两个可辩护立场", "反命题证据"], "risk_flags": [],
        }

    scored = [(operator_id, _score(card, payload)) for operator_id, card in cards.items()]
    scored.sort(key=lambda item: (-item[1]["total"], -item[1]["character_choice"], -item[1]["counter_thesis"], item[0]))
    primary = preferred or scored[0][0]
    secondary = requested_secondary
    if secondary is None and payload.get("include_secondary"):
        secondary = next((operator_id for operator_id, _ in scored if cards[operator_id].domain != cards[primary].domain), None)

    complete = bool(_as_list(payload, "evidence")) and len(_as_list(payload, "positions")) >= 2 and bool(_as_list(payload, "counterevidence"))
    card = cards[primary]
    missing: list[str] = []
    if not _as_list(payload, "evidence"):
        missing.append("人物选择及可见后果")
    if len(_as_list(payload, "positions")) < 2:
        missing.append("至少两个可辩护人物立场")
    if not _as_list(payload, "counterevidence"):
        missing.append("反命题的现实收益或文本反证")
    risks = []
    if card.risk_level in {"medium", "high"}:
        risks.append("{}: {}".format(card.risk_level, card.sections.get("现代化边界", "需核对现代解释边界")))
    return {
        "status": "active" if complete else "provisional",
        "primary_operator": primary, "secondary_operator": secondary,
        "score_breakdown": {primary: _score(card, payload)},
        "conditions": [card.sections.get("核心命题", "命题须由行动与后果成立")],
        "failure_conditions": [card.sections.get("反命题", "反命题在特定条件下成立")],
        "missing_evidence": missing, "risk_flags": risks,
    }


def _contract_path(project_root: Path, mode: str) -> Path:
    if mode == "long":
        return project_root / "设定/思想命题.md"
    if mode == "short":
        return project_root / "思想命题.md"
    raise TaoRuntimeError("thought_contract_blocked", "mode must be long or short")


def _source_chapters(primary: str | None, secondary: str | None, cards: dict[str, Card]) -> tuple[int, ...]:
    values = {chapter for operator_id in (primary, secondary) if operator_id for chapter in cards[operator_id].chapters}
    return tuple(sorted(values))


def _render_contract(mode: str, matched: dict[str, Any], cards: dict[str, Card], manifest: dict[str, Any]) -> str:
    primary_id = matched["primary_operator"]
    secondary_id = matched["secondary_operator"]
    primary = cards.get(primary_id) if primary_id else None
    source = _source_chapters(primary_id, secondary_id, cards)
    title = primary.title if primary else "待补证据"
    core = primary.sections.get("核心命题", "待人物选择证据明确后补全。") if primary else "待人物选择证据明确后补全。"
    counter = primary.sections.get("反命题", "待反方利益证据明确后补全。") if primary else "待反方利益证据明确后补全。"
    position = primary.sections.get("人物立场", "待补主角与反方立场。") if primary else "待补主角与反方立场。"
    prohibition = primary.sections.get("禁止说教方式", "只用行动、关系与后果表达。") if primary else "只用行动、关系与后果表达。"
    header = "\n".join((
        "---", "schema_version: {}".format(manifest["tao_schema_version"]),
        "operator_manifest_version: {}".format(manifest["tao_operator_manifest_version"]),
        "status: {}".format(matched["status"]), "mode: {}".format(mode),
        "primary_operator: {}".format(primary_id or "null"), "secondary_operator: {}".format(secondary_id or "null"),
        "source_chapters: [{}]".format(", ".join(map(str, source))), "evidence_basis: runtime-match",
        "---", "# 思想命题", "",
    ))
    summary = "- 主命题卡：{} / {}\n- 辅命题卡：{}\n- 待补证据：{}".format(
        title, primary_id or "待定", secondary_id or "无", "、".join(matched["missing_evidence"]) or "无",
    )
    if mode == "long":
        body = (
            "## 自动选择摘要\n{summary}\n\n## 核心命题\n{core}\n\n## 反命题\n{counter}\n\n"
            "## 成立与失效条件\n- 成立条件：由人物选择和可见后果验证。\n- 失效条件：{counter}\n\n"
            "## 人物立场\n{position}\n\n## 长篇命题检验\n- 开篇：待细纲指定选择、代价与后果。\n"
            "- 发展：待卷纲指定选择、代价与后果。\n- 高潮：待全书大纲指定选择、代价与后果。\n\n"
            "## 结局回答\n- 暂时回答：待剧情验证。\n- 保留疑问：反命题仍可能在其条件下成立。\n\n"
            "## 读者契约兼容\n- 不得削弱主角代理权、题材收益或锁定高光。\n- 潜在冲突：无。\n\n"
            "## 表达设计\n- 行动表达：通过选择、代价和后果呈现。\n- 禁止说教、错误引文和古风腔污染：{prohibition}\n\n"
            "## 迁移与诊断\n由 story-tao runtime 自动创建；未回写既有正文。\n"
        ).format(summary=summary, core=core, counter=counter, position=position, prohibition=prohibition)
    else:
        body = (
            "## 自动选择摘要\n{summary}\n\n## 核心命题与反命题\n- 核心命题：{core}\n- 反命题：{counter}\n"
            "- 成立条件：由最终选择的可见后果验证。\n- 失效条件：反例获得现实收益。\n\n"
            "## 短篇三步检验\n- 初始信念：人物以现有信念保护自身利益。\n- 反例冲击：反例迫使人物付出代价。\n"
            "- 最终选择：人物作出选择并承担可见后果。\n\n## 读者契约兼容\n不得削弱情绪兑现、反转或主角代理权。\n\n"
            "## 表达设计\n通过场景、行动和关系表达；{prohibition}\n"
        ).format(summary=summary, core=core, counter=counter, prohibition=prohibition)
    return header + body


def _render_progress() -> str:
    return (
        "# 思想进展\n\n## 当前人物立场\n待正文证据更新。\n\n## 已出现反证\n无。\n\n"
        "## 已付代价\n无。\n\n## 章节思想功能日志\n\n## 下一检验\n来自卷纲或细纲；不得新增事件。\n\n"
        "## 冲突与修复\n无。\n"
    )


def _manifest_from_cards(cards: dict[str, Card]) -> dict[str, Any]:
    manifest = load_manifest()
    if manifest["tao_operator_count"] != len(cards):
        raise TaoRuntimeError("operator_manifest_mismatch", "loaded cards do not match runtime manifest")
    return manifest


def ensure(payload: dict[str, Any], project_root: Path, cards: dict[str, Card]) -> dict[str, Any]:
    mode = str(payload.get("mode", "long"))
    manifest = _manifest_from_cards(cards)
    path = _contract_path(Path(project_root), mode)
    actions: list[str] = []
    if not path.is_file():
        matched = match_cards(payload, cards)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_contract(mode, matched, cards, manifest), encoding="utf-8")
        actions.append("created")
    else:
        text = path.read_text(encoding="utf-8")
        meta = _frontmatter(text)
        if not meta:
            raise TaoRuntimeError("thought_contract_blocked", "thought contract frontmatter is missing", {"path": str(path)})
        if meta.get("status") == "confirmed":
            text = re.sub(r"^status:\s*confirmed\s*$", "status: active", text, count=1, flags=re.MULTILINE)
            meta["status"] = "active"
            actions.append("confirmed_to_active")
        for field, expected in (("schema_version", manifest["tao_schema_version"]), ("operator_manifest_version", manifest["tao_operator_manifest_version"])):
            current = meta.get(field)
            if current is None:
                text = text.replace("---\n", "---\n{}: {}\n".format(field, expected), 1)
                meta[field] = str(expected)
                actions.append("filled_{}".format(field))
            elif current != str(expected):
                raise TaoRuntimeError("thought_contract_blocked", "unsupported {}".format(field), {"actual": current, "expected": expected})
        if meta.get("status") not in {"active", "provisional"} or meta.get("mode") != mode:
            raise TaoRuntimeError("thought_contract_blocked", "thought contract status or mode is invalid")
        for field in ("primary_operator", "secondary_operator"):
            value = meta.get(field, "null")
            if value not in {"", "null", "None"} and value not in cards:
                raise TaoRuntimeError("thought_contract_blocked", "thought contract references an unknown operator", {"operator": value})
        primary = meta.get("primary_operator", "null")
        secondary = meta.get("secondary_operator", "null")
        if primary not in {"", "null", "None"} and primary == secondary:
            raise TaoRuntimeError("thought_contract_blocked", "primary and secondary operators must differ")
        source = _chapter_list(meta.get("source_chapters", ""))
        legal = _source_chapters(primary if primary in cards else None, secondary if secondary in cards else None, cards)
        if any(chapter < 1 or chapter > manifest["tao_chapter_count"] for chapter in source) or (source and not set(source) <= set(legal)):
            raise TaoRuntimeError("thought_contract_blocked", "thought contract source chapters are invalid")
        if primary in cards and not source:
            rendered = "source_chapters: [{}]".format(", ".join(map(str, legal)))
            if "source_chapters" in meta:
                text = re.sub(r"^source_chapters:\s*.*$", rendered, text, count=1, flags=re.MULTILINE)
            else:
                text = text.replace("---\n", "---\n{}\n".format(rendered), 1)
            actions.append("filled_source_chapters")
        if meta["status"] == "active" and primary not in cards:
            raise TaoRuntimeError("thought_contract_blocked", "active thought contracts require a primary operator")
        required = LONG_SECTIONS if mode == "long" else SHORT_SECTIONS
        if any(not _sections(text).get(section, "").strip() for section in required):
            raise TaoRuntimeError("thought_contract_blocked", "thought contract is missing required sections")
        path.write_text(text, encoding="utf-8")
    if mode == "long":
        progress = Path(project_root) / "追踪/思想进展.md"
        if not progress.is_file():
            progress.parent.mkdir(parents=True, exist_ok=True)
            progress.write_text(_render_progress(), encoding="utf-8")
            actions.append("created_progress")
    meta = _frontmatter(path.read_text(encoding="utf-8"))
    return {"ok": True, "status": meta["status"], "path": str(path), "actions": actions}


def summarize(payload: dict[str, Any], project_root: Path, cards: dict[str, Card]) -> dict[str, Any]:
    ensured = ensure(payload, project_root, cards)
    text = Path(ensured["path"]).read_text(encoding="utf-8")
    meta = _frontmatter(text)
    body = _sections(text)
    primary_id = meta.get("primary_operator", "null")
    card = cards.get(primary_id)
    return {
        "status": meta["status"], "thought_gate": "pass" if meta["status"] == "active" else "revise",
        "primary_operator": None if primary_id in {"", "null", "None"} else primary_id,
        "secondary_operator": None if meta.get("secondary_operator") in {None, "", "null", "None"} else meta["secondary_operator"],
        "core_thesis": body.get("核心命题", body.get("核心命题与反命题", "")),
        "counter_thesis": body.get("反命题", body.get("核心命题与反命题", "")),
        "character_positions": body.get("人物立场", card.sections.get("人物立场", "") if card else ""),
        "chapter_function": payload.get("function"),
        "choice_cost_consequence": payload.get("choice_cost_consequence", "来自锁定细纲；不得新增事件。"),
        "expression_limits": body.get("表达设计", "只用行动、关系与后果表达。"),
        "conflict": payload.get("conflict", "none"),
    }


def map_evidence(payload: dict[str, Any], cards: dict[str, Card]) -> dict[str, Any]:
    operator_ids = _as_list(payload, "operator_ids")
    if len(operator_ids) != 3 or len(set(operator_ids)) != 3:
        raise TaoRuntimeError("evidence_mapping_invalid", "map-evidence requires exactly three distinct operators")
    unknown = [operator_id for operator_id in operator_ids if operator_id not in cards]
    if unknown:
        raise TaoRuntimeError("unknown_operator", "mapping references unknown operators", {"operators": unknown})
    evidence = _as_list(payload, "evidence")
    located = [item for item in evidence if isinstance(item, dict) and any(item.get(key) for key in ("chapter", "section", "paragraph")) and item.get("text")]
    return {
        "status": "active" if len(located) >= 3 else "provisional",
        "work_thesis": payload.get("work_thesis", "待从作品证据归纳"),
        "work_counter_thesis": payload.get("work_counter_thesis", "待从作品反证归纳"),
        "evidence": located,
        "operators": [{"id": operator_id, "title": cards[operator_id].title, "domain": cards[operator_id].domain} for operator_id in operator_ids],
        "disclaimer": "这是分析映射，不证明原作者受《道德经》影响。",
    }


def advance(payload: dict[str, Any], project_root: Path) -> dict[str, Any]:
    progress = Path(project_root) / "追踪/思想进展.md"
    if not progress.is_file():
        raise TaoRuntimeError("thought_progress_update_failed", "thought progress file is missing")
    try:
        chapter = int(payload["chapter"])
        completed = int(payload["completed_chapter"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TaoRuntimeError("thought_progress_update_failed", "chapter and completed_chapter must be integers") from exc
    text = progress.read_text(encoding="utf-8")
    existing = [int(value) for value in re.findall(r"^### 第(\d+)章：", text, re.MULTILINE)]
    if chapter < 1 or chapter > completed or (chapter not in existing and chapter != max(existing, default=0) + 1):
        raise TaoRuntimeError("thought_progress_update_failed", "cannot record a future or skipped chapter")
    function = payload.get("function")
    if chapter not in existing and function not in VALID_FUNCTIONS:
        raise TaoRuntimeError("thought_progress_update_failed", "new progress entries require a valid outline thought function")
    function = function or "recovery"
    detail = payload.get("summary") or "立场：{position}；代价：{cost}；后果：{consequence}".format(
        position=payload.get("position", "未记录"), cost=payload.get("cost", "未记录"), consequence=payload.get("consequence", "未记录"),
    )
    block = "### 第{}章：{}\n- {}\n".format(chapter, function, detail)
    pattern = re.compile(r"^### 第{}章：.*?(?=^### 第\d+章：|^## |\Z)".format(chapter), re.MULTILINE | re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(block + "\n", text, count=1)
    else:
        text = text.replace("## 下一检验", block + "\n## 下一检验", 1)
    updates = (
        ("当前人物立场", payload.get("position"), False),
        ("已出现反证", payload.get("counterevidence"), True),
        ("已付代价", payload.get("cost"), True),
        ("下一检验", payload.get("next_test"), False),
    )
    for heading, value, keep_history in updates:
        if not value:
            continue
        section_pattern = re.compile(r"(^## {}\s*$\n)(.*?)(?=^## |\Z)".format(re.escape(heading)), re.MULTILINE | re.DOTALL)
        section = section_pattern.search(text)
        if not section:
            raise TaoRuntimeError("thought_progress_update_failed", "thought progress section is missing", {"section": heading})
        entry = "- 章节 {}：{}".format(chapter, value)
        old_body = section.group(2).strip()
        if keep_history:
            old_body = re.sub(r"^- 章节 {}：.*$".format(chapter), entry, old_body, flags=re.MULTILINE)
            if not re.search(r"^- 章节 {}：".format(chapter), old_body, re.MULTILINE):
                old_body = "{}\n{}".format(old_body if old_body not in {"", "无。"} else "", entry).strip()
            new_body = old_body
        else:
            new_body = entry
        text = text[:section.start()] + section.group(1) + new_body + "\n\n" + text[section.end():]
    progress.write_text(text, encoding="utf-8")
    return {"ok": True, "chapter": chapter, "path": str(progress), "updated": chapter in existing}


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TaoRuntimeError("input_invalid", "JSON input must be an object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("match", "ensure", "summarize", "map-evidence", "advance"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--resource-root", type=Path)
    parser.add_argument("--mode", choices=("long", "short"))
    args = parser.parse_args(argv)
    try:
        payload = _read_payload()
        if args.mode:
            payload["mode"] = args.mode
        manifest = load_manifest(args.manifest)
        resource_root = args.resource_root or Path(__file__).resolve().parent.parent
        cards = load_cards(resource_root, manifest)
        commands = {
            "match": lambda: match_cards(payload, cards),
            "ensure": lambda: ensure(payload, args.project_root, cards),
            "summarize": lambda: summarize(payload, args.project_root, cards),
            "map-evidence": lambda: map_evidence(payload, cards),
            "advance": lambda: advance(payload, args.project_root),
        }
        print(json.dumps({"ok": True, "command": args.command, "result": commands[args.command]()}, ensure_ascii=False))
        return 0
    except (TaoRuntimeError, json.JSONDecodeError) as exc:
        error = exc if isinstance(exc, TaoRuntimeError) else TaoRuntimeError("input_invalid", "stdin is not valid JSON")
        print(json.dumps({"ok": False, "error": {"code": error.code, "message": error.message, "details": error.details}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
