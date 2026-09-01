"""The notification feed.

Frappe already writes these. `frappe.desk.form.assign_to.add` — which
`spaceview.assign` calls — makes a Notification Log for whoever was assigned,
and `Comment.after_insert` calls `notify_mentions` for anybody named in one.
Both have been producing rows on every tenant since the day those features
shipped, and until this module there was nowhere in OneSpace to see one.

So this is a reader, not a producer, and deliberately: the store is the
framework's, per-user, permissioned to `for_user`, swept at 180 days, emailed by
each person's own preferences and deduplicated on insert. Writing our own would
have meant re-implementing all of that in order to stop receiving what we were
already being sent. See `docs/NOTIFICATIONS.md`.

Two things are ours, and they are the two the framework has no answer for:

* **Where a notification goes.** A Notification Log names a doctype and a
  document. OneSpace has no doctype routes — it has spaces and screens — so the
  destination is resolved here, through the same manifest the rail is built
  from, and against the same reader.
* **What it looks like.** The desk's row is HTML built by the producer, with
  `<b>` tags in the subject. We show the same three things every identity in
  this product is drawn from and strip the markup.
"""

import frappe
from frappe import _
from frappe.utils import strip_html

from oneapp.oneapp_core import spaceview, sync

# What a page of the feed is. The panel is a glance rather than an archive —
# somebody looking for something from last month is looking at the record, not
# at this — so the page is small and there is no second one.
PAGE = 20

# How much of a notification's own text is worth carrying to a panel row. The
# producers write a sentence; the Notification rule doctype can write a whole
# rendered template, and a panel is not where anybody reads one.
BODY = 240


@frappe.whitelist(methods=["GET"])
def feed(limit: int = PAGE) -> dict:
	"""This person's notifications, newest first, with somewhere for each to go.

	`get_list` rather than the framework's own `get_notification_logs`: that one
	selects `*` — every row's email HTML and attachment JSON — and caches the
	answer for a minute, which is a minute of a panel showing a notification as
	unread after it was read.
	"""
	limit = max(1, min(int(limit or PAGE), 100))

	rows = frappe.get_list(
		"Notification Log",
		filters={"for_user": frappe.session.user},
		fields=[
			"name", "type", "title", "subject", "description",
			"document_type", "document_name", "link", "from_user",
			"read", "creation",
		],
		order_by="creation desc",
		limit_page_length=limit,
	)

	people = _people([row.get("from_user") for row in rows])
	routes = _routes({row.get("document_type") for row in rows})

	return {
		"rows": [_shaped(row, people, routes) for row in rows],
		"unread": unread(),
	}


@frappe.whitelist(methods=["GET"])
def unread() -> int:
	"""How many are unread. Its own call because the bell needs it without the
	panel being open, and a count is one query rather than twenty rows."""
	return frappe.db.count(
		"Notification Log", {"for_user": frappe.session.user, "read": 0}
	)


@frappe.whitelist(methods=["POST"])
def mark_read(name: str | None = None) -> dict:
	"""One, or all of them.

	`for_user` is in the filter rather than checked after reading the row: this
	is a write addressed by name, and the name came from the browser.
	"""
	where = {"for_user": frappe.session.user, "read": 0}
	if name:
		where["name"] = str(name)

	frappe.db.set_value("Notification Log", where, "read", 1, update_modified=False)
	frappe.db.commit()
	return {"ok": True, "unread": unread()}


def _people(users: list) -> dict:
	"""Who sent them, as the identity every other surface here draws.

	One query for the page, the same shape `_with_people` uses for a list of
	rows — and for the same reason, since half a panel is usually one person.
	"""
	wanted = [one for one in dict.fromkeys(users) if one]
	if not wanted:
		return {}

	return {
		row["name"]: {
			"value": row["name"],
			"label": row["full_name"] or row["name"],
			"image": row["user_image"],
		}
		for row in frappe.get_all(
			"User",
			filters={"name": ["in", wanted]},
			fields=["name", "full_name", "user_image"],
		)
	}


def _routes(doctypes: set) -> dict:
	"""Doctype → the space and screen this reader would open it in.

	The framework's answer to "where does this notification go" is a desk form
	URL, which is not a place this product has. Ours is derived rather than
	stored: a Space is a manifest over doctypes, not a Frappe app, and the same
	doctype may be granted to several — so `Notification Log.app` could not have
	carried it even if every producer set it.

	Resolved against `visible`, which is the same gate the rail and every
	whitelisted read use. A notification about a record in a space this person
	may not open still appears — it was addressed to them and hiding it would be
	a lie — it simply does not link anywhere.

	First match wins, in the order the manifest lists them, so a doctype two
	spaces show opens in the one the reader sees first rather than in whichever
	the dictionary happened to hold.
	"""
	wanted = {one for one in doctypes if one}
	if not wanted:
		return {}

	found = {}
	for space in spaceview.visible(sync.state().get("spaces") or []):
		for screen in space.get("screens") or []:
			doctype = screen.get("document_type")
			if doctype in wanted and doctype not in found:
				found[doctype] = {
					"space": space.get("space_code"),
					"screen": screen.get("screen"),
				}
	return found


