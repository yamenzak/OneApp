"""Three states, not two: had it, may see it, never heard of it.

A `Space Entitlement` grew a second flag for one reason, and the reason is
worth a file of its own because it is a privacy failure rather than a bug: a
marketplace that draws a locked card for every Restricted space tells every
customer the name of every bespoke solution built for every other one. So the
default is invisible, and being allowed to see a space is a fact somebody wrote
down.

`docs/MARKETPLACE.md` §4 is the design. These are the parts of it that would
fail silently — an offer that installed an app, a revoke that left the card in
place with a working button.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps" / "oneapp_control" / "oneapp_control"

ENTITLEMENT = (
	CONTROL / "control_plane" / "doctype" / "space_entitlement"
	/ "space_entitlement.json"
)


@pytest.fixture
def registry(stub_frappe, monkeypatch):
	from oneapp_control.entitlements import apps, registry as module

	# The bench check is its own subject and has its own tests. Here it stands
	# for "the operator was allowed to do this at all".
	monkeypatch.setattr(apps, "assert_can_carry", lambda tenant, space: None)
	monkeypatch.setattr(apps, "reconcile", lambda tenant: reconciled.append(tenant))
	reconciled.clear()
	return module


reconciled = []


def _inserted(frappe, monkeypatch):
	"""Catch the row an insert would have made."""
	made = {}

	class _Doc:
		def __init__(self, values):
			made.update(values)

		def insert(self, **kwargs):
			self.name = "ent-new"
			return self

	monkeypatch.setattr(frappe, "get_doc", lambda values: _Doc(values))
	return made


def test_the_field_defaults_to_invisible():
	fields = {f["fieldname"]: f for f in json.loads(ENTITLEMENT.read_text())["fields"]}
	assert fields["offered"]["default"] == "0", (
		"a Restricted space nobody was told about must not appear in anybody's "
		"marketplace, which makes 0 the only safe default"
	)


def test_offering_does_not_install_anything(registry, stub_frappe, monkeypatch):
	made = _inserted(stub_frappe, monkeypatch)

	registry.offer("acme", "rua", note="Sales asked")

	assert made["offered"] == 1
	assert made["enabled"] == 0
	assert not reconciled, (
		"an offer is a row. Installing the app before they press the card is "
		"minutes of patches for a space they may never turn on"
	)


def test_offering_what_they_already_have_does_not_take_it_away(
	registry, stub_frappe,
):
	stub_frappe.db.values[("Space Entitlement", "name")] = "ent-1"

	registry.offer("acme", "rua")

	assert stub_frappe.db.writes == [("Space Entitlement", "ent-1", "offered", 1)], (
		"`enabled` must be left alone: offering a space somebody is already "
		"using is a no-op, not a downgrade"
	)


def test_granting_also_makes_it_visible(registry, stub_frappe):
	stub_frappe.db.values[("Space Entitlement", "name")] = "ent-1"

	registry.grant("acme", "rua")

	doctype, name, changed, _ = stub_frappe.db.writes[0]
	assert changed == {"enabled": 1, "offered": 1}, (
		"a space they are using is not one they are forbidden to see — and "
		"without this it leaves their marketplace the moment they turn it off"
	)
	assert reconciled == ["acme"]


def test_revoking_clears_both(registry, stub_frappe):
	stub_frappe.db.values[("Space Entitlement", "name")] = "ent-1"

	registry.revoke("acme", "rua")

	doctype, name, changed, _ = stub_frappe.db.writes[0]
	assert changed == {"enabled": 0, "offered": 0}, (
		"leaving `offered` on puts the card straight back in their marketplace "
		"with a button that works, which is not what revoke means"
	)


def test_the_offered_list_is_the_same_column_list_as_the_manifest():
	"""The drift `test_apps_and_spaces` guards for the Restricted manifest,
	guarded again for the query beside it: a field added to SPACE_FIELDS and
	forgotten here reaches every card a workspace has and no card it is being
	offered."""
	source = (CONTROL / "entitlements" / "registry.py").read_text()
	body = source[source.index("def offered_spaces"):]
	assert "SELECT {SPACE_COLUMNS}" in body
	assert "e.offered = 1" in body and "e.enabled = 0" in body, (
		"a space they already have belongs in the manifest, not in the list of "
		"things they could add"
	)


def test_the_backfill_only_touches_what_is_enabled():
	patch = (CONTROL / "patches" / "offer_existing_entitlements.py").read_text()
	assert "WHERE enabled = 1" in patch, (
		"a revoked row is one an operator deliberately took away; backfilling "
		"it would hand back what they removed"
	)
	registered = (CONTROL / "patches.txt").read_text()
	assert "offer_existing_entitlements" in registered


# --------------------------------------------------------------------------- #
# The endpoints
#
# The card states are the whole design (§4): collapsing "installing" is the
# difference between a marketplace that is honest and one that appears to hang.
# --------------------------------------------------------------------------- #

CUSTOMER = (CONTROL / "api" / "customer.py").read_text()
RELAY = (CONTROL / "api" / "tenant.py").read_text()


def test_a_card_says_which_app_the_bench_lacks():
	body = CUSTOMER[CUSTOMER.index("def _card"):]
	assert '"unavailable", ", ".join(missing)' in body, (
		'"unavailable" on its own is a card nobody can act on and a support '
		"ticket that starts with 'it just says no'"
	)


def test_a_queued_install_already_counts_as_installing():
	"""A job the runner has not picked up yet is still a job. Leaving
	`Requested` out makes the card look like the button did nothing."""
	states = CUSTOMER[CUSTOMER.index("RUNNING = ("):]
	states = states[:states.index(")")]
	for state in ("Requested", "Running", "Awaiting Agent", "Bootstrapping"):
		assert state in states
	assert "Succeeded" not in states and "Failed" not in states


def test_enabling_is_refused_for_a_space_nobody_offered():
	"""`grant` alone would let anybody who can guess a space code help
	themselves to somebody else's bespoke solution."""
	body = CUSTOMER[CUSTOMER.index("def enable_space"):]
	assert '"offered": 1' in body[:body.index("registry.grant")]
	assert "frappe.PermissionError" in body


