"""A space with more than one seat, and the screen that belongs to one of them.

Every space until now shipped exactly one role, so "what did this space grant"
and "what did it grant *me*" were the same question and `_granted_doctypes`
answered both by reading one role's DocPerms. They stopped being the same
question the moment a manifest could name a role on a grant — and the failure
was total rather than partial: a doctype granted to a named role was granted to
*nobody* as far as the resolver was concerned, because the resolver only ever
looked at the base role.

OnePeople is what made it visible. Attendance belongs to the people officer, so
opening the Attendance screen — which is in the rail, in front of you, under a
heading called Time — answered "Attendance is not part of OnePeople", for every
seat including the one that holds it.
"""

import types

import pytest

from test_screens import spaceview  # noqa: F401


@pytest.fixture
def seated(spaceview, stub_frappe):  # noqa: F811
	"""A space's four seats, and the DocPerms behind three of them.

	`HR-User` is the default seat and the other three are its ladder, which is
	`spaces/roles.py` and the convention `_space_roles` derives. Audit holds
	nothing here because this fixture is about which seat reaches what, and an
	auditor reaching everything would make every assertion below pass.
	"""
	perms = {
		"HR-User": ["Employee", "Leave Application"],
		"HR-Manager": ["Attendance", "Job Applicant"],
		"HR-Admin": ["Salary Slip"],
	}

	def get_all(doctype, filters=None, pluck=None, **kw):
		filters = filters or {}
		if doctype == "Custom DocPerm":
			asked = filters.get("role")
			roles = asked[1] if isinstance(asked, list) else [asked]
			return [dt for role in roles for dt in perms.get(role, [])]
		return []

	stub_frappe.get_all = get_all
	return types.SimpleNamespace(module=spaceview, perms=perms)


SPACE = {"role_name": "HR", "space_label": "OnePeople"}


def test_a_space_knows_every_role_its_manifest_became(seated, stub_frappe):
	"""Derived from the prefix rather than looked up, so a seat nobody has
	granted anything to is still one of the space's four.

	The prefix itself is in the list for the two spaces the control plane runs
	over itself — the operator console and a customer's account area — which
	have one job each and one role rather than four."""
	assert seated.module._space_roles(SPACE) == [
		"HR", "HR-User", "HR-Manager", "HR-Audit", "HR-Admin",
	]


def test_a_space_with_no_role_reaches_nothing(seated):
	"""Not everything: a cached space with no role name is a space whose
	permissions were never written, and answering "everything" would be a
	screen that renders and then fails at the query."""
	assert seated.module._space_roles({}) == []
	assert seated.module._granted_doctypes({}) == set()


def test_the_seat_you_hold_is_what_you_reach(seated, stub_frappe):
	stub_frappe.get_roles = lambda *a: ["HR-User", "HR-Admin"]
	assert seated.module._granted_doctypes(SPACE) == {
		"Employee", "Leave Application", "Salary Slip",
	}


def test_a_doctype_granted_to_another_seat_is_still_part_of_the_space(seated, stub_frappe):
	"""The distinction the two refusals are made of. Attendance is OnePeople's; it
	is simply not this person's — and a message saying it is not part of the
	space is wrong in a way that sends somebody looking at the manifest."""
	stub_frappe.get_roles = lambda *a: ["HR-User"]

	assert "Attendance" not in seated.module._granted_doctypes(SPACE)
	assert "Attendance" in seated.module._granted_doctypes(SPACE, held=False)


def test_the_named_seats_reach_what_the_base_one_cannot(seated, stub_frappe):
	"""The bug itself, stated as a rule: reading one seat alone makes every
	grant naming another unreachable by everybody."""
	stub_frappe.get_roles = lambda *a: ["HR-User", "HR-Manager"]
	reached = seated.module._granted_doctypes(SPACE)
	assert "Attendance" in reached and "Job Applicant" in reached
	assert "Salary Slip" not in reached, "that seat is the space admin's"


