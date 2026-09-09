"""Minimal Stripe REST client.

Deliberately not the `stripe` SDK: the surface we need is small, and calling the
REST API directly keeps error handling explicit and the dependency set honest.

Stripe owns the recurring schedule, dunning, SCA and card updates. We mirror its
state; we never try to reproduce it.
"""

import frappe
import requests

API_BASE = "https://api.stripe.com/v1"
TIMEOUT = 30


class StripeError(Exception):
	pass


def secret_key() -> str:
	"""The one credential everything here runs on.

	Our own settings first. It used to be only the payments app's Stripe
	Settings, which meant carrying that whole app on the control bench for a
	single Password field — and none of what it exists for is how anything here
	charges: we drive Stripe's API directly and mirror the result, rather than
	going through Payment Requests and a redirect flow.

	A Stripe Settings that still holds a key is still read, so an existing
	deployment keeps working until somebody moves the key across.
	"""
	settings = frappe.get_single("OneSpace Control Settings")
	if settings:
		key = settings.get_password("stripe_secret_key", raise_exception=False)
		if key:
			return key

	if frappe.db.exists("DocType", "Stripe Settings"):
		name = frappe.db.get_value("Stripe Settings", {}, "name")
		if name:
			key = frappe.get_doc("Stripe Settings", name).get_password(
				"secret_key", raise_exception=False
			)
			if key:
				return key

	raise StripeError(
		"No Stripe secret key found. Set it in Settings → Billing."
	)


def _flatten(data: dict, parent: str = "") -> list[tuple[str, str]]:
	"""Stripe takes form encoding with bracket notation, not JSON."""
	items = []
	for key, value in data.items():
		field = f"{parent}[{key}]" if parent else key
		if isinstance(value, dict):
			items.extend(_flatten(value, field))
		elif isinstance(value, list):
			for i, item in enumerate(value):
				if isinstance(item, dict):
					items.extend(_flatten(item, f"{field}[{i}]"))
				else:
					items.append((f"{field}[{i}]", str(item)))
		elif value is not None:
			items.append((field, str(value)))
	return items


def request(method: str, path: str, data: dict | None = None,
            idempotency_key: str | None = None, params: dict | None = None) -> dict:
	headers = {"Authorization": f"Bearer {secret_key()}"}
	if idempotency_key:
		# Stripe dedupes on this for 24h, so a retried checkout cannot double-charge.
		headers["Idempotency-Key"] = idempotency_key

	try:
		response = requests.request(
			method,
			f"{API_BASE}/{path.lstrip('/')}",
			headers=headers,
			data=_flatten(data or {}),
			# `expand` on a GET has to be in the query string — Stripe does not
			# read a body on a GET, and a silently ignored expand comes back as
			# a bare id where the code expected an object.
			params=_flatten(params or {}),
			timeout=TIMEOUT,
		)
	except requests.RequestException as e:
		raise StripeError(f"Stripe unreachable: {e}") from e

	body = {}
	try:
		body = response.json()
	except ValueError:
		pass

	if response.status_code >= 400:
		message = (body.get("error") or {}).get("message") or response.text[:300]
		raise StripeError(f"Stripe {response.status_code}: {message}")

	return body


def create_checkout_session(**kwargs) -> dict:
	return request("POST", "checkout/sessions", kwargs,
	               idempotency_key=kwargs.pop("_idempotency_key", None))


def get_subscription(subscription_id: str) -> dict:
	return request("GET", f"subscriptions/{subscription_id}")


def get_charge(charge_id: str) -> dict:
	"""One charge, with the balance transaction that says what Stripe kept.

	The fee is not on the charge and not on the invoice — it is on the balance
	transaction, which is what makes a payout the net of a batch rather than
	the sum of its charges. Expanded here so learning the fee is one call.
	"""
	return request("GET", f"charges/{charge_id}",
	               params={"expand": ["balance_transaction"]})


def get_payment_intent(intent_id: str) -> dict:
	"""A checkout session names an intent, not a charge. This bridges the two."""
	return request("GET", f"payment_intents/{intent_id}")


def update_subscription(subscription_id: str, **kwargs) -> dict:
	return request("POST", f"subscriptions/{subscription_id}", kwargs,
	               idempotency_key=kwargs.pop("_idempotency_key", None))


# --------------------------------------------------------------------------- #
# Catalogue
#
# Products carry the name on the invoice; Prices carry the money. A Price is
# immutable in `unit_amount` and `currency` — the only way to change what a plan
# costs is to mint a new one and archive the old, which is also what leaves
# existing subscriptions billing at the price they bought.
# --------------------------------------------------------------------------- #

def create_product(idempotency_key: str | None = None, **kwargs) -> dict:
	return request("POST", "products", kwargs, idempotency_key=idempotency_key)


def update_product(product_id: str, **kwargs) -> dict:
	return request("POST", f"products/{product_id}", kwargs)


def create_price(idempotency_key: str | None = None, **kwargs) -> dict:
	return request("POST", "prices", kwargs, idempotency_key=idempotency_key)


def archive_price(price_id: str) -> dict:
	"""Stop a price being sellable. Existing subscriptions keep billing on it."""
	return request("POST", f"prices/{price_id}", {"active": "false"})


def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> dict:
	if at_period_end:
		return request("POST", f"subscriptions/{subscription_id}",
		               {"cancel_at_period_end": "true"})
	return request("DELETE", f"subscriptions/{subscription_id}")


def create_billing_portal_session(customer_id: str, return_url: str) -> dict:
	"""Let customers manage their own card and cancellations."""
	return request("POST", "billing_portal/sessions",
	               {"customer": customer_id, "return_url": return_url})


# --------------------------------------------------------------------------- #
# Discounts
#
# Two objects, deliberately. A **Coupon** is the money — percent or amount, and
# for how many billing periods. A **Promotion Code** is the string somebody types
# and the rules about who may type it: how many times in total, until when,
# first-time customers only.
#
# A coupon's terms are immutable once created, exactly like a price. Changing a
# percentage means minting a new coupon, which is why nothing here updates one.
# --------------------------------------------------------------------------- #

def create_coupon(idempotency_key: str | None = None, **kwargs) -> dict:
	return request("POST", "coupons", kwargs, idempotency_key=idempotency_key)


def create_promotion_code(idempotency_key: str | None = None, **kwargs) -> dict:
	return request("POST", "promotion_codes", kwargs, idempotency_key=idempotency_key)


def update_promotion_code(promotion_code_id: str, **kwargs) -> dict:
	"""Only `active` and `metadata` are mutable; the money is on the coupon."""
	return request("POST", f"promotion_codes/{promotion_code_id}", kwargs)


def get_promotion_code(promotion_code_id: str) -> dict:
	return request("GET", f"promotion_codes/{promotion_code_id}")
