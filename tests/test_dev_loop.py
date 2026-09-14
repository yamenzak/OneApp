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
		for line in re.findall(r"^  ([a-z0-9|]+)\)$", body, re.M)
		for one in line.split("|")
	}


def _documented() -> set:
	"""The ones its own header advertises."""
	return set(re.findall(r"^#   scripts/dev\.sh ([a-z0-9]+)", DEV_SH, re.M))


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
		for named in set(re.findall(r"dev\.sh ([a-z0-9]+)", path.read_text())):
			assert named in cases, f"{path.name} names `dev.sh {named}`, which does not exist"


def test_the_fixture_does_not_strip_a_component_off_a_screen_that_has_one():
	"""A space the dev fixture seeds keeps the components it declares.

	The tenant has no control plane, so both seeders build the manifest the
	browser reads out of the space module in process — and two of them hand
	every screen `component=None` on the way, which was safe for exactly as
	long as no space they seeded declared one. The three ERPNext spaces then
	grew a Configuration page, and it rendered as "This screen has nothing to
	show yet": `resolve` returns early on a component and there was none, so
	the screen fell through to the no-doctype branch and said so.

	Nothing threw, on either side. So this reads the nulling out of the seeder
	and asks the manifest it is applied to whether it minded.
	"""
	import importlib.util

	spaces = ROOT / "apps/oneapp_control/oneapp_control/spaces"

	def declares_a_component(stem: str) -> bool:
		path = spaces / f"{stem}.py"
		assert path.exists(), (
			f"the nulling is applied to `{stem}.SCREENS`, which is not a space "
			"module this can read — name the module, or stop nulling"
		)
		spec = importlib.util.spec_from_file_location(f"seeded_{stem}", path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		return any(one.get("component") for one in getattr(module, "SCREENS", []))

	# `dict(one, component=None) for one in rua.SCREENS`, and the mock space's
	# bare `for v in SCREENS`, which names no module at all.
	pattern = re.compile(r"component=None\) for \w+ in (?:(\w+)\.)?SCREENS")
	found = 0
	for name in ("seed_dev_space.py", "seed_erp_spaces.py"):
		for named in pattern.findall((ROOT / "scripts" / name).read_text()):
			found += 1
			# The mock space declares its screens in the seeder itself, so
			# there is no module to ask and the list is right there.
			if not named:
				continue
			assert not declares_a_component(named), (
				f"{name} nulls the component of every {named} screen, and "
				f"{named} declares one — that screen will render empty"
			)
	assert found, "the nulling moved; this guard now checks nothing"