# The same seats, and the rail each should be given.
#
# A screen per doctype above, plus the two cases that are deliberately kept: a
# component screen with nothing to grant, and one pointing at a doctype no role
# in this space grants at all.
RAIL = [
	{"screen": "people", "label": "People", "document_type": "Employee"},
	{"screen": "leave", "label": "Leave", "document_type": "Leave Application"},
	{"screen": "attendance", "label": "Attendance", "document_type": "Attendance"},
	{"screen": "payslips", "label": "Payslips", "document_type": "Salary Slip"},
	{"screen": "insights", "label": "Insights", "component": "HrInsights"},
	# A component screen that *does* name a doctype, for one reason: to say who
	# it is for. "Mark the day" is a page for whoever keeps attendance and
	# there is nothing else about it a grant could be read off.
	{"screen": "roster", "label": "Mark the day", "component": "HrRoster",
	 "document_type": "Attendance"},
	{"screen": "orphan", "label": "Orphan", "document_type": "Sales Invoice"},
]

WITH_RAIL = {**SPACE, "screens": RAIL}


def _shown(module, space):
	return [one["screen"] for one in module.navigable(space)]


def test_the_rail_offers_the_screens_this_seat_can_open(seated, stub_frappe):
	"""§4 of `docs/ERP-SPACES.md`: an employee saw Payslips and was refused it.

	The refusal is correct and the entry was not — a door drawn for somebody who
	may not walk through it is a rail that has to be learned rather than read.
	"""
	stub_frappe.get_roles = lambda *a: ["HR-User"]
	assert _shown(seated.module, WITH_RAIL) == [
		"people", "leave", "insights", "orphan",
	]


def test_another_seat_is_offered_its_own(seated, stub_frappe):
	stub_frappe.get_roles = lambda *a: ["HR-User", "HR-Admin"]
	assert "payslips" in _shown(seated.module, WITH_RAIL)
	assert "attendance" not in _shown(seated.module, WITH_RAIL)

	stub_frappe.get_roles = lambda *a: ["HR-User", "HR-Manager"]
	assert "attendance" in _shown(seated.module, WITH_RAIL)
	assert "payslips" not in _shown(seated.module, WITH_RAIL)


def test_a_screen_with_nothing_to_grant_is_always_offered(seated, stub_frappe):
	"""A component screen names no doctype, so there is no grant to consult and
	nothing to hide it by. Hiding it on a technicality would make the escape
	hatch in §2 unreachable for every seat but the one that happens to hold
	whatever else is in the space."""
	stub_frappe.get_roles = lambda *a: ["HR-User"]
	assert "insights" in _shown(seated.module, WITH_RAIL)


def test_a_component_screen_may_name_a_doctype_to_say_who_it_is_for(seated, stub_frappe):
	"""The other half of the rule above, and the reason it is not "component
	screens are always shown".

	A component screen has no grant to be hidden by — which is right for one
	that is a dashboard everybody reads, and wrong for one that is a form only
	the officer may post. Naming the doctype it writes is how such a screen
	says so, and it costs nothing: the resolver returns before it would have
	read any of it.
	"""
	stub_frappe.get_roles = lambda *a: ["HR-User"]
	assert "roster" not in _shown(seated.module, WITH_RAIL)

	stub_frappe.get_roles = lambda *a: ["HR-User", "HR-Manager"]
	assert "roster" in _shown(seated.module, WITH_RAIL)


def test_a_screen_no_seat_grants_stays_where_somebody_can_see_it(seated, stub_frappe):
	"""The other refusal, kept visible on purpose. A doctype outside every role
	in the space is a manifest that does not add up, and a rail that quietly
	drops it turns a mistake somebody can see into one nobody can."""
	stub_frappe.get_roles = lambda *a: ["HR-User", "HR-Admin"]
	assert "orphan" in _shown(seated.module, WITH_RAIL)


def test_a_site_that_granted_nothing_keeps_its_whole_rail(seated, stub_frappe):
	"""Permissions are written by the entitlement sync, and a site where that
	has never run has no DocPerms at all. Narrowing against nothing would empty
	the rail of a space that works — so the absence of grants is read as "do not
	know", which is what it is."""
	stub_frappe.get_roles = lambda *a: ["HR-User"]
	stub_frappe.get_all = lambda *a, **kw: []
	assert _shown(seated.module, WITH_RAIL) == [one["screen"] for one in RAIL]


def test_a_space_with_no_screens_is_left_alone(seated):
	assert seated.module.navigable({**SPACE}) == []
	assert seated.module.navigable({**SPACE, "screens": []}) == []
