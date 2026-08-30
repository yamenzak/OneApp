#!/usr/bin/env python3
"""Is a newer frappe-ui out, and what changed?

Run on demand — not from the test suite, which must not depend on the network
or fail because someone else published a release.

Everything the guards check is read out of the installed package: prop and slot
declarations, literal unions, retired tokens, the settings dialog's geometry.
So upgrading is the moment they earn their keep — run the suite straight after,
and whatever the new version renamed shows up as a failure rather than as a
blank page.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ("oneapp", "oneapp_control")


def installed(app: str) -> str:
    pkg = ROOT / f"apps/{app}/frontend/node_modules/frappe-ui/package.json"
    return json.loads(pkg.read_text())["version"] if pkg.exists() else "(not installed)"


def pinned(app: str) -> str:
    pkg = json.loads((ROOT / f"apps/{app}/frontend/package.json").read_text())
    return pkg["dependencies"]["frappe-ui"]


def published() -> dict:
    out = subprocess.run(
        ["npm", "screen", "frappe-ui", "dist-tags", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode:
        raise SystemExit(f"npm screen failed: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout)


def main() -> int:
    tags = published()
    # `latest` still points at the v0 line; the v1 series ships under `beta`.
    newest = tags.get("beta", "")
    print(f"published beta:   {newest}")
    print(f"published latest: {tags.get('latest', '?')}  (still the v0 line)")

    behind = False
    for app in APPS:
        here = installed(app)
        print(f"  {app:15} pinned {pinned(app):20} installed {here}")
        behind |= here != newest

    if behind:
        print(
            "\nA newer beta is out. To take it:\n"
            "  1. bump the pin in scripts/gen_frontend.py and regenerate\n"
            "  2. npm install in both frontends\n"
            "  3. run the suite — the guards read the installed package, so a\n"
            "     renamed prop, a retired token or a changed slot fails there\n"
            "     rather than silently emptying a page\n"
            "  4. re-read docs/migration and the changelog for anything the\n"
            "     guards cannot see"
        )
    else:
        print("\nUp to date with the newest published beta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
