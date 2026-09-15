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

import where

ROOT = Path(__file__).resolve().parent.parent
DRIVE = ROOT / "apps/oneapp/oneapp/onestorage"


@pytest.fixture
def drive(monkeypatch):
	from oneapp import onestorage as module

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
	from oneapp.onestorage.query import _visible

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
	"""There is no second store behind the rail, which is why it is cheap.

	`records` is the exception and is still not a second store: it is a *tree*
	rather than a `where`, walked by `scopes.py` out of the attachment rows at
	the moment it is asked for — the same tree a mounted `doctype:Quotation`
	presents. So it has no clause here, and that is the thing to assert."""
	for place in drive.PLACES:
		filters, _or = _filters(drive, place)
		assert isinstance(filters, dict)

	source = (ROOT / "apps/oneapp/oneapp/onestorage/query.py").read_text()
	clauses = source[source.index("def _place_filters("):source.index("def _searching(")]
	assert "RECORDS" not in clauses, (
		"the Records place grew a filter — it is a tree, and two answers to "
		"what a record has on it is exactly what §E1 was about"
	)


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
# A record's room, which is a place rather than a viewer
# --------------------------------------------------------------------------- #

@pytest.fixture
def making(monkeypatch, stub_frappe):
	"""`make_folder`, with the row it would insert captured instead."""
	from oneapp.onestorage import writing

	made = {}
	asked = []

	class Fake:
		def __init__(self, fresh):
			self.__dict__.update(fresh)
			self.name = "made"

		def get(self, key, fallback=None):
			return self.__dict__.get(key, fallback)

		def insert(self):
			made.update(self.__dict__)
			return self

		def check_permission(self, what):
			asked.append((getattr(self, "doctype", "?"), what))

	def get_doc(first, second=None, **kw):
		if isinstance(first, dict):
			return Fake(first)
		# A record, or an existing File — both answer `check_permission`.
		row = Fake(dict(parents.get((first, second), {})))
		row.doctype = first
		return row

	parents = {}
	monkeypatch.setattr(stub_frappe, "get_doc", get_doc, raising=False)
	monkeypatch.setattr(writing, "_deny_remote", lambda name: None, raising=False)
	return types.SimpleNamespace(
		run=writing.make_folder, made=made, asked=asked, parents=parents,
	)


def test_a_folder_in_a_room_is_a_file_that_is_both(making):
	"""The whole of how a room becomes writable without a row per record.

	§E1 refuses a directory per record — four thousand quotations is four
	thousand rows. A folder that carries `attached_to_*` is a row only because
	somebody made it, so a record nobody filed anything under still costs
	nothing."""
	making.run("Correspondence", doctype="Project", docname="P-1")

	assert making.made["is_folder"] == 1
	assert making.made["attached_to_doctype"] == "Project"
	assert making.made["attached_to_name"] == "P-1"
	# No parent: a room is the top, and `file.py` names it from the room.
	assert not making.made["folder"]


def test_making_one_asks_the_record_and_not_the_folder(making):
	"""A room is the record's, so permission to file something in it is
	permission to change the record."""
	making.run("Correspondence", doctype="Project", docname="P-1")
	assert ("Project", "write") in making.asked


def test_a_folder_inside_a_room_stays_the_records(making):
	"""Otherwise a subfolder is a quiet way out of the permission the room
	hangs off — and a file three deep would be in the drive, not on the
	record."""
	making.parents[("File", "Project/P-1/Drawings")] = {
		"attached_to_doctype": "Project", "attached_to_name": "P-1",
	}
	making.run("Revisions", folder="Project/P-1/Drawings")

	assert making.made["attached_to_doctype"] == "Project"
	assert making.made["folder"] == "Project/P-1/Drawings"


def test_an_ordinary_folder_is_not_anybodys_room(making):
	making.parents[("File", "Home/Drawings")] = {}
	making.run("Revisions", folder="Home/Drawings")

	assert not making.made.get("attached_to_doctype")


