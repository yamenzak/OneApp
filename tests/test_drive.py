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

import re
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

def _filters(drive, place):
	"""One place's filters. `record` is the only one that needs an address."""
	return drive._place_filters(place, attached_to=("ToDo", "abc"))


def test_every_place_is_a_filter_over_one_table(drive):
	"""There is no second store behind the rail, which is why it is cheap."""
	for place in drive.PLACES:
		filters, _or = _filters(drive, place)
		assert isinstance(filters, dict)


def test_the_bin_is_the_only_place_that_shows_trashed_files(drive):
	for place in drive.PLACES:
		filters, _or = _filters(drive, place)
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


# --------------------------------------------------------------------------- #
# The link that outlives a session
# --------------------------------------------------------------------------- #

def test_every_link_ends(drive):
	"""A link with no expiry is a file published for ever by somebody who has
	since left, and there is no control anywhere that would find it again."""
	source = (DRIVE / "sharing.py").read_text()
	making = source[source.index("def make_link("):source.index("def links(")]
	assert "expires_on" in making
	assert "1 <= days <= MAX_DAYS" in making


def test_a_link_cannot_outlast_the_person_who_made_it(drive):
	assert 30 <= drive.MAX_DAYS <= 365
	assert drive.DEFAULT_DAYS <= drive.MAX_DAYS


def test_a_folder_cannot_be_linked():
	"""It would be a link to everything anybody puts in it afterwards, which is
	not what the person sharing agreed to."""
	source = (DRIVE / "sharing.py").read_text()
	making = source[source.index("def make_link("):source.index("def links(")]
	assert "is_folder" in making


def test_making_a_link_needs_the_share_permission_and_not_read():
	"""Opening a file and publishing it to the internet are different things,
	and Frappe already has both permissions."""
	source = (DRIVE / "sharing.py").read_text()
	for name in ("def make_link(", "def links(", "def revoke("):
		body = source[source.index(name):]
		body = body[:body.index("\n\n\n")]
		assert '"share"' in body, name


def test_the_secret_is_random_and_not_derived(drive):
	"""A secret that is a hash of the file name is a secret anybody who knows
	the file name already has."""
	source = (DRIVE / "sharing.py").read_text()
	assert "import secrets" in source
	assert "token_urlsafe(SECRET_BYTES)" in source
	assert drive.SECRET_BYTES >= 16


def test_a_guest_is_told_nothing_about_why_a_link_failed():
	"""Different messages for revoked, expired and wrong would tell a stranger
	whether the secret they guessed was right."""
	source = (DRIVE / "sharing.py").read_text()
	opening = source[source.index("def open_link("):source.index("def sweep_links(")]
	assert opening.count('_("This link is not available.")') == 2
	# And nothing else — no other message can leak out of that function.
	assert "frappe.throw" in opening
	assert opening.count("frappe.throw") == 2


def test_revoking_marks_rather_than_deletes():
	"""'Who shared this, and when did it stop' is a question somebody asks
	after something has gone wrong, and a deleted row answers with silence."""
	source = (DRIVE / "sharing.py").read_text()
	revoking = source[source.index("def revoke("):source.index("def _shape(")]
	assert 'db_set("revoked", 1' in revoking
	assert "delete_doc" not in revoking


def test_a_link_works_on_a_site_with_no_bucket():
	"""Development runs without R2 keys and so does anybody self-hosting before
	they have a bucket. There the object is on local disk, there is nothing to
	presign, and the bytes have to come back in the response instead.

	One function, in `r2`, because a preview that only worked on a site with a
	bucket was exactly this bug on the other route: it fetched the download
	endpoint and rendered the error page as the file's contents.
	"""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/storage/r2.py").read_text()
	serving = source[source.index("def serve("):source.index("def sync_backup_to_r2(")]
	assert "is_configured()" in serving
	assert "filecontent" in serving
	assert "r2.serve(" in (DRIVE / "sharing.py").read_text()


def test_the_audit_trail_outlives_the_link():
	"""'This stopped working last Tuesday' is the answer somebody needs in the
	week after it stops working."""
	source = (DRIVE / "sharing.py").read_text()
	sweeping = source[source.index("def sweep_links("):]
	assert "-30" in sweeping


# --------------------------------------------------------------------------- #
# The picker
# --------------------------------------------------------------------------- #

def test_the_picker_looks_at_every_file_and_not_the_root(drive):
	"""Almost every file in a workspace is an attachment and lives in
	`Home/Attachments`, so a picker over the root folder is an empty picker."""
	filters, _or = drive._place_filters(drive.ALL)
	assert "folder" not in filters
	assert filters["name"] == ["!=", "Home"]


def test_attaching_writes_a_second_row_rather_than_moving_the_file():
	"""The file being picked is usually already attached to something else —
	which is generally why it was worth picking."""
	source = (DRIVE / "writing.py").read_text()
	attaching = source[source.index("def attach("):source.index("def trash(")]
	assert "file_url" in attaching
	assert "attached_to_doctype" in attaching
	# And it points at the *same* bytes, in both storage worlds: the R2 key so
	# the download resolves, and the content hash so Frappe's own delete spares
	# the file on disk while a second row still names it.
	assert '"r2_key"' in attaching
	assert "content_hash" in attaching


