"""A screen narrowed to whoever is reading it.

`onespace/mine.py` is four lines of substitution and one safety property, and
the property is the whole reason it is its own module: **an unresolvable
subject narrows to nothing.**

Every other way of getting this wrong is loud. A reader who cannot be
identified and is shown an empty My leave will say so. A reader who cannot be
identified and has the clause quietly dropped is shown *everybody's* leave, on
a screen whose label says it is theirs, and nothing anywhere complains. That is
the test below that matters; the rest are the shapes it has to survive.
"""

import types

import pytest


@pytest.fixture
def mine(stub_frappe):
	from oneapp.onespace import mine as module

	stub_frappe.get_hooks = lambda key, *a, **kw: {}
	return types.SimpleNamespace(it=module, frappe=stub_frappe)


#: Path → what that provider answers, or an exception for it to raise.
ANSWERS: dict = {}


def _provider(frappe, kind, answer):
	path = f"some.app.{kind}"
	ANSWERS[path] = answer
	frappe.get_hooks = lambda key, *a, **kw: (
		{kind: [path]} if key == "onespace_subjects" else {}
	)

	def get_attr(asked):
		found = ANSWERS[asked]
		if isinstance(found, Exception):
			def boom():
				raise found
			return boom
		return lambda: found

	frappe.get_attr = get_attr


# --------------------------------------------------------------------------- #
# The one that matters
# --------------------------------------------------------------------------- #

def test_a_subject_nobody_can_resolve_narrows_to_nothing(mine):
	"""Not to everything, which is the same bug that leaks a payroll."""
	_provider(mine.frappe, "employee", "")

	found = mine.it.resolve({"employee": "@me:employee"})
	assert "employee" in found, (
		"the clause was dropped — the screen now shows every row in the "
		"doctype under a label that says it is this person's"
	)
	assert found["employee"] == mine.it.NOBODY


def test_a_kind_nobody_registered_narrows_to_nothing(mine):
	assert mine.it.resolve({"employee": "@me:employee"})["employee"] == mine.it.NOBODY


def test_a_provider_that_raises_narrows_to_nothing(mine):
	_provider(mine.frappe, "employee", RuntimeError("no"))
	assert mine.it.resolve({"employee": "@me:employee"})["employee"] == mine.it.NOBODY


def test_nobody_is_not_a_name_any_row_could_hold(mine):
	"""A sentinel that collided with a real id would be worse than no filter:
	it would show one arbitrary person's rows to everybody."""
	assert "\x00" in mine.it.NOBODY, (
		"the sentinel is now something an autoname could produce"
	)


# --------------------------------------------------------------------------- #
# The shapes
# --------------------------------------------------------------------------- #

def test_bare_me_is_the_session_s_user(mine):
	mine.frappe.session.user = "omar@example.com"
	assert mine.it.resolve({"owner": "@me"})["owner"] == "omar@example.com"


def test_a_registered_kind_is_asked(mine):
	_provider(mine.frappe, "employee", "HR-EMP-7")
	assert mine.it.resolve({"employee": "@me:employee"})["employee"] == "HR-EMP-7"


def test_an_operator_pair_is_rewritten_too(mine):
	"""`_all_filters` reads a `[operator, value]` pair as anything but equality,
	and a sentinel left inside one is a filter matching four characters."""
	mine.frappe.session.user = "omar@example.com"
	assert mine.it.resolve({"owner": ["!=", "@me"]})["owner"] == ["!=", "omar@example.com"]


def test_everything_else_is_left_alone(mine):
	asked = {"status": "Open", "amount": [">", 100], "employee": "HR-EMP-2"}
	assert mine.it.resolve(dict(asked)) == asked


def test_a_screen_with_no_filters_is_unchanged(mine):
	assert mine.it.resolve({}) == {}
	assert mine.it.resolve(None) == {}


def test_a_value_that_only_looks_like_a_sentinel_is_not_one(mine):
	"""`wanted` reads the start of the string, so a real value beginning with
	the same characters would be replaced. Nothing in this product names a row
	`@me…`, and the day something does this is where it shows."""
	assert mine.it.wanted("@me") is True
	assert mine.it.wanted("@me:employee") is True
	assert mine.it.wanted("not @me") is False
	assert mine.it.wanted(None) is False
	assert mine.it.wanted(7) is False