@pytest.fixture
def moving(monkeypatch, stub_frappe):
	"""`move`, over rows a test can describe."""
	from oneapp.onestorage import writing

	rows = {}
	saved = []

	class Row:
		def __init__(self, name, fields):
			self.name = name
			self.__dict__.update(fields)

		def get(self, key, fallback=None):
			return self.__dict__.get(key, fallback)

		def check_permission(self, what):
			pass

		def save(self):
			saved.append(self)

	def get_doc(first, second=None, **kw):
		if isinstance(first, dict):
			return Row("made", first)
		key = second if second is not None else first
		row = Row(key, dict(rows.get(key, {})))
		row.doctype = first
		return row

	monkeypatch.setattr(stub_frappe, "get_doc", get_doc, raising=False)
	monkeypatch.setattr(stub_frappe.db, "get_value", lambda *a, **k: None, raising=False)
	monkeypatch.setattr(writing, "_deny_remote", lambda name: None, raising=False)
	return types.SimpleNamespace(run=writing.move, rows=rows, saved=saved)


def test_a_file_moved_into_a_room_becomes_the_records(moving):
	"""The test of whether the Records tree is a place or a viewer."""
	moving.rows["f1"] = {"folder": "Home", "attached_to_doctype": "", "attached_to_name": ""}
	moving.run(["f1"], doctype="Project", docname="P-1")

	one = moving.saved[0]
	assert (one.attached_to_doctype, one.attached_to_name) == ("Project", "P-1")
	# The top of a room is not a folder — there is no row to be inside.
	assert one.folder == ""


def test_a_file_moved_out_of_a_room_stops_being_the_records(moving):
	moving.rows["f1"] = {"folder": "", "attached_to_doctype": "Project", "attached_to_name": "P-1"}
	moving.rows["Home/Drawings"] = {"folder": "Home"}
	answer = moving.run(["f1"], folder="Home/Drawings")

	one = moving.saved[0]
	assert not one.attached_to_doctype
	# Counted, so the warning the caller showed can be checked against what
	# actually happened rather than against what it predicted.
	assert answer["left"] == 1


def test_filing_an_attachment_does_not_detach_it(moving):
	""""A file can have both" is the sentence the module rests on. An
	attachment somebody also filed into a folder of their own is attached *and*
	in the drive, and dragging it between two drive folders has nothing to do
	with the record it belongs to."""
	moving.rows["f1"] = {
		"folder": "Home/Invoices", "attached_to_doctype": "Project", "attached_to_name": "P-1",
	}
	moving.rows["Home/Paid"] = {"folder": "Home"}
	answer = moving.run(["f1"], folder="Home/Paid")

	one = moving.saved[0]
	assert one.attached_to_doctype == "Project"
	assert answer["left"] == 0


def test_a_move_inside_one_room_keeps_the_record(moving):
	moving.rows["f1"] = {"folder": "", "attached_to_doctype": "Project", "attached_to_name": "P-1"}
	moving.rows["Project/P-1/Drawings"] = {
		"folder": "", "attached_to_doctype": "Project", "attached_to_name": "P-1",
	}
	answer = moving.run(["f1"], folder="Project/P-1/Drawings")

	assert moving.saved[0].attached_to_doctype == "Project"
	assert answer["left"] == 0


def test_a_room_folder_is_named_after_the_room():
	"""Two records may each have a `Correspondence`. Frappe names a parentless
	folder by its title alone, so without this they would be one primary key —
	and the obvious fix, a real parent per record, is the row-per-record §E1
	refuses."""
	source = (DRIVE / "file.py").read_text()
	naming = source[source.index("def autoname("):source.index("def set_folder_name(")]
	assert "attached_to_doctype}/{self.attached_to_name}" in naming


def test_a_file_landing_in_a_room_becomes_the_records():
	"""The test of whether the Records tree is a place or a viewer: the room
	lists what is attached to the record, so an unattached file in one of its
	folders is invisible from both directions at once.

	On the row and not in the upload endpoint, because there is more than one
	way in — the signed upload, `upload_file`, the sheet a child table writes,
	a copy."""
	source = (DRIVE / "file.py").read_text()
	inserting = source[source.index("def before_insert("):source.index("def autoname(")]
	assert "self.folder and not self.attached_to_doctype" in inserting
	assert "attached_to_name = room.attached_to_name" in inserting


