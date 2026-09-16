"""Who a record lands with, decided by a rule rather than by whoever noticed.

`docs/WORK.md` stage 7, and the last of that arc. The sentence it exists to
make writable is:

    When a **task** reaches **In review**, hand it to **the reviewers**, one
    after another.

Frappe already does all of it. `Assignment Rule` is condition → users → a way
of choosing between them, run on every save of the doctype it names, and it
assigns through `assign_to.add` — the same ToDo every other assignment in this
product is. Nothing here is a second engine; `docs/WORK.md` §2 is emphatic that
an assignment is Frappe's and stays Frappe's.

What is here is the gate and the shape, and both are `onespace/alerts.py`'s,
deliberately: an alert and a routing rule are the same sentence with a
different verb — when *this* happens to *that kind of record*, do something —
so the vocabulary they are written in is shared rather than rewritten. This
module imports `alerts` for the parts that are about *records*: which doctypes
a workspace may reach, which fields a condition may test, and how a condition
is compiled. What it adds is the part that is about *people*.

## Three decisions

**The condition is compiled, never typed.** `assign_condition` is `eval`ed with
the document in scope on every save, so a text box here is a text box that runs
Python. The triple `alerts._condition` builds is the same one the alerts
builder uses, and the rules people write — "when the state is In review" — need
three controls rather than a language.

**The users are the workspace's.** Not `frappe.get_all("User")`, which on any
site includes Administrator and every Guest-shaped account an integration left
behind: a rule that round-robins onto Administrator is a rule that assigns work
to us.

**Unassign is not offered.** Frappe will take an assignment *away* when a
second condition goes true, and that is a footgun with a delay on it: work
vanishes from somebody's list, on a rule written weeks ago, with nothing on the
record to say why. A rule here adds; a person removes.
"""

import frappe
from frappe import _

from oneapp.onespace import alerts, sync

#: The mark on a rule this workspace wrote — the same field and the same
#: argument as `alerts.MARK`, on a different doctype. `install.py` adds it.
MARK = alerts.MARK

OURS = {MARK: 1}

#: How a rule chooses between the people it was given.
#:
#: Frappe's three, in the words somebody would use. The right-hand side is its
#: own `rule` Select, so this is a vocabulary rather than a second chooser.
WAYS = {
	"in turn": "Round Robin",
	"by load": "Load Balancing",
	"by field": "Based on Field",
}

#: How many people one rule may name. Past this it is a team, and a team is a
#: role — which is what an alert names and what a queue screen is for.
MOST_USERS = 20

#: Every day. Frappe's `Assignment Rule` needs at least one `Assignment Day`
#: row or it assigns on no day at all, and "only on Tuesdays" is a rule nobody
#: in this product has asked for — so the days are all of them, written once.
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday")


def doctypes(space: str = "") -> list[dict]:
	"""What a rule may be about, and what each offers to test and to assign by.

	`alerts.doctypes` answers most of it — the same scope, the same permission
	check, the same shape — and this adds the one thing routing needs that an
	alert does not: which fields hold a *person*, for the rule that assigns by
	a field on the record.
	"""
	found = alerts.doctypes(space)
	for one in found:
		meta = alerts._meta(one["doctype"])
		one["people"] = alerts._fields(meta, ("Link",), option="User") if meta else []
	return found


def users() -> list[dict]:
	"""The people a rule may hand work to.

	This workspace's members, from the same place the people picker reads —
	and not `get_all("User")`, which includes Administrator, every disabled
	account and whatever a integration left behind. A rule that round-robins
	onto Administrator is a rule that assigns work to us.
	"""
	from oneapp.onespace.spaceview.people import colleagues

	return [
		{"value": one["value"], "label": one.get("label") or one["value"]}
		for one in (colleagues() or [])
	]


def listing() -> list[dict]:
	"""Every routing rule this workspace made, newest first."""
	granted = sync.granted_doctypes()
	rows = []
	for name in frappe.get_all(
		"Assignment Rule", filters=OURS, pluck="name", order_by="creation desc",
	):
		rule = _read(frappe.get_doc("Assignment Rule", name))
		# A rule on a doctype the workspace no longer has. Shown and flagged,
		# for `alerts.listing`'s reason: hiding it leaves a rule nobody can
		# find to delete.
		rule["orphaned"] = rule["doctype"] not in granted
		rows.append(rule)
	return rows


