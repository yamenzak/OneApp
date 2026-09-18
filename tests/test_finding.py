"""One box over every space, and the four rules it must not break.

`docs/FRAPPE.md` named this as the first of the ten gaps, and the design
decision behind it is a measurement rather than a preference: Frappe's own
`__global_search` is the desk's metadata, matches whole words, and carries no
idea which screen shows a hit. `finding.py`'s docstring has the numbers.

What is checked here is what a fan-out over a hundred tables can quietly get
wrong:

  * a hit is a row the screen it names would itself list — the screen's own
    filters apply, `@me` included, so search is not a way around a narrowing;
  * only fields the screen shows are searched, which is `filters.py`'s rule and
    is imported rather than restated;
  * nothing reaches past `navigable`, so a screen a seat cannot open is not a
    screen its records can be found through;
  * one screen that refuses does not take the palette down with it.
"""

import ast
import pathlib
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onespace/finding.py"
DIALOG = ROOT / "apps/oneapp/frontend/src/modules/onespace/components/shell/Finder.vue"
STORE = ROOT / "apps/oneapp/frontend/src/modules/onespace/lib/shell/finding.js"
APP = ROOT / "apps/oneapp/frontend/src/App.vue"
CLIENT = ROOT / "apps/oneapp/frontend/src/shared/lib/workspace/finding.js"


@pytest.fixture
def finding(stub_frappe):
	from oneapp.onespace import finding as module

	return module


def _field(fieldtype="Data"):
	return types.SimpleNamespace(fieldtype=fieldtype)


def _meta(fields: dict, title: str = ""):
	return types.SimpleNamespace(
		title_field=title,
		get_field=lambda name: fields.get(name),
		track_changes=0,
	)


# ---------------------------------------------------------------- the fields

def test_only_fields_the_screen_lists_are_searched(finding, stub_frappe):
	stub_frappe._meta["Sales Invoice"] = _meta({
		"customer_name": _field(), "remarks": _field("Small Text"),
		"secret_note": _field(),
	})
	reach = finding._fields("Sales Invoice", "customer_name,remarks")
	assert "secret_note" not in reach, (
		"a field the screen does not show is a field watching which rows come "
		"back would read for you"
	)


def test_the_id_is_always_first(finding, stub_frappe):
	stub_frappe._meta["Task"] = _meta({"subject": _field()})
	assert finding._fields("Task", "subject")[0] == "name"


def test_a_field_a_like_cannot_ask_about_is_left_out(finding, stub_frappe):
	stub_frappe._meta["Payment Entry"] = _meta({
		"party_name": _field(), "paid_amount": _field("Currency"),
		"posting_date": _field("Date"),
	})
	reach = finding._fields("Payment Entry", "party_name,paid_amount,posting_date")
	assert reach == ["name", "party_name"]


def test_a_doctype_this_site_has_not_got_answers_nothing(finding):
	def missing(doctype):
		raise RuntimeError("no such doctype")

	finding.frappe.get_meta = missing
	assert finding._fields("Nowhere At All", "subject") == []


def test_the_search_column_ceiling_is_the_lists_own(finding):
	from oneapp.onespace.spaceview import filters

	assert finding.MAX_SEARCH_COLUMNS is filters.MAX_SEARCH_COLUMNS
	assert finding.NEVER_SEARCHED is filters.NEVER_SEARCHED


# --------------------------------------------------------------- the ranking

def test_a_hit_nobody_can_see_the_reason_for_goes_last(finding, stub_frappe):
	"""The ledger entry named `09b526cc60`, which matched on its account.

	A row may match on any column its screen shows, so a hit whose own name
	says nothing about what was typed is a real answer and an unreadable one.
	Ranked under every title match rather than dropped: it *is* what was asked
	for, and a search that hides its own answers is worse than one that sorts
	them badly.
	"""
	stub_frappe._meta["GL Entry"] = _meta({"against": _field()})
	finding.frappe.get_list = lambda *a, **k: [{"name": "09b526cc60"}]
	found = finding._hits(_target(doctype="GL Entry", fields="against"), "merid")
	assert found[0]["rank"] == finding.ELSEWHERE


