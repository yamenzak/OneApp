"""The record a document or a workbook is written about.

A quotation's covering letter is prose with the quotation's numbers in it, and
an estimator's workbook is arithmetic with the job's dimensions at the top of
it. Both had to be typed twice, and the second copy went stale the moment
somebody changed the record.

So a file may be **bound** to a record, and both editors may then name its
fields: the document has an inline token that renders the field, the workbook
has a `RECORD()` formula that returns it. One module because it is one
question — what does this record say, and may this person be told — and two
copies of the answer would be two permission checks to keep in step.

**A document's binding is its attachment.** `File.attached_to_doctype` and
`attached_to_name` already exist, `docs.make` already sets them, and a
document written about a quotation is a document attached to that quotation:
one concept, and the record's Attachments panel is where somebody looks for it
anyway. Nothing new is stored for a bound document.

**A template's binding is a doctype with no record**, which is the one thing
attachment cannot express — a template is for *any* quotation. That is
`custom_bound_doctype`, the one column this adds, and it is what makes the
picker appear when somebody starts a document from that template.

**Freshness.** Nothing here is pushed. A value is read when the file is opened
and when somebody asks again, and what is stored in the file is the last
answer — which for a workbook it has to be, because the formula engine runs in
the browser and the server stores what it computed (`docs/SHEETS.md` §1). What
follows is that a bound file is only as fresh as its last read, and every
surface that shows one says when that was.
"""

import frappe
from frappe import _

#: The doctype a *template* is for. On `File` with the other columns this
#: product adds there — see `onestorage/kinds.py` — because a template is a
#: file and a binding is a fact about that file.
BOUND_FIELD = "custom_bound_doctype"

#: What a token or a formula may never name. Two different reasons in one
#: tuple: the first row is stored ciphertext or a blob that has no text to
#: render, and the second is layout — a Section Break has no value at all.
#:
#: `Password` is the one that matters. Everything else here would render as
#: nonsense; that one would render as a secret, in a document somebody prints.
NEVER_BOUND = (
	"Password", "Signature", "Attach", "Attach Image", "Geolocation",
	"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold",
	"Heading", "Table", "Table MultiSelect",
)

#: How many fields one call may resolve. A document with more tokens than this
#: is generated rather than written, and the generator is `print_format`.
MAX_FIELDS = 60


# --------------------------------------------------------------------------- #
# What is bound to what
# --------------------------------------------------------------------------- #

def bound(file: str) -> dict:
	"""The record this file is written about, or the doctype it is for.

	Three answers and they are different things:

	    {}                                 nothing is bound
	    {"doctype": …}                     a template, for any of those
	    {"doctype": …, "name": …}          a file about one record

	Read off the `File` row and never off the body: the body is a blob a
	browser wrote, and a browser is not where a permission boundary goes.
	"""
	row = frappe.db.get_value(
		"File", file,
		["attached_to_doctype", "attached_to_name", BOUND_FIELD],
		as_dict=True,
	) or {}

	if row.get("attached_to_doctype") and row.get("attached_to_name"):
		return {"doctype": row["attached_to_doctype"], "name": row["attached_to_name"]}
	if row.get(BOUND_FIELD):
		return {"doctype": row[BOUND_FIELD]}
	return {}


def bind_template(file: str, doctype: str) -> None:
	"""Say which doctype a template is for, or clear it with an empty string.

	Only a template. A binding on a document is its attachment, and writing
	this column on one would give it a second answer that disagrees.
	"""
	from ..onestorage import kinds

	if doctype and not frappe.db.exists("DocType", doctype):
		frappe.throw(_("There is nothing called {0} here.").format(doctype))
	if doctype and not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(_("You cannot read {0}.").format(doctype))

	frappe.db.set_value("File", file, BOUND_FIELD, doctype or None,
	                    update_modified=False)
	# A file bound to a doctype is a template by construction: the binding is
	# only ever read when somebody starts something from it.
	if doctype:
		frappe.db.set_value("File", file, kinds.TEMPLATE_FIELD, 1,
		                    update_modified=False)


# --------------------------------------------------------------------------- #
# What a record will answer
# --------------------------------------------------------------------------- #

