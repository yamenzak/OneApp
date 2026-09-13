"""The doctype's own rules, evaluated by the code that will evaluate them.

`depends_on` and its two cousins are strings out of a database, and the desk
runs them as JavaScript. Ours does not — see `apps/oneapp/frontend/src/modules/onespace/lib/screen/
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
RULES = ROOT / "apps/oneapp/frontend/src/modules/onespace/lib/screen/rules.js"


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


# --------------------------------------------------------------------------- #
# The server's copy, and the corpus that proves the two agree
#
# `read_only_depends_on` was honoured on the record form and nowhere else —
# not in a child-table grid, not in an inline cell, and not on save, because
# `_writable` is built from the *static* `read_only` flag. So the rule was
# advisory in one place and absent in three, and a write the form forbids went
# through. `docs/UNIFICATION.md` §B5.
#
# Closing it needed the same grammar on the server. Two evaluators that
# disagree are worse than one — a field would lock in the browser and stay
# writable here — so this is the check that keeps them one thing: the same
# corpus through both, and the answers have to match exactly.
# --------------------------------------------------------------------------- #

from oneapp.shared import fieldrules  # noqa: E402

#: Every shape this grammar supports, and the ones it deliberately refuses.
#: Extended rather than replaced when either side learns something new — a
#: case added to one evaluator and not the other is the drift this exists to
#: catch.
BOTH = [
	# A bare fieldname
	("status", {"status": "Open"}),
	("status", {"status": ""}),
	("status", {}),
	# Equality, loose on purpose
	('eval:doc.status=="Closed"', {"status": "Closed"}),
	('eval:doc.status!="Closed"', {"status": "Closed"}),
	("eval:doc.done == true", {"done": 1}),
	("eval:doc.done == false", {"done": 0}),
	("eval:doc.qty == 5", {"qty": 5}),
	('eval:doc.qty == "5"', {"qty": 5}),
	("eval:doc.missing == null", {}),
	# Order
	("eval:doc.qty > 3", {"qty": 5}),
	("eval:doc.qty >= 5", {"qty": 5}),
	("eval:doc.qty < 3", {"qty": 5}),
	("eval:doc.qty <= 5", {"qty": 5}),
	# And a comparison that cannot be made. JavaScript coerces and answers
	# false; Python would raise, so the port catches it and answers the same.
	('eval:doc.status > 3', {"status": "Open"}),
	# Logic and brackets
	('eval:doc.status=="Open" && doc.qty > 0', {"status": "Open", "qty": 0}),
	('eval:doc.status=="Open" || doc.qty > 0', {"status": "Open", "qty": 0}),
	('eval:!(doc.status=="Open")', {"status": "Open"}),
	('eval:(doc.status=="Open" || doc.qty > 0) && doc.status!="Closed"',
	 {"status": "Open", "qty": 0}),
	# Membership and length
	("eval:doc.status in ['Open', 'Closed']", {"status": "Open"}),
	("eval:doc.status in ['Closed']", {"status": "Open"}),
	("eval:doc.tags.length > 1", {"tags": ["a", "b"]}),
	("eval:doc.missing.length > 0", {}),
	# Truthiness, where the two languages could have differed. "0" is a
	# non-empty string and therefore true in JavaScript; the port says so too.
	("eval:doc.code", {"code": "0"}),
	("eval:doc.code", {"code": ""}),
	("eval:doc.n", {"n": 0}),
	# Unreadable, which is `null` rather than false on both sides
	("eval:doc.status.startsWith('O')", {"status": "Open"}),
	("eval:frappe.user_roles.includes('Manager')", {}),
	("eval:doc.status ==", {"status": "Open"}),
	("eval:", {}),
	("", {}),
]


def test_the_browser_and_the_server_answer_the_same():
	theirs = run(BOTH)
	ours = [fieldrules.evaluate(rule, doc) for rule, doc in BOTH]
	disagree = [
		f"{rule!r} on {doc!r}: browser {a!r}, server {b!r}"
		for (rule, doc), a, b in zip(BOTH, theirs, ours) if a != b
	]
	assert not disagree, (
		"the two evaluators have drifted:\n  " + "\n  ".join(disagree)
	)


def test_the_corpus_covers_more_than_the_easy_cases():
	"""A corpus of six true answers would pass whatever either side did."""
	answered = [fieldrules.evaluate(rule, doc) for rule, doc in BOTH]
	assert answered.count(True) >= 12
	assert answered.count(False) >= 8
	assert answered.count(None) >= 5


def test_locked_reads_the_field_s_own_rule():
	field = {"fieldname": "amount", "read_only_depends_on": 'eval:doc.status=="Closed"'}
	assert fieldrules.locked(field, {"status": "Closed"}) is True
	assert fieldrules.locked(field, {"status": "Open"}) is False
	# No rule locks nothing, and neither does one nobody can read.
	assert fieldrules.locked({"fieldname": "amount"}, {"status": "Closed"}) is False
	assert fieldrules.locked(
		{"read_only_depends_on": "eval:doc.status.startsWith('C')"}, {"status": "Closed"}
	) is False
	# A field the meta does not have at all — `get_field` answers None.
	assert fieldrules.locked(None, {"status": "Closed"}) is False


def test_the_save_path_consults_it():
	"""The half that was missing. `_writable` narrows on the static flag; this
	is what narrows on the dynamic one, and without it the browser fix is a
	suggestion."""
	import inspect

	from oneapp.onespace.spaceview import records

	assert "fieldrules.locked" in inspect.getsource(records._unlocked)
	assert "_unlocked(" in inspect.getsource(records.save)


def test_the_grid_and_the_cell_consult_it_too():
	"""The two surfaces that had it and did not. They reach the doctype's rules
	through `lib/fields/state.js` now — §B5 — which folds them in with the six
	other clauses rather than leaving each surface to remember this one."""
	spa = ROOT / "apps/oneapp/frontend/src/modules/onespace/components/screen"
	grid = (spa / "record/ChildTable.vue").read_text()
	cell = (spa / "bodies/EditableCell.vue").read_text()
	for where, source in (("the child table", grid), ("the inline cell", cell)):
		assert "fieldState" in source, f"{where} does not read the doctype's rules"


# ---------------------------------------------------------------------------
# §B5 — one resolver, three renderings
# ---------------------------------------------------------------------------

SPA = ROOT / "apps/oneapp/frontend/src"

# Where a field is rendered for editing. Each of these used to fold its own
# list of clauses, and the lists disagreed.
FIELD_SURFACES = [
	"modules/onespace/components/screen/record/FormSections.vue",
	"modules/onespace/components/screen/record/ChildTable.vue",
	"modules/onespace/components/screen/bodies/EditableCell.vue",
]


def test_every_field_surface_asks_the_one_resolver():
	"""Four surfaces asked "may I edit this?" and got four different answers —
	which is how a field locked by `read_only_depends_on` came to be editable
	in a grid and in a list cell. There is one function now and each of them
	calls it."""
	for one in FIELD_SURFACES:
		text = (SPA / one).read_text()
		assert "fieldState" in text, f"{one} no longer asks `fieldState`"
		assert "lib/fields/state" in text, f"{one} resolves a field state itself"


def _code(text: str) -> str:
	"""The source with its line comments taken out.

	A guard keyed on a word has to be able to tell a decision from a note about
	one: these files say *why* a clause moved, and saying so is not keeping it.
	"""
	return "\n".join(
		line.split("//")[0] for line in text.splitlines()
	)


def test_no_surface_rolls_its_own_lock():
	"""The clauses that used to be spelled out per surface belong to the
	resolver now. A surface that spells one out again is the start of the next
	disagreement."""
	rolled = ("set_only_once", "allow_on_submit")
	offenders = []
	for one in FIELD_SURFACES:
		text = _code((SPA / one).read_text())
		for clause in rolled:
			if clause in text:
				offenders.append(f"{one}: {clause}")
	assert not offenders, (
		"these decide for themselves what `lib/fields/state.js` decides: "
		+ ", ".join(offenders)
	)


def test_a_locked_field_is_not_a_disabled_control():
	"""§B5's whole visual argument. `disabled` means *momentarily* unavailable;
	a field you may not write is information, and information reads as text.
	A caller that passes `:disabled` for "the record is locked" puts twelve
	greyed boxes on a screen, which is what a record looked like before."""
	control = (SPA / "modules/onespace/components/screen/fields/FieldControl.vue").read_text()
	assert "ReadValue" in control, "FieldControl no longer has a read-only rendering"
	assert "state: { type: String" in control, "FieldControl no longer takes a state"
	for one in FIELD_SURFACES:
		text = (SPA / one).read_text()
		if "<FieldControl" not in text:
			continue
		assert ":disabled=" not in text.split("<FieldControl")[1].split("/>")[0], (
			f"{one} passes `:disabled` to a FieldControl; the prop is `state`"
		)


def test_the_three_states_are_one_list():
	"""Three, and `disabled` is not one of them. A fourth spelling would be a
	state nothing renders."""
	state = (SPA / "shared/lib/fields/state.js").read_text()
	for one in ("writable", "readonly", "hidden"):
		assert f"'{one}'" in state, f"`{one}` is no longer a field state"