def test_the_two_levels_above_a_room_are_still_a_query():
	"""A doctype and a primary key are not anybody's choice. `can_write` is
	true at the record and nowhere above it."""
	source = (DRIVE / "reading.py").read_text()
	records = source[source.index("def _records("):source.index("def _kinds_with_files(")]
	inside, outside = records.split("if parts:", 1)
	assert 'found["can_write"] = True' in inside
	assert '"can_write": False' in outside


def test_a_room_puts_its_folders_first(drive):
	"""A room has folders of its own now, and a file manager that mixes them is
	one where a folder is somewhere in the middle of page two."""
	from oneapp.onestorage.query import ORDER

	assert ORDER["record"].startswith("is_folder desc")
	assert ORDER["records"].startswith("is_folder desc")


def test_what_a_record_makes_lands_in_its_room():
	"""A sheet started from a child table, a document written about a record,
	and a file put in an Attach field are all attachments already — so this is
	a check rather than a build, and the check is that none of them names a
	folder on the way in.

	`folder or "Home"` is the default they all pass, and `file.py` reads `Home`
	on an attachment as "nobody filed this anywhere" and clears it — which is
	what puts them at the top of the room rather than at the top of the drive.
	"""
	for module in ("onesheet", "onedoc"):
		source = (
			ROOT / f"apps/oneapp/oneapp/{module}/writing.py"
		).read_text()
		making = source[source.index("def make("):source.index("def make_text(")
		                if "def make_text(" in source else len(source)]
		assert '"folder": folder or "Home"' in making, module
		assert '"attached_to_doctype": doctype or None' in making, module

	cleared = (DRIVE / "file.py").read_text()
	assert 'if self.attached_to_doctype and (self.folder or ROOT) == ROOT:' in cleared


def test_a_room_folder_can_be_mounted_like_any_other():
	"""Sharing and DAV needed no new code, which was the claim worth checking.

	A scope is a folder id or `doctype:<name>`, and a room folder's id is an
	ordinary `File` name — so it mounts through the same branch every other
	folder does. What makes it safe is that the branch reads with `get_list`:
	an attachment's permission follows the document it hangs off, so a room
	somebody may not read is an empty directory rather than a leak."""
	source = (DRIVE / "scopes.py").read_text()
	assert "frappe.get_list(" in source
	assert "frappe.get_all(" not in source, (
		"a scope reading with get_all would hand a key holder every file on "
		"the site — the permission is the whole of what a scope is"
	)


def test_a_mount_sees_the_same_room_as_the_drive():
	"""One resolver, or a rail place and a `doctype:Quotation` mount would be
	two answers to what a record has on it."""
	source = (DRIVE / "scopes.py").read_text()
	rooms = source[source.index("if node.about:"):source.index("if node.row:")]
	assert '"folder": ["is", "not set"]' in rooms


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
	source = (ROOT / "apps/oneapp/oneapp/onestorage/r2.py").read_text()
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
	source = (ROOT / "apps/oneapp/oneapp/onestorage/file.py").read_text()
	inserting = source[source.index("def after_insert("):source.index("def move_to_r2(")]
	assert 'self.get("r2_key")' in inserting


def test_deleting_one_attachment_does_not_empty_the_other():
	"""Two rows can point at one object, which is what picking a file that is
	already attached somewhere writes. Deleting the object because one of them
	went would empty the original, from a record nobody was looking at."""
	source = (ROOT / "apps/oneapp/oneapp/onestorage/file.py").read_text()
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
	trashing = (ROOT / "apps/oneapp/oneapp/onestorage/file.py").read_text()
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


