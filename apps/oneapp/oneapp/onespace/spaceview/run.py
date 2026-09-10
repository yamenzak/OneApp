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


# How many child rows one derive may carry. A grid past this is a document
# being imported rather than typed, and the import path is where that belongs.
MAX_DERIVE_ROWS = 200


@frappe.whitelist(methods=["POST"])
def derive(space_code: str, screen: str, values: str | dict,
           name: str | None = None) -> dict:
	"""What the doctype makes of these values, without saving them.

	A quotation line is width × height × qty × rate, and the grid edited
	values and derived nothing: the amount appeared after a save and was blank
	while it was being typed.

	Frappe puts that arithmetic in two places. A client script recalculates in
	the browser on every keystroke, and the controller's own `validate`
	recomputes it as the truth before the row is written. This product has no
	client-script layer at all — there is no `/app` here — so it had neither
	half in the browser and only the second on save.

	So the browser asks the server what the document would say. The document is
	built in memory, the controller's `validate` runs over it, and what came
	back different is answered. Deliberately not a formula engine of our own:
	re-implementing ERPNext's rounding in JavaScript is a second answer to the
	same question, and only one of the two would be the one the save agrees
	with.

	**Nothing is written.** A savepoint is taken and rolled back whatever
	happens, because a controller's `validate` is allowed to touch other rows.
	Most do not; some do; "most" is not a guarantee to build a read-only
	endpoint on.

	**A `validate` that throws is an ordinary answer**, not an error. Half a
	line is not a line — a mandatory field nobody has filled in makes the
	document invalid and says nothing about the arithmetic — and the reader is
	still typing. The answer is then what they typed, and the save is where
	they will be told.
	"""
	from .records import _child_changes, _writable

	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		return {"values": {}, "children": {}}

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		return {"values": {}, "children": {}}

	# The same allowlist a save goes through, and the same permission. A
	# derive is a read of what the framework would compute, but it is a read
	# performed by building the document — so it may only be asked of a record
	# this person could have saved.
	if name:
		if not frappe.has_permission(doctype, "write", doc=name):
			raise frappe.PermissionError(_("You cannot change {0}.").format(name))
	elif not frappe.has_permission(doctype, "create"):
		raise frappe.PermissionError(_("You cannot create one of these."))

	allowed = _writable(resolved)
	changes = {k: v for k, v in values.items() if k in allowed}
	changes.update(_child_changes(resolved, values))
	if _too_many_rows(changes):
		frappe.throw(_("That is more rows than one line can be worked out over."))

	frappe.db.savepoint("derive")
	try:
		doc = frappe.get_doc(doctype, name) if name else frappe.new_doc(doctype)
		doc.update(changes)
		doc.run_method("validate")
	except Exception:
		# Rolled back and answered empty. What the reader typed stands, which
		# is the right answer for a document that is not finished yet.
		frappe.db.rollback(save_point="derive")
		frappe.clear_last_message()
		return {"values": {}, "children": {}}

	answered = _derived(resolved, doc, values)
	frappe.db.rollback(save_point="derive")
	return answered


def _too_many_rows(changes: dict) -> bool:
	return any(isinstance(rows, list) and len(rows) > MAX_DERIVE_ROWS
	           for rows in changes.values())


def _derived(resolved: dict, doc, asked: dict) -> dict:
	"""What the document says that the browser did not already have.

	Only the differences, so a form patches the two cells that moved rather
	than being rewritten under a cursor that is still in one of them.

	Read off `all_columns` rather than off the document: a derived value is
	usually a read-only field, so the writable allowlist is exactly the wrong
	list to read back through.
	"""
	columns = resolved.get("all_columns") or []
	parent = {}
	for column in columns:
		fieldname = column["fieldname"]
		if column.get("child"):
			continue
		now = doc.get(fieldname)
		if not _same(asked.get(fieldname), now):
			parent[fieldname] = now

	children = {}
	for column in columns:
		if not column.get("child"):
			continue
		fieldname = column["fieldname"]
		typed = asked.get(fieldname)
		if not isinstance(typed, list):
			continue
		offered = [c["fieldname"] for c in column["child"]["fields"]]
		rows = []
		for at, row in enumerate(doc.get(fieldname) or []):
			was = typed[at] if at < len(typed) and isinstance(typed[at], dict) else {}
			moved = {one: row.get(one) for one in offered
			         if not _same(was.get(one), row.get(one))}
			# `idx` always, because it is how the browser lines a row up with
			# the one it sent: the controller may reorder or renumber them.
			rows.append({**moved, "idx": row.get("idx")})
		if any(len(row) > 1 for row in rows):
			children[fieldname] = rows

	return {"values": parent, "children": children}


def _same(one, other) -> bool:
	"""Whether two values are the same to a form.

	`4` and `4.0` and `"4"` are one number that has been through JSON, a
	float field and a browser. Compared as text with the float flattened,
	because a diff that reports every untouched number is a diff that
	rewrites the whole form on every keystroke.
	"""
	if one is None or one == "":
		one = ""
	if other is None or other == "":
		other = ""
	if isinstance(one, (int, float)) or isinstance(other, (int, float)):
		try:
			return abs(float(one or 0) - float(other or 0)) < 1e-9
		except (TypeError, ValueError):
			pass
	return str(one) == str(other)
