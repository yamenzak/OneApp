"""What a child table will accept, said in the sheet and enforced at the pull.

A grid holds anything. `TBC` in a quantity column, `Widgt` where the item is
`Widget`, a line somebody meant to come back to — all three used to reach
`target.save()`, and what came back was one of Frappe's own exceptions: about
one row, in the framework's words, and thrown after the child table had
already been replaced.

Three claims are worth pinning.

**The sheet stops what it can while somebody types.** `for_columns` turns the
child doctype's own fields into the browser engine's validation rules, which
is a slice of the stored workbook — so a Select gets the same dropdown the
form has and nothing in the browser had to change.

**The server stops what only it can know.** Whether a link is a document,
whether a Select option is one of the doctype's, whether `TBC` is about to be
priced at zero. Not whether a mandatory field was filled: a controller fills
half of those itself, and the check that tried refused every real quotation.

**Nothing is written until everything is checked.** One refusal naming every
bad cell, before the document is touched.
"""

import sys
import types

import pytest


@pytest.fixture
def stubbed(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]
	stub_frappe.clear_last_message = lambda: None
	return stub_frappe


@pytest.fixture
def rules(stubbed):
	stubbed._meta = {"Quotation Item": meta(LINE)}
	stubbed.db.exists = lambda doctype, name=None: True
	stubbed.has_permission = lambda *a, **k: True
	stubbed.get_list = lambda doctype, **kw: []
	stubbed.get_all = lambda doctype, **kw: []

	from oneapp.onesheet import rules as module

	return module


def field(**kw):
	one = {"fieldname": "", "label": "", "fieldtype": "Data", "options": "",
	       "reqd": 0, "default": "", "non_negative": 0}
	one.update(kw)
	got = types.SimpleNamespace(**one)
	got.get = lambda key, _one=one: _one.get(key)
	return got


def meta(fields):
	return types.SimpleNamespace(fields=list(fields))


LINE = [
	field(fieldname="item_code", label="Item", fieldtype="Link",
	      options="Item", reqd=1),
	field(fieldname="qty", label="Quantity", fieldtype="Float", non_negative=1),
	field(fieldname="rate", label="Rate", fieldtype="Currency"),
	field(fieldname="uom", label="UOM", fieldtype="Select", options="\nNos\nMtr\nKg"),
	field(fieldname="stocked", label="Stocked", fieldtype="Check"),
	field(fieldname="note", label="Note", fieldtype="Data"),
]

#: `feed._columns`'s answer for a sheet whose headings match the child.
COLUMNS = [
	{"index": 0, "header": "Item", "unit": "", "fieldname": "item_code",
	 "fieldtype": "Link"},
	{"index": 1, "header": "Quantity", "unit": "", "fieldname": "qty",
	 "fieldtype": "Float"},
	{"index": 2, "header": "Rate", "unit": "", "fieldname": "rate",
	 "fieldtype": "Currency"},
	{"index": 3, "header": "UOM", "unit": "", "fieldname": "uom",
	 "fieldtype": "Select"},
]


# --------------------------------------------------------------------------- #
# What the sheet is told
# --------------------------------------------------------------------------- #

def test_a_select_becomes_the_dropdown_the_form_has(rules):
	found = rules.for_columns("Quotation Item", ["uom"])
	assert found[0]["type"] == "list"
	# The blank first option goes: the engine does not validate an empty cell,
	# so a blank entry in the dropdown would be a row that does nothing.
	assert found[0]["options"] == ["Nos", "Mtr", "Kg"]
	assert found[0]["severity"] == "reject"


def test_a_number_column_refuses_a_word(rules):
	found = rules.for_columns("Quotation Item", ["rate"])
	assert found[0]["type"] == "number"


def test_non_negative_is_the_one_bound_a_doctype_gives(rules):
	found = rules.for_columns("Quotation Item", ["qty"])
	assert (found[0]["operator"], found[0]["min"]) == ("gte", 0)


def test_a_check_is_a_tickbox(rules):
	assert rules.for_columns("Quotation Item", ["stocked"])[0]["type"] == "checkbox"


def test_a_plain_text_column_gets_no_rule(rules):
	"""A rule saying "this holds text" is a rule that only gets in the way."""
	assert rules.for_columns("Quotation Item", ["note"]) == {}


