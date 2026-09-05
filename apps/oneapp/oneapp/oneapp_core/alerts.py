"""Tell somebody when something happens to a record.

The last real gap in the mailbox, and the one `docs/EMAIL.md` called the biggest
single win through two rounds of deferral: a workspace wanting "email me when an
invoice goes overdue" had nowhere to say so.

Frappe already does all of it. `Notification` is rule → recipients → message on
a document event, with a scheduler for the date-relative ones, Jinja for the
body, and a `System Notification` channel that writes the same `Notification
Log` our bell already reads. Nothing here reimplements any of that. What is here
is the gate and the shape.

## The shape, and why it is this small

A rule is one sentence:

    When an **invoice** is **3 days past its due date**, email **the accounts
    role** — and say **this**.

Frappe's own form offers eight events, a Jinja condition box, a filters JSON, a
property to set afterwards, four channels and a Slack webhook. That is the right
surface for somebody automating a factory and the wrong one for somebody who
wants to be told about an overdue invoice. So this offers five events, one
optional condition written as a field, an operator and a value, and recipients
that are a role, a person or a field on the document holding an address.

The condition is **compiled, never typed**. Frappe `eval`s `condition` with the
document in scope, so a text box here would be a text box that runs Python as
the system user. `_condition()` builds the string from a triple this module
validated, which is the same argument `Mail Rule` makes about filing: the rules
people actually write are "when the status is Overdue", and a builder that can
express anything is a builder nobody uses to express something.

The door is `workspace._alerts_gate`, beside every other settings gate, and
this module is the logic behind it — the same split `naming` and `printing`
have.

## What a workspace may reach

Its own spaces' doctypes, the same scope `naming` and `printing` use, and the
same reason: a workspace that can put a rule on `Error Log` has been handed the
platform's own bookkeeping to mail itself about.
"""

import frappe
from frappe import _

from oneapp.oneapp_core import sync

# The mark on a rule this workspace wrote.
#
# `is_standard` was the obvious answer and is the wrong one. It says a rule
# belongs to a `Module Def` and is exported to disk, which is a real and useful
# distinction — but Frappe ships two non-standard Notifications of its own on
# every site, `[Error] {{ doc.method }}` and its integration twin, and listing
# the platform's own error alerts in a customer's settings is a bug the first
# customer would report.
#
# So ours carry a field of ours, the same way `Communication` carries
# `custom_thread`. `module` would have been the other candidate and it is a Link
# to `Module Def`: a module row existing only to label rows is a doctype
# pretending to be a flag.
MARK = "custom_onespace"

OURS = {MARK: 1}

# What a rule can wait for, in the words somebody would use. The right-hand side
# is Frappe's own `event`, which is what the scheduler and the document hooks
# read — so this is a vocabulary, not a second event system.
WHEN = {
	"created": "New",
	"changed": "Save",
	"submitted": "Submit",
	"cancelled": "Cancel",
	"before": "Days Before",
	"after": "Days After",
}

# The two that need a date field to count from, and a number of days.
DATED = ("before", "after")

# How long a rule may wait. Frappe bounds none; a rule ninety days out is one
# whose author has forgotten it exists, and the scheduler walks every dated rule
# every day.
MAX_DAYS = 60

# What a condition can ask. Deliberately the operators a person can read back
# out of the sentence they wrote — no `like`, because "contains" on a status is
# a question about a Select and the answer is `is`.
OPERATORS = {
	"is": "==",
	"is not": "!=",
	"over": ">",
	"under": "<",
	"is set": "",
	"is not set": "",
}

# Where a rule can send. Frappe has four channels; Slack needs a webhook nobody
# has configured and SMS needs a gateway we do not run.
CHANNELS = {
	"email": "Email",
	"app": "System Notification",
}


def doctypes() -> list[dict]:
	"""What a rule may be about, and what each one offers to watch and to say."""
	found = []
	for doctype in sorted(sync.granted_doctypes()):
		if not frappe.has_permission(doctype, "read"):
			# Granted by the space and not reachable by this person's role.
			# Absent rather than refused: a settings page listing what you
			# cannot open is a page that lies about your access.
			continue
		meta = _meta(doctype)
		if not meta:
			continue
		found.append({
			"doctype": doctype,
			"label": _(doctype),
			"dates": _fields(meta, ("Date", "Datetime")),
			"watchable": _fields(meta, ("Select", "Link", "Check", "Data")),
			"addresses": _fields(meta, ("Data",), option="Email"),
			"submittable": bool(meta.is_submittable),
		})
	return found


