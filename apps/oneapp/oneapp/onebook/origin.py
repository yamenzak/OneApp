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
#:
#: OneHR was the other one. A payroll run, a claim and a staff advance all end
#: up as money and all used to be stamped as having come from there; the space
#: has moved to the desk, so there is nowhere for that word to point and the
#: rows it would have marked read as this workspace's own.
PROJECTS = catalogue.BY_ID["oneproject"]["id"]


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


def _origin_of(doc) -> str:
	"""The space that raised this, or an empty string for "somebody here".

	One space can raise a document from outside OneBook, so there is one
	question left: does it belong to a job. A journal entry never does — it is
	somebody here moving money between accounts — so it is answered first and
	separately rather than by looking for a project it cannot carry.
	"""
	if doc.doctype == "Journal Entry":
		return ""

	# Everything else: whose job is it. A payroll run does not raise an
	# invoice, and a payment that clears a staff advance is now just a payment.
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

