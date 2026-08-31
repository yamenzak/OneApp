"""Extra quota, bought per month against the subscription that is already there.

An add-on is a second recurring line on the same Stripe subscription — one
invoice, one dunning cycle, one card. It is deliberately not a plan: plans differ
only in quotas and carry every feature, while an add-on adds to a quota without
moving anybody between tiers. That is the difference between "I have outgrown
this" and "I need more room".
"""

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/oneapp_control/oneapp_control"
ADDONS = APP / "billing/addons.py"
DOCTYPE = APP / "control_plane/doctype/add_on/add_on.json"
CONTROLLER = APP / "control_plane/doctype/add_on/add_on.py"


def function(path: Path, name: str) -> str:
	source = path.read_text()
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return ast.get_source_segment(source, node)
	raise AssertionError(f"{name} is missing from {path.name}")


def fields() -> dict:
	return {f["fieldname"]: f for f in json.loads(DOCTYPE.read_text())["fields"]}


@pytest.fixture
def addons(stub_frappe):
	from oneapp_control.billing import addons as module

	return module


# --------------------------------------------------------------------------- #
# The doctype
# --------------------------------------------------------------------------- #

def test_frappe_can_find_the_controller():
	"""`get_controller` builds the class name by removing spaces and hyphens, so
	"Add-on" is `Addon`. Anything else is an ImportError at the first read, and
	a doctype that silently has no controller."""
	assert DOCTYPE.parent.name == "add_on"
	assert "class Addon(Document)" in CONTROLLER.read_text()


def test_the_kind_is_a_closed_list():
	"""The quota layer switches on it. A third kind is a code change either way,
	so it is better to fail at save time than to add a row nothing honours."""
	kind = fields()["kind"]
	assert kind["fieldtype"] == "Select"
	assert set(kind["options"].split("\n")) == {"File Storage", "Database Storage"}
	assert kind.get("reqd") == 1


def test_every_kind_maps_to_a_quota_field():
	"""A kind with nowhere to add is an add-on somebody pays for and never
	receives."""
	from oneapp_control.billing.addons import QUOTA_FIELD

	options = set(fields()["kind"]["options"].split("\n"))
	assert options == set(QUOTA_FIELD), "a kind the quota layer does not know"


def test_the_quota_fields_are_real_plan_terms():
	"""An add-on adds to what the plan gave, so it has to name the same field the
	subscription captured."""
	from oneapp_control.billing.addons import QUOTA_FIELD

	plan = {
		f["fieldname"]
		for f in json.loads((APP / "control_plane/doctype/plan/plan.json").read_text())["fields"]
	}
	for field in QUOTA_FIELD.values():
		assert field in plan, field


def test_it_is_priced_at_both_cadences():
	"""Stripe requires every recurring line on one subscription to share an
	interval, so a yearly workspace cannot hold a monthly add-on."""
	shape = fields()
	assert "price_monthly" in shape and "price_yearly" in shape
	assert shape["stripe_price_id_monthly"].get("read_only") == 1
	assert shape["stripe_price_id_yearly"].get("read_only") == 1


def test_the_price_ids_are_not_typed_by_hand():
	for name in ("stripe_product_id", "stripe_price_id_monthly", "stripe_price_id_yearly"):
		assert fields()[name].get("read_only") == 1, name


def test_it_carries_its_own_price_history():
	assert fields()["prices"]["options"] == "Catalogue Price"


# --------------------------------------------------------------------------- #
# What may be saved
# --------------------------------------------------------------------------- #

def test_an_add_on_with_no_price_cannot_be_saved():
	"""Nobody can buy it, and it would sit in the catalogue looking available."""
	body = function(CONTROLLER, "validate_price")
	assert "not (self.price_monthly or 0) and not (self.price_yearly or 0)" in body


def test_an_add_on_that_adds_nothing_cannot_be_saved():
	body = function(CONTROLLER, "validate_unit")
	assert "unit_gb" in body


def test_a_changed_unit_size_says_it_does_not_move_anybody():
	"""What a workspace holds is captured at purchase, so editing this changes
	what the next purchase buys and nothing else — which is surprising the first
	time."""
	body = function(CONTROLLER, "on_update")
	assert "unit_gb" in body
	assert "msgprint" in body


