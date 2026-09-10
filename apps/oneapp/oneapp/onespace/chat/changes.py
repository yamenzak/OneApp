"""A write the assistant has asked for, and the moment somebody says yes.

The assistant cannot save anything. What it can do is write one of these — a
row saying which record, which fields, and what they would become — and the
write itself happens later, in a request a person made by pressing Apply, going
through `spaceview.records.save`: the same function the form posts to, with the
same field allowlist, the same permission checks and the same workflow rule
about who may edit a document where it currently is.

That is the whole of the safety argument and it is worth being exact about why
it is not a formality. A tool that saves is a tool that saves on a model's
say-so, and the failure mode is not a wrong field — it is a wrong *record*, at
the end of a chain of lookups nobody read. Splitting the ask from the write puts
a human between those two things, and puts the diff in front of them while they
decide.

Three rules make the card honest.

**Everything is checked at proposal time.** The screen has to resolve, the
record has to be one that screen would list, and every fieldname has to be one
the screen may write. A model that names a field wrongly is told so on the turn
it made the mistake, rather than a person discovering it when they press Apply.

**What is there now is captured with it.** `before` holds the same fields as
they read at proposal time. Apply compares, and a record that moved in between
is refused rather than overwritten — the person agreed to a diff, and it is no
longer that diff.

**Nothing drains this.** No scheduler, no queue, no retry. A proposal nobody
answered is a question nobody answered, and the only two things that resolve one
are a person pressing Apply and a person pressing Discard.
"""

import json

import frappe
from frappe import _

CHANGE = "OneSpace Chat Change"

PROPOSED, APPLIED, DISCARDED, FAILED = "Proposed", "Applied", "Discarded", "Failed"

#: Fields one proposal may touch. Not a performance limit — a model that has
#: decided to rewrite forty fields of a record has misunderstood the question,
#: and a card with forty rows is one nobody reads before pressing Apply.
MAX_FIELDS = 20


def mine(name: str, level: str = "read"):
	"""The proposal, if it is this person's. The same check the sessions use."""
	if not frappe.has_permission(CHANGE, level, doc=name):
		frappe.throw(_("That change is not yours."), frappe.PermissionError)
	return frappe.get_doc(CHANGE, name)


# --------------------------------------------------------------------------- #
# Proposing
# --------------------------------------------------------------------------- #

def propose(session: str, space: str, screen: str, values: dict,
            docname: str = "") -> dict:
	"""Record what would be written, having checked that it could be.

	Returns what the model is told, which is deliberately not "done": it says
	the change is waiting, so the answer it writes afterwards says so too.
	"""
	from oneapp.onespace.spaceview.resolve import _resolve

	resolved = _resolve(space, screen)
	if not resolved.get("doctype"):
		return {"error": _("That screen holds no records to change.")}

	if not isinstance(values, dict) or not values:
		return {"error": _("Say which fields to set, and to what.")}
	if len(values) > MAX_FIELDS:
		return {"error": _("That is more fields than one change may set.")}

	writable = _writable(resolved)
	unknown = [one for one in values if one not in writable]
	if unknown:
		return {"error": _("This screen has no field called {0}. Call "
		                   "describe_screen to see what it carries.").format(unknown[0])}

	before, current = {}, None
	if docname:
		current = _record(space, screen, docname)
		if not current:
			return {"error": _("No record called {0} on that screen.").format(docname)}
		if not _editable(resolved["doctype"], docname):
			return {"error": _("That record is not yours to change where it is.")}
		before = {one: current.get(one) for one in values}
		values = {k: v for k, v in values.items() if not _same(before.get(k), v)}
		if not values:
			return {"answer": _("It already says that. Nothing to change.")}
		before = {one: before.get(one) for one in values}

	doc = frappe.get_doc({
		"doctype": CHANGE,
		"session": session,
		"after_message": _last_message(session),
		"kind": "Update" if docname else "Create",
		"state": PROPOSED,
		"space": space,
		"screen": screen,
		"docname": docname or "",
		"summary": _summary(resolved, current, values, docname),
		"changes": json.dumps(values, default=str),
		"before": json.dumps(before, default=str),
	})
	doc.insert()

	return {
		"proposed": doc.name,
		"summary": doc.summary,
		"note": _("Nothing has been changed. This is waiting for the person to "
		          "approve it — tell them what it would do and stop there."),
	}


