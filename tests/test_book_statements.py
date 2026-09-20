"""The three statements a set of books exists to produce.

`docs/ONEBOOK.md` stage 1. OneBook shipped with twenty-one screens, a ledger
and no way to answer "what did we earn" — the gap the retrospective after
`docs/CLEANUP.md` stage 13 named first.

The reports are ERPNext's, called rather than copied, so what is ours and what
these check is the three things around them: an allowlist of which reports may
be run at all, filters filled from the workspace rather than from a form, and
one payload shape for all three so `Statement.vue` draws any of them.

Building this found the fixture's revenue sitting in **Exchange Gain** — the
first Income leaf in ERPNext's chart, which is what the seeder's old fallback
picked — and its supplier bills in **Exchange Loss** and **Payroll Payable**.
A year of that was invisible, because a list of invoices shows the customer and
the total and never the account. It took a profit and loss to see it, which is
the argument for this stage in one sentence.
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onebook/statements.py"
SCREEN = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/onebook/Statement.vue"
REGISTRY = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
MANIFEST = ROOT / "apps/oneapp_control/oneapp_control/spaces/onebook.py"


@pytest.fixture
def statements(stub_frappe):
	from oneapp.onebook import statements as module

	return module


def declared():
	import importlib.util

	spec = importlib.util.spec_from_file_location("books_manifest", MANIFEST)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


# --------------------------------------------------------------------------- #
# A. The allowlist
# --------------------------------------------------------------------------- #

def test_only_three_reports_may_be_run(statements):
	assert set(statements.REPORTS) == {
		"trial-balance", "profit-and-loss", "balance-sheet"}


def test_a_report_nobody_declared_is_refused(statements):
	"""A whitelisted endpoint that ran any report by name would run
	`Bisect Accounting Statements` and everything else ERPNext ships, against a
	filter dictionary a caller composed."""
	with pytest.raises(Exception):
		statements.statement("bisect-accounting-statements")


def test_every_report_names_a_module_in_erpnext(statements):
	for kind, one in statements.REPORTS.items():
		assert one["module"].startswith("erpnext.accounts.report."), kind


def test_the_ledger_is_the_permission(statements):
	"""A statement reads every posting in the company, so this is not a
	formality — and it is the only check, because a report is not a list and
	none of the list machinery runs."""
	source = SOURCE.read_text()
	assert 'frappe.has_permission("GL Entry", "read")' in source
	assert "PermissionError" in source


# --------------------------------------------------------------------------- #
# B. One shape for all three
# --------------------------------------------------------------------------- #

COLUMNS = [
	{"fieldname": "account", "label": "Account", "fieldtype": "Link"},
	{"fieldname": "acc_name", "label": "Account Name", "fieldtype": "Data"},
	{"fieldname": "currency", "label": "Currency", "fieldtype": "Link"},
	{"fieldname": "dec_2026", "label": "2026", "fieldtype": "Currency"},
]


def test_only_the_money_columns_survive(statements):
	"""The account, its name, its number and its currency are on every row
	already. A payload repeating them as columns is four columns of chrome in
	front of the one that is a number."""
	found = statements._shape(COLUMNS, [])
	assert [one["key"] for one in found["columns"]] == ["dec_2026"]
	assert found["columns"][0]["label"] == "2026"


def test_a_row_carries_its_indent_and_its_values(statements):
	rows = statements._shape(COLUMNS, [
		{"account": "Income - ZZN", "account_name": "Income", "indent": 0.0,
		 "parent_account": "", "currency": "AED", "dec_2026": 430000.0},
	])["rows"]
	assert rows == [{
		"kind": "account", "account": "Income - ZZN", "label": "Income",
		"indent": 0, "is_group": False, "currency": "AED",
		"values": [430000.0],
	}]


def test_a_blank_row_is_kept_as_a_gap(statements):
	"""ERPNext's own section break, and the only thing separating income from
	expenses on a profit and loss. Dropping it would put the cost base
	immediately under the revenue with no line between them."""
	rows = statements._shape(COLUMNS, [None, {}])["rows"]
	assert [one["kind"] for one in rows] == ["gap", "gap"]


def test_a_total_is_marked_rather_than_dropped(statements):
	"""ERPNext appends them with no parent and no indent, and quotes the
	label. A statement without its totals is a list of accounts."""
	rows = statements._shape(COLUMNS, [
		{"account": "'Total Income (Credit)'",
		 "account_name": "'Total Income (Credit)'", "currency": "AED",
		 "dec_2026": 430000.0},
	])["rows"]
	assert rows[0]["kind"] == "total"
	assert rows[0]["label"] == "Total Income (Credit)", "the quotes are ERPNext's"


def test_a_group_row_says_so(statements):
	rows = statements._shape(COLUMNS, [
		{"account": "Income - ZZN", "account_name": "Income", "indent": 0.0,
		 "parent_account": "", "is_group": 1, "currency": "AED"},
	])["rows"]
	assert rows[0]["is_group"] is True


# --------------------------------------------------------------------------- #
# C. The filters, which are the workspace's facts rather than a form's
# --------------------------------------------------------------------------- #

def test_a_trial_balance_and_a_period_report_want_different_filters(statements):
	year = {"name": "2026", "year_start_date": "2026-01-01",
	        "year_end_date": "2026-12-31"}
	stub_company = "zz"

	period = statements._filters("profit-and-loss", year, stub_company, "Monthly")
	assert period["periodicity"] == "Monthly"
	assert period["from_fiscal_year"] == period["to_fiscal_year"] == "2026"

	trial = statements._filters("trial-balance", year, stub_company, "Monthly")
	assert "periodicity" not in trial
	assert trial["fiscal_year"] == "2026"
	# Without this an opening balance double-counts the retained earnings the
	# closing voucher just moved.
	assert trial["with_period_closing_entry_for_opening"] == 1


def test_a_period_nobody_offers_falls_back(statements):
	"""`periodicity` reaches ERPNext's own filters, so a caller inventing one
	is a caller choosing how their report is built."""
	assert "Fortnightly" not in statements.PERIODS
	source = SOURCE.read_text()
	assert "periodicity not in PERIODS" in source


def test_the_company_is_read_and_never_asked(statements):
	"""One workspace has one company — `docs/WORKSPACE-SETTINGS.md`, and
	`onespace/books.py` refuses a second — so a company filter would offer a
	choice of one and a way to get it wrong."""
	source = SOURCE.read_text()
	assert "def _company(" in source
	assert "def statement(kind: str, fiscal_year: str = \"\"" in source
	assert "company:" not in source.split("def statement(")[1].split(")")[0]


def test_the_year_falls_back_to_the_one_today_is_in(statements):
	"""Not the newest. A workspace that has set up next year in advance would
	otherwise open every statement on a year with nothing in it."""
	body = SOURCE.read_text().split("def _year(")[1].split("\ndef ")[0]
	assert 'frappe.utils.nowdate()' in body
	assert '"year_start_date": ("<=", today)' in body


# --------------------------------------------------------------------------- #
# D. The three screens
# --------------------------------------------------------------------------- #

def test_each_statement_is_a_screen(statements):
	screens = {one["screen"]: one for one in declared().SCREENS}
	for kind in statements.REPORTS:
		assert kind in screens, kind
		assert screens[kind]["component"] == f"onebook/{kind}", kind
		assert screens[kind]["screen_group"] == "Statements", kind


def test_the_screen_slug_is_the_report_kind(statements):
	"""`Statement.vue` reads `props.screen` as the kind, so the manifest and
	the endpoint's allowlist are the same three words. A screen renamed without
	the report is a page that draws somebody else's statement."""
	assert "props.screen || 'trial-balance'" in SCREEN.read_text()