def test_the_sync_belongs_to_the_save_the_operator_asked_for():
	body = function(CONTROLLER, "validate")
	assert "addons.sync(self)" in body


# --------------------------------------------------------------------------- #
# What a purchase is worth
# --------------------------------------------------------------------------- #

def row(kind, quantity, unit_gb):
	return {"kind": kind, "quantity": quantity, "unit_gb": unit_gb}


def test_nothing_held_adds_nothing(addons):
	assert addons.quota_for([]) == {"storage_gb": 0, "database_gb": 0}


def test_quantity_multiplies_the_unit(addons):
	found = addons.quota_for([row("File Storage", 3, 50)])
	assert found["storage_gb"] == 150


def test_the_two_kinds_land_in_different_places(addons):
	found = addons.quota_for([row("File Storage", 1, 50), row("Database Storage", 2, 10)])
	assert found == {"storage_gb": 50, "database_gb": 20}


def test_two_lines_of_one_kind_add_up(addons):
	found = addons.quota_for([row("File Storage", 1, 50), row("File Storage", 2, 250)])
	assert found["storage_gb"] == 550


def test_a_kind_we_do_not_know_is_ignored_rather_than_guessed(addons):
	"""A row written before a kind was retired should not silently add to
	whichever quota happens to be first."""
	assert addons.quota_for([row("Bandwidth", 5, 100)]) == {"storage_gb": 0, "database_gb": 0}


def test_the_gb_comes_off_the_purchase_not_the_catalogue(addons):
	"""Captured at purchase, like plan terms: editing the Add-on must not move
	somebody who already bought."""
	body = function(ADDONS, "quota_for")
	assert "unit_gb" in body
	assert "frappe.get_doc" not in body, "it went back to the catalogue"


# --------------------------------------------------------------------------- #
# Selling one
# --------------------------------------------------------------------------- #

def test_a_retired_add_on_and_an_unpriced_one_fail_differently(addons):
	"""They are not the same problem. One is withdrawn; the other is simply not
	sold at the cadence this workspace bills on, which a plan change would fix."""
	body = function(ADDONS, "sellable")
	assert "is_active" in body
	assert "not sold on a" in body


def test_a_price_belongs_to_the_catalogue_it_was_sold_from(addons):
	assert '"Add-on"' in function(ADDONS, "addon_for_price")


# --------------------------------------------------------------------------- #
# On a subscription
#
# An add-on is a line on the same Stripe subscription, so buying, growing and
# releasing are one operation at different quantities. Three endpoints would be
# three places to get the proration wrong.
# --------------------------------------------------------------------------- #

CHECKOUT = APP / "billing/checkout.py"
WEBHOOKS = APP / "billing/webhooks.py"
QUOTAS = APP / "billing/quotas.py"
CUSTOMER = APP / "api/customer.py"
LINE = APP / "control_plane/doctype/subscription_add_on/subscription_add_on.json"


def line_fields() -> dict:
	return {f["fieldname"]: f for f in json.loads(LINE.read_text())["fields"]}


def test_the_line_records_which_stripe_item_it_is():
	"""Without it the only way to change a quantity would be to guess which of
	the subscription's items this row meant."""
	assert "stripe_subscription_item_id" in line_fields()


def test_the_line_captures_what_was_bought():
	"""Same promise as the plan's terms: redefining the add-on changes the next
	purchase and never this one."""
	shape = line_fields()
	for field in ("kind", "unit_gb", "unit_amount", "currency"):
		assert field in shape, field


def test_the_subscription_carries_its_lines():
	spec = json.loads((APP / "control_plane/doctype/subscription/subscription.json").read_text())
	table = next(f for f in spec["fields"] if f["fieldname"] == "addons")
	assert table["options"] == "Subscription Add-on"


def test_one_entry_point_buys_grows_and_releases():
	body = function(CHECKOUT, "set_addon_quantity")
	assert "quantity == 0" in function(CHECKOUT, "_apply_addon_item")
	assert "proration_behavior" in function(CHECKOUT, "_apply_addon_item")
	assert "create_prorations" in function(CHECKOUT, "_apply_addon_item")
	assert "max_units" in body


