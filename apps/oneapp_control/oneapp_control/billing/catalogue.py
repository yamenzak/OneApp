"""Keeping Stripe in step with anything we sell.

Three things carry a price now — plans, add-ons and credit packs — and all three
want the same behaviour, because it is Stripe's behaviour rather than a
preference of ours:

**Stripe Prices are immutable in amount and currency.** Changing what something
costs means minting a *new* Price and archiving the old one, never editing in
place. That is not a workaround; it is what makes grandfathering real. Everyone
already subscribed keeps billing on the Price they bought, because their
subscription still points at it, and the `Catalogue Price` table keeps the id so
we can still say what that price was for.

**Nothing here may prevent a record from being saved.** Stripe being unreachable
is a temporary condition; a plan an operator cannot edit is a worse one. Failures
land in the doc's own `sync_error` and the next save retries.

The parent-specific parts — what the doc calls its amounts, which field holds the
current price id, what the product is named — are passed in. Everything else is
here once, so a fourth thing to sell is a description rather than a fourth copy
of this file.
"""

import frappe
from frappe.utils import now_datetime

from oneapp_control.billing import stripe_client

# What our interval names mean to Stripe. `One-off` is deliberately absent: it is
# not a recurring interval, it is the absence of one, and `recurring` is simply
# omitted from the price.
INTERVALS = {"Monthly": "month", "Yearly": "year"}
ONE_OFF = "One-off"


def configured() -> bool:
	"""Whether there is a Stripe account to sync against at all.

	A control plane without Stripe is a perfectly good place to draft a
	catalogue. Readiness already reports that none of it can be sold yet.
	"""
	try:
		return bool(stripe_client.secret_key())
	except stripe_client.StripeError:
		return False


def sync(doc, *, kind: str, product_name: str, amounts: dict, price_field=None,
         currency: str | None = None) -> None:
	"""Bring Stripe in line with one catalogue record. Never raises.

	`kind` names the catalogue in Stripe metadata and in the idempotency keys —
	`plan`, `addon`, `pack`. `amounts` maps an interval to what it costs; an
	interval priced at zero or less is not sold. `price_field` says where the
	current price id for an interval is stored on the doc, and may be a callable
	or None when the doc keeps only one.

	Called from the record's own `validate`, so the product id, the price ids and
	the new `Catalogue Price` rows are part of the same save the operator asked
	for, rather than a second write that could half-apply.
	"""
	try:
		doc.sync_error = None
		if not configured():
			return

		ensure_product(doc, kind=kind, name=product_name)
		for interval, amount in amounts.items():
			ensure_price(
				doc,
				kind=kind,
				interval=interval,
				amount=float(amount or 0),
				currency=(currency or getattr(doc, "currency", None) or "USD").lower(),
				price_field=price_field,
			)
	except Exception as e:
		# Recorded, not raised. The record saves either way and keeps selling on
		# whatever prices it already has.
		doc.sync_error = str(e)[:1000]
		frappe.log_error(
			title=f"Stripe sync failed for {kind} {doc.name}",
			message=frappe.get_traceback(),
		)


def ensure_product(doc, *, kind: str, name: str) -> None:
	"""One Stripe Product per record, carrying the name customers see."""
	if doc.stripe_product_id:
		# The name is the only mutable thing we care about, and it is what shows
		# on the invoice, so a renamed record should not keep the old name there.
		stripe_client.update_product(
			doc.stripe_product_id, name=name, metadata={kind: doc.name}
		)
		return

	product = stripe_client.create_product(
		name=name,
		metadata={kind: doc.name},
		# Stripe dedupes on this for 24h, so a double-saved new record cannot
		# leave two products behind.
		idempotency_key=f"{kind}-product:{doc.name}",
	)
	doc.stripe_product_id = product["id"]


def ensure_price(doc, *, kind: str, interval: str, amount: float, currency: str,
                 price_field=None) -> None:
	"""Make sure the current Price matches what the record says it costs."""
	field = _field(price_field, interval)
	current = current_row(doc, interval)

	if amount <= 0:
		# A plan can be monthly-only. Nothing to sell at that cadence, so nothing
		# to mint — but an existing price stays listed, because someone may be on
		# it.
		if current:
			retire_row(current)
			if field:
				doc.set(field, None)
		return

	if current and _matches(current, amount, currency):
		if field:
			doc.set(field, current.stripe_price_id)
		return

	cents = int(round(amount * 100))
	price = stripe_client.create_price(
		product=doc.stripe_product_id,
		currency=currency,
		unit_amount=cents,
		# Omitted entirely for a one-off. Stripe reads the presence of
		# `recurring` as "this is a subscription price", so passing it empty is
		# not the same as leaving it out.
		**({} if interval == ONE_OFF else {"recurring": {"interval": INTERVALS[interval]}}),
		metadata={kind: doc.name, "interval": interval},
		# Keyed on the amount as well as the record: minting the same price twice
		# is a duplicate, minting a different one is a deliberate change.
		idempotency_key=f"{kind}-price:{doc.name}:{interval}:{currency}:{cents}",
	)

	if current:
		# Archived in Stripe so it can never be sold again. Stripe keeps billing
		# existing subscriptions on an archived price, which is exactly the
		# behaviour grandfathering needs.
		stripe_client.archive_price(current.stripe_price_id)
		retire_row(current)

	doc.append(
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
	if field:
		doc.set(field, price["id"])


def current_row(doc, interval: str):
	for row in doc.prices or []:
		if row.interval == interval and row.is_current:
			return row
	return None


def retire_row(row) -> None:
	row.is_current = 0
	row.archived_on = now_datetime()


def _matches(row, amount: float, currency: str) -> bool:
	return (
		abs(float(row.unit_amount or 0) - amount) < 0.005
		and (row.currency or "").lower() == currency
	)


def _field(price_field, interval: str):
	if price_field is None:
		return None
	return price_field(interval) if callable(price_field) else price_field


# --------------------------------------------------------------------------- #
# Reading back
# --------------------------------------------------------------------------- #

def owner_of_price(price_id: str, parenttype: str) -> str | None:
	"""Which record of `parenttype` is this Stripe price?

	The question a webhook has to answer when a subscription changes underneath
	us: Stripe tells us the price, and only this table knows what it was sold as.
	Grandfathered prices resolve too, which is the point of keeping them.

	`parenttype` is not optional. One table holds every catalogue's history, so
	without it an add-on's price would resolve to "a plan" and reprice the
	workspace onto whatever happened to match.
	"""
	if not price_id:
		return None
	return frappe.db.get_value(
		"Catalogue Price",
		{"stripe_price_id": price_id, "parenttype": parenttype},
		"parent",
	)


def interval_of_price(price_id: str, parenttype: str) -> str | None:
	if not price_id:
		return None
	return frappe.db.get_value(
		"Catalogue Price",
		{"stripe_price_id": price_id, "parenttype": parenttype},
		"interval",
	)
