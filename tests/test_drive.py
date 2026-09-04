"""One file manager, over the table attachments already live in.

Three things are worth holding here.

The kind is a column, derived once, and the whole reason the filter chips can
exist — so the derivation is tested against the extensions people actually send
rather than against a mime map nobody has.

The bin is a promise with a date on it, and the shape that makes it a promise is
that trashing writes a column while deleting removes the row *and* the object
together. A trash that deleted would be a delete with a longer name.

And the access model: every read is `get_list`, which is the same one-word
difference the record's mail rests on. A file manager on `get_all` would hand
every reader every file on the site, most of which are attachments on records
they cannot open.
"""

import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DRIVE = ROOT / "apps/oneapp/oneapp/oneapp_core/drive"


@pytest.fixture
def drive(monkeypatch):
	from oneapp.oneapp_core import drive as module

	return module


# --------------------------------------------------------------------------- #
# What a file is
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,expected", [
	("site-plan.pdf", "PDF"),
	("elevation.PDF", "PDF"),
	("photo.jpeg", "Image"),
	("logo.SVG", "Image"),
	("walkthrough.mp4", "Video"),
	("voicenote.m4a", "Audio"),
	("schedule.xlsx", "Document"),
	("notes.md", "Document"),
	("drawing.dwg", "Other"),
	("archive", "Other"),
	("", "Other"),
])
def test_a_file_knows_what_it_is_from_its_name(drive, name, expected):
	assert drive.kind_of(name) == expected


def test_a_folder_is_a_kind_rather_than_a_flag(drive):
	"""Every list here sorts folders first, and a sort has to sort on something."""
	assert drive.kind_of("Drawings", is_folder=True) == "Folder"
	# Even when the name looks like a file, which is what a folder called
	# `2024.01` would otherwise be read as.
	assert drive.kind_of("2024.01", is_folder=True) == "Folder"


def test_the_extension_decides_and_not_the_browser(drive):
	"""The browser's guess for an upload is famously the thing that calls a
	`.dwg` an octet-stream, which is why nothing here reads a mime type."""
	source = (DRIVE / "kinds.py").read_text()
	assert "content_type" not in source
	assert "mimetypes" not in source


def test_a_file_that_arrived_before_this_existed_is_not_broken(drive):
	"""Its status column is empty, and empty has to mean Active.

	The alternative is a backfill: a write over every File on every site to
	record what its absence already says.
	"""
	from oneapp.oneapp_core.drive.query import _visible

	assert _visible()[drive.STATUS_FIELD] == ["in", [drive.ACTIVE, "", None]]


def test_a_new_file_is_stamped_on_the_way_in(drive):
	doc = types.SimpleNamespace(values={})
	doc.get = lambda key, default=None: doc.values.get(key, default)
	doc.set = lambda key, value: doc.values.__setitem__(key, value)
	doc.values["file_name"] = "tower.pdf"

	drive.on_insert(doc)
	assert doc.values[drive.KIND_FIELD] == "PDF"
	assert doc.values[drive.STATUS_FIELD] == drive.ACTIVE


# --------------------------------------------------------------------------- #
# The places
# --------------------------------------------------------------------------- #

def test_every_place_is_a_filter_over_one_table(drive):
	"""There is no second store behind the rail, which is why it is cheap."""
	for place in drive.PLACES:
		filters, _or = drive._place_filters(place)
		assert isinstance(filters, dict)


def test_the_bin_is_the_only_place_that_shows_trashed_files(drive):
	for place in drive.PLACES:
		filters, _or = drive._place_filters(place)
		if place == "trash":
			assert filters[drive.STATUS_FIELD] == drive.TRASHED
		else:
			assert filters[drive.STATUS_FIELD] == ["in", [drive.ACTIVE, "", None]]


def test_shared_is_what_reached_me_and_is_not_mine(drive):
	"""What makes it reachable is `DocShare`, which `get_list` has already
	applied by the time this filter is read — so the filter itself is only the
	half that says "not mine"."""
	filters, _or = drive._place_filters("shared")
	assert filters["owner"][0] == "!="


def test_a_kind_that_is_not_one_of_ours_is_dropped(drive, monkeypatch):
	"""The chips are an allowlist. Without this the fieldname is the hole."""
	source = (DRIVE / "reading.py").read_text()
	assert "if kind and kind not in KINDS:" in source


