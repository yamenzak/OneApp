"""No module may reference a name that does not exist.

The Python half of `test_design_tokens`: a name nothing defines is invisible
until the line runs, and the lines that carry them are the ones that run least
— an error path, a branch behind a setting, an endpoint one view type asks for.

Three of these were live when this was written and every one of them was a
`NameError` in production code rather than a typo in a test:

* `records.dashboard_data` carried `_window(resolved, since, until)` into a
  function that has no `since` and no `until`, so **every dashboard** answered
  500 for one commit. The browser suite caught it and it was mistaken for
  fixture noise, which is exactly how a whole-suite signal gets spent.
* `email/folders.py` called Frappe's `_()` seven times without importing it —
  in the throw paths, so the failure only appears when somebody names a folder
  the mail server refuses.
* `provisioning/steps.py` raised `PressTransientError` three times without
  importing it, in the branches that handle DNS not having propagated. A
  provisioning failure would have become a `NameError` about the failure.

Ruff's F821 finds all of it in under a second, which is the whole argument for
having this rather than trusting a browser to walk every branch.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Everything in this repo that is Python we wrote. `apps/*/node_modules` and the
# vendored spreadsheet are JavaScript, so there is nothing here to exclude that
# ruff does not already skip.
LOOKED_AT = ("apps", "scripts", "workers", "tests")


@pytest.mark.skipif(not shutil.which("ruff"), reason="ruff is not installed")
def test_no_module_uses_a_name_nothing_defines():
	found = subprocess.run(
		[
			"ruff", "check",
			# F821 alone, on purpose. This is a correctness guard and not a
			# style one: adding rules here would make it a lint suite somebody
			# eventually turns off, and the rule that catches a `NameError`
			# would go with it.
			"--select", "F821",
			"--no-cache",
			"--output-format", "concise",
			*LOOKED_AT,
		],
		cwd=ROOT,
		capture_output=True,
		text=True,
	)
	assert found.returncode == 0, (
		"a name nothing defines — an unimported symbol, a parameter that was "
		f"renamed, or a typo:\n\n{found.stdout}{found.stderr}"
	)
