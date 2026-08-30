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


# --------------------------------------------------------------------------- #
# What the rules answer for a whole field, and for a whole section
# --------------------------------------------------------------------------- #

def run_field(cases: list[tuple[dict, dict]]) -> list:
	"""[(field, doc)] -> [what `fieldRules` answered]."""
	script = (
		f"import {{ fieldRules }} from {json.dumps(RULES.as_uri())};"
		f"const cases = {json.dumps(cases)};"
		"console.log(JSON.stringify(cases.map(([field, doc]) => fieldRules(field, doc))));"
	)
	out = subprocess.run(
		["node", "--input-type=module", "-e", script],
		capture_output=True, text=True, check=True,
	)
	return json.loads(out.stdout.strip().splitlines()[-1])


def run_section(cases: list[tuple[dict, dict]]) -> list:
	"""[(section, doc)] -> [whether it starts folded]."""
	script = (
		f"import {{ sectionCollapsed }} from {json.dumps(RULES.as_uri())};"
		f"const cases = {json.dumps(cases)};"
		"console.log(JSON.stringify("
		"cases.map(([section, doc]) => sectionCollapsed(section, doc))));"
	)
	out = subprocess.run(
		["node", "--input-type=module", "-e", script],
		capture_output=True, text=True, check=True,
	)
	return json.loads(out.stdout.strip().splitlines()[-1])


def test_not_nullable_is_required():
	"""Three ways for a field to insist on a value, one question for the
	control. `not_nullable` is the strictest — Frappe refuses an empty value
	outright rather than asking — so it counts here even though its message
	elsewhere is different."""
	assert [r["required"] for r in run_field([
		({"reqd": 0, "not_nullable": 0}, {}),
		({"reqd": 1, "not_nullable": 0}, {}),
		({"reqd": 0, "not_nullable": 1}, {}),
		({"reqd": 0, "mandatory_depends_on": "eval:doc.kind == 'x'"}, {"kind": "x"}),
	])] == [False, True, True, True]


def test_a_section_folds_only_when_the_doctype_says_so():
	assert run_section([
		({"collapsible": 0}, {}),
		({"collapsible": 1}, {}),
	]) == [False, True]


def test_a_conditional_fold_reads_the_record():
	"""`collapsible_depends_on` is the same dialect as `depends_on`, so it goes
	through the same parser rather than a second one."""
	assert run_section([
		({"collapsible": 1, "collapsible_depends_on": "eval:doc.kind == 'simple'"},
		 {"kind": "simple"}),
		({"collapsible": 1, "collapsible_depends_on": "eval:doc.kind == 'simple'"},
		 {"kind": "full"}),
	]) == [True, False]


def test_an_unreadable_fold_expression_leaves_the_section_open():
	"""The safe direction. A section nobody can open is worse than one that is
	always open, and `evaluate` answers null rather than guessing."""
	assert run_section([
		({"collapsible": 1, "collapsible_depends_on": "eval:doc.a ?? ("}, {"a": 1}),
	]) == [False]


def test_a_section_that_is_not_collapsible_ignores_its_expression():
	"""Frappe writes both, and only the first decides whether there is a
	disclosure at all."""
	assert run_section([
		({"collapsible": 0, "collapsible_depends_on": "eval:1 == 1"}, {}),
	]) == [False]
