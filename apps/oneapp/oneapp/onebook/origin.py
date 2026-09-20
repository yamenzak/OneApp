"""Which space raised this document, read off what it already points at.

OneBook's lists are the one place in the product where four spaces' work lands
in the same table. A bookkeeper opening **Invoices** is looking at invoices they
raised, invoices OneProject raised against a job, and — once a subcontractor is
involved — bills against the same job; **Journal entries** is mostly theirs and
occasionally a payroll run's. Their first question about any row is *whose is
this*, because the answer decides who they go and ask about it.

ERPNext knows, and puts the answer in a different place each time:

* a Sales Invoice carries `project`, or its items do;
* a payroll bank entry is a Journal Entry with a `Journal Entry Account` row
  whose `reference_type` is `Payroll Entry`;
* a payment settling an expense claim carries a `Payment Entry Reference` row
  naming the claim.

Three joins, none of them a column, none of them sortable, every one of them
needing the record open. So this writes the answer onto the document as
`custom_origin` on save — a **cache of a join**, which is the only honest way to
describe it and the reason it is read-only everywhere: it is not a field
somebody sets, it is a field somebody would otherwise have to work out.

The value is a space id from `oneapp/catalogue.py` and nothing else, so a
screen grouping by it is grouping by the same word the rail uses. Blank means
nobody else raised it, which is the common case and is deliberately not spelt
"OneBook": a blank cell reads as "ours" and a filled one reads as "theirs",
which is the distinction being drawn.

**Not built: the CRM lane.** A Sales Invoice made from a Sales Order made from
a Quotation made from an Opportunity is OneCRM's, and finding that out is three
joins up a chain on every save of every invoice. It would be right and it would
be slow, and the honest place for it is the nightly pass that does not exist
yet rather than a `validate` hook. Until then those invoices read as raised
here, which is wrong in a way somebody can see rather than wrong in a way that
costs a page load.
"""

import frappe

from oneapp import catalogue

#: The four documents OneBook stamps, in one place, so the hook list, the
#: manifest's custom fields and the backfill below cannot disagree about which
#: of them wear this. `spaces/onebook.py` declares the same set under the same
#: name and `tests/test_onebook_origin.py` holds the two together.
POSTED_INTO = ("Sales Invoice", "Purchase Invoice", "Payment Entry",
               "Journal Entry")

#: The field, on all four doctypes. Declared in
#: `oneapp_control/spaces/onebook.py` and applied by the tenant seeder, which
#: is why every reader below asks `meta.has_field` first.
FIELD = "custom_origin"

#: Where a document can have come from. Read off the catalogue rather than
#: written here, so a space that is renamed cannot leave this stamping a word
#: nothing else uses — `tests/test_onebook_origin.py` holds both ends.
PEOPLE = catalogue.BY_ID["onehr"]["id"]
PROJECTS = catalogue.BY_ID["oneproject"]["id"]

#: What OneHR raises that ends up as money. Every one of these is a doctype
#: HRMS writes and OneBook only reads — `spaces/onebook.py` says so in the
#: grants — so a reference to one of them is proof the row came from there.
#:
#: `Payroll Entry` and `Salary Slip` are the run and the slip; the other four
#: are the ways an individual is owed something outside the run.
FROM_PEOPLE = frozenset({
	"Payroll Entry",
	"Salary Slip",
	"Expense Claim",
	"Employee Advance",
	"Gratuity",
	"Employee Benefit Claim",
})


def _wears_the_field(doc) -> bool:
	"""Whether this document has the column yet.

	Custom fields are applied by the tenant seeder rather than by migrate, so
	between installing the app and seeding the space every one of these
	doctypes exists without it. A controller that assumed otherwise would fail
	every save on a half-built site.
	"""
	return bool(doc.meta.has_field(FIELD))


def _project_on(doc) -> bool:
	"""Whether this document belongs to a project, on itself or on a line.

	Both, because ERPNext allows either: a whole invoice against one job sets
	the header field, and an invoice mixing two jobs sets it per row. An
	invoice with a project on any line is a project's invoice.
	"""
	if (doc.get("project") or "").strip():
		return True
	return any((row.get("project") or "").strip()
	           for row in doc.get("items") or [])


def _referenced(doc, table: str, field: str) -> set[str]:
	"""Every doctype a child table points at."""
	return {(row.get(field) or "").strip()
	        for row in doc.get(table) or []} - {""}


def _origin_of(doc) -> str:
	"""The space that raised this, or an empty string for "somebody here".

	Ordered people-first on purpose. A payroll bank entry can carry a cost
	centre that belongs to a project, and an invoice for a job can be settled
	by a payment that also clears a staff advance — where both are true the
	useful answer is the one that names a document somebody else approved,
	because that is the one with a person at the end of it.
	"""
	kind = doc.doctype

	if kind == "Journal Entry":
		if _referenced(doc, "accounts", "reference_type") & FROM_PEOPLE:
			return PEOPLE
		return ""

	if kind == "Payment Entry":
		if _referenced(doc, "references", "reference_doctype") & FROM_PEOPLE:
			return PEOPLE
		return PROJECTS if _project_on(doc) else ""

	# The two invoices, which have no reference table worth reading: a payroll
	# run does not raise an invoice, so the only question is whose job it is.
	return PROJECTS if _project_on(doc) else ""


def stamp(doc, method=None) -> None:
	"""`validate` on the four documents OneBook lists.

	Rewritten on every save rather than set once, because the thing it is
	derived from is editable until the document is submitted: an invoice given
	a project on the second save is a project's invoice from that save on, and
	one whose project is cleared goes back to being ours.
	"""
	if not _wears_the_field(doc):
		return
	doc.set(FIELD, _origin_of(doc))


def rewrite(doctype: str) -> int:
	"""Re-derive the origin for every row of one doctype, and say how many moved.

	For the documents already posted when a workspace was given this space,
	which is all of them on any site that had ERPNext before it had OneBook —
	the dev fixture included, which is where this is called from.

	`db_set` with no version row and no hooks: this writes a cache of something
	that has not changed, and a row of history per document saying so would be
	noise on a hundred submitted documents.
	"""
	moved = 0
	for name in frappe.get_all(doctype, pluck="name"):
		doc = frappe.get_doc(doctype, name)
		if not _wears_the_field(doc):
			return 0
		found = _origin_of(doc)
		if (doc.get(FIELD) or "") != found:
			doc.db_set(FIELD, found, update_modified=False)
			moved += 1
	return moved


def rewrite_all() -> int:
	"""All four, for a workspace that has just been given the space."""
	return sum(rewrite(doctype) for doctype in POSTED_INTO)


# POST, because it writes. A GET-able endpoint that writes has its write rolled
# back at the end of the request and still answers 200 —
# `tests/test_endpoints.py` is the guard that says so.
@frappe.whitelist(methods=["POST"])
def restamp(doctype: str) -> int:
	"""`rewrite`, over the wire, for whoever administers the workspace."""
	frappe.only_for("System Manager")
	if doctype not in POSTED_INTO:
		frappe.throw(frappe._("{0} is not a document OneBook stamps.").format(doctype))
	return rewrite(doctype)

