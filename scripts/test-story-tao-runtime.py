#!/usr/bin/env python3
"""Behavior tests for the executable story-tao runtime."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import story_tao_runtime as runtime


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = runtime.load_manifest(Path(__file__).resolve().with_name("current-contract.json"))
CARDS = runtime.load_cards(ROOT, MANIFEST)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def active_case(domain: str, expected: str) -> None:
    result = runtime.match_cards(
        {
            "domains": [domain],
            "evidence": ["具体行动造成了可见后果"],
            "positions": ["主角的立场", "反方的利益"],
            "counterevidence": ["反方的选择也有现实收益"],
            "reader_contract": "保留题材兑现",
        },
        CARDS,
    )
    require(result["status"] == "active", "{} case must be active".format(domain))
    require(result["primary_operator"] == expected, "{} case chose {}".format(domain, result["primary_operator"]))


def main() -> int:
    active_case("self-knowledge", "tao-10-self-knowledge")
    active_case("governance-restraint", "tao-46-small-fish-governance")
    active_case("war-violence", "tao-31-war-aftermath")
    active_case("governance-knowledge", "tao-48-knowledge-and-governance")

    provisional = runtime.match_cards({"genre": "复仇"}, CARDS)
    require(provisional["status"] == "provisional", "genre-only input must remain provisional")
    require(provisional["primary_operator"] is None, "genre-only input must not invent a primary card")

    try:
        runtime.match_cards({"preferred_operator": "tao-missing"}, CARDS)
    except runtime.TaoRuntimeError as exc:
        require(exc.code == "unknown_operator", "unknown operator must use a structured error")
    else:
        raise AssertionError("unknown operator must fail")

    try:
        runtime.match_cards(
            {"preferred_operator": "tao-10-self-knowledge", "secondary_operator": "tao-10-self-knowledge"},
            CARDS,
        )
    except runtime.TaoRuntimeError as exc:
        require(exc.code == "same_axis_secondary", "same-axis secondary must fail")
    else:
        raise AssertionError("same-axis secondary must fail")

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        ensured = runtime.ensure(
            {
                "mode": "long",
                "domains": ["self-knowledge"],
                "evidence": ["具体行动造成了可见后果"],
                "positions": ["主角立场", "反方利益"],
                "counterevidence": ["反方仍有现实收益"],
            },
            project,
            CARDS,
        )
        require(ensured["status"] == "active", "complete evidence must create an active contract")
        contract = project / "设定/思想命题.md"
        require(contract.is_file(), "long contract must be created")
        require((project / "追踪/思想进展.md").is_file(), "long progress state must be created")
        summary = runtime.summarize({"mode": "long"}, project, CARDS)
        require(summary["primary_operator"] == "tao-10-self-knowledge", "summary must consume the contract")
        require(summary["thought_gate"] == "pass", "active contracts must yield a passing Thought Gate")

        advanced = runtime.advance(
            {
                "chapter": 1,
                "completed_chapter": 1,
                "function": "choice",
                "position": "主角开始怀疑惯常胜法",
                "counterevidence": "反方的克制策略暂时奏效",
                "cost": "失去一项关系资源",
                "consequence": "反方获得谈判空间",
                "next_test": "按第二章细纲检验是否继续控制",
            },
            project,
        )
        require(advanced["ok"], "advance must update progress")
        runtime.advance({"chapter": 1, "completed_chapter": 1, "summary": "修订后的事实"}, project)
        progress = (project / "追踪/思想进展.md").read_text(encoding="utf-8")
        require(progress.count("第1章：") == 1, "advance must be idempotent per chapter")
        require("主角开始怀疑惯常胜法" in progress, "advance must persist the latest position")
        require("反方的克制策略暂时奏效" in progress, "advance must persist counterevidence")
        require("失去一项关系资源" in progress, "advance must persist paid costs")
        require("按第二章细纲检验是否继续控制" in progress, "advance must persist the next test")

        try:
            runtime.advance({"chapter": 3, "completed_chapter": 1}, project)
        except runtime.TaoRuntimeError as exc:
            require(exc.code == "thought_progress_update_failed", "skipped chapter must fail closed")
        else:
            raise AssertionError("skipped chapter must fail")

        old = contract.read_text(encoding="utf-8").replace("status: active", "status: confirmed")
        contract.write_text(old, encoding="utf-8")
        migrated = runtime.ensure({"mode": "long"}, project, CARDS)
        require(migrated["status"] == "active", "confirmed contracts must migrate to active")
        require("status: active" in contract.read_text(encoding="utf-8"), "migration must persist active status")
        contract.write_text(re.sub(r"^source_chapters:.*\n", "", contract.read_text(encoding="utf-8"), flags=re.MULTILINE), encoding="utf-8")
        runtime.ensure({"mode": "long"}, project, CARDS)
        require("source_chapters: [33]" in contract.read_text(encoding="utf-8"), "known legacy contracts must recover source chapters")
        contract.write_text(contract.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: 99"), encoding="utf-8")
        try:
            runtime.ensure({"mode": "long"}, project, CARDS)
        except runtime.TaoRuntimeError as exc:
            require(exc.code == "thought_contract_blocked", "unsupported schemas must fail closed")
        else:
            raise AssertionError("unsupported schemas must fail")

    with tempfile.TemporaryDirectory() as tmp:
        short_project = Path(tmp)
        short_result = runtime.ensure(
            {
                "mode": "short",
                "domains": ["identity-relationship"],
                "evidence": ["最终选择改变了人物关系"],
                "positions": ["主角立场", "反方立场"],
                "counterevidence": ["反例带来现实收益"],
            },
            short_project,
            CARDS,
        )
        require(short_result["status"] == "active", "short ensure must create an active contract from complete evidence")
        require((short_project / "思想命题.md").is_file(), "short contract must be created at project root")
        require(runtime.summarize({"mode": "short"}, short_project, CARDS)["thought_gate"] == "pass", "short summary must expose Thought Gate")

    mapped = runtime.map_evidence(
        {"operator_ids": ["tao-10-self-knowledge", "tao-31-war-aftermath", "tao-48-knowledge-and-governance"], "evidence": [{"chapter": 1, "text": "证据一"}, {"chapter": 2, "text": "证据二"}, {"chapter": 3, "text": "证据三"}]},
        CARDS,
    )
    require(len(mapped["operators"]) == 3, "map-evidence must return exactly three cards")
    require(mapped["status"] == "active", "three located evidence items must activate mapping")
    require("不证明原作者受《道德经》影响" in mapped["disclaimer"], "mapping disclaimer must be present")

    cli = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().with_name("story_tao_runtime.py")), "match"],
        input=json.dumps({"domains": ["self-knowledge"], "evidence": ["证据"], "positions": ["甲", "乙"], "counterevidence": ["反证"]}, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    require(cli.returncode == 0, "runtime CLI must accept JSON on stdin")
    require(json.loads(cli.stdout)["result"]["primary_operator"] == "tao-10-self-knowledge", "runtime CLI must emit structured JSON")

    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "story-tao"
        shutil.copytree(ROOT / "skills/story-tao", bundle)
        bundled_cli = subprocess.run(
            [sys.executable, str(bundle / "scripts/story_tao_runtime.py"), "match"],
            input=json.dumps({"domains": ["war-violence"], "evidence": ["证据"], "positions": ["甲", "乙"], "counterevidence": ["反证"]}, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
        require(bundled_cli.returncode == 0, "standalone skill bundle must run without repository files")
        require(json.loads(bundled_cli.stdout)["result"]["primary_operator"] == "tao-31-war-aftermath", "standalone bundle must load its own cards")
    print("OK: story-tao runtime match, ensure, summarize, map-evidence, and advance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
