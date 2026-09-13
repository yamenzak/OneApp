#!/bin/bash
#
# What a web session needs to run the guards, and nothing more.
#
# There is no bench here and there does not need to be one: `tests/conftest.py`
# stubs `frappe`, so the whole pytest suite is pure logic. What the suite does
# read off a bench is *source* — Frappe's fieldtype tuple, its filter table, its
# and ERPNext's translation catalogues — and that is four sparse checkouts'
# worth of files, not MariaDB and a built site.
#
# Without it 124 guards skip, and a guard that never runs is one that rots: the
# prepaint theme check asserted a file that had stopped being checked in and
# nobody heard about it for months, because CI could not reach the assertion.
#
# Local machines are left alone. A developer here has a real bench at
# `/home/frappe/bench1` and the defaults already find it.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BENCH="$(dirname "$REPO")/bench"

echo "== python =="
# What .github/workflows/tests.yml installs, so the two agree.
pip install --quiet pytest requests packaging

echo "== frontend =="
# `install` and not `--frozen-lockfile`: the container is cached after this
# runs, so a warm session re-resolves nothing.
for app in oneapp oneapp_control; do
  if [ -f "$REPO/apps/$app/frontend/package.json" ]; then
    (cd "$REPO/apps/$app/frontend" && yarn install --silent)
  fi
done

echo "== upstream source =="
# Blobless and sparse: these are read for four directories, and a full clone of
# both is some gigabytes for files nothing opens.
clone() {
  local url="$1" dir="$2"; shift 2
  if [ ! -d "$dir/.git" ]; then
    git clone --depth 1 --filter=blob:none --sparse "$url" "$dir"
    (cd "$dir" && git sparse-checkout set "$@")
  else
    # Already here from a cached container. Moved to today's upstream rather
    # than left alone: these guards exist to catch upstream drifting, and a
    # copy frozen whenever the image was built cannot see any.
    (cd "$dir" \
      && git sparse-checkout set "$@" \
      && git fetch --depth 1 -q origin HEAD \
      && git checkout -q --detach FETCH_HEAD)
  fi
}

mkdir -p "$BENCH/apps"
clone https://github.com/frappe/frappe.git "$BENCH/apps/frappe" \
  frappe/model frappe/database frappe/public/js/frappe/ui/filters frappe/locale
clone https://github.com/frappe/erpnext.git "$BENCH/apps/erpnext" \
  erpnext/public/js erpnext/locale

# Two conventions find Frappe's source and both are in the tests: `i18n.BENCH`
# wants a bench layout, and `test_field_types` wants a checkout beside the repo.
# One clone, linked, rather than two copies that can drift apart.
ln -sfn "$BENCH/apps/frappe" "$(dirname "$REPO")/frappe"

echo "export ONEAPP_BENCH=\"$BENCH\"" >> "$CLAUDE_ENV_FILE"

# No `vite build` here, deliberately. It would clear the last 13 skips, and it
# costs 49s per SPA and then gets cached into the container image — where it
# goes stale against source the next session edits. The design-token guards
# compare what the source references against what the build emitted, so a stale
# build does not skip, it fails confusingly. Their own skip says `run vite
# build`, which is the honest state and an actionable sentence.

echo "== ready =="
