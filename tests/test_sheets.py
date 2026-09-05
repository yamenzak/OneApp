"""A spreadsheet, over the file table every attachment already lives in.

Four things are worth holding here, and the first is the one the whole design
rests on.

**A sheet is a `File`.** Not a doctype of its own — so its permission, its
folder, its share, its bin and its link are all things that already existed.
Every read and write in `oneapp_core/sheets` goes through the File, and a path
that did not would be a path with no access model at all.

**A1 notation is implemented twice**, once in Python and once in JavaScript,
because the browser needs to name a cell on every keystroke and cannot ask. Two
implementations of the same rules drift, so the limits are read out of both and
compared here.

**The server never evaluates a formula.** `Sheet Cell` stores `raw` beside
`value` and every read hands back `value`. A read that reached for `raw` would
be a print format showing `=A2*B2` on an invoice.

**The read-back replaces.** A pull is "the sheet is the truth now", and an
append would silently double a quotation on a second press.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "apps/oneapp/oneapp/oneapp_core/sheets"
FRONTEND = ROOT / "apps/oneapp/frontend/src/lib/sheets"


@pytest.fixture
def sheets():
	from oneapp.oneapp_core import sheets as module

	return module


# --------------------------------------------------------------------------- #
# A1 notation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("letters,number", [
	("A", 1), ("B", 2), ("Z", 26), ("AA", 27), ("AZ", 52), ("BA", 53), ("ZZ", 702),
])
def test_a_column_letter_is_a_number(sheets, letters, number):
	assert sheets.column_number(letters) == number
	assert sheets.column_letters(number) == letters


@pytest.mark.parametrize("ref,expected", [
	("A1", (1, 1)),
	("B3", (3, 2)),
	("AA10", (10, 27)),
	("zz1", (1, 702)),
])
def test_a_ref_is_a_row_and_a_column(sheets, ref, expected):
	assert sheets.parse(ref) == expected


@pytest.mark.parametrize("bad", ["A0", "1A", "AAAA1", "", "A", "1", "A-1", "A 1", "A$"])
def test_a_ref_that_is_not_one_is_refused(sheets, bad):
	with pytest.raises(sheets.BadRef):
		sheets.parse(bad)


@pytest.mark.parametrize("typed,stored", [
	("$A$1", "A1"), ("A$1", "A1"), ("$b3", "B3"), (" c10 ", "C10"), ("aa2", "AA2"),
])
def test_a_pasted_absolute_reference_is_stored_one_way(sheets, typed, stored):
	"""Excel writes `$A$1` and people paste it.

	Accepted, and normalised on the way in: two rows for `A1` and `$A$1` is one
	cell holding two values, and every lookup in this package is by the stored
	string.
	"""
	assert sheets.canonical(typed) == stored


def test_a_range_sorts_its_corners(sheets):
	"""Dragging up and to the left selects the same rectangle as dragging down."""
	assert sheets.parse_range("C10:A1") == (1, 1, 10, 3)
	assert sheets.parse_range("A1:C10") == (1, 1, 10, 3)


def test_a_single_cell_is_a_range_of_one(sheets):
	assert sheets.parse_range("B2") == (2, 2, 2, 2)


def test_within_answers_for_the_rectangle_not_the_row(sheets):
	assert sheets.within("B2", "A1:C3")
	assert not sheets.within("D2", "A1:C3")
	assert not sheets.within("B4", "A1:C3")


# --------------------------------------------------------------------------- #
# The two implementations
# --------------------------------------------------------------------------- #

def _js_number(name: str) -> int:
	"""A `const NAME = 123` or `123_456` out of the browser's refs module."""
	source = (FRONTEND / "refs.js").read_text()
	found = re.search(rf"export const {name} = ([\d_]+)", source)
	assert found, f"lib/sheets/refs.js has no {name}"
	return int(found.group(1).replace("_", ""))


@pytest.mark.parametrize("name", ["MAX_COLUMN", "MAX_ROW", "MAX_CELLS"])
def test_both_implementations_of_a1_agree_about_the_limits(sheets, name):
	"""The browser and the server refuse the same references.

	Two implementations, because the grid names a cell on every keystroke and
	cannot ask the server what `AA10` means. Two implementations drift — the
	failure being guarded against is a browser that happily writes `A200000`
	into a sheet the server will refuse to store.
	"""
	assert _js_number(name) == getattr(sheets, name, None) or _js_number(name) == {
		"MAX_COLUMN": sheets.refs.MAX_COLUMN,
		"MAX_ROW": sheets.refs.MAX_ROW,
		"MAX_CELLS": sheets.refs.MAX_CELLS,
	}[name]


