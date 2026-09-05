"""Everything with a date on it, for the person asking.

The calendar a screen offers reads one doctype. This one reads all of them: the
week you actually have is a quotation due on Tuesday, a site visit on Wednesday
and the review somebody put in your diary, and no single screen holds those
three. So this is a *merge* first — most of what is on it belongs somewhere else and
says where — and a small store second: the events that are the reader's own
have nowhere else to live, and `Event` is where the framework already puts
them.

Two sources, and both are already permissioned:

* **Every screen the reader can open that declares a calendar.** Resolved and
  filtered through the same path the screen's own calendar uses, so a record
  absent from that screen is absent here for the same reason.
* **The reader's own `Event` rows** — Frappe's core doctype, which is what a
  workspace already has for "a thing in somebody's diary". Theirs means owned
  by them or naming them as a participant: an events *screen* shows the
  workspace's, and this shows yours.

Named `diary` and not `calendar` because a module called `calendar` inside a
package is one import away from shadowing the standard library's, which is the
kind of bug that surfaces three files later.
"""

import frappe
from frappe import _

from .spaceview import _all_filters, _resolve, _view_types, _window, visible
from . import sync


#: Where a merged entry came from, and what a click on it should do.
FROM_SCREEN = "record"
FROM_EVENT = "event"


#: Frappe's own. Nothing here writes one, so the shape is all we need.
EVENT = "Event"


@frappe.whitelist(methods=["GET"])
def agenda(since: str | None = None, until: str | None = None) -> dict:
	"""The reader's days, merged from every calendar this workspace has.

	`since` and `until` are the days on screen, the same pair the screen-level
	calendar sends and for the same reason: a diary is not a page, and a month
	drawn from whichever rows sorted first has holes in it.

	Empty rather than fatal where a source cannot be read. One screen whose
	doctype was revoked between the manifest and the query is not a reason to
	take somebody's whole week away.
	"""
	spaces = visible(sync.state().get("spaces") or [])
	mine = _own_events(since, until)
	found = _once(_from_screens(spaces, since, until) + mine)
	_theirs(found, mine)
	# By when they start, so the merge reads as one diary rather than as its
	# sources laid end to end. The grid sorts within a day itself.
	found.sort(key=lambda one: (one.get("start") or "", one.get("title") or ""))
	return {"events": found, "sources": _sources(spaces)}


def _theirs(found: list[dict], mine: list[dict]) -> None:
	"""Mark the entries that are the reader's own event, screen or no screen.

	The de-duplication above hands a shared workspace's events screen the win,
	which is right for opening a *record*: the screen is where the doctype's
	own form and rules are. It is wrong for the one thing this surface writes.
	A workspace with an events screen would otherwise let somebody press New
	here, write an event, and then never be able to edit it from the diary they
	wrote it in — the entry would open the screen instead.

	So ownership is carried separately from where the entry came from. The
	surface reads it as "yours opens here", and everything else opens where it
	lives.
	"""
	owned = {one["record"] for one in mine}
	for one in found:
		one["mine"] = one.get("doctype") == EVENT and one.get("record") in owned


def _once(found: list[dict]) -> list[dict]:
	"""One entry per record, however many sources reached it.

	A workspace with an events screen puts the same meeting in front of the
	same person twice — once because it is on that screen, once because it is
	in their own diary — and a calendar that draws Tuesday's review twice is
	one nobody trusts about Wednesday.

	Screens are folded in first and win, because a screen entry can be opened:
	it knows where the record lives. The personal row knows only that the
	record exists.
	"""
	seen, kept = set(), []
	for one in found:
		at = (one.get("doctype") or "", one.get("record") or "")
		if at in seen:
			continue
		seen.add(at)
		kept.append(one)
	return kept


def _from_screens(spaces: list, since, until) -> list[dict]:
	"""Every calendar-declaring screen's records in the range."""
	found = []
	for space in spaces:
		for screen in space.get("screens") or []:
			if "calendar" not in _view_types(screen):
				continue
			try:
				found += _screen_rows(space, screen, since, until)
			except Exception:
				# A screen that cannot be read is one screen missing from the
				# merge, not an error page over the other four. Logged rather
				# than swallowed silently — this is where a revoked doctype or
				# a manifest typo shows up.
				frappe.log_error(title="Diary: a screen could not be read")
	return found


def _screen_rows(space: dict, screen: dict, since, until) -> list[dict]:
	"""One screen's records, through that screen's own resolution.

	`_resolve` rather than a query written here: the screen's filters, its
	permissions and the doctype's own User Permissions all live on that path,
	and a second way in is a second thing to keep in step.
	"""
	code = space.get("space_code") or ""
	resolved = _resolve(code, screen.get("screen"), view_type="calendar")
	dates = resolved.get("calendar") or {}
	start, end = dates.get("start_field"), dates.get("end_field")
	if not resolved.get("doctype") or not start:
		return []

	window = _window(resolved, since, until)
	if not window:
		# No range is not "everything": a diary asking for nothing should get
		# nothing rather than every row this screen has ever had.
		return []

	title = resolved.get("title_field") or "name"
	rows = frappe.get_list(
		resolved["doctype"],
		fields=list(dict.fromkeys(["name", title, start] + ([end] if end else []))),
		filters=_all_filters(resolved, resolved.get("asked") or []) + window,
		limit_page_length=MAX_PER_SCREEN,
	)
	return [
		{
			# Unique across the merge: two screens over two doctypes can both
			# have a record called `EV00001`.
			"id": f"{code}/{screen.get('screen')}/{row.name}",
			"title": str(row.get(title) or row.name),
			"start": str(row.get(start) or ""),
			"end": str(row.get(end) or "") if end else "",
			"kind": FROM_SCREEN,
			"doctype": resolved["doctype"],
			"space": code,
			"space_label": space.get("space_label") or code,
			"screen": screen.get("screen"),
			"screen_label": screen.get("label") or screen.get("screen"),
			"record": row.name,
		}
		for row in rows
	]


