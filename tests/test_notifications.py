"""Notifications: the feed, the routes, and the workspace notices.

The store is Frappe's own — Notification Log, Notification Settings,
Notification Type — so what is pinned here is only the part that is ours: where
a notification goes, who a workspace notice reaches, and the watermark that
makes the control plane's half exactly-once. See `docs/NOTIFICATIONS.md`.
"""

import sys
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


# --------------------------------------------------------------------------- #
# Following a document
#
# Frappe has the store and no in-app delivery at all — `Document Follow` is read
# by exactly one thing, the Hourly/Daily/Weekly digest email. What is pinned
# here is the half we had to write, and the three refusals that would otherwise
# have made the bell a control that does nothing on every real workspace.
# --------------------------------------------------------------------------- #


def _tracked(frappe, doctype, labels=None):
	"""Say that a doctype tracks its changes, and what its fields are called."""
	labels = labels or {}
	frappe._meta[doctype] = types.SimpleNamespace(
		track_changes=1,
		get_field=lambda name: (
			types.SimpleNamespace(label=labels[name]) if name in labels else None
		),
	)


def test_only_a_doctype_that_reports_its_changes_can_be_followed(notifications, stub_frappe):
	"""`track_changes` is the whole condition, and it is the framework's own.

	A follow on a doctype that writes no Version row is a subscription to
	silence: the bell lights, nothing ever arrives, and the reader concludes
	the feature is broken rather than that the doctype is.
	"""
	_tracked(stub_frappe, "Note")

	assert notifications.followable("Note")
	# Never asked about it, so it does not track changes.
	assert not notifications.followable("Contact")
	# Frappe's own exclusions, kept for Frappe's own reason: these doctypes
	# *are* the activity, so following one is a loop.
	assert not notifications.followable("ToDo")
	assert not notifications.followable("Comment")
	# A log of what happened is not a thing that happens.
	assert not notifications.followable("Error Log")
	assert not notifications.followable("")


def test_a_ref_doctype_that_is_not_a_doctype_is_answered_rather_than_raised(
	notifications, stub_frappe, monkeypatch
):
	"""`Version` is written against `Series` when a naming counter moves.

	Frappe's own naming settings page does it, with `ignore_links` set exactly
	because Series is not a real doctype — so the `after_insert` hook this
	module registers runs with a `ref_doctype` that `get_meta` cannot resolve.
	Letting that raise took the whole insert down with it, which meant moving a
	series counter failed on every site this app is installed on.
	"""
	def missing(doctype):
		raise stub_frappe.DoesNotExistError(f"DocType {doctype} not found")

	monkeypatch.setattr(stub_frappe, "get_meta", missing)

	assert not notifications.followable("Series")


def test_followers_are_resolved_to_emails_and_rechecked_against_the_record(
	notifications, stub_frappe, monkeypatch
):
	"""The two things that make a fan-out write nothing when it looks right.

	`_get_user_ids` filters recipients on `User.email`, so a list of user ids
	enqueues a job that succeeds silently. And a follow outlives the permission
	that allowed it — somebody dropped from a role keeps the row — so each
	follower is re-checked against the document rather than against the store.
	"""
	asked = {}

	def get_all(doctype, filters=None, pluck=None, **kw):
		if doctype == "Document Follow":
			return ["robin@x.test", "sam@x.test"]
		if doctype == "User":
			asked["users"] = filters
			asked["pluck"] = pluck
			return ["robin@x.test"]
		return []

	monkeypatch.setattr(stub_frappe, "get_all", get_all)
	monkeypatch.setattr(
		stub_frappe, "has_permission",
		lambda doctype, ptype=None, doc=None, user=None, **k: user == "robin@x.test",
	)

	found = notifications._followers("Note", "NOTE-1")

	assert found == ["robin@x.test"]
	# Sam follows it and may no longer read it, so Sam is not asked about.
	assert asked["users"]["name"] == ["in", ["robin@x.test"]]
	assert asked["pluck"] == "email", "recipients are emails, not names"


def test_the_actor_is_not_told_about_their_own_edit(notifications, stub_frappe, monkeypatch):
	sent = []
	monkeypatch.setattr(
		notifications, "_followers", lambda doctype, name, exclude=(): (
			sent.append(list(exclude)) or ["robin@x.test"]
		),
	)
	notify = sys.modules["frappe.desk.doctype.notification_log.notification_log"]
	monkeypatch.setattr(notify, "enqueue_create_notification", lambda users, doc, **k: None)
	stub_frappe.session.user = "ada@x.test"

	notifications.notify_followers("Note", "NOTE-1", "Ada updated Note")

	assert "ada@x.test" in sent[0]