# --------------------------------------------------------------------------- #
# The read-back
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text,expected", [
	("Width [mm]", ("Width", "mm")),
	("Height [ mm ]", ("Height", "mm")),
	("Rate [AED/m2]", ("Rate", "AED/m2")),
	("Qty", ("Qty", "")),
	("  Item Name  ", ("Item Name", "")),
	("", ("", "")),
])
def test_a_heading_may_carry_its_unit(sheets, text, expected):
	"""RUA's convention, kept because one template then serves two jobs.

	A job quoted in millimetres and one quoted in metres use the same estimator
	and the same named range; only the heading changes.
	"""
	assert sheets.header(text) == expected


@pytest.mark.parametrize("value,expected", [
	("1234.5", 1234.5),
	("1,234.50", 1234.5),
	("AED 1,234.50", 1234.5),
	("-12", -12.0),
	(1234.5, 1234.5),
	(7, 7.0),
	("", 0.0),
	(None, 0.0),
	("not a number", 0.0),
	("-", 0.0),
])
def test_a_formatted_number_is_still_a_number(sheets, value, expected):
	"""Everything here is something a person types into a spreadsheet."""
	assert sheets.number(value) == expected


# --------------------------------------------------------------------------- #
# The access model
# --------------------------------------------------------------------------- #

def test_every_entry_point_goes_through_the_file(sheets):
	"""A sheet's permission is its File's, and there is no second answer.

	`Sheet Cell` is granted to System Manager only and has no rules of its own,
	so a whitelisted function that reached the cells without asking the File
	first would hand every reader every sheet on the site.
	"""
	source = "\n".join(
		(SHEETS / name).read_text()
		for name in ("reading.py", "writing.py", "export.py", "feed.py", "templates.py")
	)
	entries = re.findall(r"@frappe\.whitelist\([^)]*\)\ndef (\w+)\(", source)
	assert entries, "no whitelisted functions found — the scan is broken"

	# `make` is the one that cannot: it creates the File rather than opening
	# one, so there is nothing yet to ask about. The framework's own create
	# check on `File.insert()` is what guards it, plus a `write` check on the
	# record being attached to.
	MAKES = {"make"}

	# And these three are not about a sheet at all. `Sheet Feed` records that a
	# document's rows came off a spreadsheet, and the permission that governs
	# it is the *document's* — a row saying "this quotation was filled from
	# that estimator" is as private as the quotation, and no more. Each checks
	# `frappe.has_permission` on the reference, which the sweep below cannot
	# tell apart from checking nothing.
	ABOUT_A_DOCUMENT = {"feeds", "lock", "unlock"}

	bodies = re.split(r"@frappe\.whitelist\([^)]*\)\ndef ", source)[1:]
	unguarded = [
		body.split("(")[0]
		for body in bodies
		if body.split("(")[0] not in MAKES | ABOUT_A_DOCUMENT
		and "_mine(" not in body
		and "check_permission" not in body
		and "get_list" not in body
	]
	assert not unguarded, (
		"these reach a sheet without asking its File first: " + ", ".join(unguarded)
	)


def test_the_cells_are_never_read_with_get_all_without_a_file_check(sheets):
	"""`get_all` ignores permissions, which is fine here and only here.

	Every `get_all` in this package sits after `_mine`, which has already
	thrown if the reader cannot have the File. Stated as a test because the
	next person adding a function will copy an existing one.
	"""
	for name in ("reading.py", "writing.py", "export.py", "feed.py"):
		source = (SHEETS / name).read_text()
		if "get_all(" not in source:
			continue
		assert "_mine(" in source or "check_permission" in source, (
			f"{name} reads cells with get_all and never checks the File"
		)


def test_the_server_hands_back_value_and_never_raw(sheets):
	"""A print format wants `6480`, not `=C2*D2*E2*F2/1000000`."""
	source = (SHEETS / "reading.py").read_text()
	block = source[source.index("def read_range"):]
	assert '"value"' in block
	assert '"raw"' not in block

	export = (SHEETS / "export.py").read_text()
	assert '"value"' in export and '"raw"' not in export


def test_a_pull_replaces_rather_than_appends(sheets):
	"""Pressing it twice must not double the quotation."""
	source = (SHEETS / "feed.py").read_text()
	block = source[source.index("def pull("):]
	# The list is emptied before anything is appended to it.
	assert block.index("target.set(into, [])") < block.index("target.append(into")


def test_a_sheets_file_url_is_a_url_the_framework_accepts(sheets):
	"""`File.validate` refuses a row whose URL names nothing.

	Its own exception for a file whose bytes are produced rather than stored is
	a `/api/method/` URL, and a sheet's bytes are produced. Guarded because the
	first version pointed `file_url` at the viewer route, which inserted fine
	and then threw on the next save of the row — a rename, a move, a trash.
	"""
	assert sheets.ROUTE.startswith("/api/method/")
	assert sheets.url_for("abc123").startswith("/api/method/")
	assert "abc123" in sheets.url_for("abc123")


