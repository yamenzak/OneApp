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


def test_currency_falls_back_to_the_float_precision():
	"""Frappe leaves `currency_precision` unset to mean "follow the float
	precision", which is a different thing from zero decimal places."""
	assert run([[1234.5, {"cell": "currency"}, {"float_precision": 3}]]) == ["1,234.500"]


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
