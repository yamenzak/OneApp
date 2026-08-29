"""Fail if a generated frontend file was edited by hand.

The two SPAs are mirrored to separate repositories and so cannot share an npm
workspace. Their shared setup is generated instead — which only holds if nobody
edits the copies. This is what makes that true.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from gen_frontend import APPS, ROOT, render  # noqa: E402


def main() -> int:
    drifted = []
    missing = []

    for app, spec in APPS.items():
        base = os.path.join(ROOT, "apps", app, "frontend")
        for name, expected in render(app, spec).items():
            path = os.path.join(base, name)
            if not os.path.exists(path):
                missing.append(f"{app}/{name}")
                continue
            with open(path) as fh:
                if fh.read() != expected:
                    drifted.append(f"{app}/{name}")

    for name in missing:
        print(f"  missing  {name}")
    for name in drifted:
        print(f"  edited   {name}")

    if drifted or missing:
        print(
            "\nGenerated frontend files differ from scripts/gen_frontend.py.\n"
            "Change the generator and re-run it — editing the copies lets the two "
            "SPAs drift apart, which is the thing this prevents."
        )
        return 1

    print("frontend config is in sync across all apps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
