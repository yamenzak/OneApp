"""A form that collects a document *and its lines*.

`docs/ONEFORMS.md` §15, stage 16. `Table` was in `NEVER` from stage 1 with a
reason that was true and stopped being enough: a grid inside a page a stranger
is filling in is a different control, so it was left out — and what that left
out was every form whose subject has parts. An order has order lines. An expense
claim has expenses. A tender has a schedule of rates. A form that collects one
flat document cannot ask for any of them, and "fill the header in here and mail
us a spreadsheet for the rest" is not a product.

**The write needed nothing.** `accept` does `doc.set(fieldname, value)` for
every field the form carries, and `Document.set` on a table field with a list of
dicts is how Frappe has always filled a child table. So the submission path is
unchanged and this module is entirely about what may be in that list.

Three rules, and the second is the one that makes it safe:

* **A row may only carry the columns the form asked for.** Not the child
  doctype's own fields — the *form's*, which is a subset somebody chose. A
  payload naming `rate` on a form that only asks for a description and a
  quantity is a payload setting a price.
* **Nothing about the parent is settable from a row.** `parent`, `parenttype`,
  `parentfield`, `name`, `owner`, `docstatus` and the rest are Frappe's own
  bookkeeping, and a row that could name its own `parent` is a row that attaches
  itself to somebody else's document.
* **There is a ceiling.** A hundred lines is a big order and a thousand is an
  attack; the page draws what it is given and the server is what says no.

`Table MultiSelect` stays out. It looks like this and is not: every row is a
Link, drawn as a chip picker, and resolving a Link against Guest is the one
thing `LINKISH` says a public page cannot do.
"""

import frappe
from frappe import _

#: Where a table field keeps the columns it asks for. A custom field on
#: `Web Form Field` rather than one of Frappe's own, because every one of those
#: that would have fitted is read by somebody: `description` is the help text
#: under the label, and it was on the page before anybody noticed.
COLUMNS = "custom_onespace_columns"

#: The fieldtype this module is about. `Table MultiSelect` is deliberately not
#: here — see the module docstring.
TABLE = "Table"

#: Rows one submission may carry, per table. A hundred is a big order; a
#: thousand is somebody finding out what happens.
MOST = 100

#: What a row may never set, whatever it sends. Frappe's own bookkeeping: a row
#: that could name its `parent` is a row that files itself against somebody
#: else's document.
NEVER = {
	"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
	"parent", "parenttype", "parentfield", "doctype", "__islocal", "__unsaved",
}


def carried(doc) -> list:
	"""The form's table fields, as `(fieldname, child doctype)`."""
	return [(row.fieldname, row.options) for row in (doc.web_form_fields or [])
	        if row.fieldtype == TABLE and row.fieldname and row.options]


def asked(doc, fieldname: str) -> list[str]:
	"""Which of a child's columns this form asks for.

	The form's own list, stored as a comma list in `COLUMNS`, and every column
	the child has when it is empty. The first is what a builder sets and the
	second is what a form made before this existed does — a fallback that
	widens rather than breaks, because the alternative is a table that silently
	collects nothing.

	Not `description`, which is the help text a *reader* sees under the label.
	That was the first home and the browser showed it: "item_name, qty,
	description", printed on the page for whoever was filling the form in.
	"""
	every = [one["fieldname"] for one in columns(doc, fieldname)]
	row = next((one for one in (doc.web_form_fields or [])
	            if one.fieldname == fieldname), None)
	if not row:
		return []
	wanted = [one.strip() for one in str(row.get(COLUMNS) or "").split(",")]
	wanted = [one for one in wanted if one in every]
	return wanted or every


def columns(doc, fieldname: str) -> list[dict]:
	"""Every column of a child a row *could* ask for.

	`service.available` on the child, minus anything `LINKISH` — a Link, a
	Dynamic Link, a Table MultiSelect. Same rule and the same reason as the
	list a key holder sees: a Link has to be resolved against Guest, and a cell
	has nowhere to put a picker even if it could be.
	"""
	from oneapp.oneforms.service import LINKISH, available

	row = next((one for one in (doc.web_form_fields or [])
	            if one.fieldname == fieldname), None)
	if not row or not row.options:
		return []
	return [one for one in available(row.options)
	        if one["fieldtype"] not in LINKISH]


def clean(doc, values: dict) -> None:
	"""Hold every table in the payload to what the form asked for. Mutates.

	Silent about a column it drops and loud about a row count it will not take.
	That split is deliberate: an extra column is a payload somebody built by
	hand and there is nothing useful to tell them, while too many rows is a
	person who filled a form in and needs to know why it bounced.
	"""
	for fieldname, child in carried(doc):
		sent = values.get(fieldname)
		if sent in (None, ""):
			values[fieldname] = []
			continue
		if not isinstance(sent, list):
			frappe.throw(_("{0} should be a list of rows.").format(fieldname))
		if len(sent) > MOST:
			frappe.throw(_("That is more than {0} rows.").format(MOST))

		allowed = set(asked(doc, fieldname)) - NEVER
		rows = []
		for one in sent:
			if not isinstance(one, dict):
				continue
			kept = {key: value for key, value in one.items() if key in allowed}
			# A row where everything was empty is a row somebody added and did
			# not fill in. Dropped rather than saved: a child table of blanks is
			# what a grid with an Add button produces by accident.
			if any(str(value or "").strip() for value in kept.values()):
				rows.append(kept)
		values[fieldname] = rows


def shown(doc, fieldname: str) -> list[dict]:
	"""The columns a browser needs to draw one row.

	`columns` narrowed to what the form asks for — so the same rule decides
	what can be on a form and what can be in one of its rows, and a read-only,
	hidden or Link column is out of both.
	"""
	wanted = asked(doc, fieldname)
	by_name = {one["fieldname"]: one for one in columns(doc, fieldname)}
	return [by_name[one] for one in wanted if one in by_name]
