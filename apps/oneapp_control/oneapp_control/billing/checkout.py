"""Starting a purchase.

Two shapes, deliberately different:

* **Credit packs** are one-off payments. Purchased credits roll over.
* **Subscriptions** use Stripe Checkout in subscription mode, so Stripe owns
  renewal, dunning, SCA and card updates. Plan grants are non-rollover.
"""

import frappe
from frappe import _

from oneapp_control.billing import stripe_client


def _settings():
	return frappe.get_single("OneApp Control Settings")


def _urls(tenant: str):
	base = (_settings().control_plane_url or "").rstrip("/")
	return (
		f"{base}/billing/success?tenant={tenant}&session={{CHECKOUT_SESSION_ID}}",
		f"{base}/billing/cancelled?tenant={tenant}",
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


@frappe.whitelist()
def billing_portal(tenant: str) -> dict:
	"""Hand the customer to Stripe to manage their own card and cancellation."""
	subscription = frappe.db.get_value(
		"Subscription", {"tenant": tenant}, ["name", "stripe_customer_id"], as_dict=True
	)
	if not (subscription and subscription.stripe_customer_id):
		frappe.throw(_("No Stripe customer for {0}.").format(tenant))

	base = (_settings().control_plane_url or "").rstrip("/")
	session = stripe_client.create_billing_portal_session(
		subscription.stripe_customer_id, f"{base}/billing?tenant={tenant}"
	)
	return {"url": session.get("url")}