def test_a_room_lists_its_loose_files_and_its_own_folders(drive):
	"""A record's room is a place now, so it has a top — the same distinction
	Home makes at the top of the drive, and drawn the same way. An attachment
	arrives with its folder cleared (`file.py`), so "not set" is what a loose
	file looks like."""
	filters, _or = drive._place_filters("record", attached_to=("Project", "P-1"))
	assert filters["folder"] == ["is", "not set"]

	inside, _or = drive._place_filters(
		"record", folder="Project/P-1/Drawings", attached_to=("Project", "P-1"),
	)
	assert inside["folder"] == "Project/P-1/Drawings"
	# And still the record's, so a folder is a narrowing of the room rather
	# than a way out of it.
	assert inside["attached_to_doctype"] == "Project"


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
	source = (ROOT / "apps/oneapp/oneapp/onespace/spaceview/surround.py").read_text()
	listing = source[source.index("def attachments("):source.index("def _gallery_filters(")]
	assert "reading.FIELDS" in listing
	assert "reading._shape(" in listing


def test_the_bin_is_not_a_second_place_a_record_keeps_a_file():
	"""A file in the bin is off the record's Files tab, and off its cap.

	Two halves of one bug, found together. The tab listed every `File` row
	pointing at the record, binned ones included, so the verb appeared to do
	nothing; and Frappe counts the same rows against `max_attachments`, so four
	thrown-away files filled ERPNext Project's limit of four for good — the tab
	showed nothing and the fifth upload was refused with nothing visible to
	remove."""
	listing = (ROOT / "apps/oneapp/oneapp/onespace/spaceview/surround.py").read_text()
	shown = listing[listing.index("def attachments("):listing.index("def _gallery_filters(")]
	assert "_visible()" in shown, "a record's Files tab still lists the bin"

	override = (ROOT / "apps/oneapp/oneapp/onestorage/file.py").read_text()
	assert "def validate_attachment_limit(self):" in override, (
		"the cap counts binned files again"
	)
	counting = override[override.index("def validate_attachment_limit(self):"):]
	assert "_visible()" in counting, "the cap is counted over some other set"
	assert "super().validate_attachment_limit()" in counting, (
		"the refusal is spelled out here rather than left to the framework"
	)


def test_an_attachment_lands_on_its_record_and_not_in_a_bucket():
	"""§E1's fourth guard: no file is written to `Home/Attachments`.

	Frappe's own `set_folder_name` puts every file with an `attached_to_doctype`
	into one folder, so a workspace with four thousand quotations has four
	thousand files in a folder nobody browses, sitting *beside* the tree
	somebody made rather than inside it. Since the Records tree that bucket has
	nothing left to be.

	Two halves, and the second is what makes the first safe: Home lists
	`folder in ["", "Home", None]`, so dropping the bucket without excluding
	attachments from the root would surface every attachment in the workspace
	at the top of the drive — worse than the bucket was."""
	override = (ROOT / "apps/oneapp/oneapp/onestorage/file.py").read_text()
	assert "def set_folder_name(self):" in override, (
		"attachments are back in Frappe's flat bucket"
	)

	home = (ROOT / "apps/oneapp/oneapp/onestorage/query.py").read_text()
	clauses = home[home.index("def _place_filters("):home.index("def _searching(")]
	assert 'filters["attached_to_doctype"] = ["is", "not set"]' in clauses, (
		"the top of the drive lists every attachment in the workspace"
	)

	# And nothing writes the folder by hand either, which is how one caller
	# quietly keeps the bucket alive for its own files.
	for one in sorted((ROOT / "apps/oneapp/oneapp").rglob("*.py")):
		if one.name in ("query.py", "reading.py", "file.py", "writing.py"):
			continue
		text = one.read_text()
		assert '"folder": "Home/Attachments"' not in text, (
			f"{one.name} files its attachments into the bucket by hand"
		)


def test_a_record_has_no_file_manager_of_its_own():
	"""There is one file manager in this product and a record's Files tab is a
	door into it — `docs/DRIVE.md` §13.

	It was a tab, and behind it were four hundred lines drawing a smaller
	OneCloud: a path, a New menu, an upload button, a selection bar and a
	trash verb, each of which had to be kept in step with the real one and
	each of which was the place a new column did not arrive. The door opens
	OneCloud at the record's room, which is a folder whose id is the record's
	own address, so it is the same list with the same verbs rather than a
	second list that resembles it.
	"""
	assert not (ROOT / "apps/oneapp/frontend/src/modules/onespace/components"
	            "/screen/record/RecordFiles.vue").exists(), (
		"the record grew its own file manager back"
	)
	source = where.source("RecordView.vue")
	assert "showDrive" in source and "roomOf" in source, (
		"the record's Files door no longer opens OneCloud at the record's room"
	)