def _meta(doctype: str):
	try:
		return frappe.get_meta(doctype)
	except frappe.DoesNotExistError:
		return None


# Fields that are a real field and not something to write a rule about. The
# series is how a record is named and `amended_from` is the framework's own
# bookkeeping; both are Data or Select and would otherwise head the list.
PLUMBING = ("naming_series", "amended_from")


def _fields(meta, types, option=None) -> list[dict]:
	"""The fields of some type, as the picker needs them."""
	return [
		{"fieldname": f.fieldname, "label": _(f.label or f.fieldname),
		 "options": f.options or ""}
		for f in meta.fields
		if f.fieldtype in types
		and f.fieldname not in PLUMBING
		and not f.hidden
		and (option is None or f.options == option)
	]


def roles() -> list[dict]:
	"""The roles a rule may name.

	This workspace's own, from the synced manifest, plus the owner role every
	workspace has. Not `frappe.get_all("Role")`: that is Frappe's whole list —
	Accounts Manager, Newsletter Manager, System Manager — and a rule that mails
	System Manager is a rule that mails us.
	"""
	from oneapp.oneapp_core.workspace import OWNER_ROLE

	wanted = list(sync.state().get("roles") or []) + [OWNER_ROLE]
	found = frappe.get_all(
		"Role",
		filters={"name": ["in", list(dict.fromkeys(wanted))], "disabled": 0},
		pluck="name",
		order_by="name asc",
	)
	return [{"value": one, "label": _(one)} for one in found]


def listing() -> list[dict]:
	"""Every rule this workspace made, newest first."""
	granted = sync.granted_doctypes()
	rows = []
	for name in frappe.get_all(
		"Notification", filters=OURS, pluck="name", order_by="creation desc",
	):
		rule = _read(frappe.get_doc("Notification", name))
		# A rule on a doctype the workspace no longer has is a rule about
		# something it cannot see. Shown, because hiding it would leave a rule
		# nobody can find to delete, and flagged so it reads as broken.
		rule["orphaned"] = rule["doctype"] not in granted
		rows.append(rule)
	return rows


def _read(doc) -> dict:
	"""One Notification, back in the words it was written in."""
	when = next((word for word, event in WHEN.items() if event == doc.event), "")
	row = (doc.recipients or [None])[0]
	return {
		"name": doc.name,
		"title": doc.subject or doc.name,
		"enabled": bool(doc.enabled),
		"doctype": doc.document_type,
		"when": when,
		"date_field": doc.date_changed or "",
		"days": int(doc.days_in_advance or 0),
		"channel": next((k for k, v in CHANNELS.items() if v == doc.channel), "email"),
		"subject": doc.subject or "",
		"message": doc.message or "",
		"to_role": (row.receiver_by_role if row else "") or "",
		"to_field": (row.receiver_by_document_field if row else "") or "",
		"condition": _decompile(doc.condition),
	}


