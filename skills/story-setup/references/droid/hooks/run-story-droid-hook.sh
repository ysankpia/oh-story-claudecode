#!/usr/bin/env bash
set -u

event="${1:-}"
root="${FACTORY_PROJECT_DIR:-}"
[ -n "$event" ] && [ -n "$root" ] || exit 0
hook="$root/.factory/hooks/story_droid_hook.py"
[ -f "$hook" ] || exit 0

for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "" >/dev/null 2>&1; then
    FACTORY_PROJECT_DIR="$root" STORY_TARGET_CLI=droid exec "$candidate" "$hook" "$event"
  fi
done

exit 0
