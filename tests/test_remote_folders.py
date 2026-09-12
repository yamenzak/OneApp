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
	# And nothing here knows a mount from a Drive folder either. `walk` is the
	# seam that made a source one field: it addresses both the same way, so a
	# branch on which kind of folder this is would be the thing coming back.
	assert "walk.entries" in source
	assert "remote.newest" not in source, (
		"newest-first lost every delivery that arrived out of order; the "
		"folder is walked whole now"
	)
	assert "remote.connect" not in source and "mount_doc" not in source


def test_a_source_points_at_a_folder_and_nothing_else(stub_frappe):
	"""A folder in the Drive and a folder on somebody's SFTP host are one
	noun. Two fields on the form because both are rows and both deserve the
	framework's picker; one address below it, composed by `folder_key`."""
	import json
	import pathlib

	shape = json.loads((
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onemobility/doctype/transit_source/transit_source.json"
	).read_text())
	fields = {one["fieldname"]: one for one in shape["fields"]}

	assert "remote_folder" not in fields, (
		"a mount is one of two things `folder` may point at, not its own field"
	)
	assert fields["folder"]["fieldtype"] == "Dynamic Link"
	assert fields["folder"]["options"] == "folder_type"
	assert fields["folder_type"]["options"].split("\n") == ["File", "Remote Folder"]

	kinds = fields["kind"]["options"].split("\n")
	assert kinds == ["Folder", "HTTP", "Stream"], (
		"Upload folded into Folder: an upload lands in one now"
	)
	assert "SFTP" not in fields["kind"]["options"]

	# And below the form there is exactly one address, so no reader branches.
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import sources
	import inspect

	assert "remote.idfor" in inspect.getsource(sources.folder_key)


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


def test_browsing_a_paused_mount_does_not_unpause_it(remote):
	"""It did. The paused check lives inside `connect`, `listing` wrapped that
	in a try, and the handler wrote Failing over it — so clicking a mount you
	had just paused threw the pause away and replaced it with a symptom.

	Two halves, and both are asserted because either alone leaves the hole:
	`listing` refuses a paused mount before the try, and `_failing` refuses to
	overwrite a pause whatever reaches it.
	"""
	source = pathlib_source(remote)

	body = source.split("def listing(")[1].split("\ndef ")[0]
	before, _sep, after = body.partition("try:")
	assert 'doc.status == "Paused"' in before, (
		"the pause has to be checked before the try, or the handler rewrites it"
	)

	handler = source.split("def _failing(")[1].split("\n\n\n")[0]
	assert 'doc.status == "Paused"' in handler


def test_a_workspace_with_no_mounts_answers_nothing_rather_than_403(remote, monkeypatch):
	"""The rail asks on every Drive page load. `get_list` on a doctype the
	reader holds no role for raises, so a member with no mounts was getting
	two red console errors every time they opened Files — which the rail
	swallowed and the settings suite caught."""
	monkeypatch.setattr(remote.frappe, "has_permission", lambda *a, **kw: False,
	                    raising=False)
	def explode(*a, **kw):
		raise AssertionError("get_list must not be reached without permission")
	monkeypatch.setattr(remote.frappe, "get_all", explode)
	monkeypatch.setattr(remote.frappe, "get_list", explode, raising=False)

	assert remote.mounts() == []


# --------------------------------------------------------------------------- #
# SMB and WebDAV
# --------------------------------------------------------------------------- #

def test_every_protocol_has_a_port_and_a_client(remote):
	"""A protocol in the dropdown with no branch in `connect` is a mount that
	can be created and never opened."""
	source = pathlib_source(remote)
	body = source.split("def connect(")[1].split("\nclass ")[0]
	for protocol in remote.PROTOCOLS:
		assert protocol in remote.PORTS
		assert protocol in body or protocol in ("FTP",), (
			f"{protocol} is offered and `connect` does not build a client for it"
		)


def test_the_doctype_offers_exactly_what_connect_can_speak(stub_frappe, remote):
	"""The two lists are in different files and drift silently: a protocol in
	the dropdown that the code does not know fails at the first browse, and
	one in the code that the dropdown omits is dead."""
	import json
	import pathlib

	shape = json.loads((
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onestorage/doctype/remote_folder/remote_folder.json"
	).read_text())
	offered = {
		one["options"] for one in shape["fields"] if one["fieldname"] == "protocol"
	}.pop().split("\n")
	assert set(offered) == set(remote.PROTOCOLS)


def test_an_smb_path_becomes_a_unc_path(remote):
	"""`\\\\host\\share\\dir\\file`, which is the one path shape that is not
	posix — and the reason the first segment of `base_path` is the share."""
	client = remote._Smb.__new__(remote._Smb)
	client.host = "nas"
	assert client._unc("/drawings/2026/june.pdf") == r"\\nas\drawings\2026\june.pdf"
	assert client._unc("/drawings") == r"\\nas\drawings"


def test_an_smb_mount_must_name_a_share(remote):
	"""There is no listing above a share: `\\\\host\\` is not a directory, so a
	mount pointed at the root fails on its first browse with whatever the
	library happens to say."""
	assert "SMB" in remote.SHARED


