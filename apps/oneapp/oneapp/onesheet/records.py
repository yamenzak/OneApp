"""What `RECORD()` in a cell resolves to.

`docs/SHEETS.md` §3 got a sheet's numbers *into* a record. This is the other
direction: an estimator's workbook that says `=RECORD("grand_total") * 0.05`
rather than a number somebody read off the quotation and typed in, which was
right on the day and wrong by the third revision.

Three forms, and the middle one is why this module changed:

    RECORD("grand_total")                       the workbook's first record
    RECORD("customer", "credit_limit")          one of its records, by key
    RECORD("Quotation", "SAL-QTN-0005", "qty")  a record it names outright

A workbook reads a *set* of records, the same way a document does — see
`shared/binding.py`. The key is what makes one swappable: an estimator
started from a template fills in the quotation and the formulas do not
change.

The engine runs in the browser and is synchronous, so nothing here is called
from inside a formula. The editor collects every record a workbook names,
resolves them all in one request, and recomputes — see `recordFields.js`.
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
	`sources` comes back beside it so the browser can turn a key into a
	record without a second request.

	A record this person cannot read comes back missing rather than raising.
	A workbook naming twenty records, one of them a salary somebody may not
	see, should show nineteen answers and one `#N/A`, not refuse to open.
	"""
	_mine(sheet)

	asked = frappe.parse_json(asks) if isinstance(asks, str) else asks
	if not isinstance(asked, list):
		asked = []

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

	return {"records": found, "sources": binding.file_sources(sheet)}


def _asked(sheet: str, one) -> tuple[str, str, list] | None:
	"""One entry of the ask list, as `(doctype, name, fields)`.

	Three shapes arrive, matching the three forms of the formula: a record
	named outright, a `source` key, and neither — which means the workbook's
	first record and is how the one-argument form gets here. A workbook whose
	source has no record yet resolves nothing, which is the right answer and
	not an error: it is a template somebody has not started from.
	"""
	if not isinstance(one, dict):
		return None

	wanted = one.get("fields")
	if not isinstance(wanted, list) or not wanted:
		return None

	doctype = (one.get("doctype") or "").strip()
	name = (one.get("name") or "").strip()
	if not doctype or not name:
		where = binding.source(sheet, (one.get("source") or "").strip())
		doctype = where.get("reference_doctype") or ""
		name = where.get("reference_name") or ""
	if not doctype or not name:
		return None

	return doctype, name, [str(field) for field in wanted if field]
