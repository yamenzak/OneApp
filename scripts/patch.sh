#!/usr/bin/env bash
#
# Build a patch you can apply to a running Frappe Cloud bench.
#
# press.api.bench.apply_patch hands the diff to the agent, which runs
# `git apply` inside the running container, then restarts. Seconds, no image
# build, no bench move.
#
#   scripts/patch.sh oneapp_control [BASE]   > fix.patch
#
# BASE defaults to origin/main, so the patch carries everything on this branch
# that is not yet deployed.
#
# **The next deploy silently reverts whatever you apply this way**, because
# images are built from git. Use it to look at something now, not to ship.
#
# The SPA is the part people get wrong. `build_assets` runs Frappe's own
# bundler, which knows nothing about Vite — so a patch containing only frontend
# *source* changes nothing you can see. The built output has to travel in the
# patch itself, and it is gitignored, so it needs forcing in explicitly.

set -euo pipefail

APP="${1:-oneapp_control}"
BASE="${2:-origin/main}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT/apps/$APP"

[ -d "$APP_DIR" ] || { echo "No app at $APP_DIR" >&2; exit 1; }

# Built output, matching what the mirror repo's image would contain.
BUILT=(
  "$APP/$APP/public/frontend"
  "$APP/$APP/www"
)

cd "$ROOT"

if [ ! -d "$APP_DIR/$APP/public/frontend" ]; then
  echo "No build output — run 'npx vite build' in apps/$APP/frontend first." >&2
  exit 1
fi

# Paths inside the patch must be relative to the app repo root, because the
# agent applies it from apps/<app> in the container — not from a monorepo.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git diff "$BASE" -- "apps/$APP" > "$tmp/src.patch"

# -f because the build output is gitignored on purpose; it belongs in the patch
# even though it must never be committed.
git add -Af "${BUILT[@]/#/apps/}" 2>/dev/null || true

# __pycache__ sits inside www/ and is compiled per interpreter version, so a
# .pyc from here is binary noise that makes `git apply` reject the whole patch.
# The :(glob) magic is load-bearing — a bare ** in a pathspec does not recurse.
git reset -q -- ":(glob)apps/$APP/**/__pycache__/**" 2>/dev/null || true

# --binary is required, not cosmetic: the SPA bundle ships woff2 fonts, and
# without it git emits a placeholder line instead of the content and `git apply`
# fails with "cannot apply binary patch ... without full index line".
git diff --cached --binary -- "${BUILT[@]/#/apps/}" > "$tmp/built.patch"
git reset -q -- "${BUILT[@]/#/apps/}" 2>/dev/null || true

cat "$tmp/src.patch" "$tmp/built.patch" | sed -E "s#([ab])/apps/$APP/#\1/#g"
