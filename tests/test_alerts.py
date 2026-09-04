"""Rules that tell somebody when something happens to a record.

Two things are worth testing here and one of them is the reason the module
exists in this shape.

`Notification.condition` is `frappe.safe_eval`'d with the document in scope, so
the difference between "a workspace writes a condition" and "a workspace runs
code" is whether the string was typed or compiled. It is compiled, from a
triple this module validated, and these are the tests that say so.

The rest is the narrowing: five events rather than eight, this workspace's
doctypes rather than the site's, this workspace's roles rather than Frappe's
whole list, and a refusal to touch a rule an app shipped.
"""

import types

import pytest


@pytest.fixture
def alerts(monkeypatch):
	from oneapp.oneapp_core import alerts as module

	monkeypatch.setattr(
		module.sync, "granted_doctypes",
		lambda: {"Sales Invoice", "Project"},
	)
	return module


def meta(**fields):
	"""A doctype's metadata as `_condition` and `save` read it."""
	rows = [
		types.SimpleNamespace(fieldname=name, fieldtype=kind, label=name, options="")
		for name, kind in fields.items()
	]
	return types.SimpleNamespace(
		fields=rows,
		is_submittable=0,
		get_field=lambda name: next((f for f in rows if f.fieldname == name), None),
	)


# --------------------------------------------------------------------------- #
# A condition is built, never typed
# --------------------------------------------------------------------------- #

def test_a_condition_becomes_an_expression(alerts):
	built = alerts._condition(
		meta(status="Select"),
		{"field": "status", "operator": "is", "value": "Overdue"},
	)
	assert built == 'doc.status == "Overdue"'


def test_a_value_cannot_end_the_string_and_start_an_expression(alerts):
	"""The whole reason the condition is not a text box.

	Frappe evaluates this string with the document in scope. A status somebody
	typed as `x" or frappe.get_doc(...)` must come out as a string containing
	those characters, not as two terms.
	"""
	built = alerts._condition(
		meta(status="Select"),
		{"field": "status", "operator": "is", "value": 'x" or 1=='},
	)
	assert built.startswith("doc.status == ")
	# The quote is escaped, so what follows the operator is one string literal
	# and not a string that ends early followed by a term. Parsed rather than
	# eyeballed — counting characters would pass on `x" or 1==` too, because
	# the `==` it contains is inside the quotes either way.
	import json
	tail = built[len("doc.status == "):]
	assert json.loads(tail) == 'x" or 1=='


def test_a_field_that_does_not_exist_is_refused(alerts):
	with pytest.raises(Exception):
		alerts._condition(meta(status="Select"),
		                  {"field": "nonsense", "operator": "is", "value": "x"})


def test_an_operator_that_is_not_offered_is_refused(alerts):
	"""The map is the allowlist. Without this the operator itself is the hole."""
	with pytest.raises(Exception):
		alerts._condition(meta(status="Select"),
		                  {"field": "status", "operator": "or 1==1 or", "value": "x"})


def test_more_than_needs_a_number(alerts):
	"""A comparison against a string would be a comparison Frappe evaluates."""
	with pytest.raises(Exception):
		alerts._condition(meta(total="Currency"),
		                  {"field": "total", "operator": "over", "value": "lots"})

	assert alerts._condition(
		meta(total="Currency"), {"field": "total", "operator": "over", "value": "500"},
	) == "doc.total > 500.0"


@pytest.mark.parametrize("operator,expected", [
	("is set", "doc.owner_email"),
	("is not set", "not doc.owner_email"),
])
def test_set_and_unset_need_no_value(alerts, operator, expected):
	assert alerts._condition(
		meta(owner_email="Data"), {"field": "owner_email", "operator": operator},
	) == expected


