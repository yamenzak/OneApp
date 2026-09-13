"""A space with more than one seat, and the screen that belongs to one of them.

Every space until now shipped exactly one role, so "what did this space grant"
and "what did it grant *me*" were the same question and `_granted_doctypes`
answered both by reading one role's DocPerms. They stopped being the same
question the moment a manifest could name a role on a grant — and the failure
was total rather than partial: a doctype granted to a named role was granted to
*nobody* as far as the resolver was concerned, because the resolver only ever
looked at the base role.

OneHR is what made it visible. Attendance belongs to the people officer, so
opening the Attendance screen — which is in the rail, in front of you, under a
heading called Time — answered "Attendance is not part of OneHR", for every
seat including the one that holds it.
"""

import types

import pytest

from test_screens import spaceview  # noqa: F401


@pytest.fixture
def seated(spaceview, stub_frappe):  # noqa: F811
	"""A space whose manifest became three roles, and the DocPerms behind them.

	`OneSpace HR` is the default seat, and the other two are named after the
	jobs — which is `entitlements.registry.frappe_role_for`, and the convention
	`_space_roles` reads back.
	"""
	perms = {
		"OneSpace HR": ["Employee", "Leave Application"],
		"OneSpace HR People officer": ["Attendance", "Job Applicant"],
		"OneSpace HR Payroll": ["Salary Slip"],
	}

	def get_all(doctype, filters=None, pluck=None, **kw):
		filters = filters or {}
		if doctype == "Role":
			like = str(filters.get("name", ["", ""])[1]).rstrip("%").strip()
			return [one for one in perms if one != like and one.startswith(like)]
		if doctype == "Custom DocPerm":
			asked = filters.get("role")
			roles = asked[1] if isinstance(asked, list) else [asked]
			return [dt for role in roles for dt in perms.get(role, [])]
		return []

	stub_frappe.get_all = get_all
	return types.SimpleNamespace(module=spaceview, perms=perms)


SPACE = {"role_name": "OneSpace HR", "space_label": "OneHR"}


def test_a_space_knows_every_role_its_manifest_became(seated, stub_frappe):
	assert sorted(seated.module._space_roles(SPACE)) == [
		"OneSpace HR", "OneSpace HR Payroll", "OneSpace HR People officer",
	]


def test_a_space_with_no_role_reaches_nothing(seated):
	"""Not everything: a cached space with no role name is a space whose
	permissions were never written, and answering "everything" would be a
	screen that renders and then fails at the query."""
	assert seated.module._space_roles({}) == []
	assert seated.module._granted_doctypes({}) == set()


def test_the_seat_you_hold_is_what_you_reach(seated, stub_frappe):
	stub_frappe.get_roles = lambda *a: ["OneSpace HR", "OneSpace HR Payroll"]
	assert seated.module._granted_doctypes(SPACE) == {
		"Employee", "Leave Application", "Salary Slip",
	}


def test_a_doctype_granted_to_another_seat_is_still_part_of_the_space(seated, stub_frappe):
	"""The distinction the two refusals are made of. Attendance is OneHR's; it
	is simply not this person's — and a message saying it is not part of the
	space is wrong in a way that sends somebody looking at the manifest."""
	stub_frappe.get_roles = lambda *a: ["OneSpace HR"]

	assert "Attendance" not in seated.module._granted_doctypes(SPACE)
	assert "Attendance" in seated.module._granted_doctypes(SPACE, held=False)


def test_the_named_seats_reach_what_the_base_one_cannot(seated, stub_frappe):
	"""The bug itself, stated as a rule: reading the base role alone makes
	every grant that names a seat unreachable by everybody."""
	stub_frappe.get_roles = lambda *a: ["OneSpace HR", "OneSpace HR People officer"]
	reached = seated.module._granted_doctypes(SPACE)
	assert "Attendance" in reached and "Job Applicant" in reached
	assert "Salary Slip" not in reached, "that seat is the payroll officer's"
