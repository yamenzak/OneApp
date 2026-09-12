"""Serving a Drive folder as a WebDAV share.

The mirror of `test_remote_folders.py`, and the risks are different. That one
reaches out; this one is a **door into the workspace that the framework's own
authentication never sees** — `before_request` runs before `validate_auth`, so
every check on this path is ours and a missing one is not a 403 somewhere
else, it is a folder anybody can read.

So these assert the boundary rather than the protocol: that the route
authenticates, that a read-only key cannot write, that a path cannot climb out
of its scope, that a credential is never sent back, and that the two framework
behaviours this route depends on are still relied on deliberately — the
rollback after an exception, and the challenge Frappe would otherwise
overwrite.
"""

import sys

import pytest


@pytest.fixture
def dav(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onestorage"):
			del sys.modules[name]
	from oneapp.onestorage import dav as module

	return module


def source_of(module) -> str:
	import pathlib

	return pathlib.Path(module.__file__).read_text()


# --------------------------------------------------------------------------- #
# The boundary
# --------------------------------------------------------------------------- #

def test_a_path_cannot_climb_out_of_the_share(dav):
	"""The only thing between a key scoped to one folder and the whole Drive.

	`_parts` refuses rather than normalising, for the same reason `remote`
	does: resolving is the version that looks right and is not.
	"""
	body = source_of(dav).split("def _parts(")[1].split("\ndef ")[0]
	assert '".."' in body and "_Status(403)" in body

	# And the destination of a MOVE or COPY, which is a second path and was
	# the one it would be easy to forget.
	body = source_of(dav).split("def _destination(")[1].split("\ndef ")[0]
	assert '".."' in body and "_Status(403)" in body
	assert "startswith(PREFIX)" in body


def test_every_write_is_refused_to_a_read_only_key(dav):
	"""Read-only is the default, so this is the check most keys rely on."""
	for method in ("PUT", "MKCOL", "DELETE", "MOVE", "COPY", "PROPPATCH"):
		assert method in dav.WRITES, f"{method} changes something and is not in WRITES"
	# Nothing that only reads is in it — a read-only key that could not
	# PROPFIND would be a key that cannot be mounted at all.
	for method in ("GET", "HEAD", "PROPFIND", "OPTIONS", "LOCK", "UNLOCK"):
		assert method not in dav.WRITES

	body = source_of(dav).split("def serve(")[1].split("\nclass ")[0]
	assert "request.method in WRITES and key.read_only" in body


def test_a_key_acts_as_its_owner_and_never_wider(dav):
	"""The whole permission model. Without `set_user` the request would run as
	Guest or as whoever the last request left behind; with it, every `get_list`
	below is scoped to the person who made the key and nothing re-implements a
	permission."""
	body = source_of(dav).split("def _key_for(")[1].split("\ndef ")[0]
	assert "frappe.set_user(row.owner)" in body
	assert "compare_digest" in body, "a plain == leaks the secret's prefix by timing"
	assert "expires_on" in body and "enabled" in body


def test_the_secret_is_never_stored_and_never_returned(dav):
	"""It is a digest in the row and a plaintext in one response. A key that
	could be read back is a key an export or a screenshare leaks."""
	source = source_of(dav)
	assert "hashlib.sha256" in source

	body = source.split("def shares(")[1].split("\n@frappe")[0]
	for leak in ("secret_hash", "secret"):
		assert f'"{leak}"' not in body, f"`shares` sends {leak}"

	import json
	import pathlib

	shape = json.loads((
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/onestorage/doctype/drive_access/drive_access.json"
	).read_text())
	fields = {one["fieldname"]: one for one in shape["fields"]}
	assert fields["secret_hash"]["read_only"]
	assert "password" not in fields, "there is no reversible copy of the key"


# --------------------------------------------------------------------------- #
# The two framework behaviours this route leans on
# --------------------------------------------------------------------------- #

def test_every_write_commits_before_it_answers(dav):
	"""`application()` rolls the transaction back after any exception — and
	this route *returns by raising one*. So a handler that did not commit
	would answer 201 and change nothing, which is the worst shape a bug can
	take: the client believes the file arrived."""
	source = source_of(dav)
	for fn in ("_put", "_mkcol", "_delete", "_move", "_copy"):
		body = source.split(f"def {fn}(")[1].split("\ndef ")[0]
		assert "frappe.db.commit()" in body, f"{fn} answers without committing"


def test_the_basic_challenge_is_set_where_frappe_cannot_overwrite_it(dav):
	"""Frappe replaces `WWW-Authenticate` with an OAuth Bearer challenge on
	any 401 once resource metadata is on, and a client told to use Bearer
	never shows a password box — the share cannot be mounted at all.
	`frappe.local.response_headers` is applied after that, which is why the
	header is set twice."""
	body = source_of(dav).split("def _unauthorized(")[1].split("\ndef ")[0]
	assert "frappe.local.response_headers" in body
	assert "Basic realm=" in dav.CHALLENGE


def test_the_hook_returns_for_every_path_that_is_not_the_share(dav):
	"""It runs on every request the site serves, so the first thing it does
	has to be cheap and the second has to be leaving."""
	body = source_of(dav).split("def intercept(")[1].split("\n# ---")[0]
	assert "startswith(PREFIX" in body
	assert body.index("return") < body.index("_answered")


def test_the_hook_is_registered(stub_frappe):
	import pathlib

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/oneapp/hooks.py"
	).read_text()
	assert 'before_request = ["oneapp.onestorage.dav.intercept"]' in source