def test_a_second_row_over_one_object_is_not_uploaded_twice():
	"""`File.after_insert` moves content to R2. The row a pick writes has no
	content of its own — reading it back would mean fetching our own download
	route, and uploading it again would bill the workspace twice for one file."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/storage/file.py").read_text()
	inserting = source[source.index("def after_insert("):source.index("def move_to_r2(")]
	assert 'self.get("r2_key")' in inserting


def test_deleting_one_attachment_does_not_empty_the_other():
	"""Two rows can point at one object, which is what picking a file that is
	already attached somewhere writes. Deleting the object because one of them
	went would empty the original, from a record nobody was looking at."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/storage/file.py").read_text()
	trashing = source[source.index("def on_trash("):]
	assert "shared_object(key)" in trashing


def test_sharing_a_file_does_not_make_it_undeletable():
	"""Frappe refuses to delete anything another document links to, and a
	`File Link` is a link. Without the hook, sharing a drawing once makes that
	drawing permanent — with an error naming a doctype nobody has heard of."""
	hooks = (ROOT / "apps/oneapp/oneapp/hooks.py").read_text()
	assert 'ignore_links_on_delete = ["File Link"]' in hooks
	# And the links go rather than being orphaned: an orphan answers a
	# stranger's request with a stack trace instead of the one sentence.
	trashing = (ROOT / "apps/oneapp/oneapp/oneapp_core/storage/file.py").read_text()
	assert '"File Link"' in trashing[trashing.index("def on_trash("):]


def test_a_records_files_are_the_same_query_with_one_more_clause(drive):
	"""Which is the whole design: the Drive and a record's Files tab are two
	`where` clauses over one table, so the tab draws the Drive's own rows."""
	filters, _or = drive._place_filters("record", attached_to=("Project", "P-1"))
	assert filters["attached_to_doctype"] == "Project"
	assert filters["attached_to_name"] == "P-1"
	# And it is still the visible-files filter underneath, so a record's
	# attachment that somebody binned does not reappear on the record.
	assert filters[drive.STATUS_FIELD] == ["in", [drive.ACTIVE, "", None]]


def test_a_records_files_needs_a_record(drive):
	"""Unaddressed, it would be every attachment on the site. `get_list` would
	still scope it to what the reader may see; that is not a reason to ask a
	question that broad by accident."""
	import frappe

	with pytest.raises(frappe.ValidationError):
		drive._place_filters("record")


def test_the_storage_screen_says_which_file_and_not_only_which_kind(drive):
	"""'Photographs' is not something a person can act on. 'This 400 MB video'
	is."""
	source = (DRIVE / "reading.py").read_text()
	storing = source[source.index("def storage("):]
	for key in ('"by_kind"', '"by_folder"', '"biggest"'):
		assert key in storing


def test_a_favourite_needs_only_read(drive):
	"""A file somebody shared with you read-only is a file you may want to find
	again, and your own intention about it changes nothing about the file."""
	source = (DRIVE / "writing.py").read_text()
	faving = source[source.index("def set_favourite("):source.index("def trash(")]
	assert 'check_permission("read")' in faving
	assert 'check_permission("write")' not in faving


def test_a_colleague_share_is_docshare_and_nothing_of_ours(drive):
	"""The same row the record surface writes, read back by the same
	`get_list`, revoked by removing it."""
	source = (DRIVE / "sharing.py").read_text()
	sharing = source[source.index("def share_with("):source.index("def unshare_with(")]
	assert "collab.share(" in sharing
	assert "DocShare" not in sharing


def test_a_file_cannot_be_shared_outside_the_workspace(drive):
	"""Worse on a `File` than on a record: a file is the thing people send."""
	source = (DRIVE / "sharing.py").read_text()
	sharing = source[source.index("def share_with("):source.index("def unshare_with(")]
	assert "_colleagues()" in sharing


# --------------------------------------------------------------------------- #
# The record's Files tab
# --------------------------------------------------------------------------- #

def test_a_records_files_are_the_drives_own_rows():
	"""Two lists that looked alike would be two places to add a column to, and
	the tab would be the one that never got it."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview/surround.py").read_text()
	listing = source[source.index("def attachments("):source.index("def _gallery_filters(")]
	assert "reading.FIELDS" in listing
	assert "reading._shape(" in listing


def test_taking_a_file_off_a_record_is_reversible():
	"""It used to remove the row outright, so a misplaced click on the wrong
	record's Files tab could not be undone — which is what the bin is for."""
	source = (ROOT / "apps/oneapp/frontend/src/components/screen/record/RecordFiles.vue").read_text()
	assert "driveTrash" in source


# --------------------------------------------------------------------------- #
# The storage screen
# --------------------------------------------------------------------------- #

def test_the_storage_screen_says_what_it_cannot_see():
	"""The meter is the workspace's real usage and the breakdown is what this
	reader may see. A breakdown that summed to the meter would be a breakdown
	that leaked what it could not show, so the screen says they differ."""
	source = (ROOT / "apps/oneapp/frontend/src/components/settings/StorageSettings.vue").read_text()
	assert "cannot open" in source


def test_the_rail_and_the_phone_offer_the_same_places(drive):
	"""The shell draws a sidebar only on a desktop, so the phone reaches the
	places through a dropdown. Two hand-kept lists is how one of them ends up
	without the bin."""
	source = (ROOT / "apps/oneapp/frontend/src/components/drive/places.js").read_text()
	offered = set(re.findall(r"value: '(\w+)'", source))
	# `all` and `record` are not in the rail on purpose — one is the picker's
	# flat view and the other is a record's Files tab.
	assert offered == set(drive.PLACES) - {drive.ALL, "record"}

	# And one list rather than two copies of it.
	rail = (ROOT / "apps/oneapp/frontend/src/components/drive/DriveSidebar.vue").read_text()
	page = (ROOT / "apps/oneapp/frontend/src/pages/Drive.vue").read_text()
	assert "from './places'" in rail
	assert "drive/places'" in page
