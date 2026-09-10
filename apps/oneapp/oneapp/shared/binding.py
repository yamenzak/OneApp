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

**A file has a set of sources, and the attachment is not one of them.** This
was the other way around for exactly one iteration: a document's binding was
its attachment, which is elegant and wrong twice. A covering letter names the
quotation *and* the customer *and* the project, and an attachment holds one;
a template is bound to a *kind* rather than a record, and an attachment cannot
say that at all. So `Bound Record` rows are what a file reads, and
`attached_to_*` goes back to meaning where the file is filed.

They are still connected at the one moment it helps: a file created against a
record gets its first source seeded from that attachment, so a letter started
from a quotation is about that quotation without anybody saying so twice.

**A source has a key**, and a token names `key.field`. The key is what makes a
record swappable — starting from a template fills in the records and the prose
does not change — and what lets one letter hold two projects.

**Freshness.** Nothing here is pushed. A value is read when the file is opened
and when somebody asks again, and what is stored in the file is the last
answer — which for a workbook it has to be, because the formula engine runs in
the browser and the server stores what it computed (`docs/SHEETS.md` §1). What
follows is that a bound file is only as fresh as its last read, and every
surface that shows one says when that was.
"""

import frappe
from frappe import _

#: How many records one file may read. Past this a document is a report, and
#: a report is a screen — `spaceview` draws one, with paging and a permission
#: model that a page of prose does not have.
MAX_SOURCES = 12

#: The key a bare token means: the one a file was created about.
FIRST = "record"

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

#: The two that are not tokens but *are* readable: a child table is a block —
#: a real table in the prose, `binding.rows` behind it — rather than a phrase
#: in a sentence. Kept out of `NEVER_BOUND`'s reason, which is that a value
#: cannot be rendered; these have values, they just are not one line long.
TABLE_TYPES = ("Table", "Table MultiSelect")

#: How many child rows one block may carry. A schedule longer than this is an
#: appendix, and an appendix is the sheet the record already feeds.
MAX_ROWS = 200

#: How many fields one call may resolve. A document with more tokens than this
#: is generated rather than written, and the generator is `print_format`.
MAX_FIELDS = 60


# --------------------------------------------------------------------------- #
# What is bound to what
# --------------------------------------------------------------------------- #

#: What one source looks like coming back. Named here because three modules
#: build one and a fourth reads it.
SOURCE_FIELDS = ("name", "key", "label", "reference_doctype", "reference_name")


def sources(file: str) -> list[dict]:
	"""Every record this file reads, in the order the sidebar shows them.

	`get_all` and not `get_list`: the permission that matters was already
	asked about the *file* by whoever called this, and a `Bound Record` row
	carries nothing but two names. What the record *says* is a separate
	question, and `resolve` asks it properly.
	"""
	return frappe.get_all(
		"Bound Record", filters={"file": file}, fields=list(SOURCE_FIELDS),
		order_by="idx_hint asc, creation asc", limit_page_length=MAX_SOURCES,
	)


def source(file: str, key: str) -> dict:
	"""One source by its key, or `{}`. What resolving a token starts with."""
	for row in sources(file):
		if row["key"] == (key or FIRST):
			return row
	# A token written before the file had more than one source names nothing,
	# and means the first. Kept because documents exist that were written that
	# way, and because it is what somebody typing by hand would expect.
	rows = sources(file)
	return rows[0] if rows and not key else {}


def bound(file: str) -> dict:
	"""The file's first source, as `{doctype, name}` — or `{}`.

	The shape everything spoke before sources existed, kept because most
	callers really do want "the record this is about" and asking them all to
	learn a key would be churn for nothing.
	"""
	rows = sources(file)
	if not rows:
		return {}
	first = rows[0]
	found = {"doctype": first["reference_doctype"]}
	if first["reference_name"]:
		found["name"] = first["reference_name"]
	return found


def _may_bind(file: str) -> None:
	"""Whoever changes what a file reads must be able to write the file."""
	row = frappe.get_doc("File", file)
	row.check_permission("write")


def _unused_key(file: str, doctype: str) -> str:
	"""A key nothing else on this file is using.

	`quotation`, then `quotation_2`. Derived from the doctype rather than
	asked for, because nobody wants to name a variable to put a number in a
	letter — and stable, because a token holds it forever.
	"""
	taken = {row["key"] for row in sources(file)}
	stem = frappe.scrub(doctype) or "record"
	if not taken:
		# The first source is what a bare token means, whatever it is of.
		return FIRST
	if stem not in taken:
		return stem
	at = 2
	while f"{stem}_{at}" in taken:
		at += 1
	return f"{stem}_{at}"


@frappe.whitelist(methods=["POST"])
def add_source(file: str, doctype: str, name: str = "", label: str = "") -> dict:
	"""Give this file another record to read, or another kind to ask for.

	`name` empty declares a slot: that is a template saying "a quotation goes
	here", and the picker fills it in when somebody starts from it.
	"""
	_may_bind(file)

	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("There is nothing called {0} here.").format(doctype))
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(_("You cannot read {0}.").format(doctype))
	if name and not frappe.has_permission(doctype, "read", doc=name):
		raise frappe.PermissionError(_("You cannot read {0}.").format(name))

	held = sources(file)
	if len(held) >= MAX_SOURCES:
		frappe.throw(_("That is more records than one document can be about."))

	row = frappe.get_doc({
		"doctype": "Bound Record",
		"file": file,
		"key": _unused_key(file, doctype),
		"label": label or _(doctype),
		"reference_doctype": doctype,
		"reference_name": name or None,
		"idx_hint": len(held),
	}).insert(ignore_permissions=True)

	return {"name": row.name, "key": row.key, "label": row.label,
	        "reference_doctype": doctype, "reference_name": name or ""}


@frappe.whitelist(methods=["POST"])
def set_source(file: str, key: str, name: str) -> dict:
	"""Point an existing source at a record. What filling a template's slot is.

	The key does not move, so every token that named it keeps working and the
	prose does not have to be touched — which is the whole reason a source has
	a key rather than being addressed by its record.
	"""
	_may_bind(file)

	found = source(file, key)
	if not found:
		frappe.throw(_("This document has no source called {0}.").format(key))
	if name and not frappe.has_permission(found["reference_doctype"], "read", doc=name):
		raise frappe.PermissionError(_("You cannot read {0}.").format(name))

	frappe.db.set_value("Bound Record", found["name"], "reference_name",
	                    name or None, update_modified=False)
	return {**found, "reference_name": name or ""}


@frappe.whitelist(methods=["POST"])
def drop_source(file: str, key: str) -> dict:
	"""Stop reading a record.

	The tokens that named it are left alone and answer nothing, which shows up
	as a blank rather than as a document that will not open. Removing them is
	a decision about the prose and belongs to whoever is writing it.
	"""
	_may_bind(file)

	found = source(file, key)
	if found:
		frappe.delete_doc("Bound Record", found["name"], ignore_permissions=True,
		                  delete_permanently=True)
	return {"file": file, "key": key}


def seed_from_attachment(file: str, doctype: str, name: str) -> None:
	"""The first source, from the record a file was created against.

	Called by `docs.make` and `sheets.make`. Nothing to do when the file was
	made from the Drive rather than from a record, which is most of them.
	"""
	if not doctype or not name or sources(file):
		return
	frappe.get_doc({
		"doctype": "Bound Record", "file": file, "key": FIRST,
		"label": _(doctype), "reference_doctype": doctype,
		"reference_name": name, "idx_hint": 0,
	}).insert(ignore_permissions=True)


def copy_sources(source_file: str, into: str) -> None:
	"""Carry a template's slots onto the document made from it.

	The records are *not* carried: a template's slot is a kind, and a
	template that already had a record would make every document from it
	about that one. What comes across is the shape and the keys, which is
	what the tokens need.
	"""
	for at, row in enumerate(sources(source_file)):
		frappe.get_doc({
			"doctype": "Bound Record", "file": into, "key": row["key"],
			"label": row["label"], "reference_doctype": row["reference_doctype"],
			"reference_name": None, "idx_hint": at,
		}).insert(ignore_permissions=True)


def on_file_trash(doc, method=None) -> None:
	"""A file thrown away takes its sources with it."""
	for row in frappe.get_all("Bound Record", filters={"file": doc.name},
	                          pluck="name"):
		frappe.delete_doc("Bound Record", row, ignore_permissions=True,
		                  delete_permanently=True, force=True)


@frappe.whitelist(methods=["GET"])
def file_sources(file: str) -> list[dict]:
	"""What the sidebar draws. Each source, with the record's own title."""
	frappe.get_doc("File", file).check_permission("read")

	out = []
	for row in sources(file):
		title = ""
		if row["reference_name"]:
			meta = frappe.get_meta(row["reference_doctype"])
			field = meta.get_title_field() if meta.title_field else ""
			if field and field != "name":
				title = frappe.db.get_value(row["reference_doctype"],
				                            row["reference_name"], field) or ""
		out.append({**row, "title": title or row["reference_name"] or ""})
	return out


