"""A link a stranger can edit through.

The read-only half has been here since the Drive was built: a row naming one
file, a secret in the URL, and a date. This is the half that hands over the
pen, and it is the piece of the collaboration work with a real security
surface — a browser with no account, writing into somebody's workspace.

Five claims, and the first two are why the module exists at all rather than a
flag on the endpoints everybody else uses.

**Every call starts with the secret.** Nothing here takes a doctype, a
fieldname or a filter, and nothing reaches a second file. A guest cannot be
*granted* a permission in Frappe — `has_controller_permissions` says in its
own docstring that a controller can deny and cannot grant — so the choice was
its own narrow surface or `ignore_permissions` on the ordinary endpoints, and
the ordinary endpoints are how everybody else's files are read.

**A read link does not write.** The level is the whole of the difference and
it is checked on the server, not offered on the client.

**You cannot give away a right you do not have.** Somebody a workbook was
shared with read-only must not be able to publish an editable URL to it.

**A stranger's markup is sanitised.** A document has a second stored form —
the HTML the search and the export read — and taking that from outside the
workspace and storing it unread is the one thing in here worth refusing.

**A stranger does not rename anything.** `save_file` takes no title. A file
renamed in somebody's Drive by a person who was handed a URL is not what
"edit this" meant.
"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPA = ROOT / "apps/oneapp/frontend/src"


@pytest.fixture
def linked(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]
	return importlib.import_module("oneapp.onestorage.linked"), stub_frappe


class _Link:
	def __init__(self, **kw):
		self.name = kw.get("name", "LINK-1")
		self.file = kw.get("file", "FILE-1")
		self.label = kw.get("label", "For the consultant")
		self.level = kw.get("level", "read")
		self.revoked = kw.get("revoked", 0)
		self.expires_on = kw.get("expires_on", "2099-01-01 00:00:00")
		self.opened = kw.get("opened", 0)
		self.written = []

	def db_set(self, field, value, **_):
		self.written.append(field)
		setattr(self, field, value)


class _File:
	def __init__(self, kind="Sheet", name="FILE-1"):
		self.name = name
		self.doctype = "File"
		self.file_name = "Rates"
		self.modified = "2026-01-01 00:00:00"
		self._kind = kind

	def get(self, field):
		return self._kind if field == "custom_kind" else None

	def db_set(self, *_args, **_kw):
		pass


def _world(frappe, link=None, kind="Sheet", module=None):
	link = link or _Link()
	if module is not None:
		# The stub's clock answers None. `get_datetime` is real enough to
		# compare two strings; `now_datetime` is what needs a value.
		from datetime import datetime
		module.now_datetime = lambda: datetime(2026, 1, 1)
		module.get_datetime = lambda value: datetime.fromisoformat(str(value))
	frappe.db.get_value = lambda doctype, filters=None, field=None: (
		link.name if doctype == "File Link" else None
	)
	found = {"File Link": link, "File": _File(kind)}
	frappe.get_doc = lambda doctype, key=None: found[doctype]
	return link


def test_a_link_that_is_not_there_says_nothing(linked):
	module, frappe = linked
	frappe.db.get_value = lambda *a, **k: None
	# The same sentence for gone, expired, revoked and never real — a refusal
	# that explains itself tells somebody their secret was nearly right.
	with pytest.raises(Exception):
		module.follow("nope")


def test_a_revoked_link_is_not_available(linked):
	module, frappe = linked
	_world(frappe, _Link(revoked=1), module=module)
	with pytest.raises(Exception):
		module.follow("sekrit")


def test_an_expired_link_is_not_available(linked):
	module, frappe = linked
	_world(frappe, _Link(expires_on="2000-01-01 00:00:00"), module=module)
	with pytest.raises(Exception):
		module.follow("sekrit")


def test_following_says_which_editor_and_what_it_allows(linked):
	module, frappe = linked
	_world(frappe, _Link(level="write"), module=module)

	said = module.follow("sekrit")

	assert said["kind"] == "Sheet"
	assert said["editable"] is True
	assert said["level"] == "write"
	assert said["can_write"] is True
	# No rail through a link. A `RECORD()` formula and a document token read
	# the workspace's own data; a shared file is the file.
	assert said["sources"] == []


def test_something_neither_editor_draws_is_not_editable(linked):
	module, frappe = linked
	_world(frappe, _Link(), kind="Image", module=module)
	assert module.follow("sekrit")["editable"] is False


def test_a_read_link_does_not_save(linked):
	module, frappe = linked
	_world(frappe, _Link(level="read"), module=module)
	with pytest.raises(Exception):
		module.save_file("sekrit", "{}")


def test_a_payload_has_a_ceiling(linked):
	module, frappe = linked
	_world(frappe, _Link(level="write"), module=module)
	with pytest.raises(Exception):
		module.save_file("sekrit", "x" * (module.MAX_PAYLOAD + 1))


def test_saving_takes_no_title(linked):
	module, _ = linked
	import inspect

	# Not a style point. The signed-in editors send the title with the save
	# because it is edited in the same header; a stranger renaming somebody's
	# file in their Drive is a different thing, and the way to refuse it is
	# not to accept one.
	assert "title" not in inspect.signature(module.save_file).parameters


def test_opening_counts_and_commits(linked):
	module, frappe = linked
	import types

	link = _world(frappe, _Link(level="write"), module=module)
	def get_value(doctype, filters=None, field=None, as_dict=False):
		if doctype == "File Link":
			return link.name
		return {"payload": "{}", "head_seq": 3} if as_dict else "{}"

	frappe.db.get_value = get_value
	frappe.local.flags = types.SimpleNamespace()

	module.open_file("sekrit")

	# The count is the audit trail this row exists for, and a GET is rolled
	# back unless it says otherwise.
	assert "opened" in link.written
	assert "last_opened" in link.written
	assert frappe.local.flags.commit is True


# --------------------------------------------------------------------------- #
# The door itself
# --------------------------------------------------------------------------- #
#
# Everything above is the endpoints. These two are the page in front of them,
# and both were bugs before they were tests: the SPA refused to render at all
# for somebody with no account, and then asked a session endpoint that refuses
# them.

def test_a_link_is_the_one_path_under_one_a_stranger_may_reach():
	"""`/one/...` redirects a guest to a sign-in page. A link's holder has no
	account and never needed one, so that redirect sends them nowhere."""
	page = (ROOT / "apps/oneapp/oneapp/www/one.py").read_text()

	assert 'LINK_PREFIX = "/one/link/"' in page
	assert "startswith(LINK_PREFIX)" in page
	# And the boot payload a guest gets describes no workspace.
	assert "if not guest:" in page
	assert 'context.boot["assistant"]' in page
	assert 'context.boot["basemap"]' in page


def test_nobody_signed_in_means_no_session_fetch():
	"""The endpoint would refuse, and the only product of the round trip was a
	red toast over a page that was working."""
	session = (SPA / "modules/onespace/lib/shell/session.js").read_text()

	assert "const anonymous = sessionUser === 'Guest'" in session
	assert "immediate: !anonymous" in session
	# And the promise the router waits on has to settle anyway.
	assert "if (anonymous) return resolve()" in session
