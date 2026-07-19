#!/usr/bin/env bash
# test-droid-hooks.sh - synthetic Factory hook contract tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

ROOT="$TMP_DIR/story-project"
HOOKS="$ROOT/.factory/hooks"
HOOK="$HOOKS/story_droid_hook.py"
mkdir -p "$HOOKS"
cp "$REPO_ROOT/skills/story-setup/references/codex/hooks/story_codex_hook.py" "$HOOK"
cp "$REPO_ROOT/skills/story-setup/references/droid/hooks/run-story-droid-hook.sh" "$HOOKS/"
chmod +x "$HOOKS/run-story-droid-hook.sh" "$HOOK"
git -C "$ROOT" init -q
git -C "$ROOT" config user.email droid-hook@example.invalid
git -C "$ROOT" config user.name droid-hook-test

run_hook() {
  local event="$1" payload="$2"
  (cd "$ROOT" && printf '%s' "$payload" | FACTORY_PROJECT_DIR="$ROOT" STORY_TARGET_CLI=droid python3 "$HOOK" "$event")
}

assert_json() {
  python3 -c 'import json,sys; json.loads(sys.stdin.buffer.read().decode("utf-8"))' >/dev/null
}

assert_denied() {
  local out="$1" label="$2"
  printf '%s' "$out" | assert_json || fail "$label did not emit JSON: $out"
  printf '%s' "$out" | python3 -c 'import json,sys; o=json.loads(sys.stdin.buffer.read().decode("utf-8")); h=o.get("hookSpecificOutput",{}); assert h.get("hookEventName")=="PreToolUse" and h.get("permissionDecision")=="deny"' || fail "$label was not denied: $out"
}

assert_context() {
  local out="$1" label="$2"
  printf '%s' "$out" | assert_json || fail "$label did not emit JSON: $out"
  printf '%s' "$out" | python3 -c 'import json,sys; o=json.loads(sys.stdin.buffer.read().decode("utf-8")); assert o.get("hookSpecificOutput",{}).get("additionalContext")' || fail "$label missing context: $out"
}

mkdir -p "$ROOT/book/正文" "$ROOT/book/大纲" "$ROOT/book/设定" "$ROOT/book/追踪"
out="$(run_hook pre-tool-prose-guard '{"tool_name":"Create","tool_input":{"file_path":"book/正文/第001章_开端.md","content":"正文"}}')"
assert_denied "$out" "Factory Create without outline"
: > "$ROOT/book/大纲/细纲_第1章.md"
out="$(run_hook pre-tool-prose-guard '{"tool_name":"Create","tool_input":{"file_path":"book/正文/第001章_开端.md","content":"正文"}}')"
[ -z "$out" ] || fail "Factory Create with outline should pass: $out"

out="$(run_hook pre-tool-prose-guard '{"tool_name":"Execute","tool_input":{"command":"touch book/正文/第2章.md"}}')"
assert_denied "$out" "Factory Execute without outline"
echo "  OK Factory PreToolUse guard"

cat > "$ROOT/book/正文/第001章_开端.md" <<'TXT'
# 第001章

作为AI，我无法继续写作。
TXT
out="$(run_hook post-tool-prose-check '{"tool_name":"Edit","tool_input":{"file_path":"book/正文/第001章_开端.md"}}')"
assert_context "$out" "Factory PostToolUse prose check"
echo "$out" | grep -q 'AI' || fail "Factory PostToolUse missed prose finding"
echo "  OK Factory PostToolUse prose backstop"

cat > "$ROOT/.story-deployed" <<'TXT'
deployed_at: 2026-07-20T00:00:00Z
agents_version: 23
setup_skill_version: 1.6.0
target_cli: codex
resolver_strategy: project-local
references_dir: .codex/skills/story-setup/references/agent-references
TXT
printf 'book\n' > "$ROOT/.active-book"
printf '# 上下文\n' > "$ROOT/book/追踪/上下文.md"
out="$(run_hook session-start '{"hook_event_name":"SessionStart"}')"
assert_context "$out" "Factory SessionStart"
echo "$out" | grep -q 'Droid' || fail "Factory SessionStart did not use Droid wording"

for event in pre-compact stop; do
  out="$(run_hook "$event" "{\"hook_event_name\":\"$event\"}")"
  printf '%s' "$out" | assert_json || fail "$event returned invalid JSON: $out"
done
echo "  OK Factory session lifecycle"

nested="$ROOT/nested/a/b"
mkdir -p "$nested"
out="$(cd "$nested" && printf '%s' '{"tool_name":"Create","tool_input":{"file_path":"book/正文/第003章_嵌套.md","content":"正文"}}' | FACTORY_PROJECT_DIR="$ROOT" bash "$HOOKS/run-story-droid-hook.sh" pre-tool-prose-guard)"
assert_denied "$out" "Factory launcher from nested cwd"
echo "  OK Factory launcher root resolution"

echo "OK: Droid hook synthetic tests passed"
