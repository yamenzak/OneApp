"""Promo codes: ours to declare, Stripe's to enforce.

Saving a `Promo Code` creates two Stripe objects, and the split matters:

* a **Coupon** is the money — percent or amount off, and for how many billing
  periods it lasts;
* a **Promotion Code** is the string somebody types, plus the rules about who
  may type it: how many redemptions in total, until when, first-time customers
  only.

Nobody pastes a `promo_...` id between two systems, for the same reason nobody
pastes a price: dual entry is how a page advertises one discount and the card is
charged another. And nothing here counts redemptions — Stripe counts them, and
two systems counting the same thing disagree.

**A coupon is immutable once created.** Changing a percentage therefore mints a
new coupon and a new promotion code and deactivates the old one. Anybody already
redeemed keeps what they were given, which is Stripe's behaviour and the right
one: it is the same grandfathering shape a plan price has.

**Scope is ours.** Stripe will happily apply a coupon to any purchase in a
session that allows promotion codes, so what stops a subscription code being
used on a credit pack is that the pack's checkout is never told to accept one.
`allows` is that gate, and every caller that opens a session asks it.
"""

import frappe
from frappe import _

# What a code may be spent on. The key is the field on `Promo Code`; the value is
# the `kind` a checkout session declares itself as, so a caller asks the question
# in the vocabulary it already has.
SCOPES = {
	"subscription": "on_subscriptions",
	"addon": "on_addons",
	"credit_pack": "on_credit_packs",
}


def sync(promo) -> None:
	"""Bring Stripe in line with this code. Mutates the doc; never raises.

	Same contract as a plan's sync: a control plane that cannot reach Stripe is
	still a place to draft a code, and a code an operator cannot save is worse
	than one that is not live yet.
	"""
	from oneapp_control.billing import catalogue, stripe_client

	try:
		promo.sync_error = None
		if not catalogue.configured():
			return

		fingerprint = _fingerprint(promo)
		if promo.stripe_coupon_id and promo.get("_synced_fingerprint") == fingerprint:
			_ensure_active(promo)
			return

		if promo.stripe_coupon_id and _changed(promo, fingerprint):
			# The money moved. A coupon cannot be edited, so the old promotion
			# code is retired and a new pair is minted; everybody already
			# redeemed keeps the discount they were given.
			_deactivate(promo)
			promo.stripe_coupon_id = None
			promo.stripe_promotion_code_id = None

		if not promo.stripe_coupon_id:
			coupon = stripe_client.create_coupon(
				idempotency_key=f"promo-coupon:{promo.name}:{fingerprint}",
				**_coupon_args(promo),
			)
			promo.stripe_coupon_id = coupon["id"]

			code = stripe_client.create_promotion_code(
				idempotency_key=f"promo-code:{promo.name}:{fingerprint}",
				**_promotion_args(promo),
			)
			promo.stripe_promotion_code_id = code["id"]

		_ensure_active(promo)
	except Exception as e:
		promo.sync_error = str(e)[:1000]
		frappe.log_error(
			title=f"Stripe sync failed for promo {promo.name}",
			message=frappe.get_traceback(),
		)


def _coupon_args(promo) -> dict:
	args = {
		"name": promo.name,
		"duration": promo.duration.lower(),
		"metadata": {"promo": promo.name},
	}
	if promo.duration == "Repeating":
		args["duration_in_months"] = int(promo.duration_in_months or 1)

	if promo.discount_type == "Percent":
		args["percent_off"] = float(promo.percent_off or 0)
	else:
		args["amount_off"] = int(round(float(promo.amount_off or 0) * 100))
		args["currency"] = (promo.currency or "USD").lower()
	return args


def _promotion_args(promo) -> dict:
	args = {
		"coupon": promo.stripe_coupon_id,
		"code": promo.name,
		"metadata": {"promo": promo.name},
	}
	if promo.max_redemptions:
		args["max_redemptions"] = int(promo.max_redemptions)
	if promo.expires_on:
		from frappe.utils import get_datetime

		args["expires_at"] = int(get_datetime(promo.expires_on).timestamp())
	if promo.first_time_only:
		args["restrictions"] = {"first_time_transaction": "true"}
	return args


