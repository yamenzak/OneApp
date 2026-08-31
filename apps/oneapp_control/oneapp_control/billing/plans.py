"""Plans, and the Stripe objects behind them.

The Plan doctype is the source of truth. Saving one creates the Stripe Product
and Prices it needs, so an operator edits a plan in one place and never pastes
a `price_...` id between two systems — which is how a page ends up advertising
one number while the card is charged another.

The mechanics of that — minting a new Price rather than editing one, archiving
what it replaced, keeping the old id so a grandfathered subscription can still
be named — are `billing/catalogue.py`, because add-ons and credit packs need the
same thing. What is left here is what is specific to a plan: that it is priced
monthly and yearly, and where the current id for each of those lives.
"""

import frappe
from frappe import _

from oneapp_control.billing import catalogue

KIND = "plan"
INTERVALS = catalogue.INTERVALS


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
	`Catalogue Price` rows are part of the same save the operator asked for —
	rather than a second write that could half-apply.
	"""
	catalogue.sync(
		plan,
		kind=KIND,
		product_name=plan.plan_name,
		amounts={interval: amount_for(plan, interval) for interval in INTERVALS},
		price_field=field_for,
	)


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
	# Narrowed to Plan rows. The price table is shared with the other things we
	# sell — add-ons carry their own history in it — and without that filter an
	# add-on's price would resolve to "a plan" and reprice the workspace onto it.
	return catalogue.owner_of_price(price_id, "Plan")


def interval_for_price(price_id: str) -> str | None:
	return catalogue.interval_of_price(price_id, "Plan")


def plan_item(items: list[dict]) -> dict | None:
	"""The one line on a Stripe subscription that is the plan.

	A subscription used to be assumed to have exactly one item, and both the
	plan change and the webhook reconciliation threw or gave up when it did not.
	That assumption stopped being true the moment an add-on could be bought: an
	add-on is a second recurring item on the same subscription, deliberately, so
	that a customer gets one invoice and one dunning cycle.

	So the plan is *found* rather than counted to. Every item's price is
	resolved against the plan catalogue, grandfathered prices included; the one
	that resolves is the plan. Two that resolve is still an error worth
	refusing, because a workspace on two plans cannot be reasoned about and
	guessing which to reprice is how the wrong one moves.

	Returns None when nothing resolves — a subscription sold before the
	catalogue, or one created in the dashboard.
	"""
	found = [
		item for item in items
		if plan_for_price(((item or {}).get("price") or {}).get("id"))
	]
	if len(found) > 1:
		frappe.throw(
			_("This subscription has {0} plan lines; sort it out in Stripe.").format(len(found))
		)
	return found[0] if found else None


def current_price_id(plan, interval: str = "Monthly") -> str | None:
	"""The price a new subscription should be sold at."""
	doc = plan if hasattr(plan, "get") else frappe.get_doc("Plan", plan)
	return doc.get(field_for(interval))
