"""Who the socket relay is allowed to let into a room.

The relay itself is `apps/oneapp/realtime/handlers.js`, running inside the
socketio process the bench already runs, and its own refusals are covered by
`src/shared/lib/live/relay.test.js`. This is the other half: the one question
the relay asks the framework, which is the only place a permission is actually
checked.

Two claims, and the second is the one that would be a hole. A person who may
open a file is let in; a person who may only *read* it is let in without the
right to say anything, so watching somebody else edit a sheet shared with you
read-only is not a way to edit it. A guest is not let in at all, which is what
keeps a public link (`onestorage/sharing.py`) from becoming a way onto the bus.
"""

import importlib
import sys

import pytest


@pytest.fixture
def live(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]
	module = importlib.import_module("oneapp.onespace.live")
	return module, stub_frappe


def _a_file(frappe, name="FILE-1"):
	frappe.db.exists = lambda doctype, key=None: doctype == "File" and (key == name)
	frappe.get_doc = lambda doctype, key=None: type(
		"Doc", (), {"name": key, "doctype": doctype},
	)()
	frappe.db.get_value = lambda doctype, key, field: {
		"full_name": "Robin Vale", "user_image": "",
	}.get(field)


def _may(frappe, **allow):
	frappe.has_permission = lambda doctype, ptype="read", doc=None: bool(allow.get(ptype))


def test_a_writer_is_let_in_and_may_speak(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True, write=True)
	frappe.session.user = "robin@zzmock.test"

	seat = module.admit("file", "FILE-1")

	assert seat["ok"] is True
	assert seat["write"] is True
	# The server names the record, and the relay builds the room from this.
	assert seat["name"] == "FILE-1"
	assert seat["who"]["user"] == "robin@zzmock.test"
	assert seat["who"]["initials"] == "RV"


def test_a_reader_is_let_in_and_may_not(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True)
	frappe.session.user = "robin@zzmock.test"

	seat = module.admit("file", "FILE-1")

	assert seat["ok"] is True
	assert seat["write"] is False


def test_somebody_who_cannot_open_it_is_not_let_in(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe)
	frappe.session.user = "robin@zzmock.test"

	# And says nothing else — a refusal that explains itself is a probe that
	# works, which is the same reason `open_link` answers one sentence.
	assert module.admit("file", "FILE-1") == {"ok": False}


def test_a_guest_with_no_link_is_not_let_in(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True, write=True)
	frappe.session.user = "Guest"

	# Permission is irrelevant here and that is the point: without a link
	# there is nothing to check, so there is nothing to let them in on.
	assert module.admit("file", "FILE-1") == {"ok": False}


class _Link:
	def __init__(self, **kw):
		self.name = kw.get("name", "LINK-1")
		self.file = kw.get("file", "FILE-1")
		self.label = kw.get("label", "For the consultant")
		self.level = kw.get("level", "write")
		self.revoked = kw.get("revoked", 0)
		self.expires_on = kw.get("expires_on", "2099-01-01 00:00:00")


def _with_link(module, frappe, link):
	from datetime import datetime

	module.now_datetime = lambda: datetime(2026, 1, 1)
	module.get_datetime = lambda value: datetime.fromisoformat(str(value))
	frappe.db.exists = lambda doctype, key=None: True
	frappe.db.get_value = lambda doctype, filters=None, field=None: (
		link.name if doctype == "File Link" else None
	)
	found = {"File Link": link, "File": _Doc("FILE-1")}
	frappe.get_doc = lambda doctype, key=None: found[doctype]
	frappe.session.user = "Guest"


class _Doc:
	def __init__(self, name):
		self.name = name
		self.doctype = "File"


def test_a_guest_holding_an_editable_link_is_let_in(live):
	module, frappe = live
	_with_link(module, frappe, _Link(level="write"))

	seat = module.admit("file", "FILE-1", "sekrit")

	assert seat["ok"] is True
	assert seat["write"] is True
	assert seat["guest"] is True
	# Named for the link, because that is the truth: the workspace handed out
	# a URL and does not know who is holding it.
	assert seat["who"]["user"] == "link:LINK-1"
	assert seat["who"]["full_name"] == "For the consultant"


