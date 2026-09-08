"""The settings dialog's tabs, and the three lists that have to agree.

A tab is declared in `onespace/tabs.py` — its key, its label, its icon, and
the audience that decides who may open it. Two other places have to match, and
both fail *silently* when they do not:

  * **The component that draws it.** `SettingsShell.vue`'s `PANELS` maps a key
    to a component, and Vue renders a missing one as nothing at all — an empty
    panel under a tab that looked fine.
  * **The icon.** Tailwind's JIT emits a `lucide-*` class only where it can read
    it as a literal in the source it scans, and `tabs.py` is Python. An icon not
    in `components/settings/icons.js` renders as a blank space.

The audience half is checked here too, because it is the whole reason this file
exists: the tabs used to be written into the shell and drawn for everybody, with
the gate inside each endpoint, so the dialog could only be offered to admins.
"""

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TABS = ROOT / "apps/oneapp/oneapp/onespace/tabs.py"
SHELL = ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings/SettingsShell.vue"
ICONS = ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings/icons.js"


def declared() -> list[dict]:
	"""`TABS`, read out of the module rather than imported.

	`ast` because importing it pulls in `frappe` — and because what is being
	checked is the literal list, which is the thing the other two files are
	compared against.
	"""
	tree = ast.parse(TABS.read_text())
	for node in ast.walk(tree):
		if not isinstance(node, ast.Assign):
			continue
		if not any(getattr(t, "id", "") == "TABS" for t in node.targets):
			continue
		return [
			{
				key.value: (value.value if isinstance(value, ast.Constant) else value.id)
				for key, value in zip(entry.keys, entry.values)
			}
			for entry in node.value.elts
		]
	raise AssertionError("tabs.py no longer declares TABS")


def panels() -> set[str]:
	block = SHELL.read_text().split("const PANELS = {", 1)[1].split("}", 1)[0]
	return set(re.findall(r"^\s+'?([\w-]+)'?:", block, re.M))


def safelisted() -> set[str]:
	return set(re.findall(r"'(lucide-[\w-]+)'", ICONS.read_text()))


def test_every_panel_tab_has_a_component():
	"""A key with nothing behind it is an empty panel, drawn without complaint."""
	wanted = {tab["key"] for tab in declared() if tab["kind"] == "PANEL"}
	assert wanted <= panels(), (
		"declared as a panel with no component to draw it: "
		f"{sorted(wanted - panels())}"
	)


def test_every_component_has_a_tab():
	"""And the other way: a component nothing declares is a component nothing
	can reach, which is dead code that looks live."""
	wanted = {tab["key"] for tab in declared() if tab["kind"] == "PANEL"}
	assert panels() <= wanted, (
		f"drawn but never declared: {sorted(panels() - wanted)}"
	)


def test_every_fields_tab_is_a_workspace_group():
	"""A `fields` tab's key is a `workspace.GROUPS` key, because that is what
	renders it. One that names nothing renders an empty form."""
	source = (ROOT / "apps/oneapp/oneapp/onespace/workspace.py").read_text()
	groups = set(re.findall(r'"key": "(\w+)",\n\s+"label"', source))
	wanted = {tab["key"] for tab in declared() if tab["kind"] == "FIELDS"}
	assert wanted <= groups, (
		f"declared as fields with no group behind it: {sorted(wanted - groups)}"
	)


def test_every_tab_icon_is_one_the_build_emits():
	"""An icon named only in Python is a blank space, silently.

	The same rule `lib/shell/icons.js` exists for, one directory over: the JIT
	emits a class it can read as a literal, and it does not read Python.
	"""
	missing = sorted({tab["icon"] for tab in declared()} - safelisted())
	assert not missing, (
		"these are named in tabs.py and not written as literals in "
		f"modules/onespace/components/settings/icons.js, so they draw nothing: {missing}"
	)


def test_every_tab_names_an_audience_that_exists():
	"""An unknown audience is a closed one, so a typo hides a tab rather than
	opening it — which is the safe direction and the hard one to notice."""
	source = TABS.read_text()
	known = set(re.findall(r'^\t"(\w+)": _\w+,', source, re.M))
	assert known, "AUDIENCES no longer parses"

	wrong = sorted({tab["audience"] for tab in declared()} - known)
	assert not wrong, f"no such audience: {wrong}"


#: `support` is the exception, and the only one: it gates the groups the control
#: plane adds through `onespace_settings_groups`, which are not in `TABS`.
HOOKED = {"support"}


def test_no_audience_is_declared_and_never_used():
	"""A word with no tab under it is a rule nobody is subject to.

	`mailbox` sat here unused while the signature and the away message stayed
	inside the admin's Email tab — so the audience read as built and the person
	it was for still could not reach any of it. Unused, it is either a tab that
	was never finished or a word that should go.
	"""
	source = TABS.read_text()
	known = set(re.findall(r'^\t"(\w+)": _\w+,', source, re.M))
	unused = sorted(known - {tab["audience"] for tab in declared()} - HOOKED)
	assert not unused, f"declared and nothing is for it: {unused}"


