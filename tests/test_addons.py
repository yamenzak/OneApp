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
