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
	"""Prefer the payments app's gateway config, so there is one place to rotate."""
	name = frappe.db.get_value("Stripe Settings", {}, "name")
	if name:
		key = frappe.get_doc("Stripe Settings", name).get_password(
			"secret_key", raise_exception=False
		)
		if key:
			return key

	raise StripeError(
		"No Stripe secret key found. Configure Stripe Settings (payments app)."
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
            idempotency_key: str | None = None) -> dict:
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
