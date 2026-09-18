"""Branching, and why a condition here is a grammar rather than an expression.

`docs/ONEFORMS.md` §14, stage 10. `Web Form Field.depends_on` has carried the
answer to the browser since stage 1 and the page never read it — the same shape
of bug as the Column Break that drew an empty text box.

Fixing it was not "read the field", because of what the field *is*:
`depends_on` holds a JavaScript expression (`eval:doc.status=="Open"`) and
Frappe's own renderer evaluates it. §12 refused exactly that for
`client_script`, and the argument is unchanged — a page strangers open does not
run a customer's code, and an admin's own code is still code.

So three claims:

  * **Nothing evaluates anything.** A condition is parsed into `{field, op,
    value}` on save, stored canonically, and compared.
  * **An `eval:` is refused rather than ignored**, so a form imported from a
    Frappe site says so on the way in.
  * **A condition is a rule, not a drawing.** The submit path clears what the
    condition hides, because a browser that declined to draw a field is a
    browser and `send` is open to anybody with the route.
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/oneforms/showing.py"
PUBLIC = ROOT / "apps/oneapp/oneapp/oneforms/public.py"
BROWSER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/lib/showing.js"
PAGE = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue"
BUILDER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/FormBuilder.vue"


@pytest.fixture
def showing(stub_frappe):
	from oneapp.oneforms import showing

	return showing


# ------------------------------------------------------------------ the grammar

def test_a_comparison_is_read_into_its_parts(showing):
	assert showing.parse('status == "Open"') == {
		"field": "status", "op": "==", "value": "Open"}
	assert showing.parse("count >= 3") == {
		"field": "count", "op": ">=", "value": "3"}
	assert showing.parse('kind in "a, b"') == {
		"field": "kind", "op": "in", "value": "a, b"}


def test_nothing_is_a_condition_that_is_always_true(showing):
	assert showing.parse("") == {} and showing.parse("   ") == {}
	assert showing.holds({}, {}) is True


def test_an_unquoted_value_is_read_the_same_as_a_quoted_one(showing):
	"""Nobody types the quotes reliably and the difference is not a meaning."""
	assert showing.parse("status == Open")["value"] == "Open"
	assert showing.parse("status == 'Open'")["value"] == "Open"


def test_an_eval_expression_is_refused_by_name(showing):
	"""Frappe's own shape, which is what a form imported from a Frappe site
	carries. Refused rather than ignored, so it says so on the way in."""
	with pytest.raises(Exception) as refused:
		showing.parse('eval:doc.status=="Open"')
	assert "eval:" in str(refused.value)


def test_anything_that_is_not_a_comparison_is_refused(showing):
	"""Including the things that would have *run* under the old field."""
	for said in ('doc.status == "Open" && doc.x', "fetch('//x')", "1 == 1",
	             "status", "== Open", "status =="):
		with pytest.raises(Exception):
			showing.parse(said)


def test_an_ordering_needs_a_number_on_the_right(showing):
	with pytest.raises(Exception) as refused:
		showing.parse('count > "lots"')
	assert "number" in str(refused.value)


def test_it_is_written_back_the_same_way_however_it_was_typed(showing):
	"""Two people who wrote the same condition differently end up with the same
	document, so a diff of a form says something."""
	one = showing.written(showing.parse("status==Open"))
	two = showing.written(showing.parse('  status  ==  "Open"  '))
	assert one == two == 'status == "Open"'
	assert showing.written(showing.parse("count>3")) == "count > 3"


def test_a_condition_on_a_field_the_form_has_not_got_is_refused(showing):
	"""Nothing would ever make it true, so the field is hidden for ever — which
	is the shape of somebody renaming something and not noticing."""
	assert showing.check('status == "Open"', {"status"}) == 'status == "Open"'
	with pytest.raises(Exception) as refused:
		showing.check('stauts == "Open"', {"status"})
	assert "stauts" in str(refused.value)


# ------------------------------------------------------------------ comparing

def test_yes_and_Yes_are_the_same_answer(showing):
	"""The difference is a Select option's capitalisation that nobody filling
	the form in can see."""
	rule = showing.parse('agreed == "yes"')
	assert showing.holds(rule, {"agreed": "Yes"})
	assert showing.holds(rule, {"agreed": " YES "})
	assert not showing.holds(rule, {"agreed": "no"})


def test_a_number_typed_into_a_box_compares_as_a_number(showing):
	"""The browser sends "3", and a condition written `count == 3` means it."""
	assert showing.holds(showing.parse("count == 3"), {"count": "3"})
	assert showing.holds(showing.parse("count > 2"), {"count": 3})
	assert not showing.holds(showing.parse("count > 2"), {"count": "1"})


def test_a_checkbox_is_a_number_whichever_way_it_was_sent(showing):
	for sent in (1, True, "1", "true"):
		assert showing.holds(showing.parse("agreed == 1"), {"agreed": sent})
	for sent in (0, False, "0", "false", ""):
		assert not showing.holds(showing.parse("agreed == 1"), {"agreed": sent})


def test_an_unanswered_question_answers_nothing(showing):
	"""`!= ""` is how "when they have said something" is written, and it has to
	be false before they have."""
	rule = showing.parse('other != ""')
	assert not showing.holds(rule, {})
	assert showing.holds(rule, {"other": "something"})


def test_an_ordering_against_nothing_is_false_rather_than_an_error(showing):
	assert not showing.holds(showing.parse("count > 2"), {"count": ""})
	assert not showing.holds(showing.parse("count > 2"), {})


def test_one_of_several_is_written_as_a_list(showing):
	rule = showing.parse('kind in "car, van, bike"')
	assert showing.holds(rule, {"kind": "van"})
	assert not showing.holds(rule, {"kind": "boat"})


# ------------------------------------------------------- a rule, not a drawing

def test_what_the_condition_hides_is_named_from_the_values(showing):
	fields = [
		{"fieldname": "kind", "depends_on": ""},
		{"fieldname": "other", "depends_on": 'kind == "other"'},
	]
	assert showing.hides(fields, {"kind": "other"}) == set()
	assert showing.hides(fields, {"kind": "car"}) == {"other"}


def test_a_chain_resolves_without_iterating(showing):
	"""B waits on A and C waits on B. A hidden field carries no value, so a
	condition on it is false — one pass is enough, and a *cycle* has no answer
	at all, so iterating would only pick one arbitrarily."""
	fields = [
		{"fieldname": "a", "depends_on": ""},
		{"fieldname": "b", "depends_on": 'a == "yes"'},
		{"fieldname": "c", "depends_on": 'b == "yes"'},
	]
	assert showing.hides(fields, {"a": "no"}) == {"b", "c"}


def test_the_submit_path_clears_them_rather_than_trusting_the_browser():
	"""`send` is open to anybody with the route, so a field the page declined
	to draw is a field the page declined to draw."""
	source = PUBLIC.read_text()
	sending = source.split("def send")[1]
	assert "showing.hides" in sending
	assert 'asked[gone] = ""' in sending


def test_the_page_is_sent_the_tuple_and_not_the_string():
	"""What crosses the wire is `{field, op, value}`. A string that arrived as
	code and was compared as code would be the thing this avoids."""
	source = PUBLIC.read_text()
	assert '"shown_when"' in source and "showing.parse" in source


def test_nothing_on_either_side_evaluates_anything():
	"""The claim the whole file rests on, read off both halves."""
	tree = ast.parse(SOURCE.read_text())
	called = {ast.unparse(node.func) for node in ast.walk(tree)
	          if isinstance(node, ast.Call)}
	assert not called & {"eval", "exec", "compile", "frappe.safe_eval"}

	browser = BROWSER.read_text()
	for banned in ("eval(", "new Function", "Function(", "setTimeout("):
		assert banned not in browser


def test_the_browser_sends_only_what_it_asked():
	"""Somebody who answers a question, changes the answer above it and so puts
	that question away has left a value behind for something the form stopped
	asking."""
	assert "export function answered" in BROWSER.read_text()
	assert "answered(form.value?.fields" in PAGE.read_text()


def test_the_two_limits_the_field_already_carried_are_enforced(showing):
	"""`max_length` and `max_value` are in `SHAPE` and were on the wire from
	stage 1 — the same bug as the condition, one layer down. And nothing
	enforced them: `validate_submission` checks `reqd` and a Data field's
	`options` and not these, and `FormControl` does not even take a
	`maxlength`. So the check is the server's, like the condition."""
	fields = [{"fieldname": "why", "label": "Why you", "max_length": 10},
	          {"fieldname": "many", "label": "How many", "max_value": 5}]

	showing.within(fields, {"why": "short", "many": 3})

	with pytest.raises(Exception) as refused:
		showing.within(fields, {"why": "a very long answer indeed"})
	assert "Why you" in str(refused.value) and "10" in str(refused.value)

	with pytest.raises(Exception) as refused:
		showing.within(fields, {"many": "9"})
	assert "How many" in str(refused.value)


def test_a_limit_refuses_rather_than_truncates(showing):
	"""A form that silently cut somebody's covering letter in half would lose
	the end of it without telling anybody, and the person who finds out is the
	one reading the record."""
	assert "frappe.throw" in SOURCE.read_text().split("def within")[1]
	assert "[:" not in SOURCE.read_text().split("def within")[1]


def test_the_submit_path_checks_the_limits_too():
	assert "showing.within" in PUBLIC.read_text().split("def send")[1]
	# And somewhere to set them, on the fieldtypes they mean anything for.
	builder = BUILDER.read_text()
	assert "max_length" in builder and "NUMERIC" in builder


def test_a_condition_is_written_in_the_builder_rather_than_only_imported():
	assert 'data-slot="builder-when"' in BUILDER.read_text()