def test_a_match_is_ranked_by_where_it_landed(finding):
	assert finding._where("deal", "Deal") == finding.EXACT
	assert finding._where("dea", "Deals") == finding.STARTS
	assert finding._where("lost", "Deals lost") == finding.WORD
	assert finding._where("eal", "Deals") == finding.ANYWHERE
	assert finding._where("merid", "09b526cc60") == finding.ELSEWHERE


# --------------------------------------------------------------- the filters

def test_a_screens_own_filters_narrow_what_it_finds(finding):
	rows = finding._narrowing({"filters": '{"status": "Open"}'})
	assert rows == [["status", "=", "Open"]]


def test_an_operator_pair_survives_the_round_trip(finding):
	rows = finding._narrowing({"filters": '{"docstatus": ["!=", 2]}'})
	assert rows == [["docstatus", "!=", 2]]


def test_me_is_resolved_the_same_way_the_screen_resolves_it(finding, stub_frappe):
	stub_frappe.session.user = "reader@example.com"
	rows = finding._narrowing({"filters": '{"owner": "@me"}'})
	assert rows == [["owner", "=", "reader@example.com"]], (
		"a screen narrowed to its reader must stay narrowed when it is searched"
	)


def test_filters_that_will_not_parse_do_not_take_the_screen_out(finding):
	assert finding._narrowing({"filters": "{not json"}) == []


# ------------------------------------------------------------------ the hits

def _target(**over):
	return {
		"doctype": "Sales Invoice", "space": "onebook", "space_label": "OneBook",
		"brand": "onebook", "screen": "invoices", "label": "Invoice",
		"icon": "lucide-receipt", "fields": "customer_name", "filters": "",
		**over,
	}


def test_a_hit_says_where_to_open_it(finding, stub_frappe):
	stub_frappe._meta["Sales Invoice"] = _meta({"customer_name": _field()}, "customer_name")
	finding.frappe.get_list = lambda *a, **k: [
		{"name": "INV-0007", "customer_name": "Meridian Group"},
	]
	found = finding._hits(_target(), "meri")
	assert found[0]["space"] == "onebook"
	assert found[0]["screen"] == "invoices"
	assert found[0]["name"] == "INV-0007"


def test_markup_in_a_title_is_not_shown_as_markup(finding, stub_frappe):
	stub_frappe._meta["Task"] = _meta({"subject": _field("Text Editor")}, "subject")
	finding.frappe.get_list = lambda *a, **k: [
		{"name": "TASK-1", "subject": "<p>Chase the invoice</p>"},
	]
	assert finding._hits(_target(doctype="Task", fields="subject"), "chase")[0]["title"] \
		== "Chase the invoice"


def test_the_id_is_not_repeated_when_it_is_the_title(finding, stub_frappe):
	stub_frappe._meta["GL Entry"] = _meta({"account": _field()})
	finding.frappe.get_list = lambda *a, **k: [{"name": "0a1b2c"}]
	assert finding._hits(_target(doctype="GL Entry", fields="account"), "0a1")[0]["id"] == ""


def test_one_screen_refusing_does_not_take_the_palette_down(finding):
	def refuse(*a, **k):
		raise finding.frappe.PermissionError("no")

	finding.frappe.get_list = refuse
	assert finding._hits(_target(), "meri") == []


def test_a_screens_rows_remember_the_order_they_came_in(finding, stub_frappe):
	stub_frappe._meta["Sales Invoice"] = _meta({"customer_name": _field()}, "customer_name")
	finding.frappe.get_list = lambda *a, **k: [
		{"name": "INV-1", "customer_name": "Meridian one"},
		{"name": "INV-2", "customer_name": "Meridian two"},
	]
	assert [one["seat"] for one in finding._hits(_target(), "meri")] == [0, 1]