#: Per screen, per month. High enough that a real month is never truncated,
#: low enough that a screen over a busy doctype cannot make this one request
#: fetch a year of rows. A month past this is a screen to open on its own.
MAX_PER_SCREEN = 500


def _own_events(since, until) -> list[dict]:
	"""The reader's own `Event` rows.

	Theirs, not the workspace's: owned by them, or naming them among the
	participants. An events *screen* is where somebody reads what the workspace
	has; a diary is where they read what is theirs.

	Two queries and a union rather than one with an `or_filters`, because
	Frappe cannot put two OR groups in one `get_all` and the participant half
	is a join. Both go through `get_list`, so `Event`'s own permissions still
	decide.
	"""
	if not since or not until:
		return []

	me = frappe.session.user
	window = [[EVENT, "starts_on", "between", [since, until]]]
	fields = ["name", "subject", "starts_on", "ends_on"]

	mine = frappe.get_list(EVENT, fields=fields, filters=window + [[EVENT, "owner", "=", me]],
	                       limit_page_length=MAX_PER_SCREEN)
	joined = frappe.get_list(
		EVENT,
		fields=fields,
		filters=window + [
			["Event Participants", "reference_doctype", "=", "User"],
			["Event Participants", "reference_docname", "=", me],
		],
		limit_page_length=MAX_PER_SCREEN,
	)

	seen, out = set(), []
	for row in mine + joined:
		if row.name in seen:
			continue
		seen.add(row.name)
		out.append({
			"id": f"event/{row.name}",
			"title": str(row.subject or row.name),
			"start": str(row.starts_on or ""),
			"end": str(row.ends_on or ""),
			"kind": FROM_EVENT,
			"doctype": EVENT,
			"space": "",
			"space_label": "",
			"screen": "",
			"screen_label": _("Your diary"),
			"record": row.name,
		})
	return out


def _sources(spaces: list) -> list[dict]:
	"""What the merge is made of, so the surface can say and can filter.

	The reader's own row is always here, whether or not they have an event this
	month: a source that appears and disappears with its contents is a filter
	list that moves under the cursor.
	"""
	found = [{
		"key": FROM_EVENT,
		"label": _("Your diary"),
		"space": "",
		"screen": "",
	}]
	for space in spaces:
		for screen in space.get("screens") or []:
			if "calendar" not in _view_types(screen):
				continue
			found.append({
				"key": f"{space.get('space_code')}/{screen.get('screen')}",
				"label": screen.get("label") or screen.get("screen"),
				"space": space.get("space_code") or "",
				"space_label": space.get("space_label") or "",
				"screen": screen.get("screen"),
			})
	return found


# --------------------------------------------------------------------------- #
# The reader's own events, which are the one thing this surface stores.


@frappe.whitelist(methods=["POST"])
def save_event(values: str | dict) -> dict:
	"""Write one event of the reader's own — new, or one they already own.

	`ignore_permissions` behind this module's own gate, and the gate is
	ownership rather than the workspace's doctype grants. Those grants are how
	a *space* decides who may read its records; a diary is not a space, and
	"you may put something in your own week" is not a thing an admin should
	have to enable per workspace. `_mine` is the whole of it: a row you do not
	own is a row this endpoint will not fetch.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	subject = (values.get("subject") or "").strip()
	if not subject:
		frappe.throw(_("Give it a name."))

	starts_on = (values.get("starts_on") or "").strip()
	if not starts_on:
		frappe.throw(_("Say when it starts."))

	ends_on = (values.get("ends_on") or "").strip()
	# An end before the start is a typo every calendar makes possible and none
	# should store: the grid would draw a span running backwards.
	if ends_on and ends_on < starts_on:
		frappe.throw(_("It cannot end before it starts."))

	name = (values.get("name") or "").strip()
	doc = _mine(name) if name else frappe.new_doc(EVENT)
	doc.update({
		"subject": subject,
		"starts_on": starts_on,
		"ends_on": ends_on or None,
		"all_day": 1 if values.get("all_day") else 0,
		"description": values.get("description") or "",
		# Private, and not a choice on the form. A public Event is one the
		# whole site sees, and a diary is the last place to offer that by
		# accident — sharing an event is naming who is in it, which is the next
		# piece of this rather than a dropdown here.
		"event_type": "Private",
	})

	if name:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def remove_event(name: str) -> dict:
	"""Delete one of the reader's own events."""
	doc = _mine(name)
	frappe.delete_doc(EVENT, doc.name, ignore_permissions=True)
	return {"ok": True, "removed": name}


@frappe.whitelist(methods=["GET"])
def event(name: str) -> dict:
	"""One of the reader's own events, to edit."""
	doc = _mine(name)
	return {
		"name": doc.name,
		"subject": doc.subject or "",
		"starts_on": str(doc.starts_on or ""),
		"ends_on": str(doc.ends_on or ""),
		"all_day": int(doc.all_day or 0),
		"description": doc.description or "",
	}


def _mine(name: str):
	"""One event this person owns, or a refusal.

	Owner and not participant: being invited to something is not permission to
	rewrite it. Reading one is `agenda`, which already includes the events
	somebody was named in.
	"""
	if not name or not frappe.db.exists(EVENT, {"name": name, "owner": frappe.session.user}):
		frappe.throw(_("That is not one of your events."), frappe.PermissionError)
	return frappe.get_doc(EVENT, name)