def test_every_statement_component_is_registered(statements):
	registry = REGISTRY.read_text()
	for kind in statements.REPORTS:
		assert f"'onebook/{kind}'" in registry, kind


def test_the_three_keys_point_at_one_component(statements):
	"""One file, three keys — the same arrangement OneHR's five HRMS tools
	use. Three components would be three copies of one table."""
	registry = REGISTRY.read_text()
	for kind in statements.REPORTS:
		line = next(one for one in registry.splitlines()
		            if f"'onebook/{kind}'" in one)
		assert "screens/onebook/Statement.vue" in line, kind


def test_the_statements_sit_above_the_ledger(statements):
	"""This is what somebody opens OneBook for; the ledger is where they go
	when a number on one of these is wrong."""
	order = [one["screen"] for one in declared().SCREENS]
	assert order.index("trial-balance") < order.index("ledger")


# --------------------------------------------------------------------------- #
# E. And the seam is declared
# --------------------------------------------------------------------------- #

def test_every_report_is_in_the_erpnext_adapter(statements):
	"""`docs/CLEANUP.md` stage 10: what we change about ERPNext is a
	declaration. A report reached by a dotted string is a seam like any other —
	more fragile than an import, because an import fails at load and a string
	fails at the moment somebody presses the button."""
	import sys

	sys.path.insert(0, str(ROOT / "apps/oneapp"))
	from oneapp.adapters import erpnext

	for one in statements.REPORTS.values():
		assert one["module"] in erpnext.CALLED, one["module"]
