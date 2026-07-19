#!/usr/bin/env bash
# Verify the shared Claude Code JavaScript core and Codex Python hook agree.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_CORE="$ROOT/skills/story-setup/references/templates/hooks/story_hook_core.js"
CLAUDE_CLI="$ROOT/skills/story-setup/references/templates/hooks/story_hook_cli.js"
CODEX_HOOK="$ROOT/skills/story-setup/references/codex/hooks/story_codex_hook.py"

fail() { echo "FAIL: $*" >&2; exit 1; }

for file in "$CLAUDE_CORE" "$CLAUDE_CLI" "$CODEX_HOOK"; do
  [ -f "$file" ] || fail "missing dual-platform hook asset: $file"
done

node --check "$CLAUDE_CORE"
node --check "$CLAUDE_CLI"
python3 -m py_compile "$CODEX_HOOK"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ohstory-dual-parity.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/fixtures.json" <<'JSON'
[
  "她不是害怕，而是终于明白了。",
  "他抬手推开门，雨声灌进走廊。",
  "不是退路，是她亲手选的路。\n\n话音落下。",
  ""
]
JSON

node - "$CLAUDE_CORE" "$TMP_DIR/fixtures.json" > "$TMP_DIR/claude.txt" <<'JS'
const core = require(process.argv[2]);
const fixtures = require(process.argv[3]);
for (const text of fixtures) {
  process.stdout.write(JSON.stringify(core.proseNetFindings(text)) + "\n");
}
JS

python3 - "$CODEX_HOOK" "$TMP_DIR/fixtures.json" > "$TMP_DIR/codex.txt" <<'PY'
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("story_codex_hook", sys.argv[1])
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

for text in json.load(open(sys.argv[2], encoding="utf-8")):
    print(json.dumps(module.prose_net_findings(text), ensure_ascii=False, separators=(",", ":")))
PY

if ! diff -u "$TMP_DIR/claude.txt" "$TMP_DIR/codex.txt"; then
  fail "Claude Code and Codex prose-net findings diverged"
fi

node - "$CLAUDE_CORE" > "$TMP_DIR/claude-commit.txt" <<'JS'
const core = require(process.argv[2]);
for (const command of ["git commit -m x", "git status", "git -C book commit --amend"]) {
  process.stdout.write(String(core.isGitCommitCommand(command)) + "\n");
}
JS

python3 - "$CODEX_HOOK" > "$TMP_DIR/codex-commit.txt" <<'PY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("story_codex_hook", sys.argv[1])
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

for command in ("git commit -m x", "git status", "git -C book commit --amend"):
    print(str(module.is_git_commit_command(command)).lower())
PY

if ! diff -u "$TMP_DIR/claude-commit.txt" "$TMP_DIR/codex-commit.txt"; then
  fail "Claude Code and Codex commit detection diverged"
fi

echo "OK: Claude Code and Codex hook parity passed"
