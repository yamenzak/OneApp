"""What a form collected, and how to go and look at it.

`docs/ONEFORMS.md` §14, stage 12. §11 said "responses to this form" was not a
question the database could answer, because a `Web Form` writes an ordinary
document and marks it in no way. That was right about the fact and wrong about
what followed from it: the fix is one column, and a form that cannot say what it
collected is not a form anybody runs a business on.

**The column is `custom_web_form`, on whichever doctype a form is made over.**
Added when the form is made rather than at install, because the set of doctypes
a workspace makes forms over is not knowable until it does. `Custom Field` is
how Frappe means this to be done and it is what every space in this product
already does — `docs/APPS-AND-SPACES.md` is the argument that per-customer schema
is safe, and this is one hidden, read-only, indexed `Data` column.

**Written after `accept`, not through it.** `accept` only sets the fields the
form carries, and this is not one of them — a hidden column a stranger could put
a value in would be a form that let somebody file a submission as another form's.
So it is stamped afterwards, onto the document that came back, which is the same
rule `attaching.py` keeps and for the same reason.

**And the way through is the screen, not a list of our own.** `finding.placed`
already says which space and screen own a doctype, and `narrowing.js` already
says how a URL asks a screen for a filter. So "what came in" is the space's own
list, narrowed — with its views, its actions, its columns and everything else a
list in this product has, none of which a responses table would have had.
"""

import frappe

#: The column, on the target doctype. Named for what it holds rather than for
#: this module: somebody reading a Job Applicant's schema should be able to tell
#: what it is without knowing OneForms exists.
MARK = "custom_web_form"


def ensure(doctype: str) -> None:
	"""The column exists on that doctype. Idempotent.

	Hidden, read-only and indexed. Hidden because it is provenance rather than
	data and nobody filling in a record should meet it; read-only for the same
	reason; indexed because every form's count is a filter on it and a
	workspace with ten forms over one doctype is ten of them.
	"""
	if not doctype or frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": MARK}):
		return

	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": doctype,
		"fieldname": MARK,
		"label": "Web Form",
		"fieldtype": "Data",
		"read_only": 1,
		"hidden": 1,
		"no_copy": 1,
		"search_index": 1,
		# Out of the way of the doctype's own layout: a column nobody is meant
		# to see does not need a place in a section somebody designed.
		"insert_after": "",
	}).insert(ignore_permissions=True)


def stamp(form, made) -> None:
	"""Say which form made this document.

	`made` is what `accept` returned. Never a name from the payload — the same
	rule `attaching.py` keeps, and the reason is the same: a hidden column a
	stranger could set would be a way to file a submission as another form's.
	"""
	if not made or not getattr(made, "name", ""):
		return
	if not frappe.get_meta(made.doctype).has_field(MARK):
		return
	frappe.db.set_value(made.doctype, made.name, MARK, form.name,
	                    update_modified=False)


def how_many(form: str, doctype: str) -> int:
	"""How many documents that form has made.

	`ignore_permissions`, like every other count on the forms list: the reader
	is the workspace admin — `service._admin` ran before this — and the number
	is about the *form*, which is theirs, rather than about the records.
	"""
	if not (form and doctype):
		return 0
	try:
		if not frappe.get_meta(doctype).has_field(MARK):
			return 0
	except Exception:
		return 0
	return frappe.db.count(doctype, {MARK: form})


def where(target: dict, form: str) -> str:
	"""The link to what came in — the space's own screen, narrowed.

	Not a responses table. `finding.placed` says which screen owns the doctype
	and `narrowing.js` says how a URL asks one for a filter, so this is the
	list somebody already knows, with its views, its actions and its columns.
	"""
	space, screen = (target or {}).get("space"), (target or {}).get("screen")
	if not (space and screen and form):
		return ""
	return f"/one/space/{space}?screen={screen}&narrow={MARK}:{form}"
