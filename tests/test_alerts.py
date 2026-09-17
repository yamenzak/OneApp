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
	from oneapp.onespace import alerts as module

	monkeypatch.setattr(
		module.sync, "granted_doctypes",
		lambda: {"Sales Invoice", "Project"},
	)
	# The other half of the narrowing. `roles()` reads the synced state and
	# there is no bench here; what the tests care about is that `save` checks
	# the name against *some* list, which the refusal test below proves.
	monkeypatch.setattr(
		module, "roles",
		lambda: [{"value": "OneSpace Workspace Owner", "label": "Owner"}],
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
	`event` the scheduler and the document hooks already read.

	Read off Frappe's own Select rather than copied into a set here. A copy
	passes for as long as nobody looks at it, and the thing worth catching is
	upstream renaming one — at which point our rules keep saving and stop
	firing, which no test of a hardcoded list can see.
	"""
	import upstream

	offered = upstream.options("Notification", "event")
	if not offered:
		pytest.skip("no bench with Notification's JSON")
	theirs = {line.strip() for line in offered.split("\n") if line.strip()}
	assert set(alerts.WHEN.values()) <= theirs, (
		f"not events Frappe fires: {sorted(set(alerts.WHEN.values()) - theirs)}"
	)


def test_an_event_that_needs_a_field_is_told_which(alerts):
	"""Frappe refuses a `Value Change` with no `value_changed`, and refuses it
	on save — which would be a settings page that throws in Frappe's words
	about a field our form does not have."""
	assert set(alerts.WATCHED) <= set(alerts.WHEN)
	assert alerts.WHEN["decided"] == "Value Change"


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


def test_a_rule_files_its_in_app_row_under_a_kind_somebody_can_turn_off(
	alerts, monkeypatch
):
	"""The seam between this panel and the Notifications one.

	A rule with the in-app channel writes a `Notification Log`, which is the
	store the bell reads — so alerts were always arriving there. Frappe stamps
	the row `notification_type or "Alert"`, and an undeclared kind gets no
	switch in the settings panel: the notification arrived and there was no way
	to stop it arriving. Setting it from `notifications` is what ties the two
	halves together, and the assertion is that the name is a declared one
	rather than a string that happens to match.
	"""
	from oneapp.onespace import notifications

	written = {}

	class Recorder:
		is_standard = 0
		name = "ALERT-1"

		def update(self, values):
			written.update(values)

		def set(self, field, value):
			pass

		def append(self, field, row):
			pass

		def save(self, **kwargs):
			pass

		def get(self, field, default=None):
			return written.get(field, default)

	monkeypatch.setattr(alerts, "_meta", lambda doctype: meta(status="Select"))
	# `raising=False`: the stub frappe in `conftest` carries only what the
	# modules under test reach for, and nothing had needed `new_doc` before.
	monkeypatch.setattr(
		alerts.frappe, "new_doc", lambda doctype: Recorder(), raising=False
	)
	monkeypatch.setattr(alerts, "_read", lambda doc: written)

	alerts.save({
		"doctype": "Project", "when": "created", "subject": "Overdue",
		"to_role": "OneSpace Workspace Owner", "channel": "app",
	})

	assert written["notification_type"] == notifications.ALERT_TYPE
	assert notifications.ALERT_TYPE in notifications.KINDS


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


def test_a_rule_naming_a_role_outside_the_workspace_is_refused(alerts, monkeypatch):
	"""`receiver_by_role` is a free-text Link to Role, so the picker narrowing
	the list is not the check. Without this, a posted payload naming
	`System Manager` writes a rule that mails us — which is the thing the
	comment on `roles()` says the narrowing exists to stop."""
	monkeypatch.setattr(alerts, "_meta", lambda doctype: meta(status="Select"))
	with pytest.raises(Exception):
		alerts.save({"doctype": "Project", "when": "created", "subject": "x",
		             "to_role": "System Manager"})


# --------------------------------------------------------------------------- #
# Who a rule can reach
# --------------------------------------------------------------------------- #

def test_an_approver_is_somewhere_an_alert_can_be_sent(alerts):
	"""The gap that made every approval rule unwritable. A Link to User holds
	the person who decides — `leave_approver` on a Leave Application — and
	Frappe resolves it as an address because a user is named by their email."""
	fields = [
		types.SimpleNamespace(fieldname="leave_approver", fieldtype="Link",
		                      label="Leave Approver", options="User", hidden=0),
		types.SimpleNamespace(fieldname="contact_email", fieldtype="Data",
		                      label="Email", options="Email", hidden=0),
		types.SimpleNamespace(fieldname="employee", fieldtype="Link",
		                      label="Employee", options="Employee", hidden=0),
	]
	found = {one["fieldname"] for one in alerts.addressable(
		types.SimpleNamespace(fields=fields))}
	assert {"leave_approver", "contact_email", alerts.OWNER} <= found
	# And a Link that is not a user is not an address. A rule naming it passed
	# the old `("Data", "Link")` check, resolved to `HR-EMP-00003`, failed
	# Frappe's own `validate_email_address` and sent to nobody — silently.
	assert "employee" not in found


def test_whoever_filed_it_is_always_addressable(alerts):
	"""`owner` is not a field and is on every doctype. It is the only spelling
	of "tell the person who asked" these doctypes have: `employee` holds a
	record id, not an address."""
	assert alerts.addressable(types.SimpleNamespace(fields=[]))[0]["fieldname"] \
		== alerts.OWNER
	# And nothing is addressable on a doctype that does not exist.
	assert alerts.addressable(None) == []


# --------------------------------------------------------------------------- #
# The rules a space arrives with
#
# A space that grants Leave Application knows the person who has to approve one
# should hear about it, and a workspace should not have to work that out from an
# empty settings page. So a manifest may ship rules — and they arrive as *the
# workspace's own*, seeded once and then left alone.
# --------------------------------------------------------------------------- #

@pytest.fixture
def seeding(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	from oneapp.onespace import sync as module

	return module


def test_a_shipped_rule_is_written_once_and_then_left_alone(seeding, stub_frappe,
                                                            monkeypatch):
	"""The same contract the custom fields and print formats have, and it
	matters for the same reason: a rule a workspace reworded is a rule they
	reworded, and reapplying every quarter hour would undo it with nothing
	anywhere to say why."""
	from oneapp.onespace import alerts

	written, held = [], set()
	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: doctype == "DocType" or name in held)
	monkeypatch.setattr(alerts, "save", lambda row: written.append(row))

	rows = [{"doctype": "Leave Application", "when": "created",
	         "to_field": "leave_approver", "subject": "Leave to approve"}]

	assert seeding._seed_alerts(rows, {}) == 1
	assert len(written) == 1

	held.add("Leave to approve")
	assert seeding._seed_alerts(rows, {}) == 0
	assert len(written) == 1


def test_a_rule_that_will_not_write_costs_one_rule_rather_than_the_sync(
	seeding, stub_frappe, monkeypatch
):
	"""A rule naming a field HRMS renamed is one rule that does not arrive.
	Nothing here may fail a sync that also carries roles, members and quotas."""
	from oneapp.onespace import alerts

	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)

	def boom(row):
		raise ValueError("no such field")

	monkeypatch.setattr(alerts, "save", boom)
	assert seeding._seed_alerts(
		[{"doctype": "Leave Application", "when": "created", "subject": "x"}], {}
	) == 0


def test_a_rule_with_nothing_to_be_about_is_skipped(seeding, stub_frappe, monkeypatch):
	"""A space is only granted onto a site carrying the apps it needs, but one
	can be installing while this runs — and a row with no subject has no
	primary key, so it would collide with the next one."""
	from oneapp.onespace import alerts

	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: False)
	monkeypatch.setattr(alerts, "save", lambda row: None)
	assert seeding._seed_alerts([
		{"doctype": "Leave Application", "when": "created", "subject": "x"},
		{"doctype": "", "when": "created", "subject": "y"},
		{"doctype": "Leave Application", "when": "created", "subject": ""},
		"not a rule at all",
	], {}) == 0
	assert seeding._seed_alerts("not a list", {}) == 0


def test_a_manifest_names_a_seat_by_its_label(seeding, stub_frappe, monkeypatch):
	"""A manifest cannot write the Frappe role down: the name is derived from
	the space's `role_name`, which is a prefix the control plane owns. So it
	names one of the four seat labels and this composes `<prefix>-<Seat>`.

	A label that is not one of the four is nothing, not the prefix. It used to
	fall back, which is how a typo in a field-level row quietly granted the
	level to everybody in the space."""
	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: name == "HR-Manager")

	space = {"role_name": "HR"}
	assert seeding._space_role(space, "Manager") == "HR-Manager"
	assert seeding._space_role(space, "Nobody") == ""
	assert seeding._space_role({}, "Manager") == ""
	# A seat this site does not hold is nothing, so a rule naming it is
	# skipped rather than addressed to a role that does not exist.
	assert seeding._space_role(space, "Admin") == ""


def test_a_rule_whose_role_this_site_does_not_have_is_skipped(seeding, stub_frappe,
                                                              monkeypatch):
	"""Rather than written addressed to nobody, which is a rule that looks
	present in Settings and silently reaches no one."""
	from oneapp.onespace import alerts

	written = []
	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: doctype == "DocType")
	monkeypatch.setattr(alerts, "save", lambda row: written.append(row))

	assert seeding._seed_alerts(
		[{"doctype": "Travel Request", "when": "created",
		  "to_role_label": "Manager", "subject": "Somebody asked to travel"}],
		{"role_name": "HR"},
	) == 0
	assert written == []
