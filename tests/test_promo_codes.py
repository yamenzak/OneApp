"""A discount on anything we sell, including all of it.

Ours to declare, Stripe's to enforce. Saving a code creates a Stripe **Coupon**
(the money — percent or amount, and for how long) and a **Promotion Code** (the
string somebody types, and who may type it). Nobody pastes a `promo_...` id
between two systems, for the same reason nobody pastes a price.

The case this was built for: a hundred-percent-off code is how a demo or training
workspace exists. It is a real subscription at zero — real terms, real quotas,
real monthly credit grants — rather than a comped tenant on a lifecycle of its
own, so nothing downstream has to know it is free.
"""

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/oneapp_control/oneapp_control"
PROMOS = APP / "billing/promos.py"
CHECKOUT = APP / "billing/checkout.py"
SIGNUP = APP / "api/signup.py"
STRIPE = APP / "billing/stripe_client.py"
DOCTYPE = APP / "control_plane/doctype/promo_code/promo_code.json"
CONTROLLER = APP / "control_plane/doctype/promo_code/promo_code.py"
PAGE = ROOT / "apps/oneapp_control/frontend/src/pages/signup/SignupPage.vue"


def function(path: Path, name: str) -> str:
	source = path.read_text()
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return ast.get_source_segment(source, node)
	raise AssertionError(f"{name} is missing from {path.name}")


def code_of(path: Path, name: str) -> str:
	"""A function's statements, without its docstring."""
	tree = ast.parse(function(path, name).replace("\t", "    "))
	fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
	return "\n".join(ast.unparse(n) for n in fn.body if not isinstance(n, ast.Expr))


def fields() -> dict:
	return {f["fieldname"]: f for f in json.loads(DOCTYPE.read_text())["fields"]}


class FakePromo(dict):
	def get(self, name, default=None):
		return dict.get(self, name, default)

	def __getattr__(self, name):
		try:
			return self[name]
		except KeyError as e:
			raise AttributeError(name) from e


@pytest.fixture
def promos(stub_frappe):
	from oneapp_control.billing import promos as module

	return module


# --------------------------------------------------------------------------- #
# The record
# --------------------------------------------------------------------------- #

def test_the_code_is_the_name():
	spec = json.loads(DOCTYPE.read_text())
	assert spec["autoname"] == "field:promo_code"
	assert fields()["promo_code"].get("unique") == 1


def test_the_code_is_upper_cased_before_it_becomes_a_name():
	"""Nobody types a code the way it was written down, and Frappe would treat
	DEMO100 and demo100 as two codes."""
	body = CONTROLLER.read_text()
	assert "def before_naming" in body
	assert ".upper()" in body


def test_a_code_says_what_it_is_for():
	"""An operator reads this in six months and has to know whether it can be
	retired."""
	assert fields()["description"].get("reqd") == 1


def test_the_ids_are_not_typed_by_hand():
	for name in ("stripe_coupon_id", "stripe_promotion_code_id"):
		assert fields()[name].get("read_only") == 1, name


def test_redemptions_are_counted_by_stripe_and_not_by_us():
	"""Two systems with an opinion about the same number drift the first time a
	checkout is abandoned after the code was applied."""
	assert fields()["times_redeemed"].get("read_only") == 1

	body = code_of(PROMOS, "refresh_redemptions")
	assert "get_promotion_code" in body
	assert "+=" not in body and "+ 1" not in body


def test_a_hundred_percent_is_allowed_and_nothing_more():
	body = function(CONTROLLER, "validate_discount")
	assert "0 < percent <= 100" in body


def test_a_code_that_applies_to_nothing_is_refused():
	"""It could never be redeemed, and it would sit in the list looking live."""
	body = function(CONTROLLER, "validate_scope")
	assert "on_subscriptions or self.on_addons or self.on_credit_packs" in body


def test_a_repeating_code_says_for_how_long():
	assert "duration_in_months" in function(CONTROLLER, "validate_discount")


# --------------------------------------------------------------------------- #
# Stripe
# --------------------------------------------------------------------------- #

def test_the_money_and_the_string_are_two_objects():
	"""A coupon is the discount; a promotion code is what somebody types and the
	rules about who may. Stripe splits them and so does this."""
	body = code_of(PROMOS, "sync")
	assert "create_coupon" in body
	assert "create_promotion_code" in body


def test_a_changed_discount_mints_a_new_coupon():
	"""A coupon is immutable in Stripe once created — exactly like a price — so
	the old one is retired and everybody already redeemed keeps what they were
	given."""
	body = code_of(PROMOS, "sync")
	assert "_changed(promo" in body
	assert "_deactivate(promo)" in body

	assert "def update_coupon" not in STRIPE.read_text(), "there is no such thing"


