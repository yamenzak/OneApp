"""A screen's rows, as a file somebody can open somewhere else.

The one thing every list in this product could not do. "Send me that as a
spreadsheet" is not a power-user request in a business — it is how a register
reaches an accountant, an auditor or a bank — and answering it with nothing
meant the answer was a screenshot.

Three decisions, and the first two are the reason this is a module rather than
four lines in the browser:

* **The file is built here.** Quoting a value that contains a comma, a quote or
  a newline is the part that goes wrong, and it goes wrong silently — a
  correspondence subject with a comma in it becomes two columns and every row
  after it is off by one. Python's `csv` has done this correctly for twenty
  years and can be tested without a browser.

* **The same query as the list, through the same checks.** `_resolve`, then the
  saved view, then whatever is unsaved above it — so an export is exactly the
  rows on screen and can never reach further. An export endpoint that took a
  doctype and a filter list would be a second way to read, with its own
  permission story to get wrong.

* **What you see, in the columns you chose.** The reader's own columns in the
  reader's own order, labelled the way the header labels them. Values are the
  ones stored rather than the ones drawn: a CSV is data, and a Link cell drawn
  as "Ada Sinclair" has to come back as the id it is for the file to be worth
  anything to whoever reads it next.
"""

import csv
import io
import re

import frappe
from frappe import _

from .meta import META_COLUMN
from .filters import _all_filters, _grouped_order
from .applied import _apply_overrides, _apply_saved
from .resolve import _resolve


# How many rows one export may carry.
#
# Not a page: an export is the whole answer or it is a misleading one, so this
# is high enough that no screen in this product reaches it by accident. Past it
# the file says so — `capped` comes back true and the caller says which rows
# these are — because a truncated spreadsheet that does not admit it is the
# worst possible artefact to hand an auditor.
MAX_EXPORT = 5000


# Excel on Windows reads a UTF-8 file as the system codepage unless it finds a
# byte-order mark, which turns every Arabic subject in the correspondence
# register into mojibake. Three bytes, and the reason this repo's own fixture
# would have caught it.
EXCEL_BOM = "﻿"


@frappe.whitelist(methods=["GET"])
def export_rows(space_code: str, screen: str | None = None,
                overrides: str | dict | None = None, layout: str | None = None,
                view_type: str | None = None, names: str | list | None = None) -> dict:
	"""The rows this screen is showing, as a CSV.

	`names` narrows it to a selection: the same endpoint answers "export this
	list" and "export the four I ticked", because they are the same question
	with a different filter and splitting them would be two permission paths.
	"""
	resolved = _apply_overrides(
		_apply_saved(_resolve(space_code, screen, view_type), layout), overrides
	)
	if not resolved.get("doctype"):
		frappe.throw(_("This screen has nothing to export."))

	filters = _all_filters(resolved, resolved.get("asked") or [])
	chosen = _export_names(names)
	if chosen:
		filters = filters + [[resolved["doctype"], "name", "in", chosen]]

	# One more than the cap, so "there were more than this" needs no count.
	found = frappe.get_list(
		resolved["doctype"],
		fields=resolved["fields"],
		filters=filters,
		order_by=_grouped_order(resolved),
		limit_page_length=MAX_EXPORT + 1,
	)
	capped = len(found) > MAX_EXPORT
	found = found[:MAX_EXPORT]

	columns = _export_columns(resolved)
	return {
		"filename": _export_filename(resolved),
		"csv": _export_csv(columns, found),
		"rows": len(found),
		"columns": [one["label"] for one in columns],
		"capped": capped,
		"limit": MAX_EXPORT,
	}


def _export_names(names) -> list[str]:
	"""The selection, if there is one, as a list of ids and nothing else."""
	if isinstance(names, str):
		try:
			names = frappe.parse_json(names or "null")
		except (TypeError, ValueError):
			return []
	if not isinstance(names, list):
		return []
	return [one for one in names if isinstance(one, str) and one]


def _export_columns(resolved: dict) -> list[dict]:
	"""The reader's own columns, minus the one that is not a field.

	Activity is a rendering of four different things — when it changed, who is
	on it, how many comments — and there is no cell for it in a spreadsheet.
	"""
	return [
		one for one in resolved.get("columns") or []
		if one.get("fieldname") and one["fieldname"] != META_COLUMN
	]


def _export_csv(columns: list[dict], rows: list[dict]) -> str:
	"""Header labels, then the values, quoted by the standard library."""
	sink = io.StringIO()
	# `\r\n` and `QUOTE_MINIMAL`, which is what every spreadsheet expects and
	# what `csv` does by default. Named here so nobody has to check.
	writer = csv.writer(sink, lineterminator="\r\n")
	writer.writerow([one["label"] for one in columns])
	for row in rows:
		writer.writerow([_export_cell(row.get(one["fieldname"])) for one in columns])
	return EXCEL_BOM + sink.getvalue()


def _export_cell(value) -> str:
	"""One value, as text.

	`None` is an empty cell rather than the word "None", and a Check is 0 or 1
	rather than True or False — both of those are what a spreadsheet reads back
	as the thing it was. Everything else is already a string, a number or a
	date, and `str` is the right answer for all three.
	"""
	if value is None:
		return ""
	if isinstance(value, bool):
		return "1" if value else "0"
	return str(value)


# Anything a filesystem or a Content-Disposition header would argue about.
UNSAFE_IN_FILENAME = re.compile(r"[^\w\- ]+", re.UNICODE)


def _export_filename(resolved: dict) -> str:
	"""What the file is called when it lands in somebody's downloads.

	The screen's label and the date, because a folder with four files called
	`export.csv` in it is a folder with one usable file in it.
	"""
	label = UNSAFE_IN_FILENAME.sub("", str(resolved.get("screen_label") or "Export")).strip()
	return f"{label or 'Export'} {frappe.utils.nowdate()}.csv"
