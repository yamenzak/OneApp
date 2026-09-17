"""What is owed, and how late.

`docs/ONEBOOK.md` stage 4. The Invoices screen totals `outstanding_amount`,
which answers *how much*. An invoice for two thousand that went out last week
and one for two thousand that went out in March are the same number and
completely different problems, and no list in this space could tell them apart.

ERPNext's ageing is called rather than copied, so what is ours and what these
check is the four things around it: an allowlist of two sides, a bucket set
that cannot drift from the headings drawn over it, a roll-up that sorts by what
is *late* rather than by what is large, and a grant per side — because being
owed money is everybody's business in OneBook and owing it is the bookkeeper's.
"""

import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onebook/owing.py"
SCREEN = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/onebook/Owing.vue"
REGISTRY = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
MANIFEST = ROOT / "apps/oneapp_control/oneapp_control/spaces/onebook.py"
ADAPTER = ROOT / "apps/oneapp/oneapp/adapters/erpnext.py"


@pytest.fixture
def owing(stub_frappe):
	from oneapp.onebook import owing as module

	return module


def manifest():
	spec = importlib.util.spec_from_file_location("books_manifest", MANIFEST)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


# --------------------------------------------------------------------------- #
# A. Two sides and no more
# --------------------------------------------------------------------------- #

def test_only_two_sides_may_be_asked_for(owing):
	assert set(owing.SIDES) == {"receivable", "payable"}


def test_a_side_nobody_declared_is_refused(owing):
	"""A whitelisted endpoint that ran any report by name would run everything
	else ERPNext ships against a filter dictionary a caller composed."""
	with pytest.raises(Exception):
		owing.owing("bisect-accounting-statements")


def test_each_side_names_a_report_in_erpnext(owing):
	for kind, side in owing.SIDES.items():
		assert side["module"].startswith("erpnext.accounts.report."), kind


def test_each_side_names_the_doctype_it_is_about(owing):
	"""Which is also the grant checked on the way in, and the reason these are
	two screens rather than one with a switch."""
	assert owing.SIDES["receivable"]["doctype"] == "Sales Invoice"
	assert owing.SIDES["payable"]["doctype"] == "Purchase Invoice"
	source = SOURCE.read_text()
	assert 'frappe.has_permission(side["doctype"], "read")' in source


def test_only_their_two_bases_are_accepted(owing):
	assert list(owing.BASES) == ["Due Date", "Posting Date"]
	source = SOURCE.read_text()
	assert "if basis not in BASES:" in source, "anything else falls back"


# --------------------------------------------------------------------------- #
# B. The buckets, and the headings over them
# --------------------------------------------------------------------------- #

def test_there_are_six_buckets_and_the_first_is_not_late(owing):
	"""`range0` is the one people forget: everything not yet due, which on a
	healthy ledger is most of the money. Without it a screen says "we are owed
	four hundred thousand" where the true sentence is "and none of it is
	late"."""
	assert owing.BUCKETS[0] == "range0"
	assert len(owing.BUCKETS) == 6


def test_the_breaks_are_the_four_everybody_reads(owing):
	assert owing.BREAKS == (30, 60, 90, 120)


def test_the_headings_come_off_their_columns(owing):
	"""Read off the report rather than composed from `BREAKS`, so a boundary
	moved in one place cannot leave the headings saying the old one."""
	found = owing._labels([
		{"fieldname": "range0", "label": "<0"},
		{"fieldname": "range3", "label": "61-90"},
	])
	assert [one["key"] for one in found] == list(owing.BUCKETS)
	assert found[0]["label"] == "<0"
	assert found[3]["label"] == "61-90"
	# A column their report did not send falls back to its own key rather than
	# leaving a blank heading over a column of numbers.
	assert found[1]["label"] == "range1"


# --------------------------------------------------------------------------- #
# C. The roll-up
# --------------------------------------------------------------------------- #