def test_a_member_has_something_to_open():
	"""The claim the rail's gear rests on.

	Settings is offered to everybody now rather than to admins alone. That is
	only honest if somebody with no role of ours has tabs — otherwise the gear
	is a door onto a wall, which is exactly what the old admin-only rule was
	avoiding.
	"""
	theirs = [tab for tab in declared() if tab["audience"] == "everyone"]
	assert len(theirs) >= 3, (
		"the gear is offered to everybody but a member would see almost "
		f"nothing: {[t['key'] for t in theirs]}"
	)
	assert all(tab["section"] == "You" for tab in theirs), (
		"a tab everybody can open is one of their own, so it belongs under You"
	)


def test_the_workspaces_tabs_are_the_admins():
	"""Nothing under Workspace is open to everybody: those settings are the
	workspace's, and a member changing its branding is not the model."""
	loose = [
		tab["key"] for tab in declared()
		if tab["section"] == "Workspace" and tab["audience"] == "everyone"
	]
	assert not loose, f"open to everybody and should not be: {loose}"


# --------------------------------------------------------------------------- #
# A control is the field it writes
#
# The declared `type` decides which control the dialog draws, and the target's
# Frappe fieldtype decides what the column holds. Where the two disagree the
# form is wrong in a way nothing complains about: `Attach Image` mapped to
# `'text'` made the workspace logo a box you had to type a `/files/...` URL
# into, and a Float declared as Data made a page size a word you could type.
#
# So the pairs that may differ are named, with the reason. Anything else is a
# mismatch to fix rather than to add here.
# --------------------------------------------------------------------------- #

WORKSPACE = ROOT / "apps/oneapp/oneapp/onespace/workspace.py"
ME = ROOT / "apps/oneapp/oneapp/onespace/me.py"

#: The controls `SettingsFields.vue` and `ProfileSettings.vue` can actually draw.
#:
#: Whether a declared type *matches the column it writes* is the other half, and
#: it needs a doctype's meta — so it is `scripts/check_settings.py`, run against
#: a bench. This half needs nothing and catches the same class one step earlier.
DRAWN = {
	# No "Link": there is no Link control in this dialog, so a setting that
	# declares one is drawn as a text box. See `test_workspace_settings.py`,
	# "no setting declares a control that would be a text box".
	"Data", "Check", "Select", "Int", "Float", "Attach", "Attach Image",
	# Not a Frappe fieldtype at all — `SettingsColour.vue`, for the one
	# setting with no doctype behind it. See `onespace/branding.py`.
	"Color",
}


def declared_types(path: pathlib.Path) -> set[str]:
	return set(re.findall(r'type="([\w ]+)"', path.read_text()))


def test_every_declared_type_is_one_the_dialog_can_draw():
	"""A type with no control falls through to a text box, silently.

	That is how `Attach Image` was a URL somebody had to know, and how a Float
	was a box a word fitted in.
	"""
	for path in (WORKSPACE, ME):
		unknown = sorted(declared_types(path) - DRAWN)
		assert not unknown, f"{path.name} declares {unknown}, which nothing draws"


def test_the_renderer_draws_every_type_that_is_declared():
	"""And the other way: a control map that has lost a type is a text box."""
	fields = (ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings/SettingsFields.vue"
	          ).read_text()

	# Check and the two Attach kinds are branches; the rest come from the map.
	assert "field.type === 'Check'" in fields
	assert "field.type === 'Attach'" in fields and "'Attach Image'" in fields
	for kind in ("Select", "Int", "Float"):
		assert f"{kind}:" in fields, f"{kind} no longer has a control"


def test_an_image_setting_is_published_before_it_is_stored():
	"""A private file in an `img` tag is a broken image, and it says nothing.

	Everything the picker uploads is private — `lib/files/attach.js` passes
	`private: true` on both paths — so a logo chosen that way 403s for the one
	reader it exists for, somebody who is not signed in, and a profile picture
	403s for every colleague. Both writers publish first; see
	`drive.writing.publish`.
	"""
	for path in (WORKSPACE, ME):
		source = path.read_text()
		assert "publish(value)" in source, (
			f"{path.name} stores an image setting without publishing the file, "
			"so it draws for the person who uploaded it and nobody else"
		)


def test_a_numeric_setting_is_saved_as_a_number():
	"""`type="number"` hands back a string; the column is a Float or an Int."""
	fields = (ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings/SettingsFields.vue"
	          ).read_text()
	assert "numeric(f) ? Number(" in fields, (
		"SettingsFields no longer coerces a numeric setting before saving it"
	)
