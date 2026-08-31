"""Starting a purchase.

Two shapes, deliberately different:

* **Credit packs** are one-off payments. Purchased credits roll over.
* **Subscriptions** use Stripe Checkout in subscription mode, so Stripe owns
  renewal, dunning, SCA and card updates. Plan grants are non-rollover.
"""

import frappe
from frappe import _

from oneapp_control import portal
from oneapp_control.billing import plans as plan_catalogue
from oneapp_control.billing import quotas, stripe_client


def _settings():
	return frappe.get_single("OneSpace Control Settings")


def _urls(tenant: str):
	"""Where Stripe sends the customer back to.

	Both land on the workspace's own billing page — the one place where the
	result of the purchase is visible — with a flag the page reads to say what
	happened. Stripe substitutes the session id into the success URL.
	"""
	return (
		portal.account_url(tenant, "billing", checkout="success", session="{CHECKOUT_SESSION_ID}"),
		portal.account_url(tenant, "billing", checkout="cancelled"),
	)


def _sellable(plan: str, interval: str):
	"""The plan doc and the price a new subscription may be sold at.

	Retired plans are refused here as well as hidden from the catalogue: a plan
	code is not a secret, and "not offered any more" has to mean something at
	the point of sale rather than only in the list.
	"""
	plan_doc = frappe.get_doc("Plan", plan)
	if not plan_doc.is_active:
		frappe.throw(_("{0} is no longer offered.").format(plan_doc.plan_name))

	price_id = plan_catalogue.current_price_id(plan_doc, interval)
	if not price_id:
		frappe.throw(
			_("{0} has no Stripe price for {1} billing.").format(plan_doc.plan_name, interval)
		)
	return plan_doc, price_id


@frappe.whitelist()
def start_subscription(tenant: str, plan: str, interval: str = "Monthly") -> dict:
	"""Create a Checkout session for a plan subscription."""
	tenant_doc = frappe.get_doc("Tenant", tenant)
	plan_doc, price_id = _sellable(plan, interval)

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
					"product_data": {"name": f"{int(credits)} OneSpace credits"},
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
def change_plan(tenant: str, plan: str, interval: str = "Monthly") -> dict:
	"""Move an existing subscription onto another plan.

	Ours rather than Stripe's billing portal, for one reason that matters: the
	portal cannot know our quotas, so it will happily sell a downgrade to a
	workspace holding more data than the smaller plan allows — and the customer
	finds out afterwards, over quota, with no way back except paying again. The
	same fit check the plans page renders runs here, so the two cannot disagree.

	The portal keeps what it is good at: cards, invoices and cancellation.

	Proration is immediate and symmetric. Stripe bills or credits the difference
	on the next invoice, and the new terms take effect now — a plan change that
	charges today and applies next month is the kind of split nobody can reason
	about from a receipt.
	"""
	tenant_doc = frappe.get_doc("Tenant", tenant)
	plan_doc, price_id = _sellable(plan, interval)

	if not tenant_doc.subscription:
		# Nothing to move. A workspace with no subscription buys one instead.
		return start_subscription(tenant, plan, interval)

	subscription = frappe.get_doc("Subscription", tenant_doc.subscription)
	if subscription.plan == plan and subscription.interval == interval:
		frappe.throw(_("This workspace is already on {0}.").format(plan_doc.plan_name))

	if subscription.status not in ("Active", "Trialing", "Past Due"):
		frappe.throw(
			_("This subscription is {0}. Start a new one instead of changing this.").format(
				subscription.status.lower()
			)
		)

	blocked = quotas.blockers(tenant_doc, {field: plan_doc.get(field) for field in quotas.TERMS})
	if blocked:
		frappe.throw(
			_("This workspace is over {0}'s {1} limit. Free some first.").format(
				plan_doc.plan_name, _(" and ").join(blocked)
			)
		)

	if not subscription.stripe_subscription_id:
		frappe.throw(_("This subscription is not linked to Stripe yet."))

	remote = stripe_client.get_subscription(subscription.stripe_subscription_id)
	items = (remote.get("items") or {}).get("data") or []
	# Found rather than counted to: a subscription carries the plan *and* any
	# add-ons the workspace holds, on purpose, so that they arrive on one
	# invoice. `plan_item` resolves each line's price against the plan catalogue
	# and refuses only the case that is genuinely ambiguous — two plan lines.
	current = plan_catalogue.plan_item(items)
	if not current:
		# A subscription we did not sell, or one whose price predates the
		# catalogue. Repricing a line we cannot name is how the wrong thing
		# moves.
		frappe.throw(_("This subscription is not on a plan we recognise; sort it out in Stripe."))

	stripe_client.update_subscription(
		subscription.stripe_subscription_id,
		items=[{"id": current["id"], "price": price_id}],
		proration_behavior="create_prorations",
		# Kept in step so a later webhook, which reads metadata when it has to
		# create a record, does not resurrect the old plan.
		metadata={"tenant": tenant, "plan": plan},
		_idempotency_key=f"change-plan:{subscription.name}:{plan}:{interval}",
	)

	# Applied here as well as in the webhook. The webhook is the durable path,
	# but it may be seconds away or, on a control plane whose Stripe webhook is
	# not configured yet, never — and a customer who just paid for more storage
	# should not have to wait to be given it. Both routes are idempotent.
	apply_plan(subscription, plan, interval)

	return {"plan": plan, "interval": interval}


def apply_plan(subscription, plan: str, interval: str | None = None) -> None:
	"""Record a plan change and put its terms into force.

	Idempotent: the same change arriving twice, from the API call and again from
	the webhook, does the work once.
	"""
	from oneapp_control.provisioning import runner

	unchanged = subscription.plan == plan and (
		interval is None or subscription.interval == interval
	)
	if unchanged and subscription.terms_captured_on:
		return

	before = quotas.for_tenant(subscription.tenant)

	subscription.db_set("plan", plan)
	if interval:
		subscription.db_set("interval", interval)
	frappe.db.set_value("Tenant", subscription.tenant, "plan", plan)

	after = quotas.capture(subscription, plan)

	# The site's own plan on Frappe Cloud is part of what was bought — CPU and
	# memory, not just our quotas — so a change that moves it has to reach press
	# as well. Enqueued rather than called: press is slow and may be down, and
	# neither is a reason to fail a paid plan change.
	press_plan = after.get("press_site_plan")
	if press_plan and press_plan != before.get("press_site_plan"):
		runner.enqueue(
			subscription.tenant,
			"Change Plan",
			{"press_site_plan": press_plan},
			idempotency_key=f"change-plan:{subscription.tenant}:{plan}:{press_plan}",
		)


def start_signup(request) -> dict:
	"""Checkout for a signup, before any tenant exists.

	The Account Request id rides along in metadata so the webhook can find its
	way back — at this point there is no tenant to key on.
	"""
	plan, price_id = _sellable(request.plan, request.interval)

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
		subscription.stripe_customer_id, portal.account_url(tenant, "billing")
	)
	return {"url": session.get("url")}
