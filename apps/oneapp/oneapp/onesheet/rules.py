"""What a child table will accept, said in the sheet and enforced at the pull.

`feed.py` opens a child table as a grid and reads it back. Between those two
moments the grid is a spreadsheet, which will hold anything: `TBC` in a
quantity column, `Widgt` where the item is `Widget`, a blank line somebody
meant to fill in. All three used to reach `target.save()`, and what came back
was one of Frappe's own exceptions — accurate, about one row, and thrown after
the document had already been half rewritten.

**Two halves, because the two questions are different.**

*What the sheet can stop while somebody types.* The browser engine has a
validation model (`lib/engine/validation.js`) that the editor already draws:
a `list` rule paints a dropdown in the cell, a `number` rule refuses a word.
It is a slice of the stored workbook, so seeding it is writing JSON in
`start_from` — nothing in the browser changes. That is `for_columns`.

*What only the server knows.* Whether `WIDGET-99` is a document, whether a
Select outside its options slipped in through a paste, whether `TBC` in a
quantity column is about to be priced at zero. Those are checked in one pass
before the document is touched, and every problem in the block comes back at
once — where `target.save()` answers with the first one it hits, in the
framework's words, about one row. That is `check`.

Neither half is a substitute for the other. The engine skips validation
entirely for an empty cell — deliberately, so a cell can always be cleared —
and a `Link` to a doctype with nine thousand rows is not a dropdown.

**What is deliberately not checked: whether a mandatory field was filled.**
It reads as the most obvious thing here and it is the one thing that cannot
be known in advance. `Quotation Item` marks `item_name`, `uom` and
`conversion_factor` required and none of them is in the grid, because ERPNext
fills all three from the item code in `validate` — in Python, not through a
`fetch_from` this could read. A pre-flight mandatory check refused every real
quotation. `save()` is the only thing that knows what a controller will fill
in, so `save()` keeps that job; what is here is the three ways a *sheet* can
be wrong whatever the controller does afterwards.
"""

import frappe
from frappe import _

#: How many rows a `Link` column will offer as a dropdown. Past this the sheet
#: says nothing and the check at the pull is the whole guarantee: a list of
#: nine thousand items is not a picker, it is a payload.
LINK_CHOICES = 200

#: How many problems one refusal names. Twenty is more than anybody will fix
#: in one pass, and a message longer than a screen is a message nobody reads.
MAX_PROBLEMS = 20

#: Fieldtypes that are a number in a cell. The same tuple `feed._child` coerces
#: with, kept here because this is where what a column *means* is decided.
NUMERIC = ("Currency", "Float", "Int", "Percent")


def _options(field) -> list[str]:
	"""A Select's options, as the list the engine wants.

	Frappe stores them newline-separated, and a leading blank line is how a
	doctype says the field is optional. The blank is dropped: the engine does
	not validate an empty cell, so an empty option would be a dropdown entry
	that does nothing.
	"""
	raw = (field.options or "").split("\n")
	return [one.strip() for one in raw if one.strip()]


