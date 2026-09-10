"""A space says what the jobs are, and the installer writes them down.

The model for this landed a while ago and was never reachable: `OneSpace Space
Role` is a child table, `OneSpace Space Doctype.role` is a column, and
`registry.permission_manifest` already reads both. What was missing was the
declaration end — `spaces/install` never wrote a role row, and `DOCTYPES` was a
three-tuple with nowhere to name one. So every space shipped exactly one role
holding everything in its manifest, which is the shape the whole thing exists
to stop being.

The floor-and-above shape is the part worth pinning. A grant naming no role
reaches every role in the space, so a planner's manifest carries a Read row and
a Write row for the same doctype, and it is `sync.sync_permissions` that has to
keep the wider one. Those live in `test_workspace_roles.py`; here is the
declaration itself.
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


SHIPPED = sorted(p.stem for p in SPACES.glob("*.py") if p.stem != "__init__")


# --------------------------------------------------------------------------- #
# The declaration, for every space
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", SHIPPED)
def test_a_grant_names_a_role_the_space_actually_ships(name):
	"""A typo in the fourth element is a grant that reaches nobody: the
	manifest matches on `role_key` and silently produces no rows for it, so the
	planner opens the app and finds it read-only with nothing to say why."""
	module = declared(name)
	keys = {row["role_key"] for row in getattr(module, "ROLES", [])}

	for row in module.DOCTYPES:
		if len(row) > 3 and row[3]:
			assert row[3] in keys, (
				f"{name} grants {row[0]} to {row[3]!r}, which is not one of its "
				f"roles ({sorted(keys) or 'none'})"
			)


@pytest.mark.parametrize("name", SHIPPED)
def test_exactly_one_role_is_the_default(name):
	"""Entitling a space has to mean its members can open it. Two defaults is
	an ambiguity `space_roles` resolves by picking one, and none is an app
	nobody can see — both worth catching here rather than there."""
	roles = getattr(declared(name), "ROLES", [])
	if not roles:
		# A space that ships none keeps the old shape on purpose: `space_roles`
		# invents a single default for it.
		return

	defaults = [row for row in roles if row.get("is_default")]
	assert len(defaults) == 1, (
		f"{name} has {len(defaults)} default roles; it needs exactly one"
	)


@pytest.mark.parametrize("name", SHIPPED)
def test_every_role_says_what_it_is_for(name):
	"""The description is not decoration: it is the only sentence somebody
	handing out a role reads before handing it out."""
	for row in getattr(declared(name), "ROLES", []):
		assert row.get("label"), f"{name}:{row['role_key']} has no label"
		assert row.get("description"), (
			f"{name}:{row['role_key']} has no description, so the person "
			f"choosing it is choosing from a word"
		)


@pytest.mark.parametrize("name", SHIPPED)
def test_role_keys_are_unique(name):
	keys = [row["role_key"] for row in getattr(declared(name), "ROLES", [])]
	assert len(keys) == len(set(keys)), f"{name} declares a role key twice"


# --------------------------------------------------------------------------- #
# OneMobility's three
# --------------------------------------------------------------------------- #

def test_the_default_is_the_one_that_can_break_nothing():
	"""The point of the split. A transit authority is mostly people watching a
	map, and entitling the space used to hand every one of them the power to
	re-point a feed at a different server."""
	roles = {row["role_key"]: row for row in declared("onemobility").ROLES}

	assert roles["viewer"].get("is_default")
	assert not roles["planner"].get("is_default")
	assert not roles["feeds"].get("is_default")


def test_a_viewer_writes_nothing_but_its_own_views():
	"""Everything a viewer gets is a grant with no role on it — that is what
	"the floor" means. So the floor may contain exactly one Write, and it is
	the saved views, restricted to the person who made them."""
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
	assert sources[0][3] == "feeds"


def test_a_planner_can_see_the_feeds_without_owning_them():
	"""Which feeds exist is not a secret from the people reading their output;
	what a feed points at is. So Transit Feed is Read on the floor and Write
	only for the role that owns it."""
	feeds = {
		(row[3] if len(row) > 3 else ""): row[1]
		for row in declared("onemobility").DOCTYPES if row[0] == "Transit Feed"
	}

	assert feeds == {"": "Read", "feeds": "Write"}


# --------------------------------------------------------------------------- #
# The installer
# --------------------------------------------------------------------------- #

def test_the_installer_writes_the_roles_and_the_role_on_each_grant():
	"""Read off the source: everything above is a declaration nothing acts on
	unless `install` carries it across, and it did not until now."""
	source = (SPACES / "__init__.py").read_text()

	assert 'doc.append("roles"' in source, "a space's roles are declared and dropped"
	assert '"role": row[3] if len(row) > 3 else ""' in source, (
		"a grant's role is dropped, so every grant reaches every role again"
	)
	assert "doc.roles = []" in source, (
		"roles are appended without being cleared, so a renamed role lingers"
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