def test_a_released_line_is_deleted_rather_than_held_at_zero():
	"""A zero-quantity item keeps appearing on the invoice at nothing."""
	assert '"deleted": "true"' in function(CHECKOUT, "_apply_addon_item")


def test_an_add_on_needs_a_subscription_to_hang_from():
	"""Selling one as a separate charge would mean a second billing relationship
	for the same workspace."""
	body = function(CHECKOUT, "_subscription_for")
	assert "no subscription to add to" in body


def test_releasing_below_what_is_used_is_refused():
	"""DECISIONS §2: never destroy data and never surprise-charge. Taking the
	quota below what a workspace holds does the first."""
	body = function(CHECKOUT, "_refuse_shrinking_below_use")
	assert "quotas.blockers" in body
	assert "Free some first" in body


def test_the_purchase_is_captured_rather_than_looked_up_later():
	body = function(CHECKOUT, "_capture_addon")
	assert "unit_gb=addon_doc.unit_gb" in body
	assert "unit_amount=" in body


# --------------------------------------------------------------------------- #
# In the quota
# --------------------------------------------------------------------------- #

def test_the_quota_adds_add_ons_in_one_place():
	"""Every reader of "what is this workspace allowed" has to get the same
	answer. A caller that forgot to add would silently under-quota somebody who
	is paying."""
	for name in ("for_tenant", "for_subscription"):
		assert "with_addons" in function(QUOTAS, name), name


def test_the_added_gb_come_off_the_purchase():
	body = function(QUOTAS, "with_addons")
	assert '"Subscription Add-on"' in body
	assert "addons.quota_for" in body


def test_an_operator_grant_is_not_folded_into_the_terms():
	"""It is not something bought, so a plan change and a proration must not
	reason about it. The Tenant's own properties add it."""
	# The code, not the prose: the docstring names the grant precisely to say it
	# is somebody else's job.
	tree = ast.parse(function(QUOTAS, "for_tenant").replace("\t", "    "))
	fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
	code = "\n".join(ast.unparse(n) for n in fn.body if not isinstance(n, ast.Expr))
	assert "extra_storage_gb" not in code

	tenant = (APP / "control_plane/doctype/tenant/tenant.py").read_text()
	assert "extra_storage_gb" in tenant
	assert "extra_database_gb" in tenant


# --------------------------------------------------------------------------- #
# Reconciled from Stripe
# --------------------------------------------------------------------------- #

def test_lines_are_followed_back_from_stripe():
	"""A line added or removed in the dashboard is real money, and rows that
	disagree with Stripe under- or over-quota a paying workspace silently."""
	assert "_reconcile_addons" in function(WEBHOOKS, "handle_subscription_change")
	body = function(WEBHOOKS, "_reconcile_addons")
	assert "addon_for_price" in body


def test_reconciliation_does_not_undo_grandfathering():
	"""Stripe is the authority on which lines exist and at what quantity. It is
	not the authority on what a unit was worth when it was sold."""
	body = function(WEBHOOKS, "_same_addons")
	assert "quantity" in body
	assert "unit_amount" not in body, "the rate is being compared, so it would be rewritten"


def test_a_line_minted_in_the_dashboard_still_gets_its_gb():
	"""There is no capture to read, and treating it as zero would take a
	workspace below what it is paying for."""
	body = function(WEBHOOKS, "_reconcile_addons")
	assert "_addon_field(addon" in body


# --------------------------------------------------------------------------- #
# What a customer sees
# --------------------------------------------------------------------------- #

def test_the_catalogue_and_what_is_held_arrive_together():
	"""A stepper needs both in the same render, or the control jumps a frame
	after it appears."""
	body = function(CUSTOMER, "addons")
	assert "quantity" in body
	assert "Subscription Add-on" in body


def test_an_add_on_is_priced_at_the_cadence_the_workspace_bills_on():
	body = function(CUSTOMER, "addons")
	assert "Yearly" in body
	assert "available" in body


def test_the_quantity_is_set_through_the_one_entry_point():
	assert "checkout.set_addon_quantity" in function(CUSTOMER, "set_addon")


def test_the_customer_endpoints_prove_they_own_the_workspace():
	for name in ("addons", "set_addon"):
		assert "require_workspace(workspace)" in function(CUSTOMER, name), name
