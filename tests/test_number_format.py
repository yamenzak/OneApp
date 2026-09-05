"""How a number reads, decided by the code that decides it.

A Float column was rendering with whatever `toLocaleString` defaults to: no
grouping, no fixed decimals, and the doctype's own `precision` — which the
resolver has always sent — ignored entirely.

Run through node rather than reimplemented here, for the same reason
`test_field_rules.py` gives: a second implementation is two things to keep in
step, and the one that gets tested is never the one that ships.

The locale is pinned. `toLocaleString` with no locale follows the environment,
so the same number is "1,234.50" on one machine and "1.234,50" on another —
which would make these assertions a statement about the runner rather than
about the code.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FORMAT = ROOT / "apps/oneapp/frontend/src/lib/format.js"


def run(cases: list[tuple]) -> list:
	"""[(value, column, formats)] -> [what `formatNumber` answered]."""
	script = (
		f"import {{ formatNumber }} from {json.dumps(FORMAT.as_uri())};"
		f"const cases = {json.dumps(cases)};"
		"console.log(JSON.stringify("
		"cases.map(([value, column, formats]) => formatNumber(value, column, formats))));"
	)
	out = subprocess.run(
		["node", "--input-type=module", "-e", script],
		capture_output=True, text=True, check=True,
		env={"PATH": "/usr/bin:/bin:/usr/local/bin", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"},
	)
	return json.loads(out.stdout.strip().splitlines()[-1])


pytestmark = pytest.mark.skipif(
	not shutil.which("node") or not FORMAT.exists(),
	reason="needs node and the SPA's format module",
)

SITE = {"float_precision": 3, "currency_precision": 2}


def test_the_fields_own_precision_wins():
	assert run([
		[1234.5678, {"cell": "number", "precision": 2}, SITE],
		[1234.5678, {"cell": "number", "precision": 4}, SITE],
	]) == ["1,234.57", "1,234.5678"]


def test_the_site_answers_when_the_field_does_not():
	"""`precision` of 0 on a DocField means unset, not "no decimals" — Frappe
	stores it as a Select whose blank option is the empty string."""
	assert run([
		[1234.5678, {"cell": "number"}, SITE],
		[1234.5678, {"cell": "number", "precision": 0}, SITE],
		[1234.5678, {"cell": "number", "precision": ""}, SITE],
	]) == ["1,234.568"] * 3


def test_money_follows_the_sites_currency_precision():
	assert run([[1234.5, {"cell": "currency"}, SITE]]) == ["1,234.50"]


def test_money_does_not_follow_the_float_precision():
	"""They are two settings about two different things.

	The browser used to read the float precision when the site sent no currency
	one, which is not a fallback Frappe makes — money follows the *number
	format*, and `#,###.##` is two places. Every contract value in the product
	rendered with a thousandth of a dirham on the end, and Frappe's own desk
	showed the same figure correctly on the same site.
	"""
	assert run([[1234.5, {"cell": "currency"}, {"float_precision": 3}]]) == ["1,234.50"]


def test_a_count_carries_no_decimals():
	"""Precision is a question about fractions. A count of 3 is not "3.000"."""
	assert run([
		[3, {"cell": "number", "fieldtype": "Int"}, SITE],
		[3, {"cell": "number", "fieldtype": "Long Int"}, SITE],
		[12345, {"cell": "number", "fieldtype": "Int"}, SITE],
	]) == ["3", "3", "12,345"]


def test_thousands_are_grouped():
	"""The reason a column of numbers is scannable at all."""
	assert run([[1234567.1, {"cell": "number", "precision": 1}, SITE]]) == ["1,234,567.1"]


def test_a_number_that_is_not_one_survives_unchanged():
	"""A data problem, and hiding it behind "NaN" loses the only evidence of
	what was actually stored."""
	assert run([["not a number", {"cell": "number"}, SITE]]) == ["not a number"]


def test_an_empty_cell_is_not_zero():
	"""`Number(null)` is 0 and `Number('')` is 0, so the obvious version of
	this renders "0.000" into every empty cell — a number nobody stored.
	Emptiness is the caller's to draw, which is why this is "" and not a dash."""
	assert run([
		[None, {"cell": "number"}, SITE],
		["", {"cell": "number"}, SITE],
		[0, {"cell": "number", "precision": 2}, SITE],
	]) == ["", "", "0.00"]


