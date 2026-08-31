"""AI credits, bought once.

The other half of how credits arrive. A plan grants some every period and they
expire at the end of it; a pack is bought outright and rolls over — which is what
makes it worth buying, because `ledger.open_grants` spends the soonest-expiring
grant first and never-expiring purchases last.

The packs themselves used to be six dictionaries in `api/customer.py`, priced
inline at checkout. That meant changing a price was a deploy and a receipt named
a product that did not exist.
"""

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/oneapp_control/oneapp_control"
PACKS = APP / "billing/packs.py"
CHECKOUT = APP / "billing/checkout.py"
CUSTOMER = APP / "api/customer.py"
WEBHOOKS = APP / "billing/webhooks.py"
DOCTYPE = APP / "control_plane/doctype/credit_pack/credit_pack.json"
CONTROLLER = APP / "control_plane/doctype/credit_pack/credit_pack.py"


def function(path: Path, name: str) -> str:
	source = path.read_text()
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return ast.get_source_segment(source, node)
	raise AssertionError(f"{name} is missing from {path.name}")


def fields() -> dict:
	return {f["fieldname"]: f for f in json.loads(DOCTYPE.read_text())["fields"]}


# --------------------------------------------------------------------------- #
# The catalogue
# --------------------------------------------------------------------------- #

def test_a_pack_is_a_record_an_operator_can_edit():
	"""Changing a price used to be a deploy."""
	assert DOCTYPE.exists()
	shape = fields()
	assert shape["credits"].get("reqd") == 1
	assert shape["amount"].get("reqd") == 1


def test_it_has_one_price_because_it_is_bought_once():
	shape = fields()
	assert "stripe_price_id" in shape
	assert "stripe_price_id_monthly" not in shape
	assert "stripe_price_id_yearly" not in shape


def test_the_one_price_is_a_one_off():
	"""Stripe reads the presence of `recurring` as 'this is a subscription
	price', so a pack minted as recurring would quietly bill every month."""
	from oneapp_control.billing import catalogue

	body = PACKS.read_text()
	assert "INTERVAL = catalogue.ONE_OFF" in body
	assert catalogue.ONE_OFF not in catalogue.INTERVALS


def test_it_still_keeps_its_price_history():
	"""Repricing has to archive the old Stripe id, or the old one stays
	sellable."""
	assert fields()["prices"]["options"] == "Catalogue Price"


def test_a_free_pack_is_refused():
	"""Giving credits away is a promo code's job, not a zero-priced product that
	anybody who finds the code can buy."""
	body = function(CONTROLLER, "validate")
	assert "self.amount or 0) <= 0" in body
	assert "promo code" in body


def test_an_empty_pack_is_refused():
	assert "self.credits or 0) <= 0" in function(CONTROLLER, "validate")


def test_the_price_ids_are_not_typed_by_hand():
	for name in ("stripe_product_id", "stripe_price_id"):
		assert fields()[name].get("read_only") == 1, name


# --------------------------------------------------------------------------- #
# Buying one
# --------------------------------------------------------------------------- #

def test_the_hard_coded_lists_are_gone():
	source = CUSTOMER.read_text()
	assert "CREDIT_PACKS" not in source
	assert "STORAGE_PACKS" not in source


def test_what_is_offered_comes_from_the_catalogue():
	assert "pack_catalogue.offered()" in function(CUSTOMER, "packs")


def test_only_active_packs_are_offered():
	assert '"is_active": 1' in function(PACKS, "offered")


def test_a_retired_pack_and_an_unpriced_one_fail_differently():
	body = function(PACKS, "sellable")
	assert "is_active" in body
	assert "not priced yet" in body


def test_the_session_uses_a_real_stripe_price():
	"""The code, not the prose: the docstring names `price_data` to say what this
	stopped doing."""
	tree = ast.parse(function(CHECKOUT, "start_credit_pack").replace("\t", "    "))
	fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
	body = "\n".join(ast.unparse(n) for n in fn.body if not isinstance(n, ast.Expr))

	assert "stripe_price_id" in body
	assert "price_data" not in body


def test_the_session_still_says_how_many_credits_it_is_for():
	"""The webhook grants from the metadata, so losing it would take the money
	and deliver nothing."""
	body = function(CHECKOUT, "start_credit_pack")
	assert '"credits": pack_doc.credits' in body
	assert '"kind": "credit_pack"' in body


# --------------------------------------------------------------------------- #
# Storage stops being a pack
# --------------------------------------------------------------------------- #

def test_nothing_opens_a_storage_pack_checkout_any_more():
	assert "def start_storage_pack" not in CHECKOUT.read_text()
	assert "def buy_storage" not in CUSTOMER.read_text()


def test_a_storage_session_already_open_is_still_honoured():
	"""Somebody may have had one open when the change shipped, and the money
	arrives either way."""
	assert 'kind") == "storage_pack"' in function(WEBHOOKS, "handle_checkout_completed")
	assert "def grant_storage_pack" in WEBHOOKS.read_text()


def test_a_purchased_credit_never_expires():
	"""What makes a pack worth buying, and the reason `open_grants` orders
	never-expiring last."""
	body = function(WEBHOOKS, "grant_credit_pack")
	assert "expires_on=None" in body
	assert 'entry_type="Purchase"' in body


# --------------------------------------------------------------------------- #
# What the customer sees
# --------------------------------------------------------------------------- #

BILLING = ROOT / "apps/oneapp/frontend/src/screens/account/Billing.vue"
PACK_CARD = ROOT / "apps/oneapp/frontend/src/screens/account/PackCard.vue"


def test_a_price_is_shown_in_its_own_currency():
	"""A hard-coded `$` reads as a price in the wrong currency, which is worse
	than no symbol at all — it is a number somebody plans around."""
	card = PACK_CARD.read_text()
	assert "${{ price }}" not in card
	assert "currency" in card
	assert "Intl.NumberFormat" in card


def test_the_balance_is_shown_beside_what_is_for_sale():
	"""'Why am I out of credits' is the question this section exists to answer,
	and a pack offered next to no balance is a shop with no price tag."""
	page = BILLING.read_text()
	assert "credits.available" in page


def test_the_ledger_is_shown_and_not_just_the_number():
	"""A balance with no history behind it is one nobody can question."""
	page = BILLING.read_text()
	assert "creditHistory" in page
	assert "entry_type" in page


def test_the_page_says_which_credits_go_first():
	"""The reason a pack is worth buying, and it is not obvious."""
	page = BILLING.read_text()
	assert "roll over" in page
	assert "spent last" in page