def _fingerprint(promo) -> str:
	"""Everything a coupon fixes at creation, as one comparable string."""
	return "|".join(str(promo.get(field) or "") for field in (
		"discount_type", "percent_off", "amount_off", "currency",
		"duration", "duration_in_months",
	))


def _changed(promo, fingerprint: str) -> bool:
	before = promo.get_doc_before_save()
	return bool(before) and _fingerprint(before) != fingerprint


def _deactivate(promo) -> None:
	from oneapp_control.billing import stripe_client

	if promo.stripe_promotion_code_id:
		stripe_client.update_promotion_code(promo.stripe_promotion_code_id, active="false")


def _ensure_active(promo) -> None:
	"""Match Stripe's `active` to ours.

	Deactivating stops the code being accepted; it does not take the discount
	away from anybody who already redeemed it. That is Stripe's behaviour and it
	is the one we want — a code withdrawn is not a bill re-raised.
	"""
	from oneapp_control.billing import stripe_client

	if not promo.stripe_promotion_code_id:
		return
	stripe_client.update_promotion_code(
		promo.stripe_promotion_code_id,
		active="true" if promo.is_active else "false",
	)


# --------------------------------------------------------------------------- #
# Spending one
# --------------------------------------------------------------------------- #

def allows(promo, kind: str) -> bool:
	"""Whether this code may be spent on this kind of purchase."""
	field = SCOPES.get(kind)
	return bool(field and promo.get(field))


def resolve(code: str, kind: str):
	"""The code somebody typed, if they may spend it here.

	Returns the doc, or throws with a reason a person can act on. Deliberately
	the same message for "no such code" and "not for this" — a promo field that
	distinguishes them is a way to enumerate the codes we have.
	"""
	if not code:
		return None

	name = str(code).strip().upper()
	promo = frappe.db.exists("Promo Code", name) and frappe.get_doc("Promo Code", name)
	if not promo or not promo.is_active or not allows(promo, kind):
		frappe.throw(_("That code is not valid here."))

	if not promo.stripe_promotion_code_id:
		# Ours but never minted — Stripe was unreachable when it was saved.
		# Named differently because this one is our fault and re-saving fixes it.
		frappe.throw(_("That code is not live yet. Try again in a minute."))

	return promo


def discounts_for(promo) -> list[dict]:
	"""The `discounts` argument for a Checkout session."""
	return [{"promotion_code": promo.stripe_promotion_code_id}] if promo else []


def is_total_discount(promo) -> bool:
	"""Whether this takes the whole amount off, for as long as it lasts.

	The thing worth knowing at checkout: Stripe collects no payment method when
	the total is zero, so a signup on one of these needs no card — which is what
	makes a demo or training workspace possible without a second lifecycle for it.
	"""
	return bool(
		promo
		and promo.discount_type == "Percent"
		and float(promo.percent_off or 0) >= 100
	)


def refresh_redemptions(promo=None) -> None:
	"""Copy Stripe's redemption count onto the record.

	Stripe counts; we display. Incrementing our own would give two systems an
	opinion about the same number, and they would drift the first time a
	checkout was abandoned after the code was applied.
	"""
	from oneapp_control.billing import catalogue, stripe_client

	if not catalogue.configured():
		return

	names = (
		[promo] if promo
		else frappe.get_all("Promo Code", filters={"is_active": 1}, pluck="name")
	)
	for name in names:
		code_id = frappe.db.get_value("Promo Code", name, "stripe_promotion_code_id")
		if not code_id:
			continue
		try:
			remote = stripe_client.get_promotion_code(code_id)
		except Exception:
			frappe.log_error(title=f"Could not read promo {name} from Stripe")
			continue
		frappe.db.set_value(
			"Promo Code", name, "times_redeemed", int(remote.get("times_redeemed") or 0)
		)