# --------------------------------------------------------------------------- #
# The protocol, where getting it wrong is invisible
# --------------------------------------------------------------------------- #

def test_a_collection_is_answered_as_one(dav):
	row = {"file_name": "Drawings", "is_folder": 1, "modified": None}
	out = dav._prop_xml("/dav/Drawings/", row)
	assert "<D:collection/>" in out
	# No length on a collection: clients differ on what one means and the
	# honest answer is to omit it.
	assert "getcontentlength" not in out


def test_a_file_says_how_big_it_is(dav):
	row = {"file_name": "a.pdf", "is_folder": 0, "file_size": 4096, "modified": None}
	out = dav._prop_xml("/dav/a.pdf", row)
	assert "<D:getcontentlength>4096</D:getcontentlength>" in out
	assert "<D:collection/>" not in out


def test_a_name_with_an_ampersand_in_it_does_not_break_the_xml(dav):
	"""One unescaped `&` makes the whole multistatus unparseable, and a client
	shows an empty folder rather than an error."""
	out = dav._prop_xml("/dav/R%26D", {"file_name": "R&D", "is_folder": 1})
	assert "R&amp;D" in out and "R&D" not in out.replace("R&amp;D", "")


def test_a_href_is_quoted_and_a_folder_ends_in_a_slash(dav):
	assert dav._href(["Site photos", "a b.jpg"], False) == "/dav/Site%20photos/a%20b.jpg"
	assert dav._href(["Site photos"], True) == "/dav/Site%20photos/"
	assert dav._href([], True) == "/dav/"


def test_infinite_depth_is_refused(dav):
	"""A PROPFIND with `Depth: infinity` is one request that walks the whole
	Drive. The RFC lets a server refuse, and it must."""
	body = source_of(dav).split("def _propfind(")[1].split("\ndef ")[0]
	assert 'depth not in ("0", "1")' in body
	assert "propfind-finite-depth" in body


def test_locks_are_answered_because_finder_needs_them(dav):
	"""And not kept, which is the honest half. A lock table behind a load
	balancer is a promise nothing can keep."""
	assert "LOCK" in dav.METHODS and "UNLOCK" in dav.METHODS
	body = source_of(dav).split("def _lock(")[1].split("\ndef ")[0]
	assert "Lock-Token" in body
	# Class 2 is what tells a client locks exist at all.
	assert '"DAV": "1, 2"' in source_of(dav)


def test_deleting_goes_to_the_bin(dav):
	"""A protocol where one keypress removes a folder is the last place to
	make delete mean delete."""
	body = source_of(dav).split("def _delete(")[1].split("\ndef ")[0]
	assert "trash(" in body


def test_an_upload_goes_through_the_quota(dav):
	"""`File.before_insert` is where the quota is enforced and the kind is
	stamped. A PUT that wrote round it would be the one upload path that does
	not count against the plan."""
	body = source_of(dav).split("def _put(")[1].split("\ndef ")[0]
	assert '"doctype": "File"' in body and ".insert()" in body
