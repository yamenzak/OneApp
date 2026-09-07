"""What a model wrote, and where.

A row per value — `Sales Invoice` / `ACC-SINV-0001` / `remarks` — so a reader
can see which words on a document were not typed by anybody. A row rather than
a field on the record, because most records are not ours: a workspace's
documents are Quotations and Sales Invoices, and marking a field on one would
mean a custom field on every doctype an app might ever touch. It is the shape
`Document Follow` and `Tag Link` already use, and it covers a child row too,
since a child row has a name of its own.

`file_url` on a `File` is how a generated image or a piece of audio is marked,
so one mechanism carries fields and media rather than two.

Three things beyond the write, and each of them is why this is a module rather
than two lines at the call site:

* **A mark is not the whole answer.** It carries the feature, the model and the
  person who asked, because "AI wrote this" is an icon and "the workspace
  assistant wrote this with <model>, at Ada's asking" is an answer to the
  question the icon provokes. Same row, no reason to store less.
* **A mark expires when a person rewrites the value.** Frappe hands us the
  document as it was on `on_update`, so the fields that actually changed are
  knowable, and the ones a person changed stop being the model's. Without this
  the icon is a lie within a month and then noise.
* **A mark goes when its document goes.** Frappe does not cascade on a name in
  a Data field, and a later document that reuses the name would inherit marks
  it never earned.
"""

import frappe

DOCTYPE = "AI Written Value"

#: Set while an AI write is being saved, so `forget_changed` knows not to drop
#: the mark it has just been given. Without it the save that writes the value
#: and the mark would immediately clear the mark: the value did change, and
#: nothing else distinguishes that from a person changing it.
WRITING = "oneapp_ai_writing"

#: Cache of the doctypes that have a mark on them anywhere. `forget_changed` is
#: hooked on `*`, so without this every save on the site pays a query to learn
#: that nothing on that doctype was ever marked — and on most sites nothing ever
#: is. Rebuilt on the first save after a mark is written or dropped.
MARKED_DOCTYPES = "oneapp_ai_marked_doctypes"


def _marked_doctypes() -> set[str]:
	cached = frappe.cache.get_value(MARKED_DOCTYPES)
	if cached is None:
		cached = frappe.get_all(
			DOCTYPE, pluck="reference_doctype", distinct=True, ignore_permissions=True
		)
		frappe.cache.set_value(MARKED_DOCTYPES, cached)
	return set(cached)


def _forget_which_doctypes_are_marked() -> None:
	frappe.cache.delete_value(MARKED_DOCTYPES)


def mark(doctype: str, name: str, fieldname: str, *, feature: str = "",
         model: str = "", asked_by: str = "") -> None:
	"""Say that a model wrote this value.

	Idempotent on the triple: a value written twice is one fact, so the second
	write updates the first rather than leaving two rows to disagree.
	"""
	if not (doctype and name and fieldname):
		return

	values = {
		"reference_doctype": doctype,
		"reference_name": name,
		"fieldname": fieldname,
		"feature_key": feature or "",
		"model_key": model or "",
		"asked_by": asked_by or frappe.session.user,
	}

	existing = frappe.db.exists(DOCTYPE, {
		"reference_doctype": doctype,
		"reference_name": name,
		"fieldname": fieldname,
	})
	if existing:
		frappe.db.set_value(DOCTYPE, existing, values, update_modified=True)
		return

	frappe.get_doc({"doctype": DOCTYPE, **values}).insert(ignore_permissions=True)
	_forget_which_doctypes_are_marked()


def forget(doctype: str, name: str, fieldname: str = "") -> None:
	"""Drop the mark on one field, or on every field of one document."""
	filters = {"reference_doctype": doctype, "reference_name": name}
	if fieldname:
		filters["fieldname"] = fieldname
	for row in frappe.get_all(DOCTYPE, filters=filters, pluck="name",
	                          ignore_permissions=True):
		frappe.delete_doc(DOCTYPE, row, force=True, ignore_permissions=True)
	_forget_which_doctypes_are_marked()


def written(doctype: str, name: str) -> dict[str, dict]:
	"""Every marked field on one document, by fieldname.

	One query. The record endpoint calls this per record it serves, and a
	document with no marks costs that one query and nothing else.
	"""
	if not (doctype and name):
		return {}

	# Permissions ignored on purpose: the doctype itself is readable by nobody,
	# and the caller has already decided this reader may see this record. See
	# the perms block in `scripts/doctypes/ai.py`.
	rows = frappe.get_all(
		DOCTYPE,
		filters={"reference_doctype": doctype, "reference_name": name},
		fields=["fieldname", "feature_key", "model_key", "asked_by", "creation"],
		ignore_permissions=True,
	)
	if not rows:
		return {}

	# The stored key is `google-ai-studio:flash`; what a reader is owed is
	# "Flash". The catalogue is already cached on this site, so naming the model
	# properly costs a dict lookup and the tooltip stops reading like a log line.
	from oneapp.oneapp_core.ai.settings import catalogue

	named = {m["model_key"]: m["display_name"] for m in catalogue()}

	return {
		row.fieldname: {
			"feature": row.feature_key or "",
			"model": named.get(row.model_key or "", row.model_key or ""),
			"by": row.asked_by or "",
			"when": row.creation,
		}
		for row in rows
	}


#: Doctypes nothing marks, skipped before the query rather than after it.
#:
#: `forget_changed` is hooked on `*` — the mark is about a value on any doctype,
#: and a workspace's records belong to apps we do not own, so there is no list
#: to hook instead. That means it runs on every save on the site, and these are
#: the ones that save constantly and can never carry a mark: the framework's own
#: logs, its version and queue rows, and this doctype itself. Skipping them is a
#: cost decision and not a correctness one — a mark on any of them would be a
#: mark nothing writes and nothing reads.
NEVER_MARKED = frozenset({
	DOCTYPE,
	"Version",
	"Comment",
	"Activity Log",
	"Access Log",
	"Error Log",
	"Route History",
	"Notification Log",
	"Email Queue",
	"Email Queue Recipient",
	"Scheduled Job Log",
	"Prepared Report",
	"View Log",
})


def forget_changed(doc, method=None) -> None:
	"""A field a person rewrote is not the model's any more.

	`get_doc_before_save` is what the framework already holds for its own
	Version rows, so this costs a comparison rather than a read. Only the
	fields that actually changed lose their mark: a save that touched one field
	must not clear the marks on the other nine.
	"""
	if doc.doctype in NEVER_MARKED or frappe.flags.get(WRITING):
		return
	if doc.doctype not in _marked_doctypes():
		return

	before = doc.get_doc_before_save()
	if not before:
		return

	marked = frappe.get_all(
		DOCTYPE,
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
		fields=["name", "fieldname"],
		ignore_permissions=True,
	)
	for row in marked:
		if doc.get(row.fieldname) != before.get(row.fieldname):
			frappe.delete_doc(DOCTYPE, row.name, force=True, ignore_permissions=True)
			_forget_which_doctypes_are_marked()


def forget_deleted(doc, method=None) -> None:
	"""The marks go with the document.

	A Data field is not a Link, so nothing cascades — and a document that later
	reuses the name would inherit marks it never earned.
	"""
	if doc.doctype in NEVER_MARKED or doc.doctype not in _marked_doctypes():
		return
	forget(doc.doctype, doc.name)