# --------------------------------------------------------------------------- #
# What a record will answer
# --------------------------------------------------------------------------- #

#: How many record kinds the sidebar's first step offers at a time. A person
#: is looking for "Quotation", not reading the schema.
KIND_ROWS = 20


@frappe.whitelist(methods=["GET"])
def kinds(query: str = "") -> list[dict]:
	"""Which record kinds this person may read — the sidebar's first step.

	Frappe's own answer to "what can this person read", filtered to the ones
	that are records rather than parts of one: a child table has no life of
	its own and a document cannot be written about a row of it.

	Searched rather than listed, because the readable set on a full ERPNext
	site is several hundred doctypes and a menu that long is a scroll bar.
	"""
	from frappe.permissions import get_doctypes_with_read

	readable = get_doctypes_with_read()
	if not readable:
		return []

	# A list of clauses rather than a dict, because two of them are about
	# `name` — the readable set and the search — and a dict can only hold one.
	filters = [["name", "in", readable], ["istable", "=", 0]]
	asked = (query or "").strip()[:140]
	if asked:
		filters.append(["name", "like", f"%{asked}%"])

	rows = frappe.get_all(
		"DocType", filters=filters, fields=["name", "module"],
		order_by="name asc", limit_page_length=KIND_ROWS,
	)
	return [{"name": row["name"], "label": _(row["name"]), "module": row["module"]}
	        for row in rows]