def _shaped(row: dict, people: dict, routes: dict) -> dict:
	"""One row, as the panel draws it.

	`title` is the newer field and `subject` the older one; the framework
	mirrors them on insert, so either may be the one a producer filled in.
	Both arrive as HTML — the desk's own producers bold the document title
	inside the sentence — and a panel row is one line of text.
	"""
	said = strip_html(row.get("title") or row.get("subject") or "").strip()
	body = strip_html(row.get("description") or "").strip()

	return {
		"name": row["name"],
		"type": row.get("type") or "",
		"said": said or _("Something happened"),
		# Only when it adds something. The producers that set no description get
		# the title mirrored into it, and a row that says the same sentence
		# twice is a row that looks broken.
		"body": (body[:BODY] if body and body != said else ""),
		"when": row.get("creation"),
		"read": bool(row.get("read")),
		"from": people.get(row.get("from_user")) or None,
		"record": row.get("document_name") or "",
		"doctype": row.get("document_type") or "",
		# A route this reader can open, or the producer's own link, or nothing —
		# in that order, because a resolved space is a place inside this product
		# and a link may be anywhere.
		"route": routes.get(row.get("document_type")) or None,
		"link": row.get("link") or "",
	}


# --------------------------------------------------------------------------- #
# Our own notification type
#
# `Notification Type` is a doctype, not an enum — the framework seeds its five
# in code and protects them from deletion, and an app adds its own the same
# way. So this is one row, installed idempotently, rather than a fork of
# anything.
# --------------------------------------------------------------------------- #

# What the workspace itself has to say: a payment that failed, a quota reached,
# a backup restored. Not a record somebody touched — the other four types are
# all about a document, and this one is about the account the documents live in.
WORKSPACE_TYPE = "Workspace"


def install_types():
	"""Our Notification Types. From `after_install` and `after_migrate`."""
	if frappe.db.exists("Notification Type", WORKSPACE_TYPE):
		return
	frappe.get_doc(
		{"doctype": "Notification Type", "type_name": WORKSPACE_TYPE, "enabled": 1}
	).insert(ignore_permissions=True)


# --------------------------------------------------------------------------- #
# Preferences
#
# The framework's own `Notification Settings`, one per user, with its own
# permission rule already pinning a person to their own row. What is added here
# is a shape the browser can render and a write that cannot reach somebody
# else's — not a second store.
# --------------------------------------------------------------------------- #


def _settings():
	"""This person's settings row, made if this is the first time they asked.

	`create_notification_settings` is the framework's own, and it seeds the
	email allow-list with every type that emails. It runs at user creation, so
	this is only for accounts made before a type existed — but the alternative
	is a settings page that 404s for them, which is a worse way to find out.
	"""
	from frappe.desk.doctype.notification_settings.notification_settings import (
		create_notification_settings,
	)

	create_notification_settings(frappe.session.user)
	return frappe.get_doc("Notification Settings", frappe.session.user)


@frappe.whitelist(methods=["GET"])
def preferences() -> dict:
	"""What this person has said about being notified.

	Two switches and a list, which is the whole of the framework's model:
	everything off; email off; and per type, whether email is wanted. The list
	is an *allow*-list — the framework treats an empty table as "email me for
	nothing" — so it is rendered as a row of switches rather than as a picker,
	because a picker with nothing in it reads as "not set up yet".
	"""
	from frappe.desk.doctype.notification_log.notification_log import get_skip_email_types

	doc = _settings()
	wanted = {row.notification_type for row in doc.email_notification_types}
	skip = get_skip_email_types()

	return {
		"enabled": bool(doc.enabled),
		"email": bool(doc.enable_email_notifications),
		# Only the types that *can* email. A type in `notification_skip_email_
		# types` never does — something else owns its email — and a switch that
		# changes nothing is a switch somebody flips once and stops trusting.
		"types": [
			{"name": name, "email": name in wanted}
			for name in frappe.get_all(
				"Notification Type", filters={"enabled": 1}, pluck="name", order_by="name asc"
			)
			if name not in skip
		],
	}


@frappe.whitelist(methods=["POST"])
def set_preferences(enabled=None, email=None, types: str | list | None = None) -> dict:
	"""Change them. Only ever this person's own row.

	Written through the document rather than `db.set_value` because the
	framework's `on_update` clears the notification cache — a preference that
	takes effect on the next cache expiry is a preference somebody sets twice.
	"""
	doc = _settings()

	if enabled is not None:
		doc.enabled = 1 if frappe.utils.sbool(enabled) else 0
	if email is not None:
		doc.enable_email_notifications = 1 if frappe.utils.sbool(email) else 0

	if types is not None:
		if isinstance(types, str):
			types = frappe.parse_json(types or "[]")
		offered = set(frappe.get_all("Notification Type", filters={"enabled": 1}, pluck="name"))
		doc.email_notification_types = []
		for name in dict.fromkeys(types or []):
			# Checked against the registry like every other name that arrives
			# from a browser. A disabled or invented type would sit in the
			# table doing nothing, which is the kind of row that outlives the
			# reason somebody thinks it is there.
			if name in offered:
				doc.append("email_notification_types", {"notification_type": name})

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return preferences()
