"""The fast loop, guarded — because a command that does not exist costs an hour.

Everything here is about one failure: the header of `scripts/dev.sh` promises a
subcommand, or `docs/ONEADMIN.md` and `CLAUDE.md` tell somebody to run one, and
the case statement no longer has it. What that produces is `usage:` on a script
somebody is following line by line, and the next twenty minutes go on reading a
shell script instead of on the change they came to make.

Small, and the reason it earns its place is that the loop is now the thing most
often followed without thinking: watch, seed, shot.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEV_SH = (ROOT / "scripts/dev.sh").read_text()


def _cases() -> set:
	"""The subcommands `dev.sh` actually answers to."""
	body = DEV_SH.split("case ", 1)[-1]
	return {
		one
		for line in re.findall(r"^  ([a-z|]+)\)$", body, re.M)
		for one in line.split("|")
	}


def _documented() -> set:
	"""The ones its own header advertises."""
	return set(re.findall(r"^#   scripts/dev\.sh ([a-z]+)", DEV_SH, re.M))


def test_the_header_and_the_script_agree():
	cases, documented = _cases(), _documented()
	assert documented <= cases, f"documented but not implemented: {documented - cases}"
	# The other direction is a warning rather than a rule — `restart` is a
	# convenience nobody needs told about — so only the loop's own commands are
	# required to be written down.
	loop = {"up", "down", "watch", "seed", "run", "shell"}
	assert loop <= documented, f"in the loop and undocumented: {loop - documented}"


@pytest.mark.parametrize("command", ["watch", "seed", "spa", "run", "up", "down"])
def test_the_loop_commands_exist(command):
	assert command in _cases()


def test_seed_takes_the_manifest_flag():
	"""The half a manifest edit needs, which is the whole point of the flag."""
	seeder = (ROOT / "scripts/seed_dev_space.py").read_text()
	assert '"--manifest" in sys.argv[1:]' in seeder
	assert "def seed_tenant(manifest_only=False):" in seeder
	# And `dev.sh run` has to hand it through, or the flag is read off this
	# wrapper's argv and is never there. That is the bug this pairs with: the
	# seeder grows a flag, the flag silently does nothing, and the fast path is
	# quietly the slow one.
	assert 'sys.argv = [path, *sys.argv[4:]]' in DEV_SH


@pytest.mark.parametrize("app", ["oneapp", "oneapp_control"])
def test_every_bundle_can_take_a_screenshot(app):
	"""`yarn shot` is generated, committed, and wired to a script."""
	import json

	shot = ROOT / f"apps/{app}/frontend/shot.mjs"
	assert shot.exists(), f"{app} has no shot.mjs — run scripts/gen_frontend.py"
	# Pointed at its own site rather than at a placeholder that renders as a
	# 404 nobody reads.
	assert "BASE_URL_PLACEHOLDER" not in shot.read_text()
	scripts = json.loads((ROOT / f"apps/{app}/frontend/package.json").read_text())["scripts"]
	assert scripts.get("shot") == "node shot.mjs"


def test_the_docs_name_commands_that_exist():
	"""Every `dev.sh <word>` written down anywhere is one the script answers to."""
	cases = _cases()
	for path in (ROOT / "docs/ONEADMIN.md", ROOT / "CLAUDE.md"):
		for named in set(re.findall(r"dev\.sh ([a-z]+)", path.read_text())):
			assert named in cases, f"{path.name} names `dev.sh {named}`, which does not exist"
