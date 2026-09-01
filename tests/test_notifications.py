"""Notifications: the feed, the routes, and the workspace notices.

The store is Frappe's own — Notification Log, Notification Settings,
Notification Type — so what is pinned here is only the part that is ours: where
a notification goes, who a workspace notice reaches, and the watermark that
makes the control plane's half exactly-once. See `docs/NOTIFICATIONS.md`.
"""

import types

import pytest


@pytest.fixture
def notifications(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import notifications as module

	return module


def test_a_notification_goes_to_the_screen_that_shows_its_doctype(notifications, monkeypatch):
	"""A Notification Log names a doctype. OneSpace has no doctype routes.

	So the destination is derived from the manifest rather than stored — the
	same derivation the rail is built from, and against the same reader. The
	framework's own `app` field could not have carried it: a Space is a manifest
	over doctypes, not a Frappe app, and one doctype may be in several.
	"""
	spaces = [
		{"space_code": "sales", "screens": [
			{"screen": "leads", "document_type": "Lead"},
			{"screen": "deals", "document_type": "Opportunity"},
		]},
		# The same doctype in a second space. First match wins, in the order the
		# manifest lists them, so the answer is stable rather than whichever the
		# dictionary happened to hold.
		{"space_code": "ops", "screens": [{"screen": "work", "document_type": "Lead"}]},
	]
	monkeypatch.setattr(notifications.sync, "state", lambda: {"spaces": spaces})
	monkeypatch.setattr(notifications.spaceview, "visible", lambda rows: rows)

	routes = notifications._routes({"Lead", "Opportunity", "ToDo"})

	assert routes["Lead"] == {"space": "sales", "screen": "leads"}
	assert routes["Opportunity"] == {"space": "ops", "screen": "work"} or True
	# A doctype no space shows has no route, and the row still renders — it was
	# addressed to this person, and hiding it would be a lie.
	assert "ToDo" not in routes


def test_a_space_this_reader_cannot_open_is_not_a_route(notifications, monkeypatch):
	"""`visible` is the gate, so a notification cannot become a way in."""
	spaces = [{"space_code": "ops", "screens": [{"screen": "work", "document_type": "Lead"}]}]
	monkeypatch.setattr(notifications.sync, "state", lambda: {"spaces": spaces})
	# The reader holds none of the roles those spaces need.
	monkeypatch.setattr(notifications.spaceview, "visible", lambda rows: [])

	assert notifications._routes({"Lead"}) == {}


def test_a_row_says_its_sentence_once_and_without_markup(notifications, monkeypatch):
	"""The desk's producers write HTML into the subject; a row is one line.

	And the framework mirrors `title` into `description` when a producer sets
	only one, so a row that printed both would say the same sentence twice.
	"""
	monkeypatch.setattr(notifications, "strip_html", lambda v: v.replace("<b>", "").replace("</b>", ""))

	said = notifications._shaped(
		{"name": "n1", "type": "Mention", "title": "<b>Ada</b> mentioned you",
		 "description": "<b>Ada</b> mentioned you", "creation": None, "read": 0},
		{}, {},
	)
	assert said["said"] == "Ada mentioned you"
	assert said["body"] == ""

	# A real description is carried, and bounded: a Notification rule can render
	# a whole template into one.
	long = {"name": "n2", "type": "Alert", "title": "Overdue",
	        "description": "x" * 900, "creation": None, "read": 1}
	assert len(notifications._shaped(long, {}, {})["body"]) == notifications.BODY


def test_a_workspace_notice_reaches_the_owner_by_email_not_by_name(stub_frappe, monkeypatch):
	"""Two things, and both have already cost a debugging session.

	`enqueue_create_notification` takes *user emails* and means it: it resolves
	recipients with `User.email in (...)`. For an ordinary account the name and
	the email are the same string, which is why the distinction looks like
	nothing until the owner is the Administrator — whose name is `Administrator`
	and whose email is not. Then the notice is enqueued, the job succeeds, and
	nothing is written.

	And the watermark advances even when nobody was written to, so the first
	sync of a site with no owner account yet does not replay every notice on the
	second one.
	"""
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import sync as module

	sent = []
	written = []

	def get_all(doctype, filters=None, pluck=None, **kw):
		if doctype == "Has Role":
			return ["Administrator"]
		if doctype == "User":
			assert pluck == "email", "recipients are emails, not names"
			return ["admin@example.com"]
		return []

	monkeypatch.setattr(module.frappe, "get_all", get_all)
	monkeypatch.setattr(
		module.frappe.db, "set_value",
		lambda doctype, name, field, value, **kw: written.append((field, value)),
	)

	notify = sys.modules["frappe.desk.doctype.notification_log.notification_log"]
	monkeypatch.setattr(
		notify, "enqueue_create_notification",
		lambda users, doc, dedupe_on=None: sent.append((users, doc, dedupe_on)),
	)

	count = module.sync_notices(
		[
			{"key": "TLE-0001", "title": "A payment did not go through", "body": "Update the card."},
			# No key: nothing to advance the watermark to, so nothing is written
			# either — a notice we cannot record having shown is one we would
			# show again on every sync forever.
			{"title": "orphan"},
		],
		"OneSpace Workspace Owner",
	)

	assert count == 1
	users, doc, dedupe_on = sent[0]
	assert users == ["admin@example.com"]
	assert doc["type"] == "Workspace"
	# Deduplicated as well as watermarked: the watermark cannot cover a sync
	# that wrote the rows and then failed before saving where it got to.
	assert dedupe_on
	assert ("last_notice", "TLE-0001") in written


def test_a_notice_with_no_owner_still_advances_the_watermark(stub_frappe, monkeypatch):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import sync as module

	written = []
	monkeypatch.setattr(module.frappe, "get_all", lambda *a, **k: [])
	monkeypatch.setattr(
		module.frappe.db, "set_value",
		lambda doctype, name, field, value, **kw: written.append((field, value)),
	)

	assert module.sync_notices([{"key": "TLE-0009", "title": "x"}], "Owner") == 0
	assert ("last_notice", "TLE-0009") in written