# --------------------------------------------------------------------------- #
# A link is not a grant, again
# --------------------------------------------------------------------------- #

def test_every_read_applies_the_readers_own_permission():
	"""`get_all` ignores permissions. A file manager built on it would list
	every attachment on the site, including the ones on records the reader
	cannot open — which is where most of a workspace's files are."""
	source = (DRIVE / "reading.py").read_text()
	body = source[source.index("def listing("):source.index("def _shape(")]
	assert "frappe.get_list(" in body
	assert "get_all" not in body
	assert "ignore_permissions" not in source


def test_changing_a_file_asks_a_different_question_from_seeing_one():
	"""`get_list` decides who may see; `check_permission("write")` decides who
	may change. They differ on a file shared read-only, which is the case that
	matters."""
	source = (DRIVE / "writing.py").read_text()
	assert 'check_permission("write")' in source


# --------------------------------------------------------------------------- #
# The bin
# --------------------------------------------------------------------------- #

def test_trashing_writes_a_column_and_deleting_removes_the_object():
	"""The distinction the whole feature rests on. Frappe deletes a `File` and
	its object together, so before this the only undo for a misplaced click was
	a backup — which is not an undo, it is a support ticket."""
	source = (DRIVE / "writing.py").read_text()

	trashing = source[source.index("def trash("):source.index("def restore(")]
	assert "delete_doc" not in trashing
	assert "TRASHED" in trashing

	emptying = source[source.index("def empty_trash("):source.index("def sweep_trash(")]
	assert "delete_permanently=True" in emptying


def test_emptying_only_ever_touches_the_bin():
	"""Otherwise the endpoint is a permanent delete with no confirmation
	anywhere in front of it."""
	source = (DRIVE / "writing.py").read_text()
	emptying = source[source.index("def empty_trash("):source.index("def sweep_trash(")]
	assert f'!= TRASHED' in emptying or "get(STATUS_FIELD) != TRASHED" in emptying


def test_the_sweep_deletes_through_the_document_and_not_around_it():
	"""`on_trash` on the `File` override is what removes the R2 object. A row
	deleted with SQL is an object nobody will ever find again, still billed."""
	source = (DRIVE / "writing.py").read_text()
	sweep = source[source.index("def sweep_trash("):]
	assert "frappe.delete_doc" in sweep
	assert "db.sql" not in sweep


def test_the_bin_keeps_things_long_enough_to_notice(drive):
	assert 7 <= drive.writing.KEEP_DAYS <= 90


# --------------------------------------------------------------------------- #
# Folders
# --------------------------------------------------------------------------- #

def test_a_folder_cannot_be_moved_inside_itself():
	"""Frappe will store it happily, and the breadcrumb walk is what discovers
	it — one reader at a time, forever."""
	source = (DRIVE / "writing.py").read_text()
	moving = source[source.index("def move("):source.index("def _upward(")]
	assert "_upward(folder)" in moving


def test_every_walk_up_the_tree_is_bounded():
	"""`File.folder` is a Link and nothing stops one pointing into its own
	subtree, so both walks need a cap rather than a `while True`."""
	for module in ("reading.py", "writing.py"):
		assert "DEPTH" in (DRIVE / module).read_text()


def test_a_folder_name_cannot_contain_a_slash():
	"""Frappe builds `Home/Attachments`-style names out of this."""
	source = (DRIVE / "writing.py").read_text()
	assert '"/" in title' in source


def test_deleting_a_folder_takes_what_is_in_it():
	"""A folder emptied of everything but the row is a folder that reappears
	empty, which reads as data loss whether or not it is."""
	source = (DRIVE / "writing.py").read_text()
	trashing = source[source.index("def trash("):source.index("def restore(")]
	assert "_subtree(" in trashing


def test_restoring_puts_things_back_where_they_were():
	"""Nothing cleared `folder` on the way in, precisely so this is possible —
	and a file whose folder was itself thrown away comes back to the top rather
	than into the bin."""
	source = (DRIVE / "writing.py").read_text()
	restoring = source[source.index("def restore("):source.index("def _subtree(")]
	assert '"Home"' in restoring