def test_a_dav_response_is_read_by_local_name(remote):
	"""`D:`, `d:` and `lp1:` are all in the wild. A prefix match returns
	nothing for whichever server chose differently, which shows up as a mount
	that lists empty rather than one that fails — the worst way to be wrong."""
	body = b"""<?xml version="1.0"?>
	<lp1:multistatus xmlns:lp1="DAV:">
	  <lp1:response>
	    <lp1:href>/plans/</lp1:href>
	    <lp1:propstat><lp1:prop>
	      <lp1:resourcetype><lp1:collection/></lp1:resourcetype>
	    </lp1:prop></lp1:propstat>
	  </lp1:response>
	  <lp1:response>
	    <lp1:href>/plans/fahrplan.csv</lp1:href>
	    <lp1:propstat><lp1:prop>
	      <lp1:resourcetype/>
	      <lp1:getcontentlength>4096</lp1:getcontentlength>
	      <lp1:getlastmodified>Sat, 12 Sep 2026 07:20:23 GMT</lp1:getlastmodified>
	    </lp1:prop></lp1:propstat>
	  </lp1:response>
	</lp1:multistatus>"""
	found = remote._multistatus(body)
	assert [one[0] for one in found] == ["/plans/", "/plans/fahrplan.csv"]
	assert found[0][1]["is_dir"] is True
	assert found[1][1]["size"] == 4096
	assert found[1][1]["mtime"] > 0


def test_a_dav_collection_weighs_nothing(remote):
	"""SharePoint sends a `getcontentlength` on collections. Summing those
	into the Drive's figures is a folder that appears to be using storage."""
	body = (b'<d:multistatus xmlns:d="DAV:"><d:response><d:href>/a/</d:href>'
	        b"<d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype>"
	        b"<d:getcontentlength>4096</d:getcontentlength></d:prop></d:propstat>"
	        b"</d:response></d:multistatus>")
	assert remote._multistatus(body)[0][1]["size"] == 0


# --------------------------------------------------------------------------- #
# Editing one
# --------------------------------------------------------------------------- #

def test_the_settings_payload_never_carries_a_credential(remote):
	"""It is read by the browser to fill a form. A password that reaches the
	form is a password in a page somebody screenshares."""
	source = pathlib_source(remote)
	body = source.split("def folder_settings(")[1].split("\ndef ")[0]
	assert "has_secret" in body and "has_private_key" in body
	for leak in ('doc.get_password("secret")', '"secret": ', '"private_key": '):
		assert leak not in body, f"folder_settings sends {leak}"
	assert "secret" not in remote.EDITABLE and "private_key" not in remote.EDITABLE


def test_the_name_is_not_editable(remote):
	"""It is the mount's id and the first segment of every `remote://` path
	under it, so renaming one renames every link anybody saved."""
	assert "folder_name" not in remote.EDITABLE
	# Nor is pausing, which is one decision with one endpoint.
	assert "status" not in remote.EDITABLE


def test_a_blank_password_means_unchanged(remote):
	"""The form cannot show what it was, so it cannot tell "leave it" from
	"clear it" — and clearing a working credential by opening a form and
	saving it is the worse of the two mistakes."""
	source = pathlib_source(remote)
	body = source.split("def update_folder(")[1].split("\n@frappe")[0]
	assert "if fields.get(field)" in body


def test_an_edit_that_does_not_connect_changes_nothing(remote):
	"""A typo in a hostname should cost you the typo, not the connection that
	was working before you made it."""
	source = pathlib_source(remote)
	body = source.split("def update_folder(")[1].split("\n@frappe")[0]
	assert "doc.reload()" in body
	assert "for field, value in was.items()" in body
	assert "nothing was changed" in body


def test_both_paths_prove_before_they_keep(remote):
	"""Creating and editing run the same `_prove`, so neither can be the one
	that writes Connected without having connected."""
	source = pathlib_source(remote)
	for fn in ("connect_folder(", "update_folder("):
		body = source.split(f"def {fn}")[1].split("\n@frappe")[0]
		assert "_prove(doc)" in body, fn
	prove = source.split("def _prove(")[1]
	assert "client.listdir" in prove and '"status": "Connected"' in prove


def test_the_form_offers_the_protocols_the_server_speaks(remote):
	"""Three lists now say what a mount can be — `remote.PROTOCOLS`, the
	doctype's Select, and the dialog's own array — and the dialog is the one
	that drifts silently: a protocol missing from it is a protocol nobody can
	choose, and the form renders "Select option" over a mount that has one.
	Which is exactly what it did the first time this shipped.
	"""
	import pathlib
	import re

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/frontend/src/modules/onestorage/components/ConnectFolder.vue"
	).read_text()

	offered = re.search(r"const PROTOCOLS = \[([^\]]+)\]", source).group(1)
	assert set(re.findall(r"'([^']+)'", offered)) == set(remote.PROTOCOLS)

	# And the placeholder ports, for the same reason: a protocol with no
	# default shows an empty hint where every other one shows a number.
	ports = re.search(r"const PORTS = \{([^}]+)\}", source).group(1)
	assert set(re.findall(r"(\w+):", ports)) == set(remote.PORTS)
