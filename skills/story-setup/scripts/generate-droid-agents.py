#!/usr/bin/env python3
"""Generate Factory custom droids from the canonical Claude agent templates."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TOOL_MAP = {
    "Read": ["Read"],
    "Glob": ["Glob"],
    "Grep": ["Grep"],
    "Write": ["Create", "Edit"],
    "Edit": ["Edit"],
    "Bash": ["Execute"],
    "WebSearch": ["WebSearch"],
    "WebFetch": ["FetchUrl"],
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    lines = text[4:end].splitlines()
    data: dict[str, str] = {}
    index = 0
    while index < len(lines):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", lines[index])
        if not match:
            index += 1
            continue
        key, value = match.group(1), (match.group(2) or "").rstrip()
        if value in {"|", ">", ">-"}:
            block: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index] or lines[index][0].isspace()):
                block.append(lines[index][2:] if lines[index].startswith("  ") else lines[index].lstrip())
                index += 1
            data[key] = "\n".join(block).strip()
            continue
        data[key] = value.strip().strip('"').strip("'")
        index += 1
    return data, text[end + len("\n---\n") :].lstrip()


def parse_tools(raw: str) -> list[str]:
    source = [item.strip().strip('"').strip("'") for item in raw.strip("[]").split(",")]
    result: list[str] = []
    for name in source:
        if not name:
            continue
        mapped = TOOL_MAP.get(name)
        if mapped is None:
            raise ValueError(f"unsupported Claude tool for Droid: {name}")
        for tool in mapped:
            if tool not in result:
                result.append(tool)
    return result


def adapt_body(body: str, name: str) -> str:
    adapted = body.replace(
        ".claude/skills/story-setup/references/agent-references/",
        ".factory/skills/story-setup/references/agent-references/",
    )
    adapted = adapted.replace("当前 Claude 部署", "当前 Droid 部署")
    adapted = adapted.replace("Claude Code subagent", "Droid custom droid")
    return (
        adapted.rstrip()
        + "\n\n---\n\n"
        + "Droid adaptation notes:\n"
        + f'- Parent workflows invoke this droid through the Task tool with `subagent_type: "{name}"`.\n'
        + "- A custom droid cannot spawn another subagent. Return blockers and checkpoint data to the parent instead.\n"
        + "- Use only `.factory/skills/story-setup/references/agent-references/` for deployed references.\n"
        + "- For long work, preserve file checkpoints before returning so the parent can resume without replaying completed work.\n"
    )


def render_file(path: Path) -> tuple[str, str]:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    name = meta.get("name") or path.stem
    if name != path.stem or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) is None:
        raise ValueError(f"{path}: unsafe or mismatched agent name {name!r}")
    description = meta.get("description", "").strip()
    if not description:
        raise ValueError(f"{path}: missing description")
    tools = parse_tools(meta.get("tools", ""))
    frontmatter = [
        "---",
        f"name: {name}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "model: inherit",
    ]
    if tools:
        frontmatter.append("tools: " + json.dumps(tools, ensure_ascii=False))
    frontmatter.extend(["---", ""])
    return f"{name}.md", "\n".join(frontmatter) + adapt_body(body, name)


def publish(rendered: dict[str, str], destination: Path) -> None:
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError(f"destination must be a real directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".droids.staging-", dir=destination.parent))
    backup = Path(tempfile.mkdtemp(prefix=".droids.backup-", dir=destination.parent))
    try:
        for filename, content in rendered.items():
            (staging / filename).write_text(content, encoding="utf-8", newline="\n")
        existing = list(destination.glob("*.md"))
        for path in existing:
            if path.is_dir() and not path.is_symlink():
                raise IsADirectoryError(path)
            shutil.copy2(path, backup / path.name)
        try:
            for filename in rendered:
                os.replace(staging / filename, destination / filename)
            for path in existing:
                if path.name not in rendered:
                    path.unlink()
        except BaseException:
            for path in destination.glob("*.md"):
                if path.name not in {item.name for item in backup.iterdir()}:
                    path.unlink(missing_ok=True)
            for path in backup.iterdir():
                shutil.copy2(path, destination / path.name)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=SKILL_ROOT / "references/templates/agents",
    )
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    sources = sorted(args.source.glob("*.md"))
    if not sources:
        raise SystemExit(f"no agent templates found in {args.source}")
    rendered = dict(render_file(path) for path in sources)
    if args.check:
        actual = {path.name: path.read_text(encoding="utf-8") for path in args.dest.glob("*.md")}
        if actual != rendered:
            raise SystemExit("generated Droid definitions are stale")
    else:
        publish(rendered, args.dest)
        print(f"Generated {len(rendered)} Droid definitions in {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