def test_a_short_link_target_becomes_a_dropdown(rules, stubbed):
	stubbed.get_list = lambda doctype, **kw: ["WIDGET-1", "WIDGET-2"]
	found = rules.for_columns("Quotation Item", ["item_code"])
	assert found[0]["options"] == ["WIDGET-1", "WIDGET-2"]


def test_a_link_target_nobody_could_pick_from_gets_no_rule(rules, stubbed):
	"""Half a list is worse than none: a rule that rejects a valid item
	because it was the two hundred and first is a rule to work around."""
	stubbed.get_list = lambda doctype, **kw: [f"I-{n}" for n in range(500)]
	assert rules.for_columns("Quotation Item", ["item_code"]) == {}


def test_the_dropdown_is_what_this_person_could_pick(rules, stubbed):
	"""`get_list`, so User Permissions narrow it the way the form's own
	picker is narrowed. The check below asks a different question."""
	asked = {}
	stubbed.get_list = lambda doctype, **kw: asked.setdefault("with", kw) and []
	stubbed.has_permission = lambda *a, **k: False
	assert rules.for_columns("Quotation Item", ["item_code"]) == {}


# --------------------------------------------------------------------------- #
# What the server refuses
# --------------------------------------------------------------------------- #

def test_a_link_that_is_not_a_document_is_named(rules, stubbed):
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1"]
	found = rules.check("Quotation Item", COLUMNS,
	                    [["WIDGET-1", 2, 10, "Nos"], ["WIDGET-9", 1, 5, "Nos"]])
	assert len(found) == 1
	# The row as the person sees it: the heading is row 1, so the second body
	# line is row 3.
	assert "Row 3" in found[0] and "WIDGET-9" in found[0]


def test_every_link_column_is_one_query(rules, stubbed):
	"""A hundred lines naming twenty items is twenty rows out of the
	database, not two thousand."""
	asked = []
	stubbed.get_all = lambda doctype, **kw: asked.append(kw) or ["W-1"]
	rules.check("Quotation Item", COLUMNS, [["W-1", 1, 1, "Nos"]] * 100)
	assert len(asked) == 1


def test_whether_a_mandatory_field_was_filled_is_left_to_the_save(rules, stubbed):
	"""The one thing here that reads as obvious and cannot be known.

	`Quotation Item` marks `item_name`, `uom` and `conversion_factor`
	required and puts none of them in the grid, because ERPNext fills all
	three from the item code in `validate` — in Python, not through a
	`fetch_from` this could read. A pre-flight mandatory check refused every
	real quotation, which is how this rule came to be dropped.
	"""
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1"]
	# A blank in a required column, and a required column that is not there
	# at all. Neither is a problem this can see.
	assert rules.check("Quotation Item", COLUMNS, [["", 2, 10, "Nos"]]) == []
	without = [{**one, "index": at} for at, one in
	           enumerate(c for c in COLUMNS if c["fieldname"] != "item_code")]
	assert rules.check("Quotation Item", without, [[1, 10, "Nos"]] * 20) == []


def test_a_word_in_a_number_column_is_not_quietly_zero(rules, stubbed):
	"""`feed.number` forgives `AED 1,234.50` and answers 0.0 for anything it
	cannot read. A quantity of `TBC` priced at zero is worse than a refusal."""
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1"]
	found = rules.check("Quotation Item", COLUMNS,
	                    [["WIDGET-1", "TBC", 10, "Nos"]])
	assert len(found) == 1 and "not a number" in found[0]


def test_a_number_that_really_is_zero_is_allowed(rules, stubbed):
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1"]
	for written in ("0", "0.00", " 0 ", "0,000"):
		assert rules.check("Quotation Item", COLUMNS,
		                   [["WIDGET-1", written, 10, "Nos"]]) == [], written


def test_money_a_person_typed_is_still_a_number(rules, stubbed):
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1"]
	assert rules.check("Quotation Item", COLUMNS,
	                   [["WIDGET-1", 2, "AED 1,234.50", "Nos"]]) == []


def test_a_select_outside_its_options_is_named(rules, stubbed):
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1"]
	found = rules.check("Quotation Item", COLUMNS,
	                    [["WIDGET-1", 2, 10, "Furlongs"]])
	assert len(found) == 1 and "Furlongs" in found[0]


