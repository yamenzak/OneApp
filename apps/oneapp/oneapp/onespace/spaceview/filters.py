"""Turning what a reader asked for into a query the framework accepts."""

import frappe
from frappe import _
from oneapp.onespace import collab, dashboard, docflow, fieldtypes, printing, showcase
from .meta import ALWAYS, META_COLUMN, PAGE_SIZES


def _page_length(value) -> int:
	"""One of the sizes the footer offers, or nothing.

	Not clamped to a range: the footer is a set of buttons, so a number that is
	not one of them did not come from the footer, and `limit` is bounded again
	where it is used anyway.
	"""
	try:
		asked = int(value or 0)
	except (TypeError, ValueError):
		return 0
	return asked if asked in PAGE_SIZES else 0


def _group_by(resolved: dict, fieldname) -> str:
	"""Which column the rows are grouped under.

	A column the screen offers, or nothing. Not `name` — grouping by the id
	makes a group per row — and not the activity column, which is not a field
	and has no value to group on.
	"""
	if not isinstance(fieldname, str) or not fieldname:
		return ""
	offered = {c["fieldname"] for c in resolved.get("all_columns") or resolved.get("columns") or []}
	if fieldname not in offered or fieldname in (META_COLUMN, "name"):
		return ""
	return fieldname


def _grouped_order(resolved: dict) -> str:
	"""The sort, with the group column in front of it.

	Rows have to arrive grouped for the list to render them that way — the page
	is one query and a group whose rows are scattered through it would render as
	the same heading three times.
	"""
	order = resolved["order_by"]
	group = resolved.get("group_by")
	if not group or order.split(" ")[0] == group:
		return order
	return f"{group} asc, {order}"


def _safe_order(resolved: dict, order_by: str) -> str:
	"""Only a field the screen shows, only a direction we recognise.

	`order_by` reaches the query layer, so it is rebuilt from parts rather than
	passed through — a string a browser sent is not a fragment of SQL.
	"""
	parts = (order_by or "").split()
	fieldname = parts[0] if parts else ""
	direction = (parts[1] if len(parts) > 1 else "desc").lower()

	offered = resolved.get("all_columns") or resolved.get("columns") or []
	known = {c["fieldname"] for c in offered} | set(ALWAYS) | {"modified", "creation"}
	if fieldname not in known or direction not in ("asc", "desc"):
		return resolved["order_by"]
	return f"{fieldname} {direction}"


# How many values one `in` filter may carry, and how many filters one screen
# may be asked. Neither is a security boundary on its own — every one of them is
# already bounded to a field the screen shows — but an unbounded list is a way
# to make one request cost a great deal.
# A selection is a person clicking checkboxes, so this is generous. It exists
# because one request that deletes ten thousand rows is a different thing.
MAX_DELETE = 100


MAX_FILTERS = 20


MAX_IN_VALUES = 100


# How many columns one search box reaches.
#
# A real cost rather than a tidiness bound: `%q%` cannot use an index, so each
# column in the OR is a scan of the table. Ten is about what a wide screen
# shows, and past it the eleventh column is one nobody had in mind when they
# typed.
MAX_SEARCH_COLUMNS = 10

# And how much of what was typed is used. A search box is not a paste target.
MAX_SEARCH_LENGTH = 140

# Never searched, whatever a screen shows, and there are two reasons in here.
#
# Some cannot match: a Password holds ciphertext, a Signature and an Attach are
# a data URI and a path, and a `like` against any of them costs the scan and
# finds nothing.
#
# The rest can match and should not. Frappe allows `like` on a Currency and a
# Date — its operator table is a deny list, so almost everything is in — and
# `%42%` against six money columns is six scans to find a total nobody was
# looking for by substring. Money and dates are what the filter panel is for,
# where the question is `>` or `between` and means something.
NEVER_SEARCHED = (
	"Password", "Signature", "Attach", "Attach Image", "Geolocation", "Icon", "Color",
	"Currency", "Float", "Int", "Long Int", "Percent", "Rating", "Duration", "Slider",
	"Date", "Datetime", "Time",
)


