"""Add-ons, and the Stripe objects behind them.

An add-on is extra quota bought per month against a workspace's existing
subscription — a second recurring line on the same Stripe subscription, so the
customer gets one invoice, one dunning cycle and one card.

It is deliberately not a plan. Plans differ only in quotas and carry every
feature (`DECISIONS.md` §3); an add-on adds to a quota without moving anybody
between plans, which is the difference between "I have outgrown this tier" and
"I need more room".

Sold per unit: `+50 GB` bought three times is one line at quantity three, not
three products. That is what lets a workspace grow without a new price for every
size somebody might want.

The Stripe mechanics — minting a price rather than editing one, archiving what
it replaced, keeping the old id so a grandfathered line can still be named —
are `billing/catalogue.py`, shared with plans and credit packs.
"""

import frappe

from oneapp_control.billing import catalogue

KIND = "addon"
INTERVALS = catalogue.INTERVALS

# What each kind of add-on adds to. The key is the `Add-on.kind` option; the
# value is the quota field on a Plan, which is also what `quotas.TERMS` calls it
# and what the Subscription captures. One mapping, so a new kind is one line here
# and a Select option rather than a hunt.
QUOTA_FIELD = {
	"File Storage": "storage_gb",
	"Database Storage": "database_gb",
}


def field_for(interval: str) -> str:
	return f"stripe_price_id_{interval.lower()}"


def amount_for(addon, interval: str) -> float:
	return float((addon.price_yearly if interval == "Yearly" else addon.price_monthly) or 0)


def sync(addon) -> None:
	"""Bring Stripe in line with this add-on. Mutates the doc; never raises."""
	catalogue.sync(
		addon,
		kind=KIND,
		product_name=addon.addon_name,
		amounts={interval: amount_for(addon, interval) for interval in INTERVALS},
		price_field=field_for,
	)


# --------------------------------------------------------------------------- #
# Reading back
# --------------------------------------------------------------------------- #

def addon_for_price(price_id: str) -> str | None:
	"""Which add-on is this Stripe price?

	The mirror of `plans.plan_for_price`, and narrowed the same way: one table
	holds every catalogue's history, so without the parenttype a plan's price
	would resolve to "an add-on".
	"""
	return catalogue.owner_of_price(price_id, "Add-on")


def current_price_id(addon, interval: str = "Monthly") -> str | None:
	"""The price a new line should be sold at."""
	doc = addon if hasattr(addon, "get") else frappe.get_doc("Add-on", addon)
	return doc.get(field_for(interval))


def sellable(addon: str, interval: str = "Monthly"):
	"""The add-on and its price, or a refusal saying which is missing.

	Two ways to fail and they are not the same: an add-on that has been retired,
	and one that is simply not priced at the cadence this workspace bills on. A
	yearly workspace cannot hold a monthly line — Stripe requires every recurring
	item on a subscription to share an interval — so an add-on priced only
	monthly is genuinely unavailable to them rather than broken.
	"""
	from frappe import _

	doc = frappe.get_doc("Add-on", addon)
	if not doc.is_active:
		frappe.throw(_("{0} is not available.").format(doc.addon_name))

	price_id = current_price_id(doc, interval)
	if not price_id:
		frappe.throw(
			_("{0} is not sold on a {1} subscription.").format(doc.addon_name, interval.lower())
		)
	return doc, price_id


def quota_for(rows) -> dict:
	"""What a set of Subscription Add-on rows adds to the quota.

	Returns the quota fields an add-on can move, so a caller adds rather than
	branches. The GB per unit comes off the row and not off the Add-on: it is
	captured at purchase for the same reason plan terms are, so that editing the
	catalogue does not silently move somebody who already bought.
	"""
	found = {field: 0 for field in QUOTA_FIELD.values()}
	for row in rows or []:
		field = QUOTA_FIELD.get(row.get("kind") if isinstance(row, dict) else row.kind)
		if not field:
			continue
		quantity = int((row.get("quantity") if isinstance(row, dict) else row.quantity) or 0)
		unit = int((row.get("unit_gb") if isinstance(row, dict) else row.unit_gb) or 0)
		found[field] += quantity * unit
	return found
