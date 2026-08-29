"""Starting a purchase.

Two shapes, deliberately different:

* **Credit packs** are one-off payments. Purchased credits roll over.
* **Subscriptions** use Stripe Checkout in subscription mode, so Stripe owns
  renewal, dunning, SCA and card updates. Plan grants are non-rollover.
"""

import frappe
from frappe import _

from oneapp_control import portal
from oneapp_control.billing import stripe_client


def _settings():
	return frappe.get_single("OneApp Control Settings")


def _urls(tenant: str):
	"""Where Stripe sends the customer back to.

	Both land on the workspace's own billing page — the one place where the
	result of the purchase is visible — with a flag the page reads to say what
	happened. Stripe substitutes the session id into the success URL.
	"""
	return (
		portal.account_url(tenant, tab="billing", checkout="success", session="{CHECKOUT_SESSION_ID}"),
		portal.account_url(tenant, tab="billing", checkout="cancelled"),
	)


@frappe.whitelist()
def start_subscription(tenant: str, plan: str, interval: str = "Monthly") -> dict:
	"""Create a Checkout session for a plan subscription."""
	tenant_doc = frappe.get_doc("Tenant", tenant)
	plan_doc = frappe.get_doc("Plan", plan)

	price_id = (
		plan_doc.stripe_price_id_yearly
		if interval == "Yearly"
		else plan_doc.stripe_price_id_monthly
	)
	if not price_id:
		frappe.throw(_("Plan {0} has no Stripe price for {1} billing.").format(plan, interval))

	success_url, cancel_url = _urls(tenant)

	session = stripe_client.create_checkout_session(
		mode="subscription",
		line_items=[{"price": price_id, "quantity": 1}],
		success_url=success_url,
		cancel_url=cancel_url,
		customer_email=tenant_doc.owner_email,
		client_reference_id=tenant,
		# Echoed back on every webhook, so we never have to guess which tenant an
		# event belongs to.
		subscription_data={"metadata": {"tenant": tenant, "plan": plan}},
		metadata={"tenant": tenant, "plan": plan, "interval": interval},
	)

	return {"url": session.get("url"), "id": session.get("id")}


@frappe.whitelist()
def start_credit_pack(tenant: str, credits: float, amount: float,
                      currency: str = "usd") -> dict:
	"""Create a Checkout session for a one-off credit pack."""
	tenant_doc = frappe.get_doc("Tenant", tenant)
	credits = float(credits)
	amount = float(amount)

	if credits <= 0 or amount <= 0:
		frappe.throw(_("Credit pack must have a positive size and price."))

	success_url, cancel_url = _urls(tenant)

	session = stripe_client.create_checkout_session(
		mode="payment",
		line_items=[
			{
				"quantity": 1,
				"price_data": {
					"currency": currency,
					"unit_amount": int(round(amount * 100)),
					"product_data": {"name": f"{int(credits)} OneApp credits"},
				},
			}
		],
		success_url=success_url,
		cancel_url=cancel_url,
		customer_email=tenant_doc.owner_email,
		client_reference_id=tenant,
		payment_intent_data={"metadata": {"tenant": tenant, "credits": credits}},
		metadata={"tenant": tenant, "credits": credits, "kind": "credit_pack"},
	)

	return {"url": session.get("url"), "id": session.get("id")}


def start_signup(request) -> dict:
	"""Checkout for a signup, before any tenant exists.

	The Account Request id rides along in metadata so the webhook can find its
	way back — at this point there is no tenant to key on.
	"""
	plan = frappe.get_doc("Plan", request.plan)
	price_id = (
		plan.stripe_price_id_yearly
		if request.interval == "Yearly"
		else plan.stripe_price_id_monthly
	)
	if not price_id:
		frappe.throw(
			_("{0} has no Stripe price for {1} billing.").format(plan.plan_name, request.interval)
		)

	session = stripe_client.create_checkout_session(
		mode="subscription",
		line_items=[{"price": price_id, "quantity": 1}],
		success_url=portal.welcome_url(request.name),
		cancel_url=portal.signup_url(cancelled=request.name),
		customer_email=request.email,
		client_reference_id=request.name,
		subscription_data={
			"metadata": {"account_request": request.name, "plan": request.plan}
		},
		metadata={
			"account_request": request.name,
			"plan": request.plan,
			"interval": request.interval,
			"kind": "signup",
		},
		# Stripe dedupes for 24h, so a double-submitted form cannot create two
		# subscriptions for the same request.
		_idempotency_key=f"signup:{request.name}",
	)

	return {"id": session.get("id"), "url": session.get("url")}


def start_storage_pack(tenant: str, gb: int, amount: float, currency: str = "usd") -> dict:
	"""One-off purchase of permanent extra storage."""
	tenant_doc = frappe.get_doc("Tenant", tenant)
	success_url, cancel_url = _urls(tenant)

	session = stripe_client.create_checkout_session(
		mode="payment",
		line_items=[
			{
				"quantity": 1,
				"price_data": {
					"currency": currency,
					"unit_amount": int(round(float(amount) * 100)),
					"product_data": {"name": f"{int(gb)} GB additional storage"},
				},
			}
		],
		success_url=success_url,
		cancel_url=cancel_url,
		customer_email=tenant_doc.owner_email,
		client_reference_id=tenant,
		payment_intent_data={"metadata": {"tenant": tenant, "storage_gb": gb}},
		metadata={"tenant": tenant, "storage_gb": gb, "kind": "storage_pack"},
	)

	return {"url": session.get("url"), "id": session.get("id")}


@frappe.whitelist()
def billing_portal(tenant: str) -> dict:
	"""Hand the customer to Stripe to manage their own card and cancellation."""
	subscription = frappe.db.get_value(
		"Subscription", {"tenant": tenant}, ["name", "stripe_customer_id"], as_dict=True
	)
	if not (subscription and subscription.stripe_customer_id):
		frappe.throw(_("No Stripe customer for {0}.").format(tenant))

	session = stripe_client.create_billing_portal_session(
		subscription.stripe_customer_id, portal.account_url(tenant, tab="billing")
	)
	return {"url": session.get("url")}