def _filterable(resolved: dict) -> dict:
	"""The fields a filter may name, keyed by fieldname.

	The columns, plus `name`. The id is not a column — it lives in the title
	cell, under the title — but it is the one thing everybody searches by, and
	Frappe's own list gives it a box of its own above every list. Described here
	rather than looked up, because `name` is not a DocField.
	"""
	offered = {c["fieldname"]: c
	           for c in resolved.get("all_columns") or resolved.get("columns") or []}
	offered.setdefault("name", {
		"fieldname": "name",
		"label": _("ID"),
		"fieldtype": "Data",
		"options": None,
	})
	# And the child tables' own fields, under their dotted keys. Same checks as
	# everything else here — a fieldtype's operators, a value's shape — and a
	# different query shape on the way out, which `_as_query_filters` builds.
	for column in resolved.get("child_columns") or []:
		offered[column["fieldname"]] = column
	return offered


def _asked_filters(offered: dict, extra) -> list:
	"""What someone asked to filter by, reduced to something a screen may ask.

	A filter is `[fieldname, operator, value]`, which is Frappe's own shape. The
	operator being a named part rather than something smuggled inside the value
	is what lets this be checked at all: it is looked up against the operators
	that fieldtype allows — Frappe's own table, inverted from a deny list into
	an allow list in `fieldtypes.OPERATORS` — and anything else is dropped.

	Three bounds, and all three matter:

	* **Only fields the screen shows.** A filter on a hidden field narrows the
	  list, which sounds harmless — but a customer who can watch which rows come
	  back can read a field they were never shown, one guess at a time.
	* **Only operators that fieldtype allows.** `descendants of` runs a subquery
	  against another doctype's tree; `regex` is a way to spend a lot of database
	  time. Neither is in Frappe's own filter menu, so neither is here.
	* **Only values of the shape the operator takes.** `between` is exactly two,
	  `is` is one of two words, `in` is a bounded list, everything else is a
	  scalar. A list arriving where a scalar belongs is dropped rather than
	  reinterpreted.

	This is the form that gets stored and echoed back to the controls: what
	someone chose, not the query it turns into.
	"""
	if isinstance(extra, str):
		extra = frappe.parse_json(extra or "null")

	# The shape this used to be, before operators: `{fieldname: value}`. Saved
	# screens written then are still on disk, so they are read as what they meant.
	if isinstance(extra, dict):
		extra = [
			[fieldname, fieldtypes.default_operator(
				offered[fieldname]["fieldtype"] if fieldname in offered else "Data", fieldname),
			 value]
			for fieldname, value in extra.items()
			if fieldname in offered
		]
	if not isinstance(extra, (list, tuple)):
		return []

	asked = []
	for row in extra[:MAX_FILTERS]:
		clean = _asked_filter(offered, row)
		if clean:
			asked.append(clean)
	return asked


def _asked_filter(offered: dict, row) -> list | None:
	"""One filter, or None if it is not one this screen may be asked."""
	if not isinstance(row, (list, tuple)) or len(row) != 3:
		return None

	fieldname, operator, value = row
	column = offered.get(fieldname)
	if not column or not isinstance(operator, str):
		return None

	operator = operator.strip().lower()
	if operator not in fieldtypes.operators_for(column["fieldtype"]):
		return None

	shape = fieldtypes.value_shape(column["fieldtype"], operator)

	if shape == "set":
		return [fieldname, operator, value] if value in ("set", "not set") else None

	if shape == "timespan":
		return [fieldname, operator, value] if value in fieldtypes.TIMESPANS else None

	if shape == "range":
		if not isinstance(value, (list, tuple)) or len(value) != 2:
			return None
		if any(_not_a_value(v) for v in value):
			return None
		return [fieldname, operator, [value[0], value[1]]]

	if shape == "multi":
		if isinstance(value, str):
			# Frappe's own filter splits a typed list on commas.
			value = [v.strip() for v in value.split(",") if v.strip()]
		if not isinstance(value, (list, tuple)) or not value:
			return None
		values = [v for v in value[:MAX_IN_VALUES] if not _not_a_value(v)]
		return [fieldname, operator, values] if values else None

	return None if _not_a_value(value) else [fieldname, operator, value]


def _not_a_value(value) -> bool:
	"""A scalar someone could have typed. Anything else is a shape we did not
	ask for, and reinterpreting it is how a filter becomes a query."""
	return (
		value in ("", None)
		or isinstance(value, (list, tuple, dict, set))
	)