def _summary(resolved: dict, current: dict | None, values: dict, docname: str) -> str:
	"""One line, written here rather than by the model.

	A card whose heading is the model's wording and whose rows are the stored
	diff is a card that can say two different things, and the one somebody
	reads is the heading.
	"""
	one_of = resolved.get("singular") or _("record")
	if not docname:
		return _("Create a {0} on {1}").format(one_of, resolved.get("screen_label") or "")

	title = (resolved.get("title_field") or "").strip()
	said = str((current or {}).get(title) or "").strip() if title else ""
	called = f"{said} ({docname})" if said and said != docname else docname
	return _("Change {0} on {1}").format(called, _words(resolved, values))


def _words(resolved: dict, values: dict) -> str:
	"""The fields being set, in the screen's own labels."""
	labels = {c["fieldname"]: c.get("label") or c["fieldname"]
	          for c in (resolved.get("all_columns") or resolved.get("columns") or [])}
	return ", ".join(labels.get(one, one) for one in values)


# --------------------------------------------------------------------------- #
# Answering
# --------------------------------------------------------------------------- #

def apply(name: str) -> dict:
	"""Write it, as the person who pressed Apply.

	Through `records.save`, which is the point: the assistant's proposal has no
	privileges of its own, and a change to a screen this person may not write
	is refused here exactly as it would be from the form.
	"""
	from oneapp.onespace.spaceview.records import save

	doc = mine(name, "write")
	if doc.state != PROPOSED:
		frappe.throw(_("That change has already been answered."))

	if stale := _moved(doc):
		doc.db_set({"state": FAILED, "error": stale}, update_modified=False)
		return {"ok": False, "state": FAILED, "error": stale}

	frappe.db.savepoint("chat_change")
	try:
		written = save(
			space_code=doc.space, screen=doc.screen,
			values=json.loads(doc.changes or "{}"),
			name=doc.docname or None,
		)
	except Exception as e:
		# Back to the savepoint rather than the whole transaction: a validation
		# failure part-way through a document must not leave half of it behind,
		# and rolling the request back instead would take the Failed row with
		# it and leave the card sitting on Proposed, inviting the same press.
		frappe.db.rollback(save_point="chat_change")
		doc.db_set({"state": FAILED, "error": _said(e)}, update_modified=False)
		return {"ok": False, "state": FAILED, "error": doc.error}
	frappe.db.release_savepoint("chat_change")

	doc.db_set({
		"state": APPLIED,
		"applied_on": frappe.utils.now(),
		"applied_name": written.get("name") or doc.docname or "",
	}, update_modified=False)
	return {"ok": True, "state": APPLIED, "name": written.get("name") or ""}


def discard(name: str) -> dict:
	"""No. Kept rather than deleted, so the thread still says it was asked."""
	doc = mine(name, "write")
	if doc.state != PROPOSED:
		frappe.throw(_("That change has already been answered."))
	doc.db_set({"state": DISCARDED}, update_modified=False)
	return {"ok": True, "state": DISCARDED}


def _moved(doc) -> str:
	"""Whether the record has changed under the proposal, said in words."""
	if doc.kind != "Update":
		return ""
	before = json.loads(doc.before or "{}")
	if not before:
		return ""

	now = _record(doc.space, doc.screen, doc.docname)
	if not now:
		return _("That record is gone.")

	moved = [one for one, was in before.items() if not _same(was, now.get(one))]
	if moved:
		return _("{0} changed since this was suggested, so it was not "
		         "applied.").format(", ".join(moved))
	return ""


