"""A folder on somebody else's server, and the boundary around it.

Two things here could go quietly wrong in a way no screen would show. A path
that walks upward turns a mount's base into the whole host's filesystem; and a
`remote://` name reaching a write turns "this cannot be renamed" into a stack
trace about a `File` that does not exist. Both are one line of code and both
are asserted here.

The transports themselves are not: paramiko and ftplib are somebody else's and
testing them needs a server. What is ours is the naming, the ordering, the row
shape and the refusals.
"""

import sys

import pytest


@pytest.fixture
def remote(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onestorage"):
			del sys.modules[name]
	from oneapp.onestorage import remote as module

	return module


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #

def test_a_name_carries_its_mount_and_its_path(remote):
	assert remote.idfor("drops", "/2026/june") == "remote://drops/2026/june"
	assert remote.split("remote://drops/2026/june") == ("drops", "/2026/june")


def test_the_top_of_a_mount_is_a_path_too(remote):
	"""`remote://drops/` and `remote://drops` are the same folder, and the rail
	writes the first while a crumb writes the second."""
	assert remote.split("remote://drops/") == ("drops", "/")
	assert remote.split("remote://drops") == ("drops", "/")


def test_one_of_ours_is_not_remote(remote):
	assert not remote.is_remote("Home/Drawings")
	assert not remote.is_remote("")
	assert remote.is_remote("remote://drops/x")


def test_a_path_cannot_walk_upwards(remote):
	"""The mount's whole security boundary. Refused rather than normalised:
	`normpath` over a symlink gives an answer the host disagrees with."""
	for bad in ("/../etc", "/a/../../b", "..", "/a/./b"):
		with pytest.raises(Exception):
			remote.safe_path(bad)


def test_the_base_path_is_what_a_path_is_under(remote):
	assert remote._join("/out", "/2026/june") == "/out/2026/june"
	assert remote._join("out", "/") == "/out"
	assert remote._join("/", "/june") == "/june"


def test_a_crumb_walks_without_asking_the_host(remote):
	"""The one thing a mount is easier at than a `File`: the parent of
	`/2026/june` is `/2026` and nothing has to be read to know it."""
	assert remote.crumbs("remote://drops/2026/june") == [
		{"name": "remote://drops/", "label": "drops"},
		{"name": "remote://drops/2026", "label": "2026"},
		{"name": "remote://drops/2026/june", "label": "june"},
	]


# --------------------------------------------------------------------------- #
# Rows
# --------------------------------------------------------------------------- #

def test_a_row_is_the_shape_the_list_already_draws(remote):
	"""Every field `reading.FIELDS` reads, and the three the list adds. A row
	missing one is a column that renders `undefined`."""
	from oneapp.onestorage import reading

	row = remote._row("drops", "/2026", {"name": "june.zip", "is_dir": False,
	                                     "size": 4096, "mtime": 0})
	for field in reading.FIELDS:
		if field == "_liked_by":
			continue
		assert field in row, field
	for extra in ("liked", "owner_person", "folder_label", "remote"):
		assert extra in row


def test_a_remote_row_says_which_mount_it_is_on(remote):
	"""What every surface reads to know this is not ours: the row hides its
	heart, the pane offers Copy, and `writing` refuses it."""
	row = remote._row("drops", "/", {"name": "a.zip", "is_dir": False, "size": 1,
	                                 "mtime": 0})
	assert row["remote"] == "drops"
	assert row["name"] == "remote://drops/a.zip"
	assert row["folder"] == "remote://drops/"


def test_nobody_owns_a_remote_file(remote):
	"""Not the reader, which is the tempting wrong answer — a details pane
	would then grow an avatar for somebody who has never seen the file."""
	row = remote._row("drops", "/", {"name": "a.zip", "is_dir": False, "size": 1,
	                                 "mtime": 0})
	assert row["owner"] == ""
	assert row["liked"] is False


def test_a_folder_weighs_nothing(remote):
	"""Whatever the host says. An FTP directory's `size` is its inode, and
	summing those into the Drive's own figures is how a mount appears to be
	using storage it is not."""
	row = remote._row("drops", "/", {"name": "2026", "is_dir": True,
	                                 "size": 4096, "mtime": 0})
	assert row["file_size"] == 0
	assert row["is_folder"] == 1


def test_folders_sort_first_whatever_the_key(remote):
	"""The rule `query.ordering` keeps. A remote listing that mixed them would
	be the one list in the product that did."""
	rows = [
		remote._row("d", "/", {"name": "z.zip", "is_dir": False, "size": 9, "mtime": 0}),
		remote._row("d", "/", {"name": "a", "is_dir": True, "size": 0, "mtime": 0}),
	]
	for key in ("", "name", "size", "kind"):
		assert [one["file_name"] for one in sorted(rows, key=remote._order(key))][0] == "a"


# --------------------------------------------------------------------------- #
# The refusals
# --------------------------------------------------------------------------- #

def test_a_write_aimed_at_a_mount_is_refused_in_words(remote):
	with pytest.raises(Exception):
		remote.deny("remote://drops/a.zip")
	# And one of ours passes straight through.
	assert remote.deny("Home/Drawings") is None


def test_every_mutation_checks(stub_frappe):
	"""The list that matters, read off the source rather than remembered: a
	write added later without the guard is a stack trace about a `File` that
	has never existed."""
	import pathlib

	root = pathlib.Path(__file__).resolve().parent.parent
	for module, wants in (
		("writing.py", ("_mine", "set_favourite", "attach")),
		("sharing.py", ("share_with", "unshare_with", "make_link")),
	):
		source = (root / "apps/oneapp/oneapp/onestorage" / module).read_text()
		for fn in wants:
			body = source.split(f"def {fn}(")[1].split("\n@frappe")[0]
			assert "_deny_remote" in body, f"{module}:{fn} does not refuse a mount"


def test_the_download_route_serves_a_mount(stub_frappe):
	import pathlib

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onestorage/r2.py"
	).read_text()
	body = source.split("def download(")[1].split("\ndef ")[0]
	assert "remote.is_remote" in body
	assert "remote.fetch" in body


