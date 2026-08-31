"""A subscription carries more than the plan.

An add-on is a second recurring item on the same Stripe subscription — one
invoice, one dunning cycle, one card. That is the right shape for the customer
and it broke two assumptions at once: `change_plan` refused any subscription
with more than one line, and `_reconcile_plan` silently returned. So the first
add-on anybody bought would have frozen their plan and stopped reconciliation
without anything visible saying so.

These pin the replacement: the plan's line is *found*, by resolving each price
against the plan catalogue.
"""

import pytest


@pytest.fixture
def plans(stub_frappe):
	from oneapp_control.billing import plans as module

	return module


def priced(*price_ids):
	"""Stripe's shape for a subscription's line items."""
	return [{"id": f"si_{n}", "price": {"id": pid}} for n, pid in enumerate(price_ids)]


def catalogue(stub_frappe, mapping: dict):
	"""Make `plan_for_price` answer from `mapping`, as the price table would."""
	def get_value(doctype, filters=None, fieldname=None, *a, **k):
		if doctype != "Plan Price" or not isinstance(filters, dict):
			return None
		if filters.get("parenttype") != "Plan":
			return None
		found = mapping.get(filters.get("stripe_price_id"))
		if not found:
			return None
		return found if fieldname == "parent" else "Monthly"

	stub_frappe.db.get_value = get_value


def test_the_only_plan_line_is_the_plan_line(plans, stub_frappe):
	catalogue(stub_frappe, {"price_pro": "pro"})
	found = plans.plan_item(priced("price_pro"))
	assert found["id"] == "si_0"


def test_an_add_on_beside_the_plan_does_not_confuse_it(plans, stub_frappe):
	"""The case the whole change exists for."""
	catalogue(stub_frappe, {"price_pro": "pro"})
	found = plans.plan_item(priced("price_storage_50", "price_pro", "price_db_10"))
	assert found["id"] == "si_1"


def test_a_subscription_of_only_add_ons_has_no_plan_line(plans, stub_frappe):
	"""None rather than an exception: the callers each decide what to do, and
	one of them is a webhook that must not fail the delivery."""
	catalogue(stub_frappe, {"price_pro": "pro"})
	assert plans.plan_item(priced("price_storage_50")) is None


def test_a_price_we_did_not_mint_resolves_to_nothing(plans, stub_frappe):
	catalogue(stub_frappe, {})
	assert plans.plan_item(priced("price_made_in_the_dashboard")) is None


def test_an_empty_subscription_resolves_to_nothing(plans, stub_frappe):
	catalogue(stub_frappe, {})
	assert plans.plan_item([]) is None


def test_two_plan_lines_is_still_refused(plans, stub_frappe):
	"""The one genuinely ambiguous case. A workspace on two plans cannot be
	reasoned about, and guessing which to reprice is how the wrong one moves."""
	catalogue(stub_frappe, {"price_pro": "pro", "price_business": "business"})
	with pytest.raises(Exception, match="plan lines"):
		plans.plan_item(priced("price_pro", "price_business"))


def test_a_line_with_no_price_is_skipped(plans, stub_frappe):
	"""Stripe's shapes are not all the same, and a line we cannot read the price
	off is not the plan by default."""
	catalogue(stub_frappe, {"price_pro": "pro"})
	items = [{"id": "si_odd"}, *priced("price_pro")]
	assert plans.plan_item(items)["price"]["id"] == "price_pro"


# --------------------------------------------------------------------------- #
# Fit
#
# `blockers` decides whether a workspace may move to a plan. It read the plan's
# allowance and the raw usage and nothing else, while `Tenant.storage_quota_bytes`
# added the operator's grant on top — so a workspace that had been granted extra
# room was told it was over a limit it was not actually past, and refused a plan
# change it would have fitted.
# --------------------------------------------------------------------------- #

GB = 1024**3


@pytest.fixture
def quotas(stub_frappe):
	from oneapp_control.billing import quotas as module

	return module


class FakeTenant:
	"""Enough of a Tenant for `blockers`, which reads four fields."""

	def __init__(self, storage=0, database=0, extra_storage=0, extra_database=0, members=()):
		self.storage_used_bytes = storage
		self.database_used_bytes = database
		self.extra_storage_gb = extra_storage
		self.extra_database_gb = extra_database
		self.members = list(members)

	def get(self, name, default=None):
		return getattr(self, name, default)


SMALL = {"storage_gb": 10, "database_gb": 2, "max_users": 3}


def test_a_workspace_inside_the_plan_is_not_blocked(quotas):
	assert quotas.blockers(FakeTenant(storage=5 * GB, database=1 * GB), SMALL) == []


def test_a_workspace_over_the_plan_is_blocked(quotas):
	assert quotas.blockers(FakeTenant(storage=50 * GB), SMALL) == ["storage"]


def test_a_granted_allowance_counts_toward_the_fit(quotas):
	"""The bug. 50 GB used against a 10 GB plan reads as over — unless somebody
	has already been granted the 100 GB they are sitting on."""
	tenant = FakeTenant(storage=50 * GB, extra_storage=100)
	assert quotas.blockers(tenant, SMALL) == []


def test_a_granted_database_allowance_counts_too(quotas):
	tenant = FakeTenant(database=20 * GB, extra_database=50)
	assert quotas.blockers(tenant, SMALL) == []


def test_seats_count_the_owner(quotas):
	"""One owner plus two members is three seats, which is exactly a 3-seat plan
	— and `>` rather than `>=` is what makes that fit."""
	assert quotas.blockers(FakeTenant(members=["a", "b"]), SMALL) == []
	assert quotas.blockers(FakeTenant(members=["a", "b", "c"]), SMALL) == ["seats"]


def test_an_unset_limit_never_blocks(quotas):
	"""Zero means unconfigured, not 'zero allowed'."""
	tenant = FakeTenant(storage=500 * GB, database=500 * GB, members=["a"] * 50)
	assert quotas.blockers(tenant, {"storage_gb": 0, "database_gb": 0, "max_users": 0}) == []
