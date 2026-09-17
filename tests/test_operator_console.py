"""The operator console, and the customer's account space beside it.

`/admin` was ~6,000 lines of Vue over eighteen doctypes, almost none of it
doing anything the screen machinery does not already do better — and every
improvement to that machinery stopped at the tenant boundary and never reached
the console. It became a Space, and `docs/CLEANUP.md` stage 8 finished the job
by moving its declaration into `spaces/oneadmin.py`, in the same shape as the
five spaces beside it.

**Half this file went in that stage, and that is the point of it.** Every rule
here that checked a fieldname against its doctype, a status field against its
Select, a screen against the space's own grants, an icon against the closed
list, or two screens sharing a heading was a second, smaller copy of a rule
`tests/test_space_screens.py` and `tests/test_manifests.py` already applied to
every other manifest — and they could not read this one, because it was
seven-tuples in another package. Now they can, so those are gone rather than
duplicated.

What is left is what is genuinely only true here: that the rail cannot grow
back to thirty-two entries, that a table only a person writes keeps its New
button, that the console's components are registered in the SPA, and that the
operator space and the customer's account space are kept apart.
"""

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

from doctype_paths import slug as doctype_slug

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"
CONSOLE = CONTROL / "spaces/oneadmin.py"
SCREENS_INDEX = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"


