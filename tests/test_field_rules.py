"""The doctype's own rules, evaluated by the code that will evaluate them.

`depends_on` and its two cousins are strings out of a database, and the desk
runs them as JavaScript. Ours does not — see `apps/oneapp/frontend/src/lib/
rules.js` for why — so what it does instead has to be right about the
expressions people actually write.

These run the real module through node rather than reimplementing it in Python.
A second implementation to test the first against is two things to keep in
step, and the one that gets tested is never the one that ships.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "apps/oneapp/frontend/src/lib/rules.js"


def run(cases: list[tuple[str, dict]]) -> list:
	"""[(expression, doc)] -> [what `evaluate` answered]."""
	script = (
		f"import {{ evaluate }} from {json.dumps(RULES.as_uri())};"
		f"const cases = {json.dumps(cases)};"
		"console.log(JSON.stringify(cases.map(([rule, doc]) => evaluate(rule, doc))));"
	)
	out = subprocess.run(
		["node", "--input-type=module", "-e", script],
		capture_output=True, text=True, check=True,
	)
	return json.loads(out.stdout.strip().splitlines()[-1])


pytestmark = pytest.mark.skipif(
	not shutil.which("node") or not RULES.exists(),
	reason="needs node and the SPA's rules module",
)


def test_a_bare_fieldname_asks_whether_it_is_filled_in():
	"""Frappe's shorthand, and the commonest of the three forms."""
	assert run([
		("status", {"status": "Open"}),
		("status", {"status": ""}),
		("status", {}),
	]) == [True, False, False]


def test_the_comparisons_people_actually_write():
	doc = {"status": "Closed", "qty": 5, "done": 1}
	assert run([
		('eval:doc.status=="Closed"', doc),
		('eval:doc.status!="Closed"', doc),
		("eval:doc.qty > 3", doc),
		("eval:doc.qty >= 5", doc),
		("eval:doc.qty < 3", doc),
		# A Check is 0 or 1 in the database and `false` in a rule, so the
		# comparison is loose on purpose.
		("eval:doc.done == true", doc),
	]) == [True, False, True, True, False, True]


def test_and_or_not_and_brackets():
	doc = {"status": "Open", "qty": 0}
	assert run([
		('eval:doc.status=="Open" && doc.qty > 0', doc),
		('eval:doc.status=="Open" || doc.qty > 0', doc),
		('eval:!(doc.status=="Open")', doc),
		('eval:(doc.status=="Open" || doc.qty > 0) && doc.status!="Closed"', doc),
	]) == [False, True, False, True]


def test_membership_and_length():
	doc = {"status": "Open", "tags": ["a", "b"]}
	assert run([
		("eval:doc.status in ['Open', 'Closed']", doc),
		("eval:doc.status in ['Closed']", doc),
		("eval:doc.tags.length > 1", doc),
		("eval:doc.missing.length > 0", doc),
	]) == [True, False, True, False]


def test_a_rule_that_cannot_be_read_is_no_rule():
	"""`null`, not `false`. A caller has to be able to tell "no" from "no
	idea", because the two mean opposite things for a field that would
	otherwise be shown."""
	assert run([
		("eval:doc.status.startsWith('O')", {"status": "Open"}),
		("eval:frappe.user_roles.includes('Manager')", {}),
		("eval:doc.status ==", {"status": "Open"}),
		("eval:", {}),
		("", {}),
		(None, {}),
	]) == [None, None, None, None, None, None]


def test_nothing_it_reads_can_call_anything():
	"""The whole reason it parses rather than evaluates: the string is a row in
	a database, editable by anyone who can write a Property Setter.

	Comments first. The file explains at length why it does not call
	`new Function`, and a scan that reads the explanation as the thing it warns
	about fails on the file that is right."""
	source = re.sub(r"/\*.*?\*/", "", RULES.read_text(), flags=re.S)
	source = re.sub(r"^[ \t]*//.*$", "", source, flags=re.M)
	for banned in ("new Function", "eval(", "setTimeout", "import("):
		assert banned not in source, f"rules.js reaches for {banned}"