# --------------------------------------------------------------------------- #
# The storage screen
# --------------------------------------------------------------------------- #

def test_the_storage_screen_says_what_it_cannot_see():
	"""The meter is the workspace's real usage and the breakdown is what this
	reader may see. A breakdown that summed to the meter would be a breakdown
	that leaked what it could not show, so the screen says they differ."""
	source = (ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings/StorageSettings.vue").read_text()
	assert "cannot open" in source


def test_every_kind_somebody_makes_here_has_a_door(drive):
	"""§E2+E3's first guard, and the finding behind it: a person who wanted to
	see *their documents* had nowhere to go.

	`custom_kind` held `Doc` and `Sheet` as first-class kinds, every rail place
	is one `where`, and neither had one — so the cheapest large improvement in
	section E was four filters the product already computed and did not offer.

	Mechanical, from `kinds.py`: a kind that is declared rather than derived
	from a filename is a kind somebody *made* here, and a thing somebody makes
	needs a list of the ones they made."""
	from oneapp.onestorage import kinds

	for kind in kinds.DECLARED:
		place = kinds.PLACE_FOR.get(kind)
		assert place, f"{kind} is made here and has no place to be listed in"
		assert place in drive.PLACES, f"{place} is not a place the endpoint takes"

	# And the place really is that filter, rather than a name that resolves to
	# whatever `_place_filters` falls through to.
	for place, kind in drive.EDITED.items():
		filters, _or = drive._place_filters(place)
		assert filters[drive.KIND_FIELD] == kind


def test_the_rail_and_the_phone_offer_the_same_places(drive):
	"""The shell draws a sidebar only on a desktop, so the phone reaches the
	places through a dropdown. Two hand-kept lists is how one of them ends up
	without the bin."""
	source = where.module("places.js").read_text()
	offered = set(re.findall(r"value: '(\w+)'", source))
	# `all` and `record` are not in the rail on purpose — one is the picker's
	# flat view and the other is a record's Files tab.
	#
	# And `start` is the other way round: a place the rail offers and the
	# endpoint does not. Home is three of the places below it — favourites,
	# recents, shared — asked for a few rows each and drawn in one screen, so
	# there is nothing for `listing` to take. It is the only entry here that
	# is allowed to be absent from the server's list, and a second one would
	# be a rail entry that opens onto nothing.
	assert offered - {"start"} == set(drive.PLACES) - {drive.ALL, "record"}
	assert "start" not in drive.PLACES, (
		"Home has grown a server-side filter; it is three lists, not a where"
	)

	# And one list rather than two copies of it.
	# One module, imported by both — the claim is that there is a single list,
	# not where the file sits.
	for name in ("DriveSidebar.vue", "Drive.vue"):
		assert where.imports(where.source(name), "places"), f"{name} has its own list"


def test_the_rail_is_drawn_from_the_places_and_never_types_one(drive):
	"""`PLACES` is the endpoint's vocabulary and `RAIL` is the rail, and the
	split is the whole reason the rail stopped growing an entry per filter.

	What it must not become is a second list. Every band is built by looking a
	value up in `PLACES` — `at('records')`, never `{ value: 'records', ... }` —
	so a place renamed on the server is a rail entry that stops resolving here
	rather than one that quietly points at nothing. This asserts the shape: no
	`value:` literal anywhere below the `PLACES` array."""
	source = where.module("places.js").read_text()
	below = source[source.index("export const RAIL"):source.index("export const labelOf")]
	assert "value:" not in below, (
		"the rail is typing its own places rather than looking them up in "
		"`PLACES`, which is how the two lists drift apart"
	)

	# And every value it does look up is one that exists. Every quoted word
	# below the array is either a band's own key or a place being looked up,
	# so subtracting the keys leaves exactly the second kind.
	keys = set(re.findall(r"key: '(\w+)'", below))
	looked = set(re.findall(r"'(\w+)'", below)) - keys
	assert looked <= offered_places(source), sorted(looked - offered_places(source))


def offered_places(source: str) -> set:
	"""The `value` of every entry in `places.js`'s `PLACES`."""
	return set(re.findall(r"value: '(\w+)'", source))


def test_every_place_in_the_rail_is_one_the_page_will_open(drive):
	"""The rail is one list and `Drive.vue`'s `EMPTY` is another, and the
	second one is a *gate*: `place` falls back to `home` for anything that is
	not a key of it.

	So a place in the rail and absent from `EMPTY` highlights when you click
	it, keeps the "Files" crumb, and lists everybody's files — no error, no
	empty state, nothing to notice except that the answer is wrong. Templates
	was in that state for several stages, and Code joined it the hour it was
	added. Found by looking at the screen, which is the third time in this arc
	that a clean build and four thousand guards said nothing.
	"""
	source = where.source("Drive.vue")
	start = source.index("const EMPTY = {")
	body = source[start:source.index("\n}", start)]
	stated = set(re.findall(r"^  (\w+): \{?", body, re.M))

	rail = set(re.findall(r"value: '(\w+)'", where.module("places.js").read_text()))
	missing = sorted(rail - stated)
	assert not missing, (
		"these places are in the Drive's rail and have no entry in `EMPTY`, so "
		f"opening one silently falls back to All files: {missing}"
	)

	# And the other way, minus the one that is deliberately not in the rail.
	assert stated - rail == {drive.ALL}, sorted(stated - rail - {drive.ALL})


def test_every_endpoint_in_the_package_is_reachable(drive):
	"""A `@frappe.whitelist` the package does not re-export is a 404.

	`details` was one for three stages. It is what stamps `custom_opened`, so
	the rail's Recents could never fill and read as a place nobody used — a
	whole feature absent because of a missing name in an import line, with
	nothing failing anywhere to say so.
	"""
	import re

	missing = []
	for module in ("kinds.py", "query.py", "reading.py", "writing.py", "sharing.py"):
		source = (DRIVE / module).read_text()
		for name in re.findall(r"@frappe\.whitelist\([^)]*\)\ndef (\w+)", source):
			if not hasattr(drive, name):
				missing.append(f"{module}:{name}")

	assert not missing, (
		"whitelisted and not re-exported, so the client's call 404s: "
		+ ", ".join(missing)
	)


def test_opening_a_file_survives_the_request_that_recorded_it():
	"""Frappe commits a request only when its HTTP method changes server state,
	so a write inside a `GET` is rolled back at the end of it — silently, on a
	route that answers 200. That is how Recents stayed empty while every
	ingredient of it worked in isolation."""
	source = (DRIVE / "reading.py").read_text()
	opening = source[source.index("def details("):source.index("def storage(")]
	assert "flags.commit = True" in opening


def test_a_failed_presign_does_not_leave_half_a_redirect():
	"""`presigned_url` can raise, and assigning the response type before calling
	it leaves `type=redirect` with no location behind — which Werkzeug answers as
	`Location: None`, a 500 saying nothing about what actually failed."""
	source = (ROOT / "apps/oneapp/oneapp/onestorage/r2.py").read_text()
	serving = source[source.index("def serve("):source.index("def sync_backup_to_r2(")]
	built = serving.index("presigned_url(")
	assigned = serving.index('response["type"] = "redirect"')
	assert built < assigned


def test_a_stored_key_is_not_a_working_bucket():
	"""A row keeps its `r2_key` through a site being reconfigured, and
	presigning needs the client and the credentials rather than the key. Serving
	on the key alone is a redirect nothing can build."""
	source = (ROOT / "apps/oneapp/oneapp/onestorage/r2.py").read_text()
	serving = source[source.index("def serve("):source.index("def sync_backup_to_r2(")]
	assert "if is_configured():" in serving
