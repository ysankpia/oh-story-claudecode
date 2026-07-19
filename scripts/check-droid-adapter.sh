#!/usr/bin/env bash
# check-droid-adapter.sh - validate the repository and deployable Factory adapter.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SETUP_DIR="$REPO_ROOT/skills/story-setup"
DROID_DIR="$REPO_ROOT/droids"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

[ -L "$REPO_ROOT/.factory/skills" ] || fail ".factory/skills must be a relative symlink"
[ "$(readlink "$REPO_ROOT/.factory/skills")" = "../skills" ] || fail ".factory/skills must point to ../skills"
[ -L "$REPO_ROOT/.factory/droids" ] || fail ".factory/droids must be a relative symlink"
[ "$(readlink "$REPO_ROOT/.factory/droids")" = "../droids" ] || fail ".factory/droids must point to ../droids"

skill_count="$(find "$REPO_ROOT/skills" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')"
[ "$skill_count" = "14" ] || fail "expected 14 skills, got $skill_count"
droid_count="$(find "$DROID_DIR" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')"
[ "$droid_count" = "7" ] || fail "expected 7 custom droids, got $droid_count"

python3 - "$REPO_ROOT" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
plugin = json.loads((root / ".factory-plugin/plugin.json").read_text(encoding="utf-8"))
assert plugin["name"] == "oh-story"
assert plugin["version"] == "0.11.0"

allowed_tools = {"Read", "Glob", "Grep", "Create", "Edit", "Execute", "WebSearch", "FetchUrl"}
templates = {path.stem for path in (root / "skills/story-setup/references/templates/agents").glob("*.md")}
droids = {path.stem for path in (root / "droids").glob("*.md")}
assert droids == templates
for path in sorted((root / "droids").glob("*.md")):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name}: missing frontmatter"
    frontmatter = match.group(1)
    assert re.search(rf"^name:\s*{re.escape(path.stem)}$", frontmatter, re.M)
    assert re.search(r"^description:\s*\S", frontmatter, re.M)
    assert re.search(r"^model:\s*inherit$", frontmatter, re.M)
    tools_match = re.search(r"^tools:\s*(\[.*\])$", frontmatter, re.M)
    if tools_match:
        tools = json.loads(tools_match.group(1))
        assert set(tools) <= allowed_tools, f"{path.name}: unsupported tools {tools}"
    assert ".claude/skills/story-setup/references/agent-references/" not in text
    assert ".factory/skills/story-setup/references/agent-references/" in text

hooks = json.loads((root / "skills/story-setup/references/droid/hooks/hooks.json").read_text(encoding="utf-8"))
assert set(hooks["hooks"]) == {"SessionStart", "PreToolUse", "PostToolUse", "PreCompact", "Stop"}
for blocks in hooks["hooks"].values():
    for block in blocks:
        for hook in block["hooks"]:
            command = hook["command"]
            assert "$FACTORY_PROJECT_DIR/.factory/hooks/run-story-droid-hook.sh" in command
PY

python3 "$SCRIPT_DIR/generate-droid-agents.py" --check
python3 "$SETUP_DIR/scripts/generate-droid-agents.py" --dest "$TMP_DIR/droids"
diff -ru "$DROID_DIR" "$TMP_DIR/droids" >/dev/null || fail "bundled Droid generator is not deterministic"

cat > "$TMP_DIR/existing.json" <<'JSON'
{
  "custom": {"keep": true},
  "hooks": {
    "SessionStart": [
      {"hooks": [{"type": "command", "command": "echo user"}]},
      {"hooks": [{"type": "command", "command": "bash \"$FACTORY_PROJECT_DIR/.factory/hooks/run-story-droid-hook.sh\" old"}]}
    ],
    "Notification": [{"hooks": [{"type": "command", "command": "echo notify"}]}]
  }
}
JSON
python3 "$SETUP_DIR/scripts/merge-droid-hooks.py" \
  --existing "$TMP_DIR/existing.json" \
  --template "$SETUP_DIR/references/droid/hooks/hooks.json" \
  --output "$TMP_DIR/merged.json"
python3 "$SETUP_DIR/scripts/merge-droid-hooks.py" \
  --existing "$TMP_DIR/merged.json" \
  --template "$SETUP_DIR/references/droid/hooks/hooks.json" \
  --output "$TMP_DIR/merged-again.json"
cmp "$TMP_DIR/merged.json" "$TMP_DIR/merged-again.json" >/dev/null || fail "Droid hook merge must be idempotent"
python3 - "$TMP_DIR/merged.json" <<'PY'
import json
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert document["custom"] == {"keep": True}
commands = [
    hook["command"]
    for blocks in document["hooks"].values()
    if isinstance(blocks, list)
    for block in blocks
    if isinstance(block, dict) and isinstance(block.get("hooks"), list)
    for hook in block["hooks"]
    if isinstance(hook, dict) and isinstance(hook.get("command"), str)
]
assert "echo user" in commands and "echo notify" in commands
managed = [command for command in commands if ".factory/hooks/run-story-droid-hook.sh" in command]
assert len(managed) == 6, managed
PY

grep -q 'FACTORY_PROJECT_DIR' "$SETUP_DIR/references/droid/hooks/run-story-droid-hook.sh" || fail "Droid launcher must use FACTORY_PROJECT_DIR"
grep -q 'STORY_TARGET_CLI=droid' "$SETUP_DIR/references/droid/hooks/run-story-droid-hook.sh" || fail "Droid launcher must select Droid messages"
grep -q 'target_cli.*droid' "$SETUP_DIR/SKILL.md" || fail "story-setup must expose Droid target_cli"

echo "OK: Droid adapter checks passed"