def test_the_feed_endpoints_ask_the_document(sheets):
	"""The three that do not ask a File must ask the document instead.

	Exempting them from the sweep above is only safe if something says what
	they do ask, which is this.
	"""
	source = (SHEETS / "feed.py").read_text()
	for name in ("def feeds(", "def _set_status("):
		block = source[source.index(name):]
		head = block[:block.index("frappe.get_all") if "frappe.get_all" in block[:900] else 900]
		assert "has_permission" in head, f"{name.strip('def (')} does not check the document"


def test_a_locked_table_refuses_a_pull(sheets):
	"""What locking is for: after it, the document is the record.

	A pull that went through anyway would be a spreadsheet quietly overwriting
	a quotation somebody has since corrected by hand — which is the failure
	RUA's lock existed to prevent.
	"""
	source = (SHEETS / "feed.py").read_text()
	block = source[source.index("def pull("):]
	# The refusal comes before anything is read out of the sheet.
	assert "LOCKED" in block[:block.index("read_range(")]


def test_a_feed_says_whether_the_sheet_has_moved_on(sheets):
	"""Nothing pushes, so the only thing left is finding out.

	A sheet does not update a document — somebody presses Fill again — and that
	is the design rather than a gap: a spreadsheet that could reprice a
	quotation after it was sent would make locking the thing you must remember
	rather than the thing you choose. What is owed instead is a signal, and it
	costs one comparison and no new storage.
	"""
	source = (SHEETS / "feed.py").read_text()
	block = source[source.index("def _with_freshness("):]
	head = block[:block.index("\ndef ", 1) if "\ndef " in block[1:] else len(block)]

	# `File.modified`, which `writing._touch` stamps on every cell written.
	assert '"File"' in head and "modified" in head
	assert '"stale"' in head and '"sheet_gone"' in head

	# Both sides normalised: one of them is a string when the row was just
	# written, and comparing a datetime with a string raises.
	assert head.count("get_datetime") >= 2


def test_nothing_re_pulls_on_its_own(sheets):
	"""A cell write must not reach into a document.

	Stated as a test because "make it live" is the obvious next feature and the
	wrong one — and the place it would be written is `write_cells`.
	"""
	# Comments stripped: `on_trash` explains in prose that `Sheet Feed`
	# deliberately survives a sheet being deleted, and saying so is not doing
	# it.
	source = re.sub(r"#[^\n]*", "", (SHEETS / "writing.py").read_text())
	for reaching in ("pull(", "Sheet Feed", "reference_doctype"):
		assert reaching not in source, (
			f"writing.py reaches for {reaching} — a sheet does not update a document"
		)


def test_the_one_download_funnel_knows_about_sheets(sheets):
	"""Every download and every share link goes through `r2.serve`.

	It asks the File for its bytes, and a sheet has none — so downloading a
	sheet, and any stranger following a link to one, answered 500. Found by a
	browser pass over the Drive rather than by anything here, because nothing
	about either module read wrongly on its own.
	"""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/storage/r2.py").read_text()
	block = source[source.index("def serve("):]
	# The call, not the sentence about it — the comment above the branch names
	# `get_content()` too.
	head = block[:block.index("doc.get_content()")]
	assert "custom_kind" in head and "Sheet" in head, (
		"r2.serve reaches get_content() without a branch for a sheet"
	)
	assert hasattr(sheets, "to_response") or hasattr(sheets.export, "to_response")


def test_renaming_a_sheet_leaves_it_a_sheet(sheets):
	"""The Drive re-derives a file's kind from its new name, and must not here.

	`kind_of` reads an extension, and "Padel Pro estimator" has none — so a
	rename turned every sheet into `Other`, and the next attempt to open one
	said "That file is not a sheet." Found by renaming one in a browser; not
	findable any other way, because nothing about the two modules apart is
	wrong.
	"""
	from oneapp.oneapp_core.drive import kind_of

	assert kind_of("Padel Pro estimator", False, "Sheet") == "Sheet"
	assert kind_of("estimator.xlsx", False, "Sheet") == "Sheet"
	# Everything else still follows the name, which is the behaviour being
	# kept rather than lost.
	assert kind_of("notes.pdf", False, "Other") == "PDF"
	assert kind_of("notes", False, "PDF") == "Other"


def test_the_package_re_exports_everything_it_whitelists(sheets):
	"""`oneapp.oneapp_core.sheets.open_sheet` has to resolve, or it is a 404.

	A whitelisted function inside a package module is not reachable by the
	package's own path unless the package re-exports it. This is the same bug
	that made the Drive's Recents empty for a week.
	"""
	source = "\n".join((SHEETS / p.name).read_text() for p in SHEETS.glob("*.py"))
	for name in re.findall(r"@frappe\.whitelist\([^)]*\)\ndef (\w+)\(", source):
		assert hasattr(sheets, name), (
			f"sheets.{name} is whitelisted but not re-exported — it would 404"
		)
