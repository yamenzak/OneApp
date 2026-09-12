"""Run one of the SPA's own modules under node.

The alternative is a Python reimplementation to test the JavaScript against,
and `test_field_rules.py` says why that is worse: two things to keep in step,
and the one that gets tested is never the one that ships. `tests/js/hooks.mjs`
resolves the `@/` alias and stubs the two modules that are about the browser
rather than about the logic — the component barrel and the boot payload.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "apps/oneapp/frontend/src"
MODULES = ROOT / "apps/oneapp/frontend/node_modules"
REGISTER = ROOT / "tests/js/register.mjs"

needs_node = pytest.mark.skipif(
	not shutil.which("node") or not (MODULES / "dayjs").exists(),
	reason="needs node and the SPA's installed packages",
)


def call(
	module: str,
	body: str,
	formats: dict | None = None,
	system_tz: str = "UTC",
	local_tz: str = "UTC",
):
	"""Import `module` (a `@/…` specifier) and run `body`, which prints JSON.

	`formats` is what the workspace set — the thing the boot payload carries —
	so a test can say "this workspace writes `#.###,##`" and read back what a
	column then says.
	"""
	script = f"import * as m from {json.dumps(module)};\n{body}"
	env = {
		"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
		"LANG": "en_US.UTF-8",
		"LC_ALL": "en_US.UTF-8",
		# Pinned, because `toLocaleString` and `Intl` both follow the
		# environment and would make these assertions a statement about the
		# runner rather than about the code.
		"TZ": "UTC",
		"SPA_SRC": str(SRC),
		"SPA_MODULES": MODULES.as_uri(),
		"SPA_FORMATS": json.dumps(formats or {}),
		"SPA_SYSTEM_TZ": system_tz,
		"SPA_LOCAL_TZ": local_tz,
	}
	out = subprocess.run(
		["node", "--import", str(REGISTER), "--input-type=module", "-e", script],
		capture_output=True, text=True, check=True, env=env,
	)
	return json.loads(out.stdout.strip().splitlines()[-1])
