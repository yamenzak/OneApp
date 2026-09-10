"""One box that asks every column, and a filter that reaches a child table.

Two of the three things §13 said the list could not do. Both are about the
same seam — what a browser may ask of a screen — and both are bounded the same
way: only the columns the screen shows, because watching which rows come back
is a way of reading a field you were never given.
"""

import importlib
import sys
import types

import pytest


SCREEN = {
	"doctype": "Quotation",
	"all_columns": [
		{"fieldname": "customer_name", "label": "Customer", "fieldtype": "Data"},
		{"fieldname": "status", "label": "Status", "fieldtype": "Select"},
		{"fieldname": "grand_total", "label": "Total", "fieldtype": "Currency"},
		{"fieldname": "valid_till", "label": "Valid till", "fieldtype": "Date"},
		{"fieldname": "secret", "label": "Secret", "fieldtype": "Password"},
	],
	"child_columns": [
		{"fieldname": "items.item_code", "label": "Items → Item Code",
		 "fieldtype": "Data", "child_doctype": "Quotation Item",
		 "child_fieldname": "item_code"},
	],
}


@pytest.fixture
def filters(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onespace.spaceview.filters")


def searched(filters, text, screen=None):
	return filters._search_filters({**(screen or SCREEN), "search": text})


# --------------------------------------------------------------------------- #
# The search box
# --------------------------------------------------------------------------- #

def test_nothing_typed_narrows_nothing(filters):
	assert searched(filters, "") == []
	assert searched(filters, "   ") == []
	assert filters._search_filters(SCREEN) == []


def test_the_id_is_asked_first(filters):
	"""It is what people paste, and a screen with eleven text columns would
	otherwise spend the budget before reaching it."""
	assert searched(filters, "Q-1")[0] == ["name", "like", "%Q-1%"]


def test_only_columns_whose_fieldtype_takes_like(filters):
	"""The same generated table the filter menu is built from, so a search
	reaches exactly the fields somebody could have filtered one at a time."""
	named = [one[0] for one in searched(filters, "hall")]
	assert named == ["name", "customer_name"]
	# A Currency and a Date have no `like`: `%hall%` against them is a scan
	# that cannot match.
	assert "grand_total" not in named and "valid_till" not in named


def test_a_password_column_is_never_searched(filters):
	"""It holds ciphertext, so the `like` matches nothing and costs the scan."""
	assert "secret" not in [one[0] for one in searched(filters, "hall")]


def test_a_child_field_stays_out_of_the_search(filters):
	"""`or_filters` has no four-part form, so a child field cannot join the OR.
	Left out rather than half-searched."""
	assert "items.item_code" not in [one[0] for one in searched(filters, "hall")]


def test_the_reach_is_bounded(filters):
	"""Each column in the OR is a scan, so this is a cost and not tidiness."""
	wide = {**SCREEN, "all_columns": [
		{"fieldname": f"f{n}", "label": f"F{n}", "fieldtype": "Data"} for n in range(30)
	]}
	assert len(searched(filters, "hall", wide)) == filters.MAX_SEARCH_COLUMNS


def test_a_pasted_search_is_one_line_of_it(filters):
	"""Out of a spreadsheet it arrives with a tab in it, and `%a\\tb%` matches
	nothing while looking as though it should."""
	assert searched(filters, "  Al\tIttihad \n")[0][2] == "%Al Ittihad%"


def test_a_very_long_paste_is_cut(filters):
	found = searched(filters, "x" * 500)
	assert len(found[0][2]) == filters.MAX_SEARCH_LENGTH + 2  # the two wildcards


# --------------------------------------------------------------------------- #
# A filter on a child table
# --------------------------------------------------------------------------- #

def asked(filters, row):
	offered = filters._filterable(SCREEN)
	return filters._as_query_filters(offered, filters._asked_filters(offered, [row]))


def test_a_child_field_is_offered_under_a_dotted_key(filters):
	offered = filters._filterable(SCREEN)
	assert "items.item_code" in offered
	assert offered["items.item_code"]["child_doctype"] == "Quotation Item"


def test_a_child_filter_comes_out_as_the_four_part_form(filters):
	"""Frappe joins the child table itself when told which one. A three-part
	filter naming `item_code` looks for that column on the parent, which does
	not have it — which is what this whole key shape exists to fix."""
	assert asked(filters, ["items.item_code", "=", "CEM-42"]) == [
		["Quotation Item", "item_code", "=", "CEM-42"],
	]


def test_a_parent_field_is_still_three_parts(filters):
	assert asked(filters, ["status", "=", "Open"]) == [["status", "=", "Open"]]


def test_a_child_filter_goes_through_the_same_checks(filters):
	"""Its fieldtype's operators and its value's shape, like every other. A
	`like` gets its wildcards here too."""
	assert asked(filters, ["items.item_code", "like", "CEM"]) == [
		["Quotation Item", "item_code", "like", "%CEM%"],
	]
	assert asked(filters, ["items.item_code", "descendants of", "x"]) == []


def test_a_dotted_key_nothing_declared_is_dropped(filters):
	"""The dot is not a way in: the key has to be one the screen offered."""
	assert asked(filters, ["items.cost_centre", "=", "x"]) == []


# --------------------------------------------------------------------------- #
# Where the two travel together
# --------------------------------------------------------------------------- #

@pytest.fixture
def records(stub_frappe, filters):
	module = importlib.import_module("oneapp.onespace.spaceview.records")
	module.frappe.get_list = lambda *a, **k: []
	return module


def test_the_pair_travels_as_one(records):
	"""`filters` and `or_filters` are different questions and have to arrive
	together: a count that took only the first would label a searched list with
	an unsearched number."""
	asked_for = records._query({**SCREEN, "search": "hall", "asked": []})
	assert set(asked_for) == {"filters", "or_filters"}
	assert asked_for["or_filters"][0] == ["name", "like", "%hall%"]


def test_extra_filters_join_the_and_half(records):
	asked_for = records._query({**SCREEN, "asked": []}, [["docstatus", "=", 1]])
	assert ["docstatus", "=", 1] in asked_for["filters"]
	assert asked_for["or_filters"] == []