# --------------------------------------------------------------------------- #
# Reading them back
# --------------------------------------------------------------------------- #

def for_session(session: str) -> list[dict]:
	"""Every change proposed in one thread, oldest first, as the card needs it."""
	rows = frappe.get_list(
		CHANGE,
		filters={"session": session},
		fields=["name", "after_message", "kind", "state", "space", "screen",
		        "docname", "summary", "changes", "before", "applied_name", "error"],
		order_by="creation asc",
		limit_page_length=0,
	)
	for row in rows:
		row["changes"] = _read(row.get("changes"))
		row["before"] = _read(row.get("before"))
		row["fields"] = _rows(row)
	return rows


def _rows(row: dict) -> list[dict]:
	"""The diff, field by field, in the screen's own labels.

	Resolved on the way out rather than stored: a screen that renames a column
	should rename it on a card somebody has not answered yet.
	"""
	from oneapp.onespace.spaceview.resolve import _resolve

	try:
		resolved = _resolve(row["space"], row["screen"])
	except Exception:
		resolved = {}

	labels = {c["fieldname"]: c.get("label") or c["fieldname"]
	          for c in (resolved.get("all_columns") or resolved.get("columns") or [])}
	before = row.get("before") or {}
	return [
		{"fieldname": one, "label": labels.get(one, one),
		 "was": before.get(one), "now": value}
		for one, value in (row.get("changes") or {}).items()
	]


# --------------------------------------------------------------------------- #
# Small shared things
# --------------------------------------------------------------------------- #

def _writable(resolved: dict) -> set:
	"""What this screen may write. `records._writable`, not a second answer."""
	from oneapp.onespace.spaceview.records import _writable as allowed

	return set(allowed(resolved))


def _record(space: str, screen: str, docname: str) -> dict | None:
	from oneapp.onespace.spaceview.records import record

	return record(space_code=space, screen=screen, name=docname)


def _editable(doctype: str, docname: str) -> bool:
	"""The workflow's answer, asked before the card is drawn rather than after.

	`records.save` asks it too and would refuse on Apply. Asking here as well is
	the difference between the model being told now and a person being told
	after they agreed to something that was never going to happen.
	"""
	from oneapp.onespace import docflow

	try:
		return bool(docflow.editable(frappe.get_doc(doctype, docname)))
	except frappe.PermissionError:
		return False


def _last_message(session: str) -> str:
	rows = frappe.get_all("OneSpace Chat Message", filters={"session": session},
	                      fields=["name"], order_by="seq desc", limit_page_length=1)
	return rows[0]["name"] if rows else ""


def _same(one, other) -> bool:
	"""Whether two stored values are the same to a person.

	`1` and `"1"` come back differently from a form and from a model, and a
	proposal that reads as a change because a check arrived as a string is a
	card with a row on it saying nothing changed.
	"""
	if one is None or one == "":
		one = ""
	if other is None or other == "":
		other = ""
	return str(one) == str(other)


def _said(e: Exception) -> str:
	"""What went wrong, in the words the form would have shown.

	Frappe's own validation speaks through `frappe.throw`, which puts a
	sentence a person can act on into the message log; the exception's own
	`str` is that sentence wrapped in markup or, for anything else, a class
	name. So the log first, and a plain apology rather than a traceback when
	there is nothing in it — a stack trace on a card is a stack trace in front
	of a customer.
	"""
	log = getattr(frappe.local, "message_log", None) or []
	said = ""
	if log:
		last = log[-1]
		said = (last.get("message") if isinstance(last, dict) else str(last)) or ""
	said = frappe.utils.strip_html(said).strip() if said else ""
	return (said or _("That change could not be saved."))[:500]


def _read(raw):
	try:
		found = json.loads(raw or "{}")
	except (TypeError, ValueError):
		return {}
	return found if isinstance(found, dict) else {}
