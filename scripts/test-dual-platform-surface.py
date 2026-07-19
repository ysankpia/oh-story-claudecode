#!/usr/bin/env python3
"""Regression checks for the Claude Code and Codex-only public surface."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RETIRED_TERMS = ("opencode", "zcode", "openclaw", "reasonix", "workbuddy")
RETIRED_PATHS = (
    ".zcode-plugin",
    "marketplace.json",
    "reasonix-plugin.json",
    ".github/workflows/publish-clawhub.yml",
    ".github/workflows/sync-opencode.yml",
    "scripts/check-openclaw-skills.sh",
    "scripts/check-opencode-adapter.sh",
    "scripts/check-reasonix-adapter.sh",
    "scripts/check-zcode-adapter.sh",
    "scripts/sync-opencode.py",
    "scripts/test-opencode-cli-e2e.sh",
    "scripts/test-opencode-plugin.mjs",
    "scripts/test-zcode-hooks.sh",
    "skills/story-setup/references/generic",
    "skills/story-setup/references/openclaw",
    "skills/story-setup/references/opencode",
    "skills/story-setup/references/zcode",
)
PUBLIC_TEXT_ROOTS = ("README.md", "README_EN.md", "CONTRIBUTING.md", ".github", "skills")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def public_text_files() -> list[Path]:
    paths: list[Path] = []
    for relative in PUBLIC_TEXT_ROOTS:
        path = REPO_ROOT / relative
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and "__pycache__" not in candidate.parts
            )
    return paths


def main() -> int:
    skills = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    require(len(skills) == 14, "the Claude/Codex distribution must retain all 14 skills")
    require((REPO_ROOT / ".claude-plugin/marketplace.json").is_file(), "Claude marketplace must remain")
    require((REPO_ROOT / ".agents/skills").is_symlink(), "Codex skills discovery symlink must remain")

    for relative in RETIRED_PATHS:
        require(not (REPO_ROOT / relative).exists(), "retired platform asset remains: {}".format(relative))

    setup = (REPO_ROOT / "skills/story-setup/SKILL.md").read_text(encoding="utf-8").lower()
    require("claude-code" in setup and "codex" in setup, "story-setup must support Claude and Codex")
    for term in RETIRED_TERMS:
        require(term not in setup, "story-setup still exposes retired platform: {}".format(term))

    for skill in skills:
        text = skill.read_text(encoding="utf-8").lower()
        for term in RETIRED_TERMS:
            require(term not in text, "{} still exposes retired platform: {}".format(skill, term))

    for path in public_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in RETIRED_TERMS:
            require(term not in text, "public surface still exposes {}: {}".format(term, path))

    print("OK: public distribution is limited to Claude Code and Codex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