def test_a_guest_holding_a_read_link_may_watch_and_not_write(live):
	module, frappe = live
	_with_link(module, frappe, _Link(level="read"))

	seat = module.admit("file", "FILE-1", "sekrit")

	assert seat["ok"] is True
	assert seat["write"] is False


def test_a_link_to_another_file_opens_no_door_here(live):
	module, frappe = live
	# The one check that stops a valid secret becoming a key to the whole
	# Drive: the link names a file, and it has to be *this* file.
	_with_link(module, frappe, _Link(file="SOMETHING-ELSE"))

	assert module.admit("file", "FILE-1", "sekrit") == {"ok": False}


def test_a_revoked_or_expired_link_opens_nothing(live):
	module, frappe = live

	_with_link(module, frappe, _Link(revoked=1))
	assert module.admit("file", "FILE-1", "sekrit") == {"ok": False}

	_with_link(module, frappe, _Link(expires_on="2000-01-01 00:00:00"))
	assert module.admit("file", "FILE-1", "sekrit") == {"ok": False}


def test_a_signed_in_person_does_not_get_a_link_s_rights(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True)
	frappe.session.user = "robin@zzmock.test"

	# The link path is for `Guest` and only for `Guest`. A colleague with
	# read access who got hold of an editable URL is still a reader — their
	# own permission is what answers, and a secret does not add to it.
	seat = module.admit("file", "FILE-1", "sekrit")
	assert seat["ok"] is True
	assert seat["write"] is False


def test_only_a_kind_the_relay_knows(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True, write=True)
	frappe.session.user = "robin@zzmock.test"

	# Without this the relay is a pub/sub bus over every row on the site.
	assert module.admit("Sales Invoice", "ACC-SINV-0001") == {"ok": False}
	assert module.admit("file", "") == {"ok": False}


def test_a_file_that_is_not_there(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True, write=True)
	frappe.session.user = "robin@zzmock.test"

	assert module.admit("file", "GONE") == {"ok": False}


def test_a_person_is_the_same_colour_everywhere(live):
	module, _ = live

	# Hashed rather than handed out, so two sockets racing cannot seat two
	# people on one colour and a reconnect does not change it underneath
	# everybody's cursor.
	assert module.colour_for("robin@zzmock.test") == module.colour_for("robin@zzmock.test")
	assert module.colour_for("robin@zzmock.test") in module.COLOURS
	assert module.colour_for("") in module.COLOURS


def test_initials_of_the_people_a_workspace_has(live):
	module, _ = live

	assert module.initials_for("Robin Vale", "robin@zzmock.test") == "RV"
	assert module.initials_for("Cher", "cher@zzmock.test") == "CH"
	assert module.initials_for("Ada Byron King Lovelace", "a@b.test") == "AL"
	assert module.initials_for("", "zoe@zzmock.test") == "Z"


def test_presence_says_only_what_the_browser_cannot_work_out(live):
	module, frappe = live
	_a_file(frappe)
	_may(frappe, read=True)
	frappe.session.user = "robin@zzmock.test"

	assert module.presence("file", "FILE-1") == {
		"live": True, "write": False,
		"who": module.admit("file", "FILE-1")["who"],
	}

	_may(frappe)
	assert module.presence("file", "FILE-1") == {"live": False}


def test_a_guest_may_reach_the_door_at_all():
	"""The bug this is here for was silent and cost an evening.

	`admit` is the one endpoint the relay calls, and Frappe refuses a
	whitelisted method to a guest *before the function runs*. Without
	`allow_guest` the relay asked, got a 403, and joined the stranger to no
	room — with no error anywhere, because the relay's own catch logs a warning
	nobody was reading and the page carries on working. Everything that decides
	what a guest may do is inside `_through_link`, below the decorator.
	"""
	from pathlib import Path

	source = (Path(__file__).resolve().parent.parent
	          / "apps/oneapp/oneapp/onespace/live.py").read_text()
	door = source.index("def admit(")
	assert "allow_guest=True" in source[door - 200:door]
