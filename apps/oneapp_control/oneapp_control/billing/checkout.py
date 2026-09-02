"""Starting a purchase.

Two shapes, deliberately different:

* **Credit packs** are one-off payments. Purchased credits roll over.
* **Subscriptions** use Stripe Checkout in subscription mode, so Stripe owns
  renewal, dunning, SCA and card updates. Plan grants are non-rollover.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from oneapp_control import portal
from oneapp_control.billing import addons as addon_catalogue
from oneapp_control.billing import packs as pack_catalogue
from oneapp_control.billing import promos
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
def start_credit_pack(tenant: str, pack: str, code: str | None = None) -> dict:
	"""Create a Checkout session for a one-off credit pack.

	The pack names itself and the catalogue supplies the price. Neither the size
	nor the amount comes from the caller: accepting both would let anyone buy a
	million credits for a penny, and accepting the size alone would still let
	them buy the expensive pack at the cheap one's price.

	A real Stripe Price rather than the inline `price_data` this used, so the
	receipt names a product that exists and a reprice archives the old id like
	everything else we sell.
	"""
	tenant_doc = frappe.get_doc("Tenant", tenant)
	pack_doc = pack_catalogue.sellable(pack)
	promo = promos.resolve(code, "credit_pack")
	success_url, cancel_url = _urls(tenant)

	session = stripe_client.create_checkout_session(
		mode="payment",
		line_items=[{"price": pack_doc.stripe_price_id, "quantity": 1}],
		success_url=success_url,
		cancel_url=cancel_url,
		customer_email=tenant_doc.owner_email,
		client_reference_id=tenant,
		payment_intent_data={
			"metadata": {"tenant": tenant, "credits": pack_doc.credits, "pack": pack}
		},
		metadata={
			"tenant": tenant,
			"credits": pack_doc.credits,
			"pack": pack,
			"kind": "credit_pack",
			**({"promo": promo.name} if promo else {}),
		},
		**({"discounts": promos.discounts_for(promo)} if promo else {}),
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
	promo = promos.resolve(request.get("promo_code"), "subscription")

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
			**({"promo": promo.name} if promo else {}),
		},
		# The code, applied rather than offered. A signup already knows which one
		# was typed and validated it server-side, so showing Stripe's own promo
		# field on top would be a second place to enter a second code.
		**({"discounts": promos.discounts_for(promo)} if promo else {}),
		# Nothing to collect when the whole thing is free. Without this Stripe
		# asks for a card it will never charge, which is the difference between a
		# demo instance somebody can spin up and one they give up on.
		**(
			{"payment_method_collection": "if_required"}
			if promos.is_total_discount(promo)
			else {}
		),
		# Stripe dedupes for 24h, so a double-submitted form cannot create two
		# subscriptions for the same request.
		_idempotency_key=f"signup:{request.name}",
	)

	return {"id": session.get("id"), "url": session.get("url")}


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


# --------------------------------------------------------------------------- #
# Add-ons
#
# Extra quota, bought per month against the subscription that is already there.
# Not a checkout: there is a card on file and a billing cycle running, so this is
# a change to the subscription and the money arrives on the next invoice, prorated
# from the moment it is bought.
#
# One entry point, because "buy", "add more" and "cancel" are the same operation
# at different quantities. Three endpoints would be three places to get the
# proration wrong.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def set_addon_quantity(tenant: str, addon: str, quantity: int,
                       code: str | None = None) -> dict:
	"""Hold `quantity` units of `addon` on this workspace's subscription.

	Zero releases it. Stripe prorates in both directions: buying mid-cycle is
	charged for the part of the month it covers, releasing is credited the same
	way, and both land on the next invoice rather than as a separate charge.
	"""
	quantity = int(quantity or 0)
	if quantity < 0:
		frappe.throw(_("A quantity below zero is not a quantity."))

	tenant_doc = frappe.get_doc("Tenant", tenant)
	subscription = _subscription_for(tenant_doc)
	addon_doc, price_id = addon_catalogue.sellable(addon, subscription.interval)

	if addon_doc.max_units and quantity > addon_doc.max_units:
		frappe.throw(
			_("{0} is sold up to {1} units.").format(addon_doc.addon_name, addon_doc.max_units)
		)

	held = _addon_row(subscription, addon)
	if held and int(held.quantity or 0) == quantity:
		return {"addon": addon, "quantity": quantity, "unchanged": True}

	# Releasing storage a workspace is sitting on would take the quota below what
	# it holds, which is the one thing overage policy says never to do — see
	# docs/ONEADMIN.md, Overage. Refused with the resource named, the same shape a plan change
	# refuses a plan that is too small.
	_refuse_shrinking_below_use(tenant_doc, subscription, addon_doc, quantity, held)

	# A code on an add-on discounts the *subscription*, because that is where the
	# line lives — Stripe has no notion of a discount on one item. So it is
	# applied only when the subscription is not already carrying one, rather than
	# silently replacing a discount the customer is already receiving.
	promo = promos.resolve(code, "addon") if code else None

	item = _apply_addon_item(subscription, addon_doc, price_id, quantity, held, promo)
	_capture_addon(subscription, addon_doc, price_id, quantity, item)

	return {"addon": addon, "quantity": quantity}


def _subscription_for(tenant_doc):
	"""The subscription an add-on hangs from, or a refusal saying why not."""
	if not tenant_doc.subscription:
		# An add-on with no subscription has nowhere to live and no invoice to
		# appear on. Selling one as a separate charge would mean a second billing
		# relationship for the same workspace.
		frappe.throw(_("This workspace has no subscription to add to. Choose a plan first."))

	subscription = frappe.get_doc("Subscription", tenant_doc.subscription)
	if subscription.status not in ("Active", "Trialing", "Past Due"):
		frappe.throw(
			_("This workspace's subscription is {0}.").format(subscription.status)
		)
	if not subscription.stripe_subscription_id:
		frappe.throw(_("This subscription is not linked to Stripe yet."))
	return subscription


def _addon_row(subscription, addon: str):
	for row in subscription.addons or []:
		if row.addon == addon:
			return row
	return None


def _refuse_shrinking_below_use(tenant_doc, subscription, addon_doc, quantity, held) -> None:
	"""Refuse a release that would put the workspace over its own quota."""
	if not held or quantity >= int(held.quantity or 0):
		return

	shed = (int(held.quantity or 0) - quantity) * int(held.unit_gb or 0)
	if not shed:
		return

	after = dict(quotas.for_tenant(tenant_doc))
	field = addon_catalogue.QUOTA_FIELD.get(addon_doc.kind)
	if not field:
		return
	after[field] = (after.get(field) or 0) - shed

	blocked = quotas.blockers(tenant_doc, after)
	if blocked:
		frappe.throw(
			_("Releasing this would put the workspace over its {0} limit. "
			  "Free some first.").format(" and ".join(blocked))
		)


def _apply_addon_item(subscription, addon_doc, price_id: str, quantity: int, held,
                      promo=None) -> dict:
	"""Add, change or remove the Stripe line, and return what it became."""
	key = f"addon:{subscription.name}:{addon_doc.name}:{quantity}"

	if held and held.stripe_subscription_item_id:
		item = {"id": held.stripe_subscription_item_id}
		# Stripe deletes a line rather than holding it at zero, and a zero-quantity
		# item would keep appearing on the invoice at nothing.
		item.update({"deleted": "true"} if quantity == 0 else {"quantity": quantity})
	elif quantity == 0:
		# Nothing held and nothing asked for.
		return {}
	else:
		item = {"price": price_id, "quantity": quantity}

	remote = stripe_client.update_subscription(
		subscription.stripe_subscription_id,
		items=[item],
		proration_behavior="create_prorations",
		**({"discounts": promos.discounts_for(promo)} if promo else {}),
		_idempotency_key=key,
	)
	return _item_for_price(remote, price_id)


def _item_for_price(remote: dict, price_id: str) -> dict:
	for item in (remote.get("items") or {}).get("data") or []:
		if ((item or {}).get("price") or {}).get("id") == price_id:
			return item
	return {}


def _capture_addon(subscription, addon_doc, price_id: str, quantity: int, item: dict) -> None:
	"""Write what the workspace now holds onto the subscription.

	Captured, like the plan's terms: the GB per unit and the rate are what was
	bought, so redefining the add-on later changes the next purchase and not this
	one.
	"""
	rows = [row for row in (subscription.addons or []) if row.addon != addon_doc.name]

	if quantity:
		rows.append(
			frappe._dict(
				addon=addon_doc.name,
				kind=addon_doc.kind,
				quantity=quantity,
				unit_gb=addon_doc.unit_gb,
				stripe_subscription_item_id=item.get("id"),
				stripe_price_id=price_id,
				unit_amount=addon_catalogue.amount_for(addon_doc, subscription.interval),
				currency=(addon_doc.currency or "USD").lower(),
				added_on=now_datetime(),
			)
		)

	subscription.set("addons", [])
	for row in rows:
		subscription.append("addons", row)
	subscription.save(ignore_permissions=True)