# --------------------------------------------------------------------------- #
# And read back out again
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("condition,expected", [
	('doc.status == "Overdue"', {"field": "status", "operator": "is", "value": "Overdue"}),
	("doc.total > 500.0", {"field": "total", "operator": "over", "value": "500.0"}),
	("doc.owner_email", {"field": "owner_email", "operator": "is set", "value": ""}),
	("not doc.owner_email", {"field": "owner_email", "operator": "is not set", "value": ""}),
	# A rule made in the desk with a real Jinja condition is not ours to
	# reopen in three controls, and saying so is better than guessing.
	("frappe.db.exists('X', doc.name)", None),
	("", None),
])
def test_a_condition_reads_back_as_the_triple_it_was(alerts, condition, expected):
	assert alerts._decompile(condition) == expected


def test_a_condition_survives_the_round_trip(alerts):
	"""Built, then read back for the form to reopen on. Two places holding the
	same fact is two places to disagree, so the string is the only copy."""
	triple = {"field": "status", "operator": "is not", "value": "Paid"}
	built = alerts._condition(meta(status="Select"), triple)
	assert alerts._decompile(built) == triple


# --------------------------------------------------------------------------- #
# The narrowing
# --------------------------------------------------------------------------- #

def test_the_events_offered_are_frappes_own(alerts):
	"""A vocabulary, not a second event system: every word maps onto the
	`event` the scheduler and the document hooks already read."""
	assert set(alerts.WHEN.values()) <= {
		"New", "Save", "Submit", "Cancel", "Days Before", "Days After",
	}


def test_slack_and_sms_are_not_offered(alerts):
	"""Frappe has four channels. Slack needs a webhook nobody configured and
	SMS needs a gateway we do not run, so offering either is offering a rule
	that silently does nothing."""
	assert set(alerts.CHANNELS.values()) == {"Email", "System Notification"}


def test_a_rule_on_an_ungranted_doctype_is_refused(alerts, monkeypatch):
	"""The manifest is the allowlist here as everywhere. A workspace that can
	put a rule on `Error Log` has been handed the platform's own bookkeeping to
	mail itself about."""
	with pytest.raises(Exception):
		alerts.save({"doctype": "Error Log", "when": "created", "subject": "x",
		             "to_role": "OneSpace Workspace Owner"})


def test_a_rule_needs_somebody_to_tell(alerts, monkeypatch):
	monkeypatch.setattr(alerts, "_meta", lambda doctype: meta(status="Select"))
	with pytest.raises(Exception):
		alerts.save({"doctype": "Project", "when": "created", "subject": "x"})


def test_a_rule_needs_a_subject(alerts, monkeypatch):
	"""It is the line people see — in the inbox and in the bell alike."""
	monkeypatch.setattr(alerts, "_meta", lambda doctype: meta(status="Select"))
	with pytest.raises(Exception):
		alerts.save({"doctype": "Project", "when": "created",
		             "to_role": "OneSpace Workspace Owner"})


def test_submitted_is_not_offered_on_a_doctype_that_is_not(alerts, monkeypatch):
	"""A rule that can never fire is worse than no rule: it reads as covered."""
	monkeypatch.setattr(alerts, "_meta", lambda doctype: meta(status="Select"))
	with pytest.raises(Exception):
		alerts.save({"doctype": "Project", "when": "submitted", "subject": "x",
		             "to_role": "OneSpace Workspace Owner"})


@pytest.mark.parametrize("days", [-1, 61, 900])
def test_a_wait_is_bounded(alerts, monkeypatch, days):
	"""The scheduler walks every dated rule every day, and a rule ninety days
	out is one whose author has forgotten it exists."""
	monkeypatch.setattr(alerts, "_meta", lambda doctype: meta(due_date="Date"))
	with pytest.raises(Exception):
		alerts.save({"doctype": "Project", "when": "after", "date_field": "due_date",
		             "days": days, "subject": "x", "to_role": "OneSpace Workspace Owner"})


def test_an_apps_own_rule_is_not_ours_to_change(alerts, monkeypatch):
	"""A standard Notification belongs to the app that shipped it and is
	exported to disk, so an edit here would be edited back on the next deploy —
	silently, which is the part that matters."""
	monkeypatch.setattr(
		alerts.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(is_standard=1),
	)
	with pytest.raises(Exception):
		alerts._ours("some-rule")