def _as_query_filters(offered: dict, asked: list) -> list:
	"""The same filters, as questions the query layer can be asked.

	Only two rewrites, both Frappe's own (`get_selected_value`): a `like` gets
	wildcards unless the person wrote their own, so a box labelled "Contains"
	contains; and a Check is stored as the word someone picked and asked as the
	0 or 1 the column holds.
	"""
	query = []
	for fieldname, operator, value in asked:
		column = offered[fieldname]
		if operator in ("like", "not like") and isinstance(value, str):
			if not (value.startswith("%") or value.endswith("%")):
				value = f"%{value}%"
		elif column["fieldtype"] == "Check":
			value = 1 if str(value) in ("1", "Yes", "true", "True") else 0

		# A child table's field is asked of the child table, which is the four
		# part form: Frappe joins it and the three-part one would look for the
		# column on the parent.
		if column.get("child_doctype"):
			query.append([column["child_doctype"], column["child_fieldname"],
			              operator, value])
		else:
			query.append([fieldname, operator, value])
	return query


def _search_text(value) -> str:
	"""What was typed, as one line of it.

	Whitespace collapsed because a search pasted out of a spreadsheet arrives
	with a tab in it, and `%a\tb%` matches nothing while looking like it
	should.
	"""
	if not isinstance(value, str):
		return ""
	return " ".join(value.split())[:MAX_SEARCH_LENGTH]


def _search_filters(resolved: dict) -> list:
	"""One box, asked of every column that can answer it.

	The filter area asks a field a question. This asks all of them at once,
	which is the thing people reach for first and the one shape the controls
	did not have.

	Returned as `or_filters` and never merged into `filters`, because those are
	different questions: Frappe ANDs the two, so searching inside a filtered
	list narrows what is already narrow instead of replacing it. Every place
	that counts or totals a list has to pass both or the footer ends up
	disagreeing with the rows above it — `_query` in `records.py` is what keeps
	that from being something to remember.

	Which columns: the ones whose fieldtype takes `like`, read off the same
	generated table the filter menu is built from. So a search reaches exactly
	the fields somebody could have filtered one at a time, and a field the
	screen does not show is not searched — the same rule as everywhere else,
	and for the same reason: watching which rows come back is a way of reading
	a column you were never given.

	`name` first, because the id is what people paste and a screen with eleven
	text columns would otherwise spend the whole budget before reaching it.
	"""
	text = _search_text(resolved.get("search"))
	if not text:
		return []

	offered = _filterable(resolved)
	reach = ["name"] if "name" in offered else []
	for column in offered.values():
		fieldtype = column.get("fieldtype") or "Data"
		if column.get("child_doctype"):
			# `or_filters` has no four-part form, so a child field cannot join
			# the OR. Left out rather than half-searched.
			continue
		if column["fieldname"] in reach or fieldtype in NEVER_SEARCHED:
			continue
		if "like" not in fieldtypes.operators_for(fieldtype):
			continue
		reach.append(column["fieldname"])
		if len(reach) >= MAX_SEARCH_COLUMNS:
			break

	return [[one, "like", f"%{text}%"] for one in reach]


def _favourite_filter() -> list:
	"""Rows this person liked.

	A flag rather than a filter on `_liked_by`, and the difference matters: the
	column is a JSON array of user ids, so a filter naming it could be pointed
	at a colleague and would answer what *they* had liked. The flag can only
	ever mean the session's own user, which is the only version of this question
	anyone should be able to ask.
	"""
	return ["_liked_by", "like", f"%{frappe.session.user}%"]


def _all_filters(resolved: dict, asked: list) -> list:
	"""The screen's own filters and this person's, as one list.

	Both are applied; neither replaces the other. That is what makes the
	narrowing rule hold without a special case: two filters on one field are
	ANDed, so a saved `status = Closed` on a screen filtered to `status = Open`
	returns nothing rather than quietly returning the screen's rows. Frappe's
	desk behaves the same way, and "no rows, and there is my filter" reads
	better than a filter that appears to be ignored.
	"""
	offered = _filterable(resolved)
	own = [[fieldname, "=", value] if not isinstance(value, (list, tuple))
	       else [fieldname, value[0], value[1]]
	       for fieldname, value in (resolved.get("filters") or {}).items()]
	mine = [_favourite_filter()] if resolved.get("favourites") else []
	return own + mine + _as_query_filters(offered, asked)