def _link_choices(doctype: str) -> list[str]:
	"""What a Link column may hold, if that is a short enough list to offer.

	`get_list` and not `get_all`, so the dropdown offers what this person
	could have picked on the form — including User Permissions. The *check*
	below asks a different question and asks it differently; see there.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []
	if not frappe.has_permission(doctype, "read"):
		return []
	try:
		rows = frappe.get_list(doctype, pluck="name",
		                       limit_page_length=LINK_CHOICES + 1)
	except Exception:
		frappe.clear_last_message()
		return []
	# One over the cap means there are more than we would offer, and half a
	# list is worse than none: a rule that rejects a valid item because it was
	# the two hundred and first is a rule that has to be worked around.
	return [] if len(rows) > LINK_CHOICES else rows


def rule_for(field) -> dict | None:
	"""The engine's rule for one child field, or nothing.

	Nothing is the ordinary answer. A `Data` column holds text and a rule
	saying so would only get in the way; what earns a rule is a column where
	the doctype already knows the answer and the estimator cannot.
	"""
	if field.fieldtype == "Check":
		return {"type": "checkbox"}

	if field.fieldtype == "Select":
		options = _options(field)
		if not options:
			return None
		return {
			"type": "list", "options": options, "severity": "reject",
			"message": _("{0} is one of: {1}").format(
				_(field.label or field.fieldname), ", ".join(options)),
		}

	if field.fieldtype == "Link":
		choices = _link_choices(field.options)
		if not choices:
			return None
		return {
			"type": "list", "options": choices, "severity": "reject",
			"message": _("There is no {0} called that.").format(_(field.options)),
		}

	if field.fieldtype in NUMERIC:
		# `between` with no bounds is the engine's way of saying "a number",
		# which is what most of these columns want. `non_negative` is the one
		# thing a doctype says about a number that a sheet can hold it to.
		if field.get("non_negative"):
			return {
				"type": "number", "operator": "gte", "min": 0, "severity": "reject",
				"message": _("{0} cannot be negative.").format(
					_(field.label or field.fieldname)),
			}
		return {
			"type": "number", "operator": "between", "severity": "reject",
			"message": _("{0} is a number.").format(_(field.label or field.fieldname)),
		}

	return None


def for_columns(child: str, fieldnames: list[str]) -> dict[int, dict]:
	"""`{column index: rule}` for the columns a sheet is about to be given.

	Indexed by position rather than by fieldname because the caller is about
	to write cell ids, and the sheet has no idea what a fieldname is.
	"""
	meta = frappe.get_meta(child)
	by_fieldname = {df.fieldname: df for df in meta.fields}

	found = {}
	for at, fieldname in enumerate(fieldnames):
		field = by_fieldname.get(fieldname)
		if not field:
			continue
		rule = rule_for(field)
		if rule:
			found[at] = rule
	return found


def check(child: str, columns: list[dict], body: list[list]) -> list[str]:
	"""Everything wrong with these rows, before any of them is written.

	`columns` is `feed._columns`'s answer — which sheet column feeds which
	child field — and `body` the rows under the headings. Row numbers are the
	sheet's own, counting the heading as row 1, because that is the number the
	person is looking at.

	Only what is *in* the block. A field with no column feeding it is not a
	problem this can see — see the note at the top about mandatory fields a
	controller fills in.
	"""
	meta = frappe.get_meta(child)
	by_fieldname = {df.fieldname: df for df in meta.fields}

	problems = []
	live = _existing_links(columns, by_fieldname, body)
	for at, row in enumerate(body):
		line = at + 2
		for column in columns:
			fieldname = column["fieldname"]
			if not fieldname:
				continue
			field = by_fieldname.get(fieldname)
			if not field:
				continue
			raw = row[column["index"]] if column["index"] < len(row) else None
			problems.extend(_cell(field, raw, line, live))
			if len(problems) > MAX_PROBLEMS:
				return problems[:MAX_PROBLEMS] + [
					_("…and more. Fix these and read the rows back again.")]

	return problems


def _cell(field, raw, line: int, live: dict) -> list[str]:
	"""One cell, as nothing or as a sentence naming the row and the column."""
	label = _(field.label or field.fieldname)
	text = "" if raw is None else str(raw).strip()

	# A blank is a blank. `feed._child` writes "" or 0, which is what the form
	# would store, and whether the doctype minds is `save()`'s to say.
	if not text:
		return []

	if field.fieldtype == "Link":
		known = live.get(field.fieldname)
		# `None` means the column was not checked — a Link whose target does
		# not exist as a doctype, which `frappe.get_all` would have thrown on.
		if known is not None and text not in known:
			return [_("Row {0}: there is no {1} called {2}.").format(
				line, _(field.options), text)]
		return []

	if field.fieldtype == "Select":
		options = _options(field)
		if options and text not in options:
			return [_("Row {0}: {1} is {2}, which is not one of: {3}").format(
				line, label, text, ", ".join(options))]
		return []

	if field.fieldtype in NUMERIC:
		# `feed.number` forgives `AED 1,234.50` and answers 0.0 for anything
		# it cannot read — which is the silent zero this exists to catch. A
		# quantity of `TBC` priced at zero is worse than a refusal.
		from .feed import number

		if number(text) == 0 and not _reads_as_zero(text):
			return [_("Row {0}: {1} is {2}, which is not a number.").format(
				line, label, text)]

	return []


def _reads_as_zero(text: str) -> bool:
	"""Whether this really is zero, rather than something that came to zero."""
	try:
		return float(str(text).replace(",", "").strip().lstrip("+")) == 0
	except ValueError:
		return False


def _existing_links(columns, by_fieldname, body) -> dict:
	"""Which of the values in each Link column are documents.

	One query per column rather than one per cell: a hundred lines naming
	twenty items is twenty rows out of the database, not two thousand.

	`get_all`, deliberately. This is the same question `frappe.Document`'s own
	link validation asks — does the row exist — and a link to a record this
	person cannot *read* is still a link the form would have saved. The
	dropdown above asks the other question, and asks it with `get_list`.
	"""
	found = {}
	for column in columns:
		field = by_fieldname.get(column["fieldname"])
		if not field or field.fieldtype != "Link":
			continue

		wanted = set()
		for row in body:
			raw = row[column["index"]] if column["index"] < len(row) else None
			text = "" if raw is None else str(raw).strip()
			if text:
				wanted.add(text)
		if not wanted:
			found[field.fieldname] = set()
			continue

		try:
			rows = frappe.get_all(field.options, filters={"name": ["in", list(wanted)]},
			                      pluck="name")
		except Exception:
			# A Link pointing at a doctype this site does not have. Not this
			# module's problem to report, and not a reason to refuse the pull:
			# the save will say so, in the framework's own words.
			frappe.clear_last_message()
			continue
		found[field.fieldname] = set(rows)
	return found
