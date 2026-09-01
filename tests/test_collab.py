"""Tags and sharing, and the parts of both that are ours.

The store is Frappe's in both cases — `_user_tags` plus `Tag Link` for one,
`DocShare` for the other — so what is pinned here is the shaping, the bounds
and the two refusals that would otherwise have made a control that does
nothing. See `docs/SPACES.md`, "Tags and sharing".
"""

import types

import pytest


@pytest.fixture
def collab(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import collab as module

	return module


# --- tags ------------------------------------------------------------------


def test_a_tag_is_read_the_way_frappe_writes_it(collab):
	"""One comma-joined column, written by more than one version of Frappe.

	The leading comma is the one that matters: `DocTags.add` splits an empty
	column into `[""]` and appends, so the first tag on a record arrives back
	as `,urgent`. A reader that trusted `split(",")` would report a blank tag
	on every record that has exactly one.
	"""
	assert collab.parse(",urgent") == ["urgent"]
	assert collab.parse("urgent,renewal") == ["urgent", "renewal"]
	assert collab.parse(" urgent , renewal ") == ["urgent", "renewal"]
	assert collab.parse(None) == []
	assert collab.parse("") == []


def test_a_tag_cannot_carry_the_separator_it_is_stored_with(collab):
	"""A comma would split one tag into two on the way back out, and a newline
	would make a `Tag` document nobody can name. Both are cleaned rather than
	refused: somebody pasting a phrase meant a tag, not an error message."""
	assert collab.clean("  chase   in May ") == "chase in May"
	assert collab.clean("urgent, renewal") == "urgent renewal"
	assert collab.clean("first\nsecond") == "first second"
	assert len(collab.clean("x" * 200)) == collab.TAG_MAX


def test_a_record_stops_taking_tags_somewhere(collab, stub_frappe, monkeypatch):
	"""`_user_tags` is a `Data` column: past its width the tags stop being
	stored and nothing says so. A bound with a sentence beats a truncation."""
	monkeypatch.setattr(
		collab, "tags_of", lambda dt, dn: [f"t{i}" for i in range(collab.TAGS_PER_RECORD)]
	)
	with pytest.raises(Exception) as raised:
		collab.set_tag("Task", "T-1", "one more")
	assert str(collab.TAGS_PER_RECORD) in str(raised.value)


def test_the_tag_picker_offers_the_workspace_and_not_the_doctype(collab, stub_frappe, monkeypatch):
	"""A tag is a word the workspace uses, not a property of one kind of record.

	"urgent" means the same thing on an invoice and on a task, and offering it
	only where it has already been used is how one word becomes three spellings
	of it. What it does exclude is what is already on this record, which would
	otherwise read as a way to add it twice.
	"""
	asked = {}

	def get_all(doctype, filters=None, pluck=None, **kw):
		asked["doctype"] = doctype
		asked["filters"] = filters
		return ["urgent", "Renewal", "chase"]

	monkeypatch.setattr(stub_frappe, "get_all", get_all)

	offered = collab.tag_options("re", exclude=["renewal"])

	assert asked["doctype"] == "Tag"
	assert asked["filters"] == [["name", "like", "%re%"]]
	# Case-insensitively: "Renewal" and "renewal" are the same tag, and
	# offering the other casing is offering a duplicate.
	assert offered == ["urgent", "chase"]


# --- sharing ---------------------------------------------------------------


def test_a_share_is_read_downwards(collab):
	"""Frappe stores four independent checkboxes; we offer three levels. Read
	from the most permissive down, so a row with write and share set is "can
	share" rather than ambiguously both."""
	assert collab.level_of({"read": 1, "write": 1, "share": 1}) == "share"
	assert collab.level_of({"read": 1, "write": 1, "share": 0}) == "write"
	assert collab.level_of({"read": 1}) == "read"


def test_every_level_grants_read(collab):
	"""There is no "can edit but not see". Frappe adds read on every share for
	the same reason, and a level that did not would be a row in the list that
	does nothing."""
	assert all(one["read"] for one in collab.LEVELS.values())
	# And each is a superset of the one before, so moving somebody down takes
	# something away rather than swapping one grant for another.
	assert collab.LEVELS["write"]["write"] and not collab.LEVELS["write"]["share"]
	assert collab.LEVELS["share"]["write"] and collab.LEVELS["share"]["share"]


def test_everyone_is_not_a_person_in_the_list(collab, stub_frappe, monkeypatch):
	"""It is a different kind of statement — "anybody who can sign in here" —
	and drawing it among colleagues is how somebody grants it by accident."""
	rows = [
		{"name": "s1", "user": "robin@x.test", "everyone": 0, "read": 1, "write": 1, "share": 0},
		{"name": "s2", "user": None, "everyone": 1, "read": 1, "write": 0, "share": 0},
	]

	def get_all(doctype, filters=None, fields=None, **kw):
		if doctype == "DocShare":
			return rows
		return [{"name": "robin@x.test", "full_name": "Robin Vale", "user_image": None}]

	monkeypatch.setattr(stub_frappe, "get_all", get_all)

	found = collab.shares_of("Task", "T-1")

	assert found["everyone"] == {"level": "read"}
	assert [one["value"] for one in found["people"]] == ["robin@x.test"]
	assert found["people"][0]["label"] == "Robin Vale"
	assert found["people"][0]["level"] == "write"


def test_a_share_granted_to_an_account_that_is_gone_is_still_shown(
	collab, stub_frappe, monkeypatch
):
	"""Frappe does not sweep `DocShare` when a user is deleted. Shown by id
	rather than dropped: a permission nobody can see is a permission nobody
	removes."""
	def get_all(doctype, filters=None, fields=None, **kw):
		if doctype == "DocShare":
			return [{"name": "s1", "user": "ghost@x.test", "everyone": 0,
			         "read": 1, "write": 0, "share": 0}]
		return []

	monkeypatch.setattr(stub_frappe, "get_all", get_all)

	found = collab.shares_of("Task", "T-1")
	assert found["people"] == [
		{"value": "ghost@x.test", "label": "ghost@x.test", "image": None, "level": "read"}
	]


def test_sharing_asks_for_a_level_it_knows(collab, stub_frappe):
	with pytest.raises(Exception):
		collab.share("Task", "T-1", user="robin@x.test", level="admin")


def test_write_access_carries_the_permission_to_share():
	"""Frappe gates handing a record to somebody on `has_permission(doctype,
	"share")`. Without it in the level a manifest grants, every share on every
	workspace is refused — the same shape of bug as the roles that could not be
	assigned to and the documents that could not be followed."""
	import pathlib

	source = pathlib.Path("apps/oneapp/oneapp/oneapp_core/sync.py").read_text()
	block = source.split("ACCESS_LEVELS = {")[1].split("}\n", 1)[0]
	read, write, manage = block.split('"Read"')[1], block.split('"Write"')[1], block.split('"Manage"')[1]

	assert '"share": 1' in write.split('"Manage"')[0]
	assert '"share": 1' in manage
	# And not at Read: the level that may not give away what it was given.
	assert '"share": 1' not in read.split('"Write"')[0]
