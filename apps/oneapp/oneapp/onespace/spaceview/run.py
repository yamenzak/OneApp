"""Running a declared action, and fetching a linked field's values."""

import frappe
from frappe import _
from .meta import _json_list
from .actions import actions
from .resolve import _resolve
from .links import _link_column, _link_target


@frappe.whitelist(methods=["POST"])
def run_action(space_code: str, screen: str, action: str, name: str | list) -> dict:
	"""Run a declared action against one or more records.

	Three checks, and none of them is "the frontend sent it":

	  * the space resolves for this person, so a space code they do not hold is
	    a `PermissionError` before anything else is read;
	  * the action is one this screen declares, so a method name in the request
	    body reaches nothing that was not shipped as a declaration;
	  * Frappe says they may write the record, which is the same permission the
	    save path asks for.

	The method still runs its own guard — every one of these is a whitelisted
	endpoint that was reachable directly before this existed — so this narrows
	what may be called, it does not become the thing that decides.
	"""
	resolved = _resolve(space_code, screen)
	declared = {row["key"]: row for row in actions(space_code, resolved.get("screen") or screen)}

	chosen = declared.get(action)
	if not chosen or not chosen.get("method"):
		frappe.throw(_("{0} is not an action of this screen.").format(action),
		             frappe.PermissionError)

	names = name if isinstance(name, list) else _json_list(name) or [name]
	doctype = resolved.get("doctype")
	for one in names:
		if doctype and not frappe.has_permission(doctype, "write", doc=one):
			raise frappe.PermissionError(_("You cannot change {0}.").format(one))

	method = frappe.get_attr(chosen["method"])
	results = [method(one) for one in names]
	return {"ok": True, "results": results}


@frappe.whitelist(methods=["GET"])
def fetched(space_code: str, screen: str, fieldname: str, value: str) -> dict:
	"""What a Link's choice fills in elsewhere on this form.

	Frappe's `fetch_from` is `<link fieldname>.<field on the target>`, and the
	server already applies it on save — `Document.set_fetch_from_value` does it
	whatever wrote the record. So this changes no outcome; it changes *when* you
	see it. Without it a form shows an empty Company box, you type into it, and
	the save silently replaces what you typed. The field's note said "From
	Customer" and nothing filled it in.

	Bounded the same way every other read here is, and it has to be: the value
	is a record id from a browser.

	  * the source field must be one this screen offers, and a Link — so a
	    request cannot name any field it likes and read across the site
	  * the doctype read is the source field's own `options`, never a parameter
	  * only fields *on this screen* whose `fetch_from` names that source are
	    answered, so the reply cannot carry a column the screen does not show
	  * `frappe.db.get_value` runs the caller's own permissions, so a link to a
	    record they may not read answers nothing rather than leaking it

	The empty dict is a real answer: a Link with nothing fetching from it is
	most Links.
	"""
	resolved = _resolve(space_code, screen)
	column = _link_column(resolved, fieldname)

	if column.get("fieldtype") not in ("Link", "Dynamic Link"):
		frappe.throw(_("{0} is not a link.").format(fieldname), frappe.PermissionError)

	target = _link_target(resolved, column)
	if not target or not value or not frappe.db.exists("DocType", target):
		return {}

	prefix = f"{fieldname}."
	wanted = {}
	for one in resolved.get("all_columns") or resolved.get("columns") or []:
		source = one.get("fetch_from") or ""
		if source.startswith(prefix):
			wanted[one["fieldname"]] = {
				"field": source[len(prefix):],
				# The half that decides whether this overwrites what somebody
				# typed. Frappe's own rule: `fetch_if_empty` means fill a blank
				# and leave anything else alone.
				"only_if_empty": bool(one.get("fetch_if_empty")),
			}

	if not wanted:
		return {}

	# One read for every field, rather than one read per field.
	fields = sorted({spec["field"] for spec in wanted.values()})
	row = frappe.db.get_value(target, value, fields, as_dict=True) or {}

	return {
		fieldname: {"value": row.get(spec["field"]), "only_if_empty": spec["only_if_empty"]}
		for fieldname, spec in wanted.items()
		if spec["field"] in row
	}
