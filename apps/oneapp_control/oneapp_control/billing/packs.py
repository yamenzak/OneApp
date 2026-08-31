"""Credit packs, and the Stripe objects behind them.

The other half of how credits arrive. A plan grants some every period and they
expire at the end of it; a pack is bought outright and rolls over, which is what
makes it worth buying — `ledger.open_grants` spends the soonest-expiring grant
first and never-expiring purchases last, so a pack is only ever drawn on once
this period's grant is gone.

One price rather than two, because a pack is bought once and has no cadence. It
still carries the full price history: repricing one has to archive the old Stripe
price like everything else, or the old id stays sellable.

Packs used to be six dictionaries in `api/customer.py` with the amount built
inline at checkout, which meant changing a price was a deploy and a receipt named
a product that did not exist.
"""

import frappe
from frappe import _

from oneapp_control.billing import catalogue

KIND = "pack"
INTERVAL = catalogue.ONE_OFF


def sync(pack) -> None:
	"""Bring Stripe in line with this pack. Mutates the doc; never raises."""
	catalogue.sync(
		pack,
		kind=KIND,
		product_name=pack.pack_name,
		amounts={INTERVAL: float(pack.amount or 0)},
		price_field="stripe_price_id",
	)


def pack_for_price(price_id: str) -> str | None:
	return catalogue.owner_of_price(price_id, "Credit Pack")


def sellable(pack: str):
	"""The pack and its price, or a refusal saying which is missing."""
	doc = frappe.get_doc("Credit Pack", pack)
	if not doc.is_active:
		frappe.throw(_("{0} is not available.").format(doc.pack_name))
	if not doc.stripe_price_id:
		frappe.throw(_("{0} is not priced yet.").format(doc.pack_name))
	return doc


def offered() -> list[dict]:
	"""Every pack a customer may buy, cheapest first."""
	return frappe.get_all(
		"Credit Pack",
		filters={"is_active": 1},
		fields=["name as code", "pack_name as name", "credits", "amount", "currency",
		        "description"],
		order_by="sort_order asc, amount asc",
	)
