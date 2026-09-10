"""What `RECORD()` in a cell resolves to.

`docs/SHEETS.md` §3 got a sheet's numbers *into* a record. This is the other
direction: an estimator's workbook that says `=RECORD("grand_total") * 0.05`
rather than a number somebody read off the quotation and typed in, which was
right on the day and wrong by the third revision.

Two forms, and the second is the one that needs guarding:

    RECORD("grand_total")                       the record the sheet is bound to
    RECORD("Quotation", "SAL-QTN-0005", "qty")  a record it names

The engine runs in the browser and is synchronous, so nothing here is called
from inside a formula. The editor collects every record a workbook names,
resolves them all in one request, and recomputes — see `useRecordFields.js`.
That is also the whole of the freshness story: a cell's stored value is the
last answer, and the workbook asks again when it is opened and when somebody
presses Refresh. `codec.py` explains why it cannot be otherwise — the server
stores what the browser computed and evaluates nothing itself.

Every read goes through `shared/binding.py`, which is the same permission
check the document editor's tokens go through. A formula is a string a person
typed, and a whitelisted endpoint that took a doctype and a fieldname without
asking would be a way to read any column of any table on the site.
"""

import frappe
from frappe import _

from ..shared import binding
from .book import _mine

#: How many records one workbook may name. A sheet reading more records than
#: this is a report, and a report is a screen — `spaceview` already draws one,
#: with paging and a permission model a formula does not have.
MAX_RECORDS = 40


@frappe.whitelist(methods=["POST"])
def record_fields(sheet: str, asks: str | list) -> dict:
	"""Resolve every record this workbook names, in one request.

	One call and not one per cell: a schedule with forty rows of
	`=RECORD(...)` would otherwise be forty round trips on every open, and
	the browser would recompute forty times on the way through.

	The answer is keyed `doctype\x1fname` — a separator no doctype or record id
	can contain — and carries both halves of each field, because a cell wants
	the number and the cell beside it that says what it is wants the text.

	A record this person cannot read comes back missing rather than raising.
	A workbook naming twenty records, one of them a salary somebody may not
	see, should show nineteen answers and one `#N/A`, not refuse to open.
	"""
	_mine(sheet)

	asked = frappe.parse_json(asks) if isinstance(asks, str) else asks
	if not isinstance(asked, list):
		return {"records": {}}

	found = {}
	for one in asked[:MAX_RECORDS]:
		where = _asked(sheet, one)
		if not where:
			continue
		doctype, name, wanted = where
		try:
			answered = binding.resolve(doctype, name, wanted)
		except Exception:
			frappe.clear_last_message()
			continue
		found[f"{doctype}\x1f{name}"] = answered.get("fields") or {}

	return {"records": found, "bound": binding.bound(sheet)}


def _asked(sheet: str, one) -> tuple[str, str, list] | None:
	"""One entry of the ask list, as `(doctype, name, fields)`.

	`{"fields": [...]}` with no record named means the sheet's own binding,
	which is how the one-argument form of `RECORD()` arrives. A workbook bound
	to nothing that uses that form resolves nothing, which is the right answer
	and not an error: the sheet is a template somebody has not started from
	yet.
	"""
	if not isinstance(one, dict):
		return None

	wanted = one.get("fields")
	if not isinstance(wanted, list) or not wanted:
		return None

	doctype = (one.get("doctype") or "").strip()
	name = (one.get("name") or "").strip()
	if not doctype or not name:
		where = binding.bound(sheet)
		doctype, name = where.get("doctype") or "", where.get("name") or ""
	if not doctype or not name:
		return None

	return doctype, name, [str(field) for field in wanted if field]


@frappe.whitelist(methods=["POST"])
def bind_record(sheet: str, doctype: str = "", name: str = "") -> dict:
	"""Bind this workbook to a record, or to a doctype if it is a template.

	Naming a record attaches the workbook to it, through the same two columns
	every attachment in the product uses — so the estimator's sheet shows up
	in the quotation's Attachments, which is where somebody looks for it. A
	doctype alone is a template's binding and is the column
	`shared/binding.py` adds.
	"""
	row = _mine(sheet, "write")

	if name:
		if not doctype:
			frappe.throw(_("Which kind of record?"))
		if not frappe.has_permission(doctype, "read", doc=name):
			raise frappe.PermissionError(_("You cannot read {0}.").format(name))
		row.db_set({"attached_to_doctype": doctype, "attached_to_name": name},
		           update_modified=False)
		binding.bind_template(sheet, "")
	elif doctype:
		binding.bind_template(sheet, doctype)
	else:
		row.db_set({"attached_to_doctype": None, "attached_to_name": None},
		           update_modified=False)
		binding.bind_template(sheet, "")

	return {"sheet": sheet, "bound": binding.bound(sheet)}
