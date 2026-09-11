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
already being sent. See `docs/ONESPACE.md`.

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
from frappe import _, _lt
from frappe.utils import strip_html

from oneapp.onespace import spaceview, sync

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
		filters=_mine(),
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
	return frappe.db.count("Notification Log", {**_mine(), "read": 0})


def _mine() -> dict:
	"""This person's notifications, minus the kinds they muted in the app.

	Filtered on the way out rather than on the way in — see `MUTED_KEY`. The
	count uses the same filter as the list, because a bell that says three over
	a panel showing two is worse than either number alone.
	"""
	filters: dict = {"for_user": frappe.session.user}
	if muted := _muted():
		filters["type"] = ["not in", sorted(muted)]
	return filters


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

	`spaceview.routes`, which is where it lives now that mail filing asks the
	same question: a candidate record is only a candidate if there is a screen
	to open it on.
	"""
	return spaceview.routes(doctypes)


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

#: Every kind of notification this product sends, declared where it is sent.
#:
#: The registry exists because the panel and the senders were two lists. A
#: `Notification Type` row was enough to be *sent*, and appearing in the panel
#: was a separate matter — so the panel offered "Energy Point", the framework's
#: gamification, which nothing here awards, while a new sender inventing a type
#: of its own would have shipped a notification nobody could turn off.
#:
#: One list instead. `kind()` declares a name and what it is in the reader's
#: words; `notify()` refuses to send anything undeclared; `install_types`
#: creates the rows; and the panel is this registry joined with what the
#: framework will actually email. Declaring is the whole of what a new sender
#: does to become a switch somebody can turn off.
KINDS: dict[str, dict] = {}


def kind(name: str, about, *, ours: bool = True) -> str:
	"""Declare a notification kind, and hand back its name to send with.

	`about` is `_lt` rather than `_`: these are module-level, so a `_()` here
	would resolve once at import — in whatever language the first worker
	happened to boot in — and every reader would get that one. `_lt` is
	Frappe's lazy translation, is in its babel keyword map, and resolves when
	`preferences` reads it, per request.
	"""
	KINDS[name] = {"name": name, "about": about, "ours": ours}
	return name


# The framework's own three. Declared rather than installed: Frappe creates the
# rows and produces the notifications — an assignment through `assign_to.add`,
# a mention through `Comment.after_insert` — and what is added here is the
# sentence, because a switch labelled with a bare noun is legible to whoever
# built it and a guess for everybody else.
ASSIGNMENT_TYPE = kind(
	"Assignment", _lt("When somebody gives you a record to deal with."), ours=False)
MENTION_TYPE = kind(
	"Mention", _lt("When somebody writes your name in a comment."), ours=False)
SHARE_TYPE = kind(
	"Share", _lt("When somebody shares a record or a file with you."), ours=False)

# What the workspace itself has to say: a payment that failed, a quota reached,
# a backup restored. Not a record somebody touched — the others are all about a
# document, and this one is about the account the documents live in.
WORKSPACE_TYPE = kind(
	"Workspace", _lt("Payments, quotas and anything about the account itself."))

# What a document you follow has to say. Frappe has no type for this because
# Frappe never notifies a follower in-app — see the Following section below.
FOLLOW_TYPE = kind("Following", _lt("Changes to a record you are following."))

# A date on a record running out. Its own kind rather than the workspace notice
# it used to be sent as: somebody who wants to know about an expiring insurance
# certificate does not necessarily want to know about a failed card, and one
# switch for both is a switch neither of them can use.
EXPIRY_TYPE = kind("Expiring", _lt("A document whose expiry date is coming up."))

# What a rule somebody wrote in Settings has to say. `alerts.py` builds Frappe
# `Notification` rows, and one with the in-app channel writes into the same
# `Notification Log` this module reads — so alerts were already arriving in the
# bell. What they had no way to be was *declared*: Frappe stamps its own row
# `notification_type or "Alert"`, "Alert" was a kind nothing here knew about,
# and an undeclared kind gets no switch. Alerts landed in a feed nobody could
# turn off. Declaring it is the whole fix: the panel, the `Notification Type`
# row and the mute list all come from `declared()`.
ALERT_TYPE = kind("Alert", _lt("Rules this workspace wrote about its own records."))


def declared() -> dict[str, dict]:
	"""Every kind, ours and any an installed app adds.

	`onespace_notification_kinds` is the shape the settings-groups hook already
	uses: a method returning `{name, about}` entries. An app that notifies gets
	a switch in the same panel without this module knowing it exists.
	"""
	found = dict(KINDS)
	for method in frappe.get_hooks("onespace_notification_kinds") or []:
		try:
			for one in frappe.get_attr(method)() or []:
				name = (one.get("name") or "").strip()
				if name:
					found[name] = {
						"name": name, "about": one.get("about") or "", "ours": True}
					# An installed app's own sentence, in its own catalogue.
		except Exception:
			# An app whose hook throws must not take the panel with it: the
			# rest of the list is still true.
			frappe.log_error(title=f"Notification kinds from {method} failed")
	return found


def install_types():
	"""Our Notification Types. From `after_install` and `after_migrate`."""
	for name, spec in declared().items():
		if not spec["ours"] or frappe.db.exists("Notification Type", name):
			continue
		frappe.get_doc(
			{"doctype": "Notification Type", "type_name": name, "enabled": 1}
		).insert(ignore_permissions=True)


def notify(kind_name: str, users, message: dict, dedupe_on: list | None = None) -> int:
	"""Send one, through the framework's own producer.

	Everything this product sends goes through here, for two reasons.
	`enqueue_create_notification` is what applies each person's settings, skips
	the actor, dedupes and fans out — so a followed document, a licence about to
	expire and an assignment land in one panel with one read state. And the kind
	is checked against the registry, so a sender cannot invent a type that has
	no switch: the failure is loud here rather than silent in a settings panel
	that never mentions it.
	"""
	from frappe.desk.doctype.notification_log.notification_log import (
		enqueue_create_notification,
	)

	if kind_name not in declared():
		frappe.throw(_("{0} is not a declared notification kind.").format(kind_name))

	people = sorted({one for one in (users or []) if one})
	if not people:
		return 0

	enqueue_create_notification(
		people,
		{**message, "type": kind_name},
		**({"dedupe_on": dedupe_on} if dedupe_on else {}),
	)
	return len(people)


# --------------------------------------------------------------------------- #
# Preferences
#
# The framework's own `Notification Settings`, one per user, with its own
# permission rule already pinning a person to their own row. What is added here
# is a shape the browser can render and a write that cannot reach somebody
# else's — not a second store.
# --------------------------------------------------------------------------- #


#: The three ways a notification can reach somebody, as the panel names them.
#:
#: Only two of them are real. Push is a seam (`push.send`) and stays one until
#: the EU-jurisdiction question is settled — it is offered and refused rather
#: than hidden, because "we do not do this yet" is a more useful answer than a
#: control that is silently missing.
IN_APP, EMAIL, PUSH = "in_app", "email", "push"

#: Kinds this person does not want in the app, as a user default.
#:
#: Frappe's `Notification Settings` has a master switch and a per-kind *email*
#: allow-list, and nothing per-kind for the app itself — so somebody who wanted
#: assignments but not every change to a document they follow had one control
#: for both. The same shape mail's stars use, for the same reason: a per-person
#: preference with no doctype worth making.
#:
#: A mute hides the kind from the feed and the count rather than stopping the
#: row being written, and deliberately: the framework's producer is what sends
#: the email, so a row that is never written is an email that never goes either.
#: In app off with Email on has to keep working, and this is what makes it.
MUTED_KEY = "onespace_muted_kinds"


def _muted(user: str | None = None) -> set[str]:
	raw = frappe.defaults.get_user_default(MUTED_KEY, user or frappe.session.user)
	return {one.strip() for one in (raw or "").split(",") if one.strip()}


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
	# Declared, enabled and able to email. An allow-list rather than a
	# deny-list: a `Notification Type` row nothing declares is one nothing here
	# sends, and a switch that can never do anything is one somebody flips once
	# and then stops trusting the rest of the panel.
	known = declared()
	wanted = {row.notification_type for row in doc.email_notification_types}
	skip = get_skip_email_types()

	muted = _muted()

	# One row per kind and a state per channel, rather than one switch that
	# meant email and nothing else. A kind the framework will not email — its
	# email is owned elsewhere, `notification_skip_email_types` — still gets a
	# row here, because the app half of it is a real choice; what it does not
	# get is an email control that could never do anything.
	types = []
	for name in frappe.get_all(
		"Notification Type", filters={"enabled": 1}, pluck="name", order_by="name asc"
	):
		if name not in known:
			continue
		types.append({
			"name": name,
			# `str()` resolves the lazy translation into this request's
			# language. Left lazy it would reach the browser as whatever the
			# JSON encoder made of the object.
			"about": str(known[name]["about"]),
			"in_app": name not in muted,
			"email": name in wanted and name not in skip,
			# What the panel may offer, as opposed to what is on. Push is
			# nobody's yet; email is not every kind's.
			"can_email": name not in skip,
			"push": False,
			"can_push": False,
		})

	return {
		"enabled": bool(doc.enabled),
		"email": bool(doc.enable_email_notifications),
		"types": types,
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


@frappe.whitelist(methods=["POST"])
def set_channel(kind: str, channel: str, on: int | bool | str) -> dict:
	"""Turn one channel on or off for one kind.

	The panel's control, and the reason the two halves are written differently:
	email is the framework's allow-list on `Notification Settings`, and the app
	is ours, because the framework has no per-kind switch for it at all.
	"""
	known = declared()
	if kind not in known:
		frappe.throw(_("{0} is not a notification you can set.").format(kind))

	on = bool(frappe.utils.sbool(on))

	if channel == PUSH:
		# Offered and refused. See `IN_APP, EMAIL, PUSH`.
		frappe.throw(_("Push notifications are not available yet."))

	if channel == IN_APP:
		muted = _muted()
		muted.discard(kind) if on else muted.add(kind)
		frappe.defaults.set_user_default(
			MUTED_KEY, ",".join(sorted(muted)), frappe.session.user)
		frappe.db.commit()
		return preferences()

	if channel == EMAIL:
		doc = _settings()
		wanted = {row.notification_type for row in doc.email_notification_types}
		wanted.add(kind) if on else wanted.discard(kind)
		offered = set(frappe.get_all(
			"Notification Type", filters={"enabled": 1}, pluck="name"))
		doc.email_notification_types = []
		for name in sorted(wanted & offered):
			doc.append("email_notification_types", {"notification_type": name})
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return preferences()

	frappe.throw(_("{0} is not a way to be notified.").format(channel))


# --------------------------------------------------------------------------- #
# Following a document
#
# Frappe has this and it is half of what people assume it is.
#
# What it has: the `Document Follow` doctype — `ref_doctype`, `ref_docname`,
# `user` — and `frappe.desk.form.document_follow`, which follows, unfollows and
# answers whether a document is followed. That is a real store, permissioned
# per user and worth using rather than inventing.
#
# What it does *not* have: any in-app delivery at all. The only thing that reads
# `Document Follow` is `send_document_follow_mails`, an Hourly/Daily/Weekly cron
# that assembles a digest email from `Version` and `Comment` rows. It writes no
# Notification Log, so a bell wired straight to the framework's own follow
# toggles a subscription to an email nobody on our surface has turned on, and
# nothing appears in the panel. The producer below is that missing half.
#
# Three of the framework's four refusals are also about the desk rather than
# about correctness, and would have refused every member of every workspace:
#
#   * `has_permission("Document Follow", "create")` — the doctype grants only
#     System Manager and Desk User, and our roles ship `desk_access = 0`;
#   * `User.document_follow_notify`, which defaults to 0 and gates the digest;
#   * `Administrator`, refused outright.
#
# So the writes here are `ignore_permissions` behind a read check on the
# *document*, which is the permission that actually decides — the same shape
# `spaceview.toggle_like` and `spaceview.assign` use. The refusals we keep are
# the two that are about correctness: a doctype whose changes are not tracked
# has nothing to report, and the doctypes below *are* the activity, so
# following one is a loop.
# --------------------------------------------------------------------------- #

# Frappe's own exclusions, and for its own reason: these doctypes are what a
# timeline is made of. Following a ToDo means being notified about the record
# the ToDo is about, one level of indirection away from where anybody looked.
NOT_FOLLOWABLE = frozenset({
	"Comment",
	"Communication",
	"Email Account",
	"Email Domain",
	"Email Unsubscribe",
	"File",
	"ToDo",
	"Version",
})

# How many followers one document may notify in a single write. A document
# followed by the whole workspace is a mailing list, and the notification is
# not the place to discover that.
FOLLOWERS = 50


def followable(doctype: str) -> bool:
	"""Whether this doctype can be followed at all.

	`track_changes` because a follow that reports nothing is a switch that lies,
	and Frappe's log types because a log of what happened is not a thing that
	happens.

	And a `ref_doctype` that is not a doctype at all is not followable either.
	`Version` is written against `Series` when a naming counter moves — Frappe's
	own naming settings page does it, with `ignore_links` set precisely because
	Series is not a real doctype — and a `get_meta` here that assumed otherwise
	took the whole insert down with it. Which meant moving a counter failed on
	any site this app is installed on, ours and the desk's alike.
	"""
	from frappe.model import log_types

	if not doctype or doctype in NOT_FOLLOWABLE or doctype in log_types:
		return False
	try:
		return bool(frappe.get_meta(doctype).track_changes)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return False


def _followed(doctype: str, name: str) -> bool:
	"""Does anybody follow this at all?

	Asked first, and before anything else costs a query. `on_version` runs on
	every save of every doctype that tracks its changes, site-wide — so the
	common case is nobody follows this record, and the common case has to be one
	indexed `exists` and nothing more.
	"""
	return bool(
		frappe.db.exists("Document Follow", {"ref_doctype": doctype, "ref_docname": str(name)})
	)


def is_following(doctype: str, name: str, user: str | None = None) -> bool:
	return bool(
		frappe.db.exists(
			"Document Follow",
			{
				"ref_doctype": doctype,
				"ref_docname": str(name),
				"user": user or frappe.session.user,
			},
		)
	)


def set_following(doctype: str, name: str, wanted: bool) -> bool:
	"""Follow or unfollow, and answer with what is true afterwards.

	Re-read rather than reported from the argument, for the reason every toggle
	in this product is: a control that says what it asked for rather than what
	happened is a control that ends up out of step with its own icon.
	"""
	user = frappe.session.user
	held = is_following(doctype, name, user)

	if wanted and not held:
		frappe.get_doc(
			{
				"doctype": "Document Follow",
				"ref_doctype": doctype,
				"ref_docname": str(name),
				"user": user,
			}
		).insert(ignore_permissions=True)
	elif held and not wanted:
		for row in frappe.get_all(
			"Document Follow",
			filters={"ref_doctype": doctype, "ref_docname": str(name), "user": user},
			pluck="name",
		):
			frappe.delete_doc("Document Follow", row, force=True, ignore_permissions=True)

	return is_following(doctype, name, user)


def _followers(doctype: str, name: str, exclude=()) -> list[str]:
	"""Who to tell, as the emails `enqueue_create_notification` filters on.

	Two things happen here that cannot be skipped. Followers are checked against
	the document one at a time, because a follow outlives the permission that
	allowed it — somebody removed from a role keeps the row, and the framework's
	own digest deletes it when it notices. And the ids are turned into emails,
	because `_get_user_ids` filters recipients on `User.email` rather than on
	`User.name`: a list of ids enqueues a job that succeeds and writes nothing.
	"""
	skip = {one for one in exclude if one}

	users = [
		row
		for row in frappe.get_all(
			"Document Follow",
			filters={"ref_doctype": doctype, "ref_docname": str(name)},
			pluck="user",
			limit_page_length=FOLLOWERS,
		)
		if row and row not in skip
	]
	if not users:
		return []

	allowed = [
		one
		for one in users
		if frappe.has_permission(doctype, "read", doc=str(name), user=one)
	]
	if not allowed:
		return []

	return frappe.get_all(
		"User", filters={"name": ["in", allowed], "enabled": 1}, pluck="email"
	)


def notify_followers(doctype: str, name: str, said: str, body: str = "", exclude=()) -> int:
	"""One Notification Log per follower, through the framework's own producer.

	Not a bespoke write: `enqueue_create_notification` is what applies each
	person's notification settings, skips the actor, dedupes and fans out — and
	using it is the reason a followed-document notification lands in the same
	panel, with the same read state and the same counts, as an assignment.
	"""
	actor = frappe.session.user
	return notify(FOLLOW_TYPE, _followers(doctype, name, exclude=[*exclude, actor]), {
		"document_type": doctype,
		"document_name": str(name),
		"subject": said,
		"email_content": body or said,
		"from_user": actor,
	})


# --- the two things that happen to a document -------------------------------
#
# Both from `doc_events` in hooks.py, and both chosen rather than inherited:
# they are the same two sources the framework's own digest reads. A `Version`
# row exists only where `track_changes` is on, which is exactly the condition
# `followable` requires — so hooking Version rather than `on_update` for `*`
# means the handler never runs for a doctype that could not have been followed.


def _title(doctype: str, name: str) -> str:
	from frappe.desk.doctype.notification_log.notification_log import (
		get_title,
		get_title_html,
	)

	return get_title_html(get_title(doctype, name))


def _changed(doc, meta) -> list[str]:
	"""The labels of what changed, in the screen's words rather than the table's.

	A follower is told *that* something changed and *what* — the values are on
	the record, one click away, and a notification that carries them is a
	notification that leaks a permlevel-protected field into a panel.
	"""
	data = frappe.parse_json(doc.get("data") or "{}") or {}
	names = [row[0] for row in (data.get("changed") or []) if row and row[0]]
	names += [row[0] for row in (data.get("row_changed") or []) if row and row[0]]
	names += [row[0] for row in (data.get("added") or []) if row and row[0]]

	labels = []
	for fieldname in dict.fromkeys(names):
		field = meta.get_field(fieldname)
		labels.append(_(field.label) if field and field.label else fieldname)
	return labels


def on_version(doc, method=None):
	"""A followed document was edited."""
	doctype, name = doc.get("ref_doctype"), doc.get("docname")
	if not doctype or not name or not followable(doctype):
		return
	if not _followed(doctype, name):
		return

	meta = frappe.get_meta(doctype)
	changed = _changed(doc, meta)
	if not changed:
		# A Version with nothing readable in it. Frappe writes these for
		# changes that are only bookkeeping, and "somebody updated this" with
		# no answer to "what" is the notification people turn off.
		return

	said = _("{0} updated {1} {2}").format(
		frappe.bold(_full_name(frappe.session.user)),
		frappe.bold(_(doctype)),
		_title(doctype, name),
	)
	notify_followers(doctype, name, said, body=", ".join(changed[:6]))


def on_comment(doc, method=None):
	"""Somebody commented on a followed document."""
	if doc.get("comment_type") != "Comment":
		return

	doctype, name = doc.get("reference_doctype"), doc.get("reference_name")
	if not doctype or not name or not followable(doctype):
		return
	if not _followed(doctype, name):
		return

	# Anybody named in the comment is already being told, by Frappe, as a
	# Mention. Two rows for one comment is how a panel teaches somebody that
	# most of what is in it is noise.
	from frappe.desk.notifications import extract_mentions

	said = _("{0} commented on {1} {2}").format(
		frappe.bold(_full_name(frappe.session.user)),
		frappe.bold(_(doctype)),
		_title(doctype, name),
	)
	notify_followers(
		doctype,
		name,
		said,
		body=strip_html(doc.get("content") or "")[:BODY],
		exclude=extract_mentions(doc.get("content") or ""),
	)


def _full_name(user: str) -> str:
	return frappe.db.get_value("User", user, "full_name") or user