def test_no_site_formats_still_renders():
	"""The session has not loaded yet, or this site answered nothing. A cell
	that renders nothing at all is worse than one that renders plainly."""
	assert run([[1234.5678, {"cell": "number"}, {}]]) == ["1,234.568"]


# --------------------------------------------------------------------------- #
# Markup as one line
# --------------------------------------------------------------------------- #

def strip(cases: list) -> list:
	script = (
		f"import {{ plainText }} from {json.dumps(FORMAT.as_uri())};"
		f"const cases = {json.dumps(cases)};"
		"console.log(JSON.stringify(cases.map((value) => plainText(value))));"
	)
	out = subprocess.run(
		["node", "--input-type=module", "-e", script],
		capture_output=True, text=True, check=True,
	)
	return json.loads(out.stdout.strip().splitlines()[-1])


def test_a_title_that_is_html_reads_as_one_line():
	"""A Text Editor field holds HTML, and a title field may be one — ToDo's
	`description` is exactly that. Drawn raw, the title of every record reads
	`<p>Chase the Halloway invoice</p>`, in the list, in the crumb and in every
	link chip pointing at it."""
	assert strip([
		"<p>Chase the Halloway invoice</p>",
		"<p>Two</p><p>paragraphs</p>",
		"<em>Emphasis</em> and <strong>weight</strong>",
	]) == [
		"Chase the Halloway invoice",
		"Two paragraphs",
		"Emphasis and weight",
	]


def test_plain_text_is_returned_untouched():
	"""Which is most titles, so it is the path worth being cheap."""
	assert strip(["Chase the Halloway invoice", "", None]) == [
		"Chase the Halloway invoice", "", "",
	]


def test_a_stray_angle_bracket_is_not_markup():
	"""`5 < 6` is a title somebody wrote, not a tag."""
	assert strip(["5 < 6"]) == ["5 < 6"]


# --------------------------------------------------------------------------- #
# The site's answer, which is the server's to give
# --------------------------------------------------------------------------- #


def _formats(stub_frappe, monkeypatch, **settings):
	import sys
	import types

	said = {"float_precision": "", "currency_precision": "", "number_format": "",
	        **settings}
	monkeypatch.setattr(stub_frappe, "get_cached_doc",
	                    lambda *a, **k: types.SimpleNamespace(**said))
	# The package as well as its modules. `from oneapp import api` takes the
	# attribute off a cached `oneapp` package in preference to importing, so
	# dropping only the submodule hands back the copy that closed over the
	# previous test's stub — which passes alone and fails in a suite.
	for name in list(sys.modules):
		if name == "oneapp" or name.startswith("oneapp."):
			del sys.modules[name]
	from oneapp import api

	return api.number_formats()


def test_money_takes_its_decimals_from_the_number_format(stub_frappe, monkeypatch):
	"""Not from `float_precision`. `#,###.##` is two places and `#,###` is
	none, and neither has anything to do with how a Float renders."""
	assert _formats(stub_frappe, monkeypatch,
	                number_format="#,###.##", float_precision="3"
	                )["currency_precision"] == 2
	assert _formats(stub_frappe, monkeypatch,
	                number_format="#,###", float_precision="3"
	                )["currency_precision"] == 0


def test_a_site_that_set_the_currency_precision_gets_what_it_asked_for(stub_frappe,
                                                                      monkeypatch):
	assert _formats(stub_frappe, monkeypatch, number_format="#,###.##",
	                currency_precision="4")["currency_precision"] == 4


def test_a_number_format_nobody_could_have_chosen_still_answers(stub_frappe,
                                                                monkeypatch):
	"""A format Frappe does not know is a setting nobody reached through the
	UI — and a boot request that raises is a workspace that will not open."""
	found = _formats(stub_frappe, monkeypatch, number_format="wat")
	assert found["currency_precision"] == 2
	assert found["number_format"] == "#,###.##"