def _read(doc) -> dict:
	"""One Assignment Rule, back in the words it was written in."""
	way = next((word for word, rule in WAYS.items() if rule == doc.rule), "in turn")
	return {
		"name": doc.name,
		"title": doc.description or doc.name,
		"enabled": not bool(doc.disabled),
		"doctype": doc.document_type,
		"way": way,
		"field": doc.field or "",
		"users": [row.user for row in (doc.users or []) if row.user],
		"condition": alerts._decompile(doc.assign_condition or "", alerts.BARE),
	}


def save(values: dict) -> dict:
	"""Write one rule, in Frappe's own shape.

	Everything is validated here rather than trusted, for `alerts.save`'s
	reason and more sharply: the condition reaches an `eval` on every save of
	every record of that doctype.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	doctype = (values.get("doctype") or "").strip()
	if doctype not in sync.granted_doctypes():
		frappe.throw(_("That is not one of this workspace's records."),
		             frappe.PermissionError)
	meta = alerts._meta(doctype)

	way = (values.get("way") or "in turn").strip()
	if way not in WAYS:
		frappe.throw(_("Say how the work should be shared out."))

	# A rule that assigns *by a field* takes the person off the record and the
	# list of users is the set it is allowed to be. Frappe reads both.
	field = (values.get("field") or "").strip()
	if way == "by field":
		if not any(one["fieldname"] == field for one in
		           (alerts._fields(meta, ("Link",), option="User") if meta else [])):
			frappe.throw(_("Pick the field on {0} that holds the person.")
			             .format(_(doctype)))
	else:
		field = ""

	wanted = [one for one in (values.get("users") or []) if isinstance(one, str)]
	allowed = {one["value"] for one in users()}
	chosen = [one for one in dict.fromkeys(wanted) if one in allowed][:MOST_USERS]
	if not chosen:
		frappe.throw(_("Say who the work goes to."))

	condition = values.get("condition") or None
	if not condition:
		# Unlike an alert, which may fire on every save of a doctype, a routing
		# rule with no condition assigns *everything* of that kind to somebody
		# for ever. Refused rather than allowed: the rule people mean always
		# has a "when" in it.
		frappe.throw(_("Say when the rule should hand the record over."))
	# Bare, not `doc.`-prefixed: `Assignment Rule` passes the document as the
	# *locals* of its eval, so a prefixed test evaluates to False for ever and
	# the rule simply never fires. `alerts.BARE` is the whole of the
	# difference, and the comment on `alerts.DOC` is why there is one.
	built = alerts._condition(meta, condition, alerts.BARE)

	title = (values.get("title") or "").strip()
	if not title:
		frappe.throw(_("A rule needs a name — it is what the list shows."))

	name = (values.get("name") or "").strip()
	doc = _ours(name) if name else frappe.new_doc("Assignment Rule")
	if not name:
		# `Assignment Rule` is named by prompt — the desk asks for one in a
		# dialog before the form opens. There is no such dialog here and there
		# should not be: the rule already has a name, which is the sentence
		# somebody typed. Renaming on an edit is deliberately not done: the id
		# is what a ToDo's `assignment_rule` points at.
		doc.name = (values.get("title") or "").strip()

	doc.update({
		MARK: 1,
		"document_type": doctype,
		"description": title,
		"disabled": 0 if values.get("enabled", True) else 1,
		"rule": WAYS[way],
		"field": field or None,
		"assign_condition": built,
		# Never written. See the module docstring: a rule here adds, and a
		# person removes.
		"unassign_condition": "",
		"close_condition": "",
	})
	doc.set("users", [{"user": one} for one in chosen])
	doc.set("assignment_days", [{"day": day} for day in DAYS])
	try:
		doc.save(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		frappe.throw(_("There is already a rule called “{0}”. Give this one a "
		               "different name.").format(title))
	return _read(doc)


def set_enabled(name: str, enabled: bool) -> dict:
	"""Pause a rule, or start it again, without losing what it says."""
	doc = _ours(name)
	doc.db_set("disabled", 0 if enabled else 1, update_modified=False)
	doc.reload()
	return _read(doc)


def remove(name: str) -> dict:
	doc = _ours(name)
	frappe.delete_doc("Assignment Rule", doc.name, ignore_permissions=True)
	return {"ok": True, "removed": name}


def _ours(name: str):
	"""One rule, if it is this workspace's to touch."""
	doc = frappe.get_doc("Assignment Rule", name)
	if not doc.get(MARK):
		frappe.throw(_("That rule was not made here and cannot be changed here."),
		             frappe.PermissionError)
	return doc