def offer(doctype: str, levels: set[int] | None = None) -> list[dict]:
	"""The fields a token or a formula may name, in the doctype's own order.

	The doctype's own metadata, filtered by `NEVER_BOUND` and by permlevel:
	a field somebody cannot read on the record is not a field they may put in
	a document, and finding that out at render time would mean a document that
	looks complete to its author and blank to everybody else.

	`levels` is for a *child* doctype, and it is not an optimisation. A child
	table has no permissions of its own — the framework reads the parent's —
	so asking it for its own readable permlevels answers the empty set and
	every column is filtered out. That was the first version, and it showed up
	as a schedule with no columns in it. When `levels` is given, the caller
	has already checked the parent and is handing over its answer.

	`name` is first and is not a DocField, which is why it is described here.
	It is also the field most templates want — a covering letter says which
	quotation it is about before it says anything else.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []
	if levels is None:
		if not frappe.has_permission(doctype, "read"):
			raise frappe.PermissionError(_("You cannot read {0}.").format(doctype))
		levels = _readable_levels(doctype)

	meta = frappe.get_meta(doctype)
	allowed = levels

	# The same glyph the record, the list header and the column picker draw,
	# from the same call — `onespace/field_icons.py`. A rail that invented its
	# own would be the fifth answer to one question.
	from ..onespace import field_icons

	out = [{"fieldname": "name", "label": _("ID"), "fieldtype": "Data",
	        "icon": field_icons.icon_for("Data", doctype, "name")}]
	for field in meta.fields:
		if field.fieldtype in NEVER_BOUND or not field.fieldname:
			continue
		if (field.permlevel or 0) not in allowed:
			continue
		out.append({
			"fieldname": field.fieldname,
			"label": _(field.label or field.fieldname),
			"fieldtype": field.fieldtype,
			"icon": field_icons.icon_for(field.fieldtype, doctype, field.fieldname),
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


def tables(doctype: str) -> list[dict]:
	"""The child tables of this doctype, with the columns each one offers.

	Separate from `offer` because they are a different thing to insert: a
	token is a phrase and a table is a block, and a picker that mixed them
	would offer "Items" beside "Grand Total" as though clicking either did
	the same kind of thing.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(_("You cannot read {0}.").format(doctype))

	from ..onespace import field_icons

	# The parent's, and used for the child's columns too — a child table has
	# no permissions of its own. See `offer`.
	allowed = _readable_levels(doctype)

	out = []
	for field in frappe.get_meta(doctype).fields:
		if field.fieldtype not in TABLE_TYPES or not field.options:
			continue
		if (field.permlevel or 0) not in allowed:
			continue
		# The child's own fields, narrowed the same way the parent's are.
		# `name` is dropped: a row id in a printed schedule is noise.
		columns = [one for one in offer(field.options, allowed)
		           if one["fieldname"] != "name"]
		out.append({
			"fieldname": field.fieldname,
			"label": _(field.label or field.fieldname),
			"child_doctype": field.options,
			"icon": field_icons.icon_for(field.fieldtype, doctype, field.fieldname),
			"columns": columns,
			"default": _grid_columns(field.options, columns),
		})
	return out


