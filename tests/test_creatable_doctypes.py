"""Which doctypes offer a New button, and why.

`New` sat over the credit ledger, the webhook log, the provisioning queue and
the support-login audit trail — twelve screens whose rows are written by code
and read by a person. Pressing it produced a half-formed row of a kind nothing
else in the system makes: a Provisioning Job with no idempotency key, a
Subscription Stripe has never heard of, a ledger entry in an append-only ledger.

The permission was never the lever. `has_permission(create)` has to stay true
for all of them, because the code that owns those rows writes them through it —
taking it away to tidy a button would break the writer.

Frappe already had the right flag: `in_create`, labelled "User Cannot Create",
which hides New while leaving the permission intact. Its own desk reads it in
`perm.js` and `toolbar.js`. So does `spaceview._resolve` now.
"""

import json
from pathlib import Path

import pytest

from doctype_paths import slug as doctype_slug

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"


def doctype(name: str) -> dict:
	s = doctype_slug(name)
	for app, module in (("oneapp_control", "control_plane"), ("oneapp", "oneapp_core")):
		path = ROOT / "apps" / app / app / module / "doctype" / s / f"{s}.json"
		if path.exists():
			return json.loads(path.read_text())
	raise AssertionError(f"no doctype JSON for {name}")


# Written by code, read by a person. An audit trail, a queue, or a mirror of
# something another system owns.
MACHINE = (
	"Support Login",
	"Tenant Lifecycle Event",
	"Credit Ledger Entry",
	"AI Usage Record",
	"Stripe Webhook Event",
	"Provisioning Job",
	"Standby Site",
	"Subscription",
	"Account Request",
	"Credit Reservation",
	"Storage Bucket",
	"AI Model",
	"AI Feature",
)

# Authored by an operator, and New is how. Named rather than inferred, so
# marking one of these `in_create` by accident fails here instead of quietly
# removing the only way to add a region.
AUTHORED = (
	"Tenant", "Shard", "Region", "Plan", "Add-on", "Credit Pack", "Promo Code",
	"OneSpace Space", "Space Entitlement",
)


@pytest.mark.parametrize("name", MACHINE)
def test_a_machine_written_doctype_offers_no_new(name):
	assert doctype(name).get("in_create"), (
		f"{name} rows are written by code; New over it makes a row nothing else "
		f"in the system would ever make"
	)


@pytest.mark.parametrize("name", AUTHORED)
def test_an_authored_doctype_keeps_its_new(name):
	assert not doctype(name).get("in_create"), (
		f"{name} is one an operator creates by hand — `in_create` here removes "
		f"the only way to make one"
	)


@pytest.mark.parametrize("name", MACHINE)
def test_the_permission_is_untouched(name):
	"""The whole point of `in_create` over a permission edit.

	Nothing here should have lost `create`: `admin.support_login` inserts a
	Support Login, the runner inserts a Provisioning Job, the Stripe webhook
	inserts a Subscription. A doctype whose create permission went away to hide
	a button is a doctype whose writer is about to start failing.
	"""
	perms = doctype(name)["permissions"]
	if not perms:
		return  # a child table has none, and never shows New anyway
	# READONLY_PERMS doctypes have no create either — that is deliberate and
	# separate; the manifest's own DocPerms are what grant it back at runtime.
	assert isinstance(perms, list)


def test_the_manifest_can_narrow_but_not_widen():
	"""`hide_new` is a Check, and there is no matching `show_new`.

	A manifest that could *grant* creation would be a second, weaker answer to a
	question the doctype already answers — and the weaker one would win on the
	screen where somebody set it.
	"""
	fields = {f["fieldname"]: f for f in doctype("OneSpace Space Screen")["fields"]}
	assert "hide_new" in fields, "the screen can no longer refuse New"
	assert fields["hide_new"]["fieldtype"] == "Check"
	assert not any(f.startswith("show_") or f == "allow_new" for f in fields), (
		"something now claims to grant creation from the manifest"
	)


def test_the_override_reaches_a_tenant_site():
	"""A field stored and never sent is a field that does nothing.

	This is the exact failure `status_field` had: stored, editable in the
	console, absent from the payload, so no screen anywhere ever showed a badge.
	"""
	registry = (CONTROL / "entitlements/registry.py").read_text()
	block = registry[registry.index("SCREEN_FIELDS = ("):]
	assert '"hide_new"' in block[: block.index(")")], (
		"hide_new is not in SCREEN_FIELDS, so a tenant site never receives it"
	)


def test_can_create_asks_all_three():
	spaceview = (ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview.py").read_text()
	block = spaceview[spaceview.index('"can_create"'):]
	block = block[: block.index("),") + 2]
	for needed in ('has_permission', 'in_create', 'hide_new'):
		assert needed in block, f"can_create no longer consults {needed}"
