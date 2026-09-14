"""Where a check-in has to happen, and on whose network.

Two rules and only one is ours, which is most of what these hold.

**The geofence is HRMS's.** A Shift Location carries a position and a radius, a
Shift Assignment points a shift at one, and `Employee Checkin` refuses a log too
far away. None of that needed building and none of it is re-tested here — what
needed building was sending a position at all, and asking for one *only* where
the workspace wants it, because a location prompt nobody expected is a location
prompt somebody refuses once and then cannot use.

**The network rule is ours**, because HRMS has no notion of one. The tests below
are mostly about its failure direction: a rule somebody mistyped must not lock
an office out, and an address a caller *sends* must never satisfy it.
"""

import types

import pytest


@pytest.fixture
def place(stub_frappe):
	from oneapp.onehr import place as module

	stub_frappe.db.exists = lambda *a, **kw: True
	stub_frappe.get_all = lambda *a, **kw: []
	stub_frappe.local = types.SimpleNamespace(request_ip="203.0.113.7")
	return types.SimpleNamespace(it=module, frappe=stub_frappe)


def _place(frappe, **fields):
	"""A Shift Location assigned to the person's shift today."""
	row = {"name": "PLACE-1", "location_name": "The yard", "latitude": 25.0,
	       "longitude": 55.0, "checkin_radius": 150,
	       "custom_checkin_networks": ""}
	row.update(fields)
	frappe.get_all = lambda *a, **kw: ["PLACE-1"]
	frappe.db.get_value = lambda *a, **kw: row
	return row


# --------------------------------------------------------------------------- #
# The network rule
# --------------------------------------------------------------------------- #

def test_an_address_on_the_list_passes(place):
	_place(place.frappe, custom_checkin_networks="203.0.113.0/24")
	place.it.refuse_unless_on_network("HR-EMP-1")


def test_an_address_off_the_list_is_refused(place):
	_place(place.frappe, custom_checkin_networks="198.51.100.0/24")
	with pytest.raises(place.frappe.PermissionError):
		place.it.refuse_unless_on_network("HR-EMP-1")


def test_a_bare_address_is_its_own_network(place):
	"""So nobody has to know that "203.0.113.7" and "203.0.113.7/32" are the
	same thing."""
	_place(place.frappe, custom_checkin_networks="203.0.113.7")
	place.it.refuse_unless_on_network("HR-EMP-1")


def test_a_place_with_no_list_refuses_nobody(place):
	"""Blank means anywhere. The absence of a rule is not a rule."""
	_place(place.frappe, custom_checkin_networks="")
	place.it.refuse_unless_on_network("HR-EMP-1")


def test_somebody_with_no_place_refuses_nobody(place):
	place.frappe.get_all = lambda *a, **kw: []
	place.it.refuse_unless_on_network("HR-EMP-1")


def test_a_line_nobody_can_parse_is_dropped_and_not_fatal(place):
	"""The failure direction that matters. A typo in a settings box must not
	stop a whole office checking in — a rule one line shorter than intended is
	a smaller failure than a rule nobody can satisfy."""
	_place(place.frappe,
	       custom_checkin_networks="not an address\n203.0.113.0/24\n\n# a note")
	place.it.refuse_unless_on_network("HR-EMP-1")


def test_a_list_that_is_only_typos_refuses_nobody(place):
	"""And the same rule taken to its end: if nothing parsed, there is no
	rule — not a rule that matches nothing."""
	_place(place.frappe, custom_checkin_networks="office wifi\nthe one upstairs")
	place.it.refuse_unless_on_network("HR-EMP-1")


def test_the_address_is_read_off_the_connection(place):
	"""Never off a header. `request_ip` is what Frappe resolved from the
	connection and the proxies it trusts; reading `X-Forwarded-For` here would
	be trusting a value the caller sets, which is the whole of the attack on
	this kind of rule."""
	import inspect

	# The code, not the paragraph above it — which says "headers" on purpose
	# and would fail this on its own words.
	source = inspect.getsource(place.it._seen_from).split('"""')[-1]
	assert "request_ip" in source
	for wrong in ("headers", "X-Forwarded", "environ", "frappe.request"):
		assert wrong not in source, wrong


def test_an_unreadable_address_does_not_pass_a_rule(place):
	"""A request Frappe could not resolve an address for satisfies nothing —
	the safe direction, because the alternative is a rule that opens up when
	the proxy configuration changes."""
	_place(place.frappe, custom_checkin_networks="203.0.113.0/24")
	place.frappe.local = types.SimpleNamespace(request_ip="")
	with pytest.raises(place.frappe.PermissionError):
		place.it.refuse_unless_on_network("HR-EMP-1")


# --------------------------------------------------------------------------- #
# What the browser is told to collect
# --------------------------------------------------------------------------- #

def test_a_workspace_that_records_nothing_asks_for_nothing(place):
	"""The point of answering before the button is drawn. A position asked for
	by a workspace that does not want one is a permission prompt nobody can
	explain."""
	place.frappe.db.get_single_value = lambda *a, **kw: 0
	_place(place.frappe, custom_checkin_networks="")

	asked = place.it.needs("HR-EMP-1")
	assert asked[place.it.PLACE] is False
	assert asked[place.it.NETWORK] is False


def test_the_switch_is_what_asks_for_a_position(place):
	place.frappe.db.get_single_value = lambda *a, **kw: 1
	_place(place.frappe)
	assert place.it.needs("HR-EMP-1")[place.it.PLACE] is True


def test_a_network_rule_is_asked_for_without_the_switch(place):
	"""The two are independent: a network is read off the connection, so it
	costs nobody a prompt and works with tracking off."""
	place.frappe.db.get_single_value = lambda *a, **kw: 0
	_place(place.frappe, custom_checkin_networks="203.0.113.0/24")

	asked = place.it.needs("HR-EMP-1")
	assert asked[place.it.PLACE] is False
	assert asked[place.it.NETWORK] is True
	assert asked["at"] == "The yard"
	assert asked["within"] == 150