def offer(doctype: str) -> list[dict]:
	"""The fields a token or a formula may name, in the doctype's own order.

	The doctype's own metadata, filtered by `NEVER_BOUND` and by permlevel:
	a field somebody cannot read on the record is not a field they may put in
	a document, and finding that out at render time would mean a document that
	looks complete to its author and blank to everybody else.

	`name` is first and is not a DocField, which is why it is described here.
	It is also the field most templates want — a covering letter says which
	quotation it is about before it says anything else.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(_("You cannot read {0}.").format(doctype))

	meta = frappe.get_meta(doctype)
	allowed = _readable_levels(doctype)

	out = [{"fieldname": "name", "label": _("ID"), "fieldtype": "Data"}]
	for field in meta.fields:
		if field.fieldtype in NEVER_BOUND or not field.fieldname:
			continue
		if (field.permlevel or 0) not in allowed:
			continue
		out.append({
			"fieldname": field.fieldname,
			"label": _(field.label or field.fieldname),
			"fieldtype": field.fieldtype,
		})
	return out


def _readable_levels(doctype: str) -> set[int]:
	"""The permlevels this person may read on this doctype.

	Frappe's own answer, asked the way `spaceview` asks it: a role that grants
	`read` at a level is a role that may see every field at that level.
	"""
	mine = set(frappe.get_roles())
	return {
		int(perm.permlevel or 0)
		for perm in frappe.get_meta(doctype).permissions
		if perm.read and perm.role in mine
	}


@frappe.whitelist(methods=["GET"])
def fields(doctype: str) -> list[dict]:
	"""`offer`, as an endpoint. What the token picker and the formula hint read."""
	return offer(doctype)


# --------------------------------------------------------------------------- #
# What the record says now
# --------------------------------------------------------------------------- #

#: How many records the "which one?" picker offers at a time. A person is
#: choosing the quotation they have in mind, not browsing — the list screen is
#: where browsing happens, with paging and saved views.
PICKER_ROWS = 20


@frappe.whitelist(methods=["GET"])
def records(doctype: str, query: str = "") -> list[dict]:
	"""Which record, for the picker that appears when a bound template is used.

	`get_list` and not `get_all`, so this is the caller's own permissions —
	including User Permissions, which is the difference between a picker that
	offers the three projects somebody works on and one that offers all four
	hundred. A doctype they cannot read answers nothing rather than raising:
	a template for a record kind somebody has no business seeing should be a
	picker with nothing in it, not a page that fails to open.

	Searched on the id and on the doctype's own title field, which is what
	somebody has in mind — `SAL-QTN-2025-00005` is not what anybody remembers
	about the Halloway job.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []
	if not frappe.has_permission(doctype, "read"):
		return []

	meta = frappe.get_meta(doctype)
	title = meta.get_title_field() if meta.title_field else ""
	fields = ["name"] + ([title] if title and title != "name" else [])

	asked = (query or "").strip()[:140]
	or_filters = {}
	if asked:
		or_filters = {one: ["like", f"%{asked}%"] for one in fields}

	rows = frappe.get_list(
		doctype, fields=fields, or_filters=or_filters,
		order_by="modified desc", limit_page_length=PICKER_ROWS,
	)
	return [{"name": row["name"],
	         "title": (row.get(title) if title else "") or row["name"]}
	        for row in rows]


@frappe.whitelist(methods=["GET"])
def resolve(doctype: str, name: str, wanted: str | list | None = None) -> dict:
	"""What those fields say, as both a number and as text.

	Two answers per field because two callers want different ones. A workbook
	wants `144235.0`, because a cell that says `AED 144,235.00` cannot be added
	up. A document wants `AED 144,235.00`, because prose that says `144235.0`
	reads as a bug. Formatting a currency needs the record in hand anyway — the
	currency is a field on it — so both come back from one read.

	Bounded three ways: the person must be able to read the record, the fields
	must be ones `offer` would have offered, and there is a cap on how many.
	The middle one is the one that matters — without it this is a whitelisted
	read of any column of any doctype, permlevel and all.
	"""
	if not frappe.has_permission(doctype, "read", doc=name):
		raise frappe.PermissionError(_("You cannot read {0}.").format(name))

	asked = _asked(wanted)
	offered = {row["fieldname"]: row for row in offer(doctype)}
	chosen = [one for one in asked if one in offered][:MAX_FIELDS]
	if not chosen:
		return {"doctype": doctype, "name": name, "fields": {}}

	doc = frappe.get_doc(doctype, name)
	return {
		"doctype": doctype,
		"name": name,
		"fields": {one: _said(doc, offered[one]) for one in chosen},
	}


def _asked(wanted) -> list[str]:
	"""The field list, however it arrived — JSON from a GET, or a real list."""
	if isinstance(wanted, str):
		wanted = frappe.parse_json(wanted) if wanted.strip().startswith("[") else \
			[one.strip() for one in wanted.split(",")]
	if not isinstance(wanted, list):
		return []
	return [str(one) for one in wanted if one]


def _said(doc, column: dict) -> dict:
	"""One field, as a value and as the text a reader should see.

	`frappe.format_value` is the framework's own formatter and is what a print
	format uses, so a bound document and a printed one agree — which they have
	to, a covering letter being printed beside the quotation it describes.
	"""
	fieldname = column["fieldname"]
	value = doc.get(fieldname)
	try:
		text = frappe.format_value(value, column, doc=doc)
	except Exception:
		# A formatter that throws is a field this cannot render, not a request
		# that failed: the token shows the raw value and the document is still
		# readable. `format_value` reaches for currencies and link titles.
		text = "" if value is None else str(value)
	return {"value": value, "text": text}