def save(values: dict) -> dict:
	"""Write one rule, in Frappe's own shape.

	Everything is validated here rather than trusted, because the two fields
	that reach an `eval` — the condition and the days — are built from what this
	returns.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	doctype = (values.get("doctype") or "").strip()
	if doctype not in sync.granted_doctypes():
		frappe.throw(_("That is not one of this workspace's records."),
		             frappe.PermissionError)

	when = (values.get("when") or "").strip()
	if when not in WHEN:
		frappe.throw(_("Say when the alert should go out."))

	meta = _meta(doctype)
	if when in ("submitted", "cancelled") and not (meta and meta.is_submittable):
		frappe.throw(_("{0} is not submitted, so it cannot be submitted or cancelled.")
		             .format(_(doctype)))

	date_field, days = "", 0
	if when in DATED:
		date_field = (values.get("date_field") or "").strip()
		if not _has(meta, date_field, ("Date", "Datetime")):
			frappe.throw(_("Pick the date to count from."))
		days = int(values.get("days") or 0)
		if not 0 <= days <= MAX_DAYS:
			frappe.throw(_("Between 0 and {0} days.").format(MAX_DAYS))

	subject = (values.get("subject") or "").strip()
	if not subject:
		frappe.throw(_("An alert needs a subject — it is the line people see."))

	to_role = (values.get("to_role") or "").strip()
	to_field = (values.get("to_field") or "").strip()
	if not (to_role or to_field):
		frappe.throw(_("Say who the alert goes to."))
	if to_field and not _has(meta, to_field, ("Data", "Link")):
		frappe.throw(_("That is not a field on {0}.").format(_(doctype)))

	condition = values.get("condition") or None
	built = _condition(meta, condition) if condition else ""

	name = (values.get("name") or "").strip()
	doc = _ours(name) if name else frappe.new_doc("Notification")

	doc.update({
		MARK: 1,
		"is_standard": 0,
		"enabled": 1 if values.get("enabled", True) else 0,
		"document_type": doctype,
		"channel": CHANNELS.get(values.get("channel") or "email", "Email"),
		"event": WHEN[when],
		"date_changed": date_field or None,
		"days_in_advance": days or 0,
		"subject": subject,
		"message": values.get("message") or subject,
		"condition": built,
		"send_system_notification": 1 if values.get("channel") == "both" else 0,
	})
	doc.set("recipients", [])
	doc.append("recipients", {
		"receiver_by_role": to_role or None,
		"receiver_by_document_field": to_field or None,
	})
	try:
		doc.save(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# `Notification.autoname` is the subject, so two rules that say the
		# same thing collide on the primary key. Frappe's own message names a
		# doctype the customer has never heard of; this names the thing they
		# typed and what to do about it.
		frappe.throw(_("There is already an alert called “{0}”. Give this one a "
		               "different subject.").format(subject))
	return _read(doc)


def set_enabled(name: str, enabled: bool) -> dict:
	"""Turn one rule off without losing what it says.

	The control people actually reach for: a rule that is wrong at month end is
	a rule to pause, not one to rewrite from memory in January.
	"""
	doc = _ours(name)
	doc.db_set("enabled", 1 if enabled else 0, update_modified=False)
	doc.reload()
	return _read(doc)


def remove(name: str) -> dict:
	doc = _ours(name)
	frappe.delete_doc("Notification", doc.name, ignore_permissions=True)
	return {"ok": True, "removed": name}


def _ours(name: str):
	"""One rule, if it is this workspace's to touch."""
	doc = frappe.get_doc("Notification", name)
	if not doc.get(MARK):
		# Either shipped by an app — exported to disk and written back over on
		# the next deploy, so an edit here silently un-happens — or one of the
		# framework's own. Neither is the workspace's.
		frappe.throw(_("That alert was not made here and cannot be changed here."),
		             frappe.PermissionError)
	return doc


def _has(meta, fieldname: str, types) -> bool:
	if not (meta and fieldname):
		return False
	field = meta.get_field(fieldname)
	return bool(field and field.fieldtype in types)


def _condition(meta, condition) -> str:
	"""A field, an operator and a value, as the expression Frappe evaluates.

	Built rather than typed. `Notification.evaluate_alert` runs `condition`
	through `frappe.safe_eval` with the document in scope, so a text box here
	would be a text box that runs code as whoever the rule fires for — and the
	rules people write are "when the status is Overdue", which needs three
	controls rather than a language.
	"""
	condition = frappe.parse_json(condition) if isinstance(condition, str) else condition
	field = (condition.get("field") or "").strip()
	operator = (condition.get("operator") or "is").strip()
	value = condition.get("value")

	if not meta.get_field(field):
		frappe.throw(_("That is not a field to test."))
	if operator not in OPERATORS:
		frappe.throw(_("That is not a test this can make."))

	if operator == "is set":
		return f"doc.{field}"
	if operator == "is not set":
		return f"not doc.{field}"

	symbol = OPERATORS[operator]
	if operator in ("over", "under"):
		try:
			number = float(value)
		except (TypeError, ValueError):
			frappe.throw(_("More than and less than need a number."))
		return f"doc.{field} {symbol} {number}"

	# Quoted with `json.dumps`, so an apostrophe in a status cannot end the
	# string and start an expression.
	return f"doc.{field} {symbol} {frappe.as_json(str(value or ''))}"


def _decompile(condition: str) -> dict | None:
	"""The triple a condition was built from, for the form to reopen on.

	Read back from the string rather than stored beside it, because two places
	holding the same fact is two places to disagree — and the string is the one
	Frappe actually evaluates, so it is the one that is true.
	"""
	text = (condition or "").strip()
	if not text.startswith(("doc.", "not doc.")):
		return None

	if text.startswith("not doc."):
		return {"field": text[len("not doc."):], "operator": "is not set", "value": ""}

	body = text[len("doc."):]
	for word, symbol in OPERATORS.items():
		if not symbol:
			continue
		token = f" {symbol} "
		if token in body:
			field, _sep, value = body.partition(token)
			return {"field": field, "operator": word,
			        "value": frappe.parse_json(value) if value.startswith('"') else value}

	return {"field": body, "operator": "is set", "value": ""}