def test_the_relay_is_an_allow_list_and_now_names_both():
	body = RELAY[RELAY.index("def _may_be_asked"):]
	assert '"marketplace": customer.marketplace' in body
	assert '"enable_space": customer.enable_space' in body
	assert "getattr(customer" not in RELAY, (
		"reaching `customer` by name makes every method it ever gains callable "
		"from any tenant site"
	)


# --------------------------------------------------------------------------- #
# The screen
# --------------------------------------------------------------------------- #

PAGE = (
	ROOT / "apps/oneapp/frontend/src/pages/Marketplace.vue"
).read_text()


def test_every_state_the_server_can_send_is_drawn():
	"""A state the page has no branch for is a card that renders as its
	fallback, which here is a disabled button with no sentence beside it."""
	for state in ("available", "installing", "unavailable"):
		assert f"'{state}'" in PAGE, state


def test_a_card_that_cannot_be_pressed_says_why():
	"""Both of the states that are not `available` carry their own line. A
	disabled button on its own is a control that refuses without explaining,
	which is the thing `docs/LANGUAGE.md` is about."""
	assert PAGE.count('data-slot="marketplace-state"') == 2
	assert "which your workspace cannot carry yet" in PAGE
	assert "A few minutes" in PAGE


def test_pressing_it_does_not_leave_the_reader_waiting_for_a_sync():
	"""The grant is written on the control plane and this site learns what it
	is entitled to by pulling. Pressing a card and being told to come back in
	fifteen minutes is the failure; the pull happens in the endpoint."""
	relay = (ROOT / "apps/oneapp/oneapp/oneapp_core/account.py").read_text()
	body = relay[relay.index("def enable_space"):]
	assert "sync_from_control_plane()" in body
	assert "except Exception" in body, (
		"a sync that fails must not fail the press: the entitlement is written "
		"either way and the scheduled pull is the fallback"
	)


def test_the_rail_offers_it_only_to_somebody_who_can_use_it():
	nav = (ROOT / "apps/oneapp/frontend/src/lib/shell/nav.js").read_text()
	entry = nav[nav.index("key: 'marketplace'") - 400:nav.index("key: 'marketplace'")]
	assert "session.isAdmin" in entry, (
		"a rail icon leading to a page of refusals is worse than no icon"
	)