def test_the_drive_reads_a_mount_instead_of_the_table(stub_frappe):
	"""All three read paths, because a mount is browsed, walked and opened —
	and any one of them left behind is a `File` query for a name no `File`
	has."""
	import pathlib

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onestorage/reading.py"
	).read_text()
	for fn, wants in (("listing(", "remote.listing"), ("path(", "remote.crumbs"),
	                  ("details(", "remote.details")):
		body = source.split(f"def {fn}")[1].split("\n@frappe")[0]
		assert wants in body, fn


# --------------------------------------------------------------------------- #
# And the feed reader stopped carrying a password
# --------------------------------------------------------------------------- #

def test_onemobility_has_no_transport_of_its_own(stub_frappe):
	import pathlib

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onemobility/sources.py"
	).read_text()
	# The word survives in the prose that explains why it went. What must not
	# survive is the import.
	assert "import paramiko" not in source, (
		"the drop folder is `onestorage.remote` now; a second SFTP client here "
		"is a second copy of the credentials"
	)
	# HTTP basic auth still has one, and should: an endpoint's credential is
	# not a folder. What went is the folder's.
	assert "_over_sftp" not in source
	assert "remote.newest" in source


def test_a_source_names_a_mount_rather_than_a_host(stub_frappe):
	import json
	import pathlib

	shape = json.loads((
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onemobility/doctype/transit_source/transit_source.json"
	).read_text())
	fields = {one["fieldname"]: one for one in shape["fields"]}

	assert fields["remote_folder"]["options"] == "Remote Folder"
	assert "SFTP" not in fields["kind"]["options"]
	assert "Folder" in fields["kind"]["options"].split("\n")


def test_the_mount_doctype_keeps_its_secrets_in_auth(stub_frappe):
	"""Both of them. A key in a Data field is a key in every list payload."""
	import json
	import pathlib

	shape = json.loads((
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onestorage/doctype/remote_folder/remote_folder.json"
	).read_text())
	fields = {one["fieldname"]: one for one in shape["fields"]}
	assert fields["secret"]["fieldtype"] == "Password"
	assert fields["private_key"]["fieldtype"] == "Password"


# --------------------------------------------------------------------------- #
# Managing one, from where it is used
# --------------------------------------------------------------------------- #

def test_a_mount_something_reads_cannot_be_disconnected(remote, monkeypatch):
	"""Frappe's own link check would refuse it too, and would name a doctype
	and an id. A person deciding whether to drop a drop folder needs to read
	which feed still wants it."""
	monkeypatch.setattr(remote, "mount_doc",
	                    lambda name, write=False: type("D", (), {"name": name, "folder_name": name})())
	monkeypatch.setattr(remote.frappe, "get_all", lambda *a, **kw: ["VDV planning"])
	with pytest.raises(Exception) as failed:
		remote.disconnect("drops")
	assert "VDV planning" in str(failed.value)


def test_pausing_is_a_status_and_not_a_delete(remote):
	"""The reason it exists: a key rotated at nine on a Monday is a connection
	you want off for an hour, not a credential you want to retype."""
	source = pathlib_source(remote)
	body = source.split("def set_paused(")[1].split("\n@frappe")[0]
	assert '"Paused"' in body and '"Connected"' in body
	assert "delete" not in body


def test_a_paused_mount_refuses_every_read(remote):
	"""Including the feeds. A pause a scheduled poll ignored would be a pause
	that does nothing at three in the morning, which is when it matters."""
	source = pathlib_source(remote)
	body = source.split("def connect(")[1].split("\nclass ")[0]
	assert 'doc.status == "Paused"' in body


def pathlib_source(module):
	import pathlib

	return pathlib.Path(module.__file__).read_text()