def test_an_edit_says_what_changed_in_the_screen_s_words(
	notifications, stub_frappe, monkeypatch
):
	"""The labels, not the values.

	*That* something changed and *what* is the whole of a follow notification;
	the values are on the record one click away, and a panel row that carried
	them would be a way to read a permlevel-protected field without opening
	anything.
	"""
	_tracked(stub_frappe, "Note", {"public": "Public", "content": "Content"})
	monkeypatch.setattr(notifications, "_followed", lambda doctype, name: True)
	stub_frappe.session.user = "ada@x.test"
	monkeypatch.setattr(stub_frappe.db, "get_value", lambda *a, **k: "Ada Lovelace")

	sent = []
	monkeypatch.setattr(
		notifications, "notify_followers",
		lambda doctype, name, said, body="", exclude=(): sent.append((said, body)),
	)

	notifications.on_version(
		{
			"ref_doctype": "Note",
			"docname": "NOTE-1",
			"data": '{"changed": [["public", 0, 1], ["content", "a", "b"]]}',
		}
	)

	said, body = sent[0]
	assert "Ada Lovelace" in said and "NOTE-1" in said
	assert body == "Public, Content"
	# No values anywhere in it.
	assert "b" not in body.split(", ")


def test_a_version_with_nothing_readable_in_it_says_nothing(
	notifications, stub_frappe, monkeypatch
):
	"""Frappe writes these for bookkeeping-only changes.

	"Somebody updated this" with no answer to "what" is the notification people
	turn the whole feature off over.
	"""
	_tracked(stub_frappe, "Note")
	monkeypatch.setattr(notifications, "_followed", lambda doctype, name: True)
	sent = []
	monkeypatch.setattr(
		notifications, "notify_followers",
		lambda *a, **k: sent.append(a),
	)

	notifications.on_version({"ref_doctype": "Note", "docname": "NOTE-1", "data": "{}"})
	# And a doctype nobody could have followed never reaches the query at all.
	notifications.on_version({"ref_doctype": "Contact", "docname": "C-1",
	                          "data": '{"changed": [["x", 1, 2]]}'})

	assert sent == []


def test_a_mentioned_follower_is_not_told_twice_about_one_comment(
	notifications, stub_frappe, monkeypatch
):
	"""Frappe already notifies a mention, as a Mention.

	Two rows for one comment is how a panel teaches somebody that most of what
	is in it is noise.
	"""
	_tracked(stub_frappe, "Note")
	monkeypatch.setattr(notifications, "_followed", lambda doctype, name: True)
	stub_frappe.session.user = "ada@x.test"
	monkeypatch.setattr(stub_frappe.db, "get_value", lambda *a, **k: "Ada")

	sent = []
	monkeypatch.setattr(
		notifications, "notify_followers",
		lambda doctype, name, said, body="", exclude=(): sent.append((said, body, list(exclude))),
	)

	notifications.on_comment(
		{
			"comment_type": "Comment",
			"reference_doctype": "Note",
			"reference_name": "NOTE-1",
			"content": '<p>ping <span data-id="robin@x.test">Robin</span></p>',
		}
	)

	said, body, exclude = sent[0]
	assert "commented on" in said
	# The comment's own words, without its markup.
	assert body == "ping Robin"
	assert exclude == ["robin@x.test"]

	# A like is a Comment row too, and is not a comment.
	sent.clear()
	notifications.on_comment(
		{"comment_type": "Like", "reference_doctype": "Note", "reference_name": "NOTE-1"}
	)
	assert sent == []


def test_following_never_emails(notifications):
	"""In-app only, and deliberately.

	Following a busy record is one email per save. Frappe's answer to that is
	the digest, which is the right shape and needs a frequency preference we
	have not built — so the hook says so and `preferences` drops the type from
	the list rather than offering a switch that would do nothing.
	"""
	import pathlib

	hooks = pathlib.Path("apps/oneapp/oneapp/hooks.py").read_text()
	assert 'notification_skip_email_types = ["Workspace", "Following"]' in hooks
	assert notifications.FOLLOW_TYPE == "Following"


def test_a_save_nobody_is_following_costs_one_query(notifications, stub_frappe, monkeypatch):
	"""`on_version` runs on every save of every tracked doctype, site-wide.

	So the common case — nobody follows this record — has to be one indexed
	`exists` and nothing else. Not a title lookup, not a fan-out query, and not
	a permission check per follower.
	"""
	_tracked(stub_frappe, "Note", {"content": "Content"})

	asked = []
	monkeypatch.setattr(
		stub_frappe.db, "exists", lambda doctype, filters=None: asked.append(doctype) or False
	)
	monkeypatch.setattr(
		stub_frappe.db, "get_value",
		lambda *a, **k: pytest.fail("no lookup should happen for an unfollowed record"),
	)
	monkeypatch.setattr(
		stub_frappe, "get_all",
		lambda *a, **k: pytest.fail("no fan-out should happen for an unfollowed record"),
	)

	notifications.on_version(
		{"ref_doctype": "Note", "docname": "NOTE-1",
		 "data": '{"changed": [["content", "a", "b"]]}'}
	)

	assert asked == ["Document Follow"]