def rows():
	return [
		{"party": "A", "party_label": "Acme", "currency": "AED", "age": 5,
		 "outstanding": 100.0, "buckets": [100.0, 0, 0, 0, 0, 0]},
		{"party": "B", "party_label": "Byre", "currency": "AED", "age": 95,
		 "outstanding": 40.0, "buckets": [0, 0, 0, 0, 40.0, 0]},
		{"party": "A", "party_label": "Acme", "currency": "AED", "age": 40,
		 "outstanding": 10.0, "buckets": [0, 0, 10.0, 0, 0, 0]},
	]


def test_a_party_is_one_line_with_its_documents_counted(owing):
	found = {one["party"]: one for one in owing._by_party(rows())}
	assert found["A"]["outstanding"] == 110.0
	assert found["A"]["documents"] == 2
	assert found["A"]["oldest"] == 40


def test_what_is_late_excludes_what_is_not_due(owing):
	found = {one["party"]: one for one in owing._by_party(rows())}
	assert found["A"]["late"] == 10.0, "the 100 in range0 is not late"
	assert found["B"]["late"] == 40.0


def test_the_worst_is_first_and_that_is_not_the_biggest(owing):
	"""The whole point of the screen. The largest balance on the page is
	usually somebody's largest customer paying normally; the row worth a Monday
	morning is the smaller one sitting in the last two buckets."""
	found = owing._by_party(rows())
	assert [one["party"] for one in found] == ["B", "A"]
	assert found[0]["outstanding"] < found[1]["outstanding"]


def test_a_document_nobody_named_still_lands_somewhere(owing):
	"""A payroll accrual sits on a payable account with no supplier, and
	dropping it would make the screen disagree with the balance sheet."""
	found = owing._by_party([
		{"party": "", "party_label": "No party", "currency": "AED", "age": 49,
		 "outstanding": 200.0, "buckets": [0, 0, 200.0, 0, 0, 0]},
	])
	assert len(found) == 1 and found[0]["outstanding"] == 200.0


# --------------------------------------------------------------------------- #
# D. The screens
# --------------------------------------------------------------------------- #

def screens() -> dict:
	return {one["screen"]: one for one in manifest().SCREENS}


def test_both_sides_have_a_screen_and_they_sit_with_the_statements():
	found = screens()
	for name in ("owed-to-us", "owed-by-us"):
		assert found[name]["screen_group"] == "Statements", name
		assert found[name]["component"] == f"onebook/{name}"


def test_each_screen_names_the_doctype_its_side_reads():
	found = screens()
	assert found["owed-to-us"]["document_type"] == "Sales Invoice"
	assert found["owed-by-us"]["document_type"] == "Purchase Invoice"


def test_the_screens_are_granted_on_the_rungs_they_belong_to():
	"""Receivables to everybody, payables to the bookkeeper — the same line the
	Invoices and Bills screens are already on either side of."""
	granted = {row[0]: row for row in manifest().DOCTYPES}
	assert len(granted["Sales Invoice"]) == 3, "no seat named: the User rung"
	assert granted["Purchase Invoice"][3] == "manager"


def test_one_component_draws_both():
	registry = REGISTRY.read_text()
	for name in ("owed-to-us", "owed-by-us"):
		assert f"'onebook/{name}': () => import(" in registry
	assert SCREEN.exists()
	assert registry.count("onebook/Owing.vue") == 2


def test_the_screen_maps_its_slug_to_a_side():
	"""The manifest and the endpoint's allowlist are the same two words."""
	screen = SCREEN.read_text()
	assert "'owed-to-us': 'receivable'" in screen
	assert "'owed-by-us': 'payable'" in screen


def test_the_seam_is_declared():
	adapter = ADAPTER.read_text()
	for name in ("accounts_receivable.accounts_receivable",
	             "accounts_payable.accounts_payable"):
		assert name in adapter, name


def test_the_roll_up_is_the_only_thing_this_module_computes():
	"""The bucketing is theirs and stays theirs. A module that started dividing
	by date here would be a second answer to "are we owed this"."""
	tree = ast.parse(SOURCE.read_text())
	names = {node.name for node in ast.walk(tree)
	         if isinstance(node, ast.FunctionDef)}
	assert "_by_party" in names
	for banned in ("_age", "_bucket_for", "_days_late"):
		assert banned not in names, f"{banned} would be re-deciding the ageing"