def test_the_fingerprint_covers_everything_a_coupon_fixes():
	"""Anything a coupon cannot be edited to change has to be in here, or a
	change to it would silently do nothing."""
	body = function(PROMOS, "_fingerprint")
	for field in ("discount_type", "percent_off", "amount_off", "currency",
	              "duration", "duration_in_months"):
		assert field in body, field


def test_the_sync_never_raises():
	"""A code an operator cannot save is worse than one that is not live yet."""
	body = function(PROMOS, "sync")
	assert "except Exception" in body
	assert "sync_error" in body
	tree = ast.parse(body.replace("\t", "    ", 1) if body.startswith("\t") else body)
	assert not [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]


def test_deactivating_does_not_take_a_discount_back():
	"""A code withdrawn is not a bill re-raised."""
	assert "already redeemed" in function(PROMOS, "_ensure_active")


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #

def test_every_scope_maps_to_a_field_on_the_record():
	from oneapp_control.billing.promos import SCOPES

	shape = fields()
	for field in SCOPES.values():
		assert field in shape, field


def test_a_code_is_only_spendable_where_it_says(promos):
	promo = FakePromo(on_subscriptions=1, on_addons=0, on_credit_packs=0)
	assert promos.allows(promo, "subscription")
	assert not promos.allows(promo, "addon")
	assert not promos.allows(promo, "credit_pack")


def test_a_kind_we_do_not_know_is_refused(promos):
	promo = FakePromo(on_subscriptions=1, on_addons=1, on_credit_packs=1)
	assert not promos.allows(promo, "anything_else")


def test_the_gate_is_ours_because_stripe_has_no_opinion():
	"""Stripe applies a coupon to whatever session accepts promotion codes. What
	stops a subscription code being spent on a pack is that the pack's checkout is
	never told to accept one."""
	for name in ("start_signup", "start_credit_pack"):
		assert "promos.resolve(" in function(CHECKOUT, name), name
	assert "promos.resolve(" in function(CHECKOUT, "set_addon_quantity")


def test_a_bad_code_and_a_wrong_one_say_the_same_thing():
	"""Distinguishing them is a way to enumerate the codes we have."""
	body = function(PROMOS, "resolve")
	assert body.count("not valid here") == 1
	assert "is_active" in body and "allows(promo" in body


def test_a_code_we_never_minted_says_so_differently():
	"""That one is our fault and re-saving fixes it."""
	assert "not live yet" in function(PROMOS, "resolve")


# --------------------------------------------------------------------------- #
# The free instance
# --------------------------------------------------------------------------- #

def test_a_total_discount_is_recognised(promos):
	assert promos.is_total_discount(FakePromo(discount_type="Percent", percent_off=100))
	assert not promos.is_total_discount(FakePromo(discount_type="Percent", percent_off=99))
	assert not promos.is_total_discount(FakePromo(discount_type="Amount", amount_off=9999))
	assert not promos.is_total_discount(None)


def test_a_free_signup_collects_no_card():
	"""Without this Stripe asks for a card it will never charge, which is the
	difference between a demo instance somebody can spin up and one they give up
	on."""
	body = code_of(CHECKOUT, "start_signup")
	assert "payment_method_collection" in body
	assert "if_required" in body
	assert "is_total_discount" in body


def test_a_fully_discounted_signup_is_already_accepted():
	"""Stripe answers `no_payment_required` for a zero-total checkout, and the
	handler has taken that since before promo codes existed."""
	webhooks = (APP / "billing/webhooks.py").read_text()
	assert "no_payment_required" in webhooks


def test_the_code_is_applied_rather_than_offered():
	"""Signup already knows which code was typed and validated it server-side, so
	Stripe's own promo field would be a second place to enter a second one."""
	body = code_of(CHECKOUT, "start_signup")
	assert "discounts" in body
	assert "allow_promotion_codes" not in body


def test_a_bad_code_is_caught_before_stripe_is_reached():
	"""A message beside the field, rather than a Stripe page that refuses after
	everything else was filled in."""
	assert "promos.resolve" in function(SIGNUP, "start")


def test_the_code_is_recorded_on_the_workspace():
	"""So "which of these are free demos" is a filter rather than a
	spreadsheet."""
	assert "promo_code" in fields_of("account_request")
	assert "promo_code" in fields_of("tenant")
	assert '"promo_code": request.promo_code' in (
		APP / "provisioning/signup.py"
	).read_text()


def fields_of(slug: str) -> set[str]:
	spec = json.loads((APP / f"control_plane/doctype/{slug}/{slug}.json").read_text())
	return {f["fieldname"] for f in spec["fields"]}


def test_the_signup_page_offers_the_field_as_optional():
	"""Somebody with no code should read it as "skip this" rather than as one
	more thing to fill in."""
	page = PAGE.read_text()
	assert 'label="Promo code"' in page
	assert 'placeholder="Optional"' in page
	assert "code" not in page[page.index("const valid = computed("):page.index("// Checked server-side")]
