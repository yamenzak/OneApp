"""The spec chooser, and the one direction it is allowed to be wrong in.

`scripts/affected.py` decides which browser specs a change can break, so that
`yarn e2e` — 263 specs, two viewports, half an hour — is not the price of every
one-line edit. The whole thing rests on one asymmetry: running a spec that could
not have broken costs seconds, and *not* running one that could costs a broken
push. So every case below is either "this narrows correctly" or "this refuses to
narrow", and there is deliberately no case where an unattributable change comes
back with a short list.

The cases are the ones that actually happened this week: a settings panel that
should reach `settings.spec.js`, a shell file that should reach everything
because moving the gear out of the account menu broke `drive.spec.js`, and a
documentation edit that should reach nothing at all.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

affected = pytest.importorskip("affected")


def chosen(*paths: str) -> list[str]:
	found, _why = affected.affected(list(paths))
	return found


def test_a_leaf_panel_reaches_its_own_spec():
	"""`SettingsAttach` is three files below anything a spec names."""
	found = chosen("apps/oneapp/frontend/src/components/settings/SettingsAttach.vue")
	assert found != ["all"], "a leaf component should narrow"
	assert "e2e/settings.spec.js" in found


def test_an_endpoint_reaches_the_spec_that_calls_it():
	"""`me.py` is named by `settings.spec.js`, which asserts against it."""
	found = chosen("apps/oneapp/oneapp/oneapp_core/me.py")
	assert found != ["all"]
	assert "e2e/settings.spec.js" in found


def test_a_shared_file_means_everything():
	"""The case this exists for.

	Moving the settings gear out of the account menu changed `RailAccount.vue`
	and `App.vue` and broke `drive.spec.js` and the phone's More sheet. Neither
	is a settings file, and no honest guess would have included them.
	"""
	for path in (
		"apps/oneapp/frontend/src/App.vue",
		"apps/oneapp/frontend/src/components/RailAccount.vue",
		"apps/oneapp/frontend/src/lib/shell/nav.js",
		"apps/oneapp/frontend/e2e/auth.js",
		"scripts/spa/shell.py",
	):
		assert chosen(path) == ["all"], f"{path} is shared and should mean all"


def test_a_changed_spec_runs_itself():
	found = chosen("apps/oneapp/frontend/e2e/theme.spec.js")
	assert found == ["e2e/theme.spec.js"]


def test_documentation_runs_nothing():
	"""Nothing a browser can see changed, so nothing a browser can prove."""
	assert chosen("docs/ONESPACE.md", "tests/test_settings_tabs.py") == []


def test_something_it_cannot_place_means_everything():
	"""The safe direction, stated as a test so it stays the default.

	A path this does not model — a new top-level directory, a config file
	nobody thought about — is not evidence that nothing broke.
	"""
	assert chosen("some/new/place/config.yaml") == ["all"]


def test_every_shared_pattern_still_matches_something():
	"""A pattern that matches no file is a rule that quietly stopped applying.

	This is how a safety net rots: a file is renamed, its `SHARED` entry goes on
	matching nothing, and the tool starts narrowing on a change that should have
	meant everything — silently, because the answer still looks reasonable.
	"""
	dead = [
		one for one in affected.SHARED
		if not list(ROOT.glob(one)) and not list(ROOT.glob(one + "*"))
	]
	assert not dead, f"SHARED names nothing that exists: {dead}"
