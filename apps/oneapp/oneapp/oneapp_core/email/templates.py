"""A message written once and sent often.

The last row still open in `docs/EMAIL.md` §6, and the smallest of them: a
shared address answers the same five questions all week — where the order is,
what the lead time is, which documents we need — and typing the answer again
each time is both slow and inconsistent, which is the part customers notice.

`Email Template` is Frappe's own doctype and its own Jinja rendering, so this is
a gate and a shape rather than a feature:

* **Ours are marked.** ERPNext and HRMS ship six templates between them on every
  site — "Exit Questionnaire Notification", "Interview Reminder" — and a
  workspace's own list is not where those belong. Same field and same argument
  as `alerts.py`: `custom_onespace`, because `is_standard` says something else.
* **A template may name the record it is for.** One written for a Quotation
  offers itself when somebody writes from a Quotation and stays out of the way
  otherwise. The doctype has to be one this workspace was granted, the same
  scope `alerts`, `naming` and `printing` use.
* **Rendering happens here, against a document the caller may read.** The body
  is Jinja with `doc` in scope, which is the framework's own contract — and the
  reason writing one is an admin's job while using one is anybody's.
"""

import frappe
from frappe import _

from oneapp.oneapp_core import sync


#: The mark on a template this workspace wrote. See `alerts.MARK`.
MARK = "custom_onespace"

OURS = {MARK: 1}


def listing(for_doctype: str = "") -> list[dict]:
	"""Every template this workspace wrote, newest first.

	`for_doctype` narrows to the ones offered where somebody is writing: a
	template for a Quotation and the ones that name no record at all.
	"""
	filters = dict(OURS)
	if for_doctype:
		filters["reference_doctype"] = ("in", ["", for_doctype])

	rows = frappe.get_all(
		"Email Template",
		filters=filters,
		fields=["name", "subject", "reference_doctype", "response", "modified"],
		order_by="modified desc",
	)
	return [
		{
			"name": row.name,
			"subject": row.subject or "",
			"doctype": row.reference_doctype or "",
			"body": row.response or "",
			# A template on a record the workspace no longer has is one it
			# cannot use. Shown and flagged, the same way an orphaned alert is:
			# hiding it would leave something nobody can find to delete.
			"orphaned": bool(row.reference_doctype)
			and row.reference_doctype not in sync.granted_doctypes(),
		}
		for row in rows
	]


def save(values: str | dict) -> dict:
	"""Write one template, new or edited."""
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	title = (values.get("title") or "").strip()
	if not title:
		frappe.throw(_("Give the template a name."))

	subject = (values.get("subject") or "").strip()
	if not subject:
		frappe.throw(_("Give the template a subject line."))

	body = values.get("body") or ""
	if not (body or "").strip():
		frappe.throw(_("A template with nothing in it is not a template."))

	doctype = (values.get("doctype") or "").strip()
	if doctype and doctype not in sync.granted_doctypes():
		frappe.throw(_("That is not one of this workspace's records."),
		             frappe.PermissionError)

	name = (values.get("name") or "").strip()
	doc = _ours(name) if name else frappe.new_doc("Email Template")
	doc.update(
		{
			"subject": subject,
			"response": body,
			"reference_doctype": doctype or None,
			# Frappe renders `response` unless `use_html` is set, in which case
			# it renders `response_html` and ignores this one. The composer
			# writes HTML into `response` either way, so the switch stays off
			# and there is one field holding the body.
			"use_html": 0,
			MARK: 1,
		}
	)

	if not name:
		# `Email Template` is named by prompt, so the name *is* the title and a
		# rename is a rename. Which is the honest shape: two templates called
		# "Delivery update" would be two rows nobody could tell apart in a
		# picker that shows their names.
		doc.name = title
		doc.insert(ignore_permissions=True)
	elif doc.name != title:
		frappe.rename_doc("Email Template", doc.name, title, force=True)
		doc = frappe.get_doc("Email Template", title)
		doc.save(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	return {"ok": True, "name": doc.name}


def remove(name: str) -> dict:
	"""Delete a template. The messages written from it are not touched."""
	doc = _ours(name)
	frappe.delete_doc("Email Template", doc.name, ignore_permissions=True)
	return {"ok": True, "removed": name}


def render(name: str, doctype: str = "", docname: str = "") -> dict:
	"""A template, filled in — the subject and the body, ready to edit.

	Rendered against a document only where one is named *and* the caller may
	read it. `get_email_template` is Frappe's own, which is the point: the Jinja
	contract, the escaping and the `doc` in scope are all the framework's, and a
	second renderer here would be a second set of rules to keep in step.
	"""
	template = _ours(name)

	doc = None
	if doctype and docname:
		doc = frappe.get_doc(doctype, docname)
		# The gate. A template is Jinja with the document in scope, so rendering
		# one against a record somebody cannot read would hand them its fields.
		doc.check_permission("read")

	if doc is None:
		# Nothing to fill in from, so the template is offered as written —
		# placeholders and all, which is better than a body full of "None".
		return {"subject": template.subject or "", "message": template.response or ""}

	# Imported here rather than at the top: this is the only path that needs it,
	# and it is the framework's own renderer being borrowed rather than a
	# dependency this module has.
	from frappe.email.doctype.email_template.email_template import get_email_template

	filled = get_email_template(template.name, doc.as_dict())
	return {"subject": filled.get("subject") or "", "message": filled.get("message") or ""}


def _ours(name: str):
	"""One template this workspace wrote, or a refusal.

	By the mark, not by the name: the six ERPNext and HRMS ship are on the same
	site, and a settings screen that could edit those could edit the reminder
	somebody's leave approval depends on.
	"""
	if not name or not frappe.db.exists("Email Template", {"name": name, **OURS}):
		frappe.throw(_("That is not one of this workspace's templates."),
		             frappe.PermissionError)
	return frappe.get_doc("Email Template", name)
