"""Every space has the same four seats, and a grant names the lowest one.

A space used to invent its own jobs and there were twelve words across five of
them, no two of which lined up. Now there are four — User, Manager, Audit,
Admin — declared once in `spaces/roles.py` and written onto every space by the
installer, so a space module declares grants and never roles.

The ladder is the part worth pinning. A `DOCTYPES` row's fourth element names
**the lowest seat that may do the thing** and the seats above inherit it, so a
manager's manifest carries a Read row and a Write row for the same doctype and
it is `sync.sync_permissions` that has to keep the wider one. Those live in
`test_workspace_roles.py`; here is the declaration itself.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPACES = ROOT / "apps/oneapp_control/oneapp_control/spaces"


def declared(name: str):
	"""One space module, read without a bench. These are declaration files."""
	path = SPACES / f"{name}.py"
	spec = importlib.util.spec_from_file_location(f"space_{name}", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _is_a_space(name: str) -> bool:
	return hasattr(declared(name), "SPACE")


# A module in this directory is a space when it declares one. `roles.py` is the
# four seats every space has, and it is not a space.
SHIPPED = sorted(p.stem for p in SPACES.glob("*.py")
                 if p.stem != "__init__" and _is_a_space(p.stem))

SEATS = declared("roles")


# --------------------------------------------------------------------------- #
# The declaration, for every space
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", SHIPPED)
def test_a_grant_names_one_of_the_four_seats(name):
	"""A typo in the fourth element is a grant that reaches nobody: the
	manifest matches on `role_key` and silently produces no rows for it, so the
	manager opens the app and finds it read-only with nothing to say why."""
	module = declared(name)

	for row in module.DOCTYPES:
		if len(row) > 3 and row[3]:
			assert row[3] in SEATS.LABELS, (
				f"{name} grants {row[0]} to {row[3]!r}, which is not one of "
				f"{sorted(SEATS.LABELS)}"
			)


@pytest.mark.parametrize("name", SHIPPED)
def test_no_space_declares_its_own_roles(name):
	"""The whole point of the four. A space that ships a `ROLES` list is a
	space inventing a twelfth word for a job three others already have."""
	assert not hasattr(declared(name), "ROLES"), (
		f"{name} declares its own roles; the four are in spaces/roles.py"
	)


@pytest.mark.parametrize("name", SHIPPED)
def test_a_space_has_a_role_prefix(name):
	"""`role_name` stopped being a role and became the prefix the four seats
	are built from — `HR` giving `HR-User` and the rest. A space without one
	has four roles named `-User`."""
	prefix = declared(name).SPACE.get("role_name")
	assert prefix and "-" not in prefix and " " not in prefix, (
		f"{name} has role_name {prefix!r}; it is a prefix now, one word"
	)


def test_exactly_one_seat_is_the_default():
	"""Entitling a space has to mean its members can open it. Two defaults is
	an ambiguity `space_roles` resolves by picking one, and none is an app
	nobody can see."""
	defaults = [row for row in SEATS.ROLES if row.get("is_default")]
	assert len(defaults) == 1
	assert defaults[0]["role_key"] == SEATS.USER


def test_every_seat_says_what_it_is_for():
	"""The description is not decoration: it is the only sentence somebody
	handing out a role reads before handing it out."""
	for row in SEATS.ROLES:
		assert row.get("label"), f"{row['role_key']} has no label"
		assert row.get("description"), (
			f"{row['role_key']} has no description, so the person choosing it "
			f"is choosing from a word"
		)


def test_the_seat_keys_are_unique_and_the_four_we_meant():
	keys = [row["role_key"] for row in SEATS.ROLES]
	assert len(keys) == len(set(keys))
	assert set(keys) == {SEATS.USER, SEATS.MANAGER, SEATS.AUDIT, SEATS.ADMIN}


def test_the_ladder_goes_up_and_the_auditor_is_not_on_it():
	"""A grant at User reaches Manager and Admin; one at Admin stops there.
	Audit is derived at Read in `permission_manifest`, so putting it on the
	ladder would be an auditor who can write."""
	assert SEATS.ABOVE[SEATS.USER] == (SEATS.USER, SEATS.MANAGER, SEATS.ADMIN)
	assert SEATS.ABOVE[SEATS.MANAGER] == (SEATS.MANAGER, SEATS.ADMIN)
	assert SEATS.ABOVE[SEATS.ADMIN] == (SEATS.ADMIN,)
	assert SEATS.AUDIT not in SEATS.ABOVE[SEATS.USER]


def test_a_seat_becomes_one_frappe_role_named_after_the_space():
	assert SEATS.frappe_role("HR", SEATS.MANAGER) == "HR-Manager"
	assert SEATS.frappe_roles("CRM") == [
		"CRM-User", "CRM-Manager", "CRM-Audit", "CRM-Admin",
	]
	# A prefix nothing named, or a key that is not a seat, is nothing rather
	# than a half-formed role name.
	assert SEATS.frappe_role("", SEATS.USER) == ""
	assert SEATS.frappe_role("HR", "payroll") == ""


def test_the_two_halves_of_the_wire_agree_on_the_naming():
	"""The control plane declares the seats and the tenant derives the same
	names from a prefix it was sent. The payload carries the prefix and never
	the seats, so the two lists are the contract."""
	import sys

	sys.path.insert(0, str(ROOT / "apps/oneapp"))
	from oneapp.onespace import seats as tenant

	assert list(tenant.SEATS) == [SEATS.LABELS[key] for key in SEATS.KEYS]
	assert tenant.roles("HR") == SEATS.frappe_roles("HR")


# --------------------------------------------------------------------------- #
# OneMobility, the worked example
# --------------------------------------------------------------------------- #

def test_a_viewer_writes_nothing_but_its_own_views():
	"""Everything a User gets is a grant with no seat on it — that is what the
	bottom rung means. So it may contain exactly one Write, and it is the saved
	views, restricted to the person who made them.

	This is the point of the split. A transit authority is mostly people
	watching a map, and entitling the space must not hand every one of them the
	power to re-point a feed at a different server."""
	writes = [
		row for row in declared("onemobility").DOCTYPES
		if len(row) == 3 and row[1] != "Read"
	]

	assert [row[0] for row in writes] == ["OneSpace Saved View"]
	assert writes[0][2] == 1, "a viewer's saved views are not their own"


def test_nobody_may_edit_what_a_source_said():
	"""A claim is the record of what arrived. The answer to "this is wrong" is
	to change the precedence or fix the feed — an editable audit trail is not
	one, so no role anywhere gets Write on it."""
	for row in declared("onemobility").DOCTYPES:
		if row[0] == "Transit Claim":
			assert row[1] == "Read", f"Transit Claim is {row[1]} for {row[3:] or 'everybody'}"


def test_only_the_feed_manager_reaches_a_source():
	"""The job that can take the map down. A source is where the data comes
	from and its credentials sit on it, so it appears once and behind a role."""
	sources = [row for row in declared("onemobility").DOCTYPES if row[0] == "Transit Source"]

	assert len(sources) == 1
	assert sources[0][3] == SEATS.ADMIN


def test_a_planner_can_see_the_feeds_without_owning_them():
	"""Which feeds exist is not a secret from the people reading their output;
	what a feed points at is. So Transit Feed is Read on the floor and Write
	only for the role that owns it."""
	feeds = {
		(row[3] if len(row) > 3 else ""): row[1]
		for row in declared("onemobility").DOCTYPES if row[0] == "Transit Feed"
	}

	assert feeds == {"": "Read", SEATS.ADMIN: "Write"}


# --------------------------------------------------------------------------- #
# The installer
# --------------------------------------------------------------------------- #

def test_the_installer_writes_the_four_seats_and_the_seat_on_each_grant():
	"""Read off the source: everything above is a declaration nothing acts on
	unless `install` carries it across."""
	source = (SPACES / "__init__.py").read_text()

	assert "for row in roles.ROLES:" in source, "the four seats are never written"
	assert 'doc.append("roles"' in source, "a space's seats are declared and dropped"
	assert '"role": role' in source, (
		"a grant's seat is dropped, so every grant reaches every seat again"
	)
	assert "doc.roles = []" in source, (
		"seats are appended without being cleared, so a renamed one lingers"
	)


def test_nothing_unpacks_a_grant_row_as_a_fixed_three():
	"""The break a four-tuple causes, and why no other test could see it.

	`DOCTYPES` rows became three-or-four when a grant learned to name a role,
	and the dev seeder was still writing `for document_type, access, if_owner
	in manifest.DOCTYPES`. Nothing in this suite runs the seeder — it wants a
	bench — so it stayed green while `dev.sh seed` died halfway, which left the
	fixture dirtier than it found it and made an unrelated browser test fail
	for reasons that had nothing to do with it.
	"""
	import re

	for path in (ROOT / "scripts").glob("*.py"):
		source = path.read_text()
		guilty = re.findall(
			r"for\s+\w+\s*,\s*\w+\s*,\s*\w+\s+in\s+\w*\.?DOCTYPES", source
		)
		assert not guilty, (
			f"{path.name} unpacks a manifest grant as exactly three: {guilty[0]}. "
			f"A row may carry a fourth part naming the role it belongs to."
		)
