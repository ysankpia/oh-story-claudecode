#!/usr/bin/env python3
"""Repository entry point for the bundled story-setup Droid generator."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "skills/story-setup/scripts/generate-droid-agents.py"


def main() -> None:
    arguments = list(sys.argv[1:])
    if "--source" not in arguments:
        arguments[0:0] = [
            "--source",
            str(REPO_ROOT / "skills/story-setup/references/templates/agents"),
        ]
    if "--dest" not in arguments:
        arguments[0:0] = ["--dest", str(REPO_ROOT / "droids")]
    os.execv(sys.executable, [sys.executable, str(GENERATOR), *arguments])


if __name__ == "__main__":
    main()
