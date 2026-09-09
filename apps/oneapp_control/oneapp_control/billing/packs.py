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


def floor_price(credits: float) -> float:
	"""The least a pack of this many credits may be sold for.

	A credit is only worth selling above what it costs us to honour, and until
	this existed nothing connected the two numbers: `Credit Pack.credits` and
	`.amount` are typed by an operator, and the markup that decides what a
	credit *buys* is typed on a different screen. A pack priced below this is
	not a discount, it is a subscription to somebody else's inference bill.

	Priced against the lowest markup any callable model carries, because the
	customer picks the model. See `pricing.lowest_markup`.
	"""
	from oneapp_control.ai import pricing

	return round(float(credits) * pricing.cost_per_credit(), 2)


def check_price(credits: float, amount: float, label: str = "") -> None:
	"""Refuse a pack that sells credits for less than they cost."""
	if float(credits) <= 0 or float(amount) <= 0:
		return

	floor = floor_price(credits)
	if float(amount) >= floor:
		return

	frappe.throw(
		_(
			"{0}{1} credits cost us {2} to honour at the current markup, so they "
			"cannot be sold for {3}. Raise the price, cut the credits, or raise "
			"the AI markup."
		).format(
			f"{label}: " if label else "",
			int(credits) if float(credits).is_integer() else credits,
			frappe.utils.fmt_money(floor, currency="USD"),
			frappe.utils.fmt_money(float(amount), currency="USD"),
		)
	)


def underwater(markup: float | None = None) -> list[dict]:
	"""Every sellable pack that would be under cost at a given markup.

	Read by the two screens that can *cause* it — the global markup and a
	model's override — because lowering either is what puts a pack under water:
	a smaller markup charges fewer credits for the same provider spend, so each
	credit has to buy more of it. Raising one is always safe.
	"""
	from oneapp_control.ai import pricing

	per_credit = pricing.cost_per_credit(markup)
	found = []
	for row in frappe.get_all(
		"Credit Pack", filters={"is_active": 1},
		fields=["name", "pack_name", "credits", "amount"],
	):
		floor = round(float(row.credits or 0) * per_credit, 2)
		if float(row.amount or 0) < floor:
			found.append({**row, "floor": floor})
	return found


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
