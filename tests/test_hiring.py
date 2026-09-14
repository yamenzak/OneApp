"""The three verbs HRMS keeps in the desk's Create menu.

Scheduling an interview, making an offer and hiring the person who accepted one
were reachable only from `/app`, because the desk's own buttons are JavaScript
an app ships and running that is the door `docs/UNIFICATION.md` rail 34 refuses.

What is worth pinning is not the field values — those are four lines and a
browser pass reads them back — but the two rules underneath:

**None of these inserts.** All three targets have required fields nobody can
derive: an Interview needs a type and a time, an Employee needs a date of birth.
A verb that inserted would either fail validation or skip it, and skipping it is
how a workspace ends up with an Employee payroll cannot run.

**A verb answers with what should happen next; the engine does it.** So the
answer is a shape `spaceview/run.py` understands, and a verb that returned a
document or navigated itself would be the thing this indirection exists to
prevent.
"""

import types

import pytest


@pytest.fixture
def hiring(stub_frappe):
	from oneapp.onehr import hiring as module

	stub_frappe.db.exists = lambda *a, **kw: True
	stub_frappe.has_permission = lambda *a, **kw: True
	return types.SimpleNamespace(it=module, frappe=stub_frappe)


def _applicant(frappe, **fields):
	row = types.SimpleNamespace(
		name="dana@example.test", applicant_name="Dana", email_id="dana@example.test",
		designation="Engineer", job_title="HR-OPN-0001", company="Acme",
		status="Shortlisted", resume_link="",
	)
	for key, value in fields.items():
		setattr(row, key, value)
	frappe.get_doc = lambda *a, **kw: row
	return row


# --------------------------------------------------------------------------- #
# What a verb answers with
# --------------------------------------------------------------------------- #

def test_a_verb_asks_for_a_record_rather_than_writing_one(hiring):
	"""The rule that keeps the permission and the validation on the target
	screen rather than in here."""
	_applicant(hiring.frappe)
	answer = hiring.it.interview("dana@example.test")

	assert set(answer) == {"create"}
	assert answer["create"]["screen"] == "interviews"
	assert "open" not in answer


def test_scheduling_sends_the_applicant_and_nothing_it_could_have_derived(hiring):
	"""Interview fetches the opening, the designation and the résumé link off
	the applicant. Sending them too would be this verb having an opinion about
	values HRMS derives — and the first one HRMS changes is the one that then
	disagrees."""
	_applicant(hiring.frappe)
	values = hiring.it.interview("dana@example.test")["create"]["values"]

	assert values == {"job_applicant": "dana@example.test"}


def test_an_offer_sends_what_no_applicant_carries(hiring):
	"""The other side of the same rule: `company` and the date are required and
	are not on the applicant, and the name, email and designation are."""
	_applicant(hiring.frappe)
	hiring.frappe.utils = types.SimpleNamespace(today=lambda: "2026-09-14")
	values = hiring.it.offer("dana@example.test")["create"]["values"]

	assert values["job_applicant"] == "dana@example.test"
	assert values["company"] == "Acme"
	assert values["offer_date"] == "2026-09-14"
	assert "applicant_name" not in values
	assert "designation" not in values


def test_the_screens_a_verb_names_are_named_once(hiring):
	"""Every verb sends the reader to a screen, and `run_action` resolves that
	name against the space before it hands the answer back — so a rename that
	missed this module fails at the verb. Pinned here so the three constants
	stay the only spelling of it."""
	declared = hiring.it.actions()
	assert set(declared) == {"onehr/applicants", "onehr/offers"}
	for rows in declared.values():
		for row in rows:
			assert row["method"].startswith("oneapp.onehr.hiring.")
			assert row["scope"] == "one"


# --------------------------------------------------------------------------- #
# The refusals
# --------------------------------------------------------------------------- #

def test_only_an_accepted_offer_becomes_an_employee(hiring):
	"""The button is on every offer — one that vanished at some statuses is one
	nobody learns is there — so the refusal is where the decision lives."""
	hiring.frappe.db.get_value = lambda *a, **kw: "Awaiting Response"
	with pytest.raises(hiring.frappe.ValidationError):
		hiring.it.hire("HR-OFF-0001")


def test_an_offer_to_somebody_already_rejected_is_refused(hiring):
	_applicant(hiring.frappe, status="Rejected")
	with pytest.raises(hiring.frappe.ValidationError):
		hiring.it.offer("dana@example.test")


def test_a_workspace_without_hiring_says_so(hiring):
	hiring.frappe.db.exists = lambda *a, **kw: False
	with pytest.raises(hiring.frappe.ValidationError):
		hiring.it.interview("dana@example.test")


# --------------------------------------------------------------------------- #
# What crosses to the browser
# --------------------------------------------------------------------------- #

def test_frappe_s_own_bookkeeping_does_not_travel(hiring):
	"""`hire` hands back HRMS's mapped Employee, and a Document carries a great
	deal a New dialog has no use for. What crosses is field values."""
	for field in ("doctype", "name", "owner", "creation", "docstatus", "idx",
	              "__islocal", "_user_tags"):
		assert not hiring.it._wanted(field, "x"), field

	assert hiring.it._wanted("first_name", "Dana")
	# And nothing empty, which would arrive as a control somebody has to clear.
	assert not hiring.it._wanted("first_name", "")
	assert not hiring.it._wanted("first_name", None)
	# Nor a child table, which a dialog cannot seed.
	assert not hiring.it._wanted("rows", [{"a": 1}])
