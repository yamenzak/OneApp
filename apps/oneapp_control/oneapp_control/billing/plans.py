"""Plans, and the Stripe objects behind them.

The Plan doctype is the source of truth. Saving one creates the Stripe Product
and Prices it needs, so an operator edits a plan in one place and never pastes
a `price_...` id between two systems — which is how a page ends up advertising
one number while the card is charged another.

Stripe Prices are immutable in amount and currency. Changing what a plan costs
therefore means minting a *new* Price and archiving the old one, never editing
in place. That is not a workaround: it is what makes grandfathering real.
Everyone already subscribed keeps billing on the Price they bought, because
their subscription still points at it, and `Plan Price` keeps the id so we can
still say which plan that is.

Nothing here may prevent a plan from being saved. Stripe being unreachable is a
temporary condition; a plan an operator cannot edit is a worse one. Failures
land in `Plan.sync_error` and the next save retries.
"""

import frappe
from frappe.utils import now_datetime

from oneapp_control.billing import stripe_client

INTERVALS = {"Monthly": "month", "Yearly": "year"}


def field_for(interval: str) -> str:
	return f"stripe_price_id_{interval.lower()}"


def amount_for(plan, interval: str) -> float:
	return float((plan.price_yearly if interval == "Yearly" else plan.price_monthly) or 0)


# --------------------------------------------------------------------------- #
# Sync
# --------------------------------------------------------------------------- #

def sync(plan) -> None:
	"""Bring Stripe in line with this plan. Mutates the doc; never raises.

	Called from `Plan.validate`, so the product id, the price ids and the new
	`Plan Price` rows are part of the same save the operator asked for — rather
	than a second write that could half-apply.

	No network call happens unless something actually changed: the comparison is
	against the rows already on the doc.
	"""
	try:
		plan.sync_error = None
		if not _configured():
			# A control plane without Stripe is a perfectly good place to draft
			# plans. Readiness already reports that they cannot be sold yet.
			return

		_ensure_product(plan)
		for interval in INTERVALS:
			_ensure_price(plan, interval)
	except Exception as e:
		# Recorded, not raised. The plan saves either way and keeps selling on
		# whatever prices it already has.
		plan.sync_error = str(e)[:1000]
		frappe.log_error(
			title=f"Stripe sync failed for plan {plan.name}",
			message=frappe.get_traceback(),
		)


def _configured() -> bool:
	try:
		return bool(stripe_client.secret_key())
	except stripe_client.StripeError:
		return False


def _ensure_product(plan) -> None:
	"""One Stripe Product per plan, carrying the name customers see."""
	if plan.stripe_product_id:
		# The name is the only mutable thing we care about, and it is what shows
		# on the invoice, so a renamed plan should not keep the old name there.
		stripe_client.update_product(
			plan.stripe_product_id,
			name=plan.plan_name,
			metadata={"plan": plan.name},
		)
		return

	product = stripe_client.create_product(
		name=plan.plan_name,
		metadata={"plan": plan.name},
		# Stripe dedupes on this for 24h, so a double-saved new plan cannot
		# leave two products behind.
		idempotency_key=f"plan-product:{plan.name}",
	)
	plan.stripe_product_id = product["id"]


def _ensure_price(plan, interval: str) -> None:
	"""Make sure the current Price matches what the plan says it costs."""
	amount = amount_for(plan, interval)
	current = _current_row(plan, interval)
	currency = (plan.currency or "USD").lower()

	if amount <= 0:
		# A plan can be monthly-only. Nothing to sell yearly, so nothing to mint
		# — but an existing price stays listed, because someone may be on it.
		if current:
			_retire_row(current)
			plan.set(field_for(interval), None)
		return

	if current and _matches(current, amount, currency):
		plan.set(field_for(interval), current.stripe_price_id)
		return

	price = stripe_client.create_price(
		product=plan.stripe_product_id,
		currency=currency,
		unit_amount=int(round(amount * 100)),
		recurring={"interval": INTERVALS[interval]},
		metadata={"plan": plan.name, "interval": interval},
		# Keyed on the amount as well as the plan: minting the same price twice
		# is a duplicate, minting a different one is a deliberate change.
		idempotency_key=f"plan-price:{plan.name}:{interval}:{currency}:{int(round(amount * 100))}",
	)

	if current:
		# Archived in Stripe so it can never be sold again. Stripe keeps billing
		# existing subscriptions on an archived price, which is exactly the
		# behaviour grandfathering needs.
		stripe_client.archive_price(current.stripe_price_id)
		_retire_row(current)

	plan.append(
		"prices",
		{
			"interval": interval,
			"stripe_price_id": price["id"],
			"unit_amount": amount,
			"currency": currency,
			"is_current": 1,
			"created_on": now_datetime(),
		},
	)
	plan.set(field_for(interval), price["id"])


def _current_row(plan, interval: str):
	for row in plan.prices or []:
		if row.interval == interval and row.is_current:
			return row
	return None


def _matches(row, amount: float, currency: str) -> bool:
	return (
		abs(float(row.unit_amount or 0) - amount) < 0.005
		and (row.currency or "").lower() == currency
	)


def _retire_row(row) -> None:
	row.is_current = 0
	row.archived_on = now_datetime()


# --------------------------------------------------------------------------- #
# Reading back
# --------------------------------------------------------------------------- #

def plan_for_price(price_id: str) -> str | None:
	"""Which plan is this Stripe price?

	The question a webhook has to answer when a subscription changes underneath
	us: Stripe tells us the new price, and only this table knows what it was
	sold as. Grandfathered prices resolve too, which is the point of keeping
	them.
	"""
	if not price_id:
		return None
	return frappe.db.get_value(
		"Plan Price", {"stripe_price_id": price_id}, "parent"
	)


def interval_for_price(price_id: str) -> str | None:
	if not price_id:
		return None
	return frappe.db.get_value("Plan Price", {"stripe_price_id": price_id}, "interval")


def current_price_id(plan, interval: str = "Monthly") -> str | None:
	"""The price a new subscription should be sold at."""
	doc = plan if hasattr(plan, "get") else frappe.get_doc("Plan", plan)
	return doc.get(field_for(interval))