def _declared(path: Path):
	"""One space module, loaded off its path. These import nothing but `json`."""
	spec = importlib.util.spec_from_file_location(f"console_{path.stem}", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


CONSOLE_MODULE = _declared(CONSOLE)
SPACE = CONSOLE_MODULE.SPACE
SCREENS = CONSOLE_MODULE.SCREENS
DOCTYPES = CONSOLE_MODULE.DOCTYPES
AUTHORED = CONSOLE_MODULE.AUTHORED

LISTS = [one for one in SCREENS if one.get("document_type")]
PARTS = [one for one in SCREENS if one.get("component")]

#: The engine's own two, granted by every space and shown by none: the Words
#: page is a tab and a saved view is a control, so neither has a rail entry.
ENGINE = {"OneSpace Saved View", "OneSpace Word"}


def _doctype_json(doctype: str):
	slug = doctype_slug(doctype)
	found = list(CONTROL.glob(f"*/doctype/{slug}/{slug}.json"))
	return json.loads(found[0].read_text()) if found else None


# --------------------------------------------------------------------------- #
# A. What the console may reach, and what it shows
# --------------------------------------------------------------------------- #

def test_the_space_grants_nothing_it_does_not_show():
	"""The direction `test_space_screens.py` does not check.

	That file asks whether every screen shows a doctype the space granted. This
	is the converse and it is the one that matters on a control plane: a grant
	with no screen behind it is reachable over REST by anybody holding the
	role, and invisible in the console that is supposed to be the record of
	what the role can do.
	"""
	shown = {one["document_type"] for one in LISTS}
	granted = {row[0] for row in DOCTYPES} - ENGINE
	assert granted == shown, (
		f"granted and not shown: {sorted(granted - shown)}"
	)


def test_the_seats_are_the_four_every_space_has():
	"""It had one role — `OneSpace Operator` — where every other space has
	four, so the person who adds capacity was the person who sets prices.
	`docs/ONEADMIN-SIMPLIFICATION.md` §4 names five decisions that must stay a
	person's and had no way to say *which* person."""
	from oneapp_control.spaces import roles

	named = {row[3] for row in DOCTYPES if len(row) > 3}
	assert named <= set(roles.LABELS), named
	# All three rungs used, or the ladder is a label.
	assert {"manager", "admin"} <= named, named
	assert SPACE["role_name"] == "Ops", (
		"the Frappe roles are `<prefix>-<Seat>`, so this prefix is what an "
		"operator's role is called"
	)


def test_support_reads_everything_and_writes_almost_nothing():
	"""The User rung is somebody on a call about one workspace. Answering a
	question needs the whole picture; nothing on a support call should change a
	number."""
	base = [row for row in DOCTYPES if len(row) == 3]
	writes = [row[0] for row in base if row[1] != "Read" and row[0] not in ENGINE]
	assert not writes, f"the support seat may write {sorted(writes)}"
	# And it can see the lot, or it is not a support seat.
	assert {row[0] for row in base} >= {one["document_type"] for one in LISTS}


def test_the_money_is_a_rung_above_the_fleet():
	"""Adding capacity and setting a price are different decisions, and before
	stage 8 they were the same role."""
	rung = {row[0]: row[3] for row in DOCTYPES if len(row) > 3}
	for doctype in ("Plan", "Add-on", "Credit Pack", "Promo Code",
	                "Subscription", "Credit Ledger Entry"):
		assert rung.get(doctype) == "admin", doctype
	for doctype in ("Shard", "Region", "Storage Bucket", "Provisioning Job"):
		assert rung.get(doctype) == "manager", doctype


def test_what_is_written_elsewhere_is_read_only_at_every_rung():
	"""Three kinds of table nobody here may write at all: `OneSpace Space` is
	rewritten from `spaces/*.py` on every migration, `Workspace Role` is the
	workspace's own, and the press doctypes are virtual reads over Frappe
	Cloud's records."""
	rungs = {}
	for row in DOCTYPES:
		rungs.setdefault(row[0], []).append(row[1])
	for doctype in ("OneSpace Space", "Workspace Role", "Press Site",
	                "Press Server", "Press Bench Group"):
		assert rungs.get(doctype) == ["Read"], (doctype, rungs.get(doctype))


# --------------------------------------------------------------------------- #
# B. The components, which are the two surfaces that are not lists
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("row", PARTS, ids=[one["screen"] for one in PARTS])
def test_every_component_screen_is_registered(row):
	"""A `component` screen whose component nobody registered renders nothing
	— a blank page under a working sidebar entry."""
	assert f"'{row['component']}'" in SCREENS_INDEX.read_text(), (
		f"{row['component']} is not in the SPA's screen registry"
	)


@pytest.mark.parametrize("row", PARTS, ids=[one["screen"] for one in PARTS])
def test_every_component_key_belongs_to_this_space(row):
	"""Keyed `spaceCode/screen`, which is the convention the registry
	documents — so two spaces can each have an `overview` and neither has to
	know about the other. This is what catches a rename of the space code, and
	it caught one: stage 8 moved it from `onespace-ops` to `oneadmin`."""
	assert row["component"] == f"{SPACE['space_code']}/{row['screen']}"


def test_the_space_code_is_the_one_the_catalogue_uses():
	"""`books` had the same disagreement one stage earlier."""
	import sys

	sys.path.insert(0, str(ROOT / "apps/oneapp"))
	from oneapp import catalogue

	code = SPACE["space_code"]
	assert code in catalogue.BY_ID
	assert catalogue.kind_of(code) == catalogue.SPACE
	assert catalogue.BY_ID[code]["built"], "a space that exists is built"


def test_the_console_is_owned_by_code():
	"""It is rewritten from this module on every migration, so a hand-edit in
	the console loses on the next deploy. Stated in `spaces/__init__.py` and
	asserted here, because "why did my change vanish" is the worst way to
	learn it."""
	source = (CONTROL / "spaces/__init__.py").read_text()
	assert "doc.screens = []" in source, "install() merges, so a removed screen lingers"
	assert '"oneadmin": oneadmin' in source, "the console is not installed with the rest"


# --------------------------------------------------------------------------- #
# C. The account Space, beside it on the same site
#
# The two audiences that share a control plane. What keeps them apart is
# `role_name` and nothing else, which is why `_space` filtering on it was a
# prerequisite rather than a tidy-up.
#
# It stays declared in `entitlements/account.py` rather than moving into
# `spaces/` with the console: four component screens, no doctypes, and one role
# that is the customer's rather than a seat. The four-seat installer would give
# it a `Customer-Manager` that means nothing.
# --------------------------------------------------------------------------- #

ACCOUNT = CONTROL / "entitlements/account.py"


def _account_const(name):
	for node in ast.walk(ast.parse(ACCOUNT.read_text())):
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == name:
					return ast.literal_eval(node.value)
	raise AssertionError(f"{name} is gone from account.py")


ACCOUNT_SCREENS = _account_const("SCREENS")


@pytest.mark.parametrize("row", ACCOUNT_SCREENS, ids=[s[0] for s in ACCOUNT_SCREENS])
def test_every_account_screen_is_registered(row):
	screen, _label, _icon = row
	key = f"{_account_const('SPACE_CODE')}/{screen}"
	assert f"'{key}'" in SCREENS_INDEX.read_text(), f"{key} is not in the SPA's registry"


@pytest.mark.parametrize("row", ACCOUNT_SCREENS, ids=[s[0] for s in ACCOUNT_SCREENS])
def test_every_account_screen_component_exists(row):
	screen, _label, _icon = row
	found = list((ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/account").glob("*.vue"))
	stems = {p.stem.lower() for p in found}
	assert screen.lower() in stems, f"no component for {screen}; have {sorted(stems)}"


def test_the_account_space_grants_no_doctypes():
	"""Every screen is a component calling the customer-facing methods, each of
	which resolves the workspace from the session and refuses anything the
	caller does not own. A DocPerm here would be a second, weaker path to the
	same data, reachable over REST by anybody holding the role."""
	source = ACCOUNT.read_text()
	assert '"doctypes": []' in source


def test_the_two_spaces_are_kept_apart_only_by_role():
	"""Which is why `_space` filtering on `role_name` was a prerequisite. If
	that regresses, a customer can resolve the operator console by name."""
	assert _account_const("SPACE_CODE") != SPACE["space_code"]
	source = ACCOUNT.read_text()
	assert "CUSTOMER_ROLE" in source, "the account Space is not narrowed to customers"
	assert SPACE["role_name"] not in _account_const("SPACE_CODE")


# --------------------------------------------------------------------------- #
# D. One entry per question, and it has to stay that way
#
# The rail had thirty-two entries and one per doctype, which is how it was
# built and is not how anybody reads it. These are what stop it growing back:
# a new screen has to say which of the six questions it answers, and a screen
# over a table nobody writes by hand does not get a New button.
#
# `test_space_screens.py` checks that a group is declared in one contiguous run
# — that rule is every space's now. What is only this one's is the closed set.
# --------------------------------------------------------------------------- #

GROUPS = ("Fleet", "Money", "Catalogue", "Apps", "AI", "Trail", "Setup")


@pytest.mark.parametrize("row", SCREENS[1:], ids=[one["screen"] for one in SCREENS[1:]])
def test_every_screen_says_which_question_it_answers(row):
	"""A screen with no group is a screen back on a flat list of thirty."""
	assert row.get("screen_group") in GROUPS, (
		f"{row['screen']} is grouped {row.get('screen_group')!r}, which is not "
		f"one of {GROUPS}. A seventh group is a decision, not a typo — argue "
		f"for it here first."
	)


def test_the_leading_screen_has_no_group():
	"""Attention is above the six, not inside one of them — and it is first,
	because it is the only screen here that speaks without being asked."""
	first = SCREENS[0]
	assert first["screen"] == "attention"
	assert not first.get("screen_group"), "a leading screen carries no group"


def _inserted_doctypes() -> set[str]:
	"""Doctypes the control plane's own code creates.

	Grepped rather than imported: the question is "does anything in this app
	write one of these", and importing the app to find out needs Frappe.
	"""
	found = set()
	root = CONTROL
	for path in root.rglob("*.py"):
		if "__pycache__" in str(path) or "/doctype/" in str(path):
			continue
		source = path.read_text()
		# Both spellings: a dict handed to `get_doc`, and `new_doc` — the AI
		# catalogue sync uses the second and was invisible to the first.
		for pattern in (r'"doctype":\s*"([^"]+)"', r'new_doc\(\s*"([^"]+)"'):
			for match in re.finditer(pattern, source):
				found.add(match.group(1))
	return found


# Doctypes a person creates and no machinery does. Named rather than derived,
# because "the app inserts one somewhere" is the wrong question: the app
# inserts a Shard (`create_shard`), a Region (the press sync) and a Space
# Entitlement (the grant endpoint) too, and all three are still things an
# operator makes by hand. What matters is the converse.
HAND_ONLY = {"Plan", "Add-on", "Credit Pack", "Promo Code", "Space Claim Code"}


def _press_backed() -> set[str]:
	"""Frappe Cloud's own records. Nothing inserts them here and nothing should
	— they are a read over somebody else's table."""
	return {"Press Site", "Press Server", "Press Bench Group"}


def test_nothing_a_person_has_to_create_hides_its_New_button():
	"""The direction that actually bites.

	Hiding New on a machine-written table costs nothing — the rows arrive
	anyway. Hiding it on a `Plan` means the only way to add one is the desk,
	which this console exists to replace. So the rule is one-way: a doctype
	nothing in the app ever inserts must be authored here.
	"""
	machine = _inserted_doctypes()
	orphaned = {
		one["document_type"] for one in LISTS
		if one["document_type"] not in machine and one["screen"] not in AUTHORED
	}
	stranded = orphaned - _press_backed()
	assert not stranded, (
		f"nothing creates {sorted(stranded)} and the console will not either: "
		"add its screen to AUTHORED, or the only way to make one is the desk"
	)
	for doctype in HAND_ONLY:
		screen = next(one["screen"] for one in LISTS
		              if one["document_type"] == doctype)
		assert screen in AUTHORED, f"{doctype} is only ever typed; {screen} must offer New"


def test_every_authored_screen_is_a_real_screen():
	names = {one["screen"] for one in SCREENS}
	assert set(AUTHORED) <= names, (
		f"AUTHORED names screens that do not exist: {sorted(set(AUTHORED) - names)}"
	)


def test_the_manifest_hides_new_on_everything_else():
	"""`hide_new` is derived from `AUTHORED` by the builder rather than typed
	per screen, so this checks the derivation reached the declaration."""
	for one in LISTS:
		expected = 0 if one["screen"] in AUTHORED else 1
		assert one["hide_new"] == expected, one["screen"]
	assert len(AUTHORED) < len(LISTS) / 2, (
		"more than half these screens claim somebody types into them, which "
		"was the premise the audit disproved"
	)