def test_a_good_block_says_nothing(rules, stubbed):
	stubbed.get_all = lambda doctype, **kw: ["WIDGET-1", "WIDGET-2"]
	assert rules.check("Quotation Item", COLUMNS, [
		["WIDGET-1", 2, 10, "Nos"],
		["WIDGET-2", 1.5, "AED 4,000.00", "Mtr"],
	]) == []


def test_a_refusal_stops_naming_rows_eventually(rules, stubbed):
	"""A message longer than a screen is a message nobody reads."""
	stubbed.get_all = lambda doctype, **kw: []
	found = rules.check("Quotation Item", COLUMNS,
	                    [["WIDGET-9", 1, 1, "Nos"]] * 200)
	assert len(found) == rules.MAX_PROBLEMS + 1
	assert "and more" in found[-1]


def test_a_link_to_a_doctype_this_site_lacks_is_left_to_the_save(rules, stubbed):
	"""Not this module's problem to report, and not a reason to refuse: the
	save will say so, in the framework's own words."""
	def missing(doctype, **kw):
		raise Exception("DocType Item not found")

	stubbed.get_all = missing
	assert rules.check("Quotation Item", COLUMNS,
	                   [["WIDGET-1", 2, 10, "Nos"]]) == []


# --------------------------------------------------------------------------- #
# What a fed sheet is born with
# --------------------------------------------------------------------------- #

@pytest.fixture
def feed(rules, stubbed):
	from oneapp.onesheet import feed as module

	return module


GRID = [{"fieldname": "item_code", "label": "Item"},
        {"fieldname": "qty", "label": "Quantity"},
        {"fieldname": "uom", "label": "UOM"}]


def test_the_headings_are_protected_and_nothing_else_is(feed):
	"""They are the contract — `_columns` matches them back to fields at the
	pull — so a heading renamed by accident is a column silently left out,
	found when the quotation comes back short."""
	seeded = feed._seeded("Quotation Item", GRID, [["W-1", 1, "Nos"]])
	ranges = seeded["protection"]["Sheet1"]["ranges"]

	assert seeded["protection"]["Sheet1"]["locked"] is False
	assert len(ranges) == 1
	# Row 1 only, across every column there is.
	assert (ranges[0]["r0"], ranges[0]["r1"]) == (0, 0)
	assert (ranges[0]["c0"], ranges[0]["c1"]) == (0, len(GRID) - 1)
	# And it says why, because a cell that refuses an edit without a reason
	# is a cell somebody files a bug about.
	assert "another tab" in ranges[0]["description"]


def test_only_this_tab_is_protected(feed):
	"""The estimator's working goes on tabs they add, and protection is
	per-sheet — so adding one gives them a grid with no rules on it at all."""
	seeded = feed._seeded("Quotation Item", GRID, [])
	assert list(seeded["protection"].keys()) == ["Sheet1"]


def test_the_rules_start_under_the_headings(feed, stubbed):
	stubbed.get_list = lambda doctype, **kw: ["W-1"]
	cells = feed._seeded("Quotation Item", GRID, [["W-1", 1, "Nos"]])["validation"]["Sheet1"]

	# A1 is a heading and has no rule; A2 is the first line.
	assert "A1" not in cells
	assert cells["A2"]["type"] == "list"
	assert cells["C2"]["options"] == ["Nos", "Mtr", "Kg"]


def test_the_rules_run_past_the_last_row_somebody_has(feed):
	"""Because the next thing they do is add lines, and a column whose rule
	stops at the last row is a dropdown that disappears."""
	cells = feed._seeded("Quotation Item", GRID, [["W-1", 1, "Nos"]])["validation"]["Sheet1"]
	assert f"C{1 + feed.SPARE_ROWS}" in cells


def test_a_child_with_nothing_worth_a_rule_seeds_no_validation(feed, stubbed):
	stubbed._meta = {"Quotation Item": meta([
		field(fieldname="note", label="Note", fieldtype="Data")])}
	seeded = feed._seeded("Quotation Item", [{"fieldname": "note", "label": "Note"}], [])
	assert "validation" not in seeded
	# The headings are still the contract, whatever the columns hold.
	assert "protection" in seeded
