#!/usr/bin/env python3
"""Repository entry point for the bundled story-tao runtime."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


IMPLEMENTATION = Path(__file__).resolve().parent.parent / "skills/story-tao/scripts/story_tao_runtime.py"
SPEC = importlib.util.spec_from_file_location("story_tao_runtime_impl", IMPLEMENTATION)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load bundled story-tao runtime")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

for exported in dir(MODULE):
    if not exported.startswith("_"):
        globals()[exported] = getattr(MODULE, exported)


if __name__ == "__main__":
    raise SystemExit(MODULE.main())