#: How many columns a schedule starts with. More than this does not fit across
#: a page, and the person can add the seventh once they can see the six.
GRID_COLUMNS = 6


def _grid_columns(child: str, columns: list[dict]) -> list[str]:
	"""Which columns a block draws before anybody chooses.

	`in_list_view` — the same flag the child-table grid reads, which is the
	doctype author saying which columns this table is *about*. Without it the
	answer is the first six fields in schema order, and on `Quotation Item`
	that is Item Code followed by five checkboxes nobody wants in a letter.
	"""
	offered = {one["fieldname"] for one in columns}
	listed = [
		one.fieldname for one in frappe.get_meta(child).fields
		if getattr(one, "in_list_view", 0) and one.fieldname in offered
	]
	return (listed or [one["fieldname"] for one in columns])[:GRID_COLUMNS]


@frappe.whitelist(methods=["GET"])
def fields(doctype: str) -> dict:
	"""What this doctype will answer, as the sidebar reads it.

	Both halves in one request, because the sidebar draws both and a second
	round trip to list two child tables is a round trip for nothing.
	"""
	return {"fields": offer(doctype), "tables": tables(doctype)}


@frappe.whitelist(methods=["GET"])
def rows(doctype: str, name: str, table: str,
         columns: str | list | None = None) -> dict:
	"""A child table's rows — as text for a document, as values for a sheet.

	Narrowed exactly as a token is: the table must be one `tables` offered,
	the columns must be ones the child doctype offers, and the person must be
	able to read the parent. Without the middle one this is a whitelisted read
	of any child table of any doctype.

	Both halves, for the same reason `resolve` sends both: a schedule in a
	letter is read, so it wants `AED 99,125.00`; the same schedule in a
	workbook is added up, so it wants `99125.0`. One read of the parent
	answers both, and the two cannot disagree about how many rows there were.
	"""
	if not frappe.has_permission(doctype, "read", doc=name):
		raise frappe.PermissionError(_("You cannot read {0}.").format(name))

	found = next((one for one in tables(doctype)
	              if one["fieldname"] == table), None)
	if not found:
		return {"columns": [], "rows": []}

	offered = {one["fieldname"]: one for one in found["columns"]}
	asked = [one for one in _asked(columns) if one in offered]
	chosen = asked or found["default"]

	doc = frappe.get_doc(doctype, name)
	said, values = [], []
	for row in (doc.get(table) or [])[:MAX_ROWS]:
		answered = [_said(row, offered[one]) for one in chosen]
		said.append([one["text"] for one in answered])
		values.append([one["value"] for one in answered])

	return {
		"columns": [{"fieldname": one, "label": offered[one]["label"]}
		            for one in chosen],
		"rows": said,
		"values": values,
	}


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