# ------------------------------------------------------------------ the call

def test_one_letter_searches_nothing(finding):
	answer = finding.look("a")
	assert answer["results"] == [] and answer["looked"] == 0


def test_the_space_somebody_stood_in_breaks_the_tie(finding, stub_frappe):
	stub_frappe._meta["Sales Invoice"] = _meta({"customer_name": _field()}, "customer_name")
	finding.targets = lambda: [
		_target(space="onebook", space_label="OneBook"),
		_target(space="rua", space_label="RUA", screen="sales"),
	]
	finding.frappe.get_list = lambda *a, **k: [
		{"name": "INV-0007", "customer_name": "Meridian Group"},
	]
	assert finding.look("meri", space="rua")["results"][0]["space"] == "rua"


def test_one_record_is_one_line_however_many_spaces_reach_it(finding, stub_frappe):
	stub_frappe._meta["Sales Invoice"] = _meta({"customer_name": _field()}, "customer_name")
	finding.targets = lambda: [_target(space="onebook"), _target(space="rua")]
	finding.frappe.get_list = lambda *a, **k: [
		{"name": "INV-0007", "customer_name": "Meridian Group"},
	]
	assert len(finding.look("meri")["results"]) == 1


# ----------------------------------------------------------------- the rules

def _source() -> str:
	return SOURCE.read_text()


def test_nothing_here_ignores_permissions():
	"""Read off the tree rather than grepped for.

	The same trap `test_book_scope.py` fell into: the docstring above says the
	words "ignore_permissions", so a grep finds the file it is arguing against
	doing.
	"""
	offenders = [
		node.arg
		for node in ast.walk(ast.parse(_source()))
		if isinstance(node, ast.keyword)
		and node.arg in ("ignore_permissions", "ignore_ifnull")
	]
	assert not offenders, (
		"the fan-out is only safe because every query is `get_list` under the "
		"reader's own permissions"
	)


def test_the_endpoint_only_reads():
	for node in ast.walk(ast.parse(_source())):
		if not isinstance(node, ast.FunctionDef):
			continue
		for one in node.decorator_list:
			if not isinstance(one, ast.Call) or "whitelist" not in ast.unparse(one.func):
				continue
			methods = next(
				(ast.literal_eval(kw.value) for kw in one.keywords if kw.arg == "methods"),
				None,
			)
			assert methods == ["GET"], (
				f"{node.name} is a search and must not accept a write"
			)


def test_the_targets_come_from_what_the_seat_can_open():
	assert "navigable" in _source() and "visible" in _source(), (
		"a screen a seat cannot open is not a screen its records may be found "
		"through"
	)


# ------------------------------------------------------------- the front end

def test_the_shortcut_is_bound_where_its_exception_is_argued():
	"""Bound here, and the reason written beside it.

	Checked against the *imports* rather than by grepping the file, which is
	the trap this repository keeps falling into and `test_book_scope.py` fell
	into last: the component's own comment argues about `useShortcuts` at
	length, so a grep finds the name in the paragraph explaining why it is not
	used.
	"""
	source = DIALOG.read_text()
	assert "metaKey" in source and "ctrlKey" in source
	imported = [
		line for line in source.splitlines()
		if line.startswith("import ") and "shell/shortcuts" in line
	]
	assert not imported, (
		"the house helper stands down inside an input and over a dialog, which "
		"is exactly where this one has to work — the exception is argued in "
		"the component"
	)


def test_the_palette_is_mounted_for_the_session():
	source = APP.read_text()
	assert "<Finder " in source and "session.isLoggedIn" in source


def test_the_search_is_silent():
	assert "silent: true" in CLIENT.read_text(), (
		"a search that fails while somebody types must not put a toast over "
		"the list they are reading"
	)


def test_the_two_sides_agree_on_the_shortest_query(finding):
	source = STORE.read_text()
	said = next(line for line in source.splitlines() if "export const SHORTEST" in line)
	assert f"= {finding.SHORTEST}" in said
