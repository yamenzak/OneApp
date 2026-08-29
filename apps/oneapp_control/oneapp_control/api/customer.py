"""Customer self-service.

Every endpoint here resolves the tenant from the logged-in user and never from a
parameter. That single rule is what keeps one customer out of another's billing:
there is no argument a caller can supply that changes which workspace they act
on, so there is nothing to get wrong at a call site.

Customers hold the OneApp Customer role, which has no desk access. They reach
these through the portal only.
"""

import frappe
from frappe import _

from oneapp_control.billing import checkout, stripe_client
from oneapp_control.credits import ledger


def my_tenant():
	"""The workspace owned by the current user.

	Deliberately not parameterised. Raises rather than returning None so no
	caller can proceed on an empty result by mistake.
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in."), frappe.PermissionError)

	name = frappe.db.get_value("Tenant", {"owner_user": user}, "name")
	if not name:
		frappe.throw(_("No workspace is associated with this account."), frappe.PermissionError)

	return frappe.get_doc("Tenant", name)


@frappe.whitelist()
def overview() -> dict:
	"""Everything the account portal shows, in one call."""
	tenant = my_tenant()
	plan = frappe.get_doc("Plan", tenant.plan) if tenant.plan else None

	subscription = None
	if tenant.subscription:
		sub = frappe.get_doc("Subscription", tenant.subscription)
		subscription = {
			"status": sub.status,
			"interval": sub.interval,
			"current_period_end": str(sub.current_period_end) if sub.current_period_end else None,
			"cancel_at_period_end": bool(sub.cancel_at_period_end),
		}

	quota = tenant.storage_quota_bytes
	return {
		"workspace": {
			"name": tenant.tenant_name,
			"slug": tenant.tenant_slug,
			"status": tenant.status,
			"url": f"https://{tenant.site_name}" if tenant.site_name else None,
			"custom_domain": tenant.primary_domain,
		},
		"plan": {
			"code": tenant.plan,
			"name": plan.plan_name if plan else None,
			"price_monthly": plan.price_monthly if plan else None,
			"storage_gb": plan.storage_gb if plan else None,
			"max_users": plan.max_users if plan else None,
		},
		"subscription": subscription,
		"usage": {
			"storage_used_bytes": tenant.storage_used_bytes or 0,
			"storage_quota_bytes": quota,
			"storage_fraction": round(tenant.storage_fraction_used(), 4),
			"user_count": tenant.user_count or 0,
			"max_users": tenant.max_users,
		},
		"credits": {
			"balance": ledger.balance(tenant.name),
			"available": ledger.available(tenant.name),
		},
	}


@frappe.whitelist()
def credit_history(limit: int = 50) -> list[dict]:
	"""The tenant's own ledger. Scoped by my_tenant, so the filter cannot be
	widened by a caller."""
	tenant = my_tenant()
	return frappe.get_all(
		"Credit Ledger Entry",
		filters={"tenant": tenant.name},
		fields=["creation", "entry_type", "credits", "expires_on", "remarks"],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist()
def invoices(limit: int = 24) -> list[dict]:
	tenant = my_tenant()
	if not tenant.customer:
		return []

	return frappe.get_all(
		"Sales Invoice",
		filters={"customer": tenant.customer, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", "currency", "status"],
		order_by="posting_date desc",
		limit=min(int(limit), 100),
	)


@frappe.whitelist()
def buy_credits(credits: float, amount: float, currency: str = "usd") -> dict:
	"""Checkout for a credit pack.

	Price comes from the server's own pack table, never from the request — a
	caller supplying both size and price could otherwise buy a million credits
	for a penny.
	"""
	tenant = my_tenant()
	pack = find_pack(float(credits))
	if not pack:
		frappe.throw(_("Unknown credit pack."))

	return checkout.start_credit_pack(
		tenant.name, credits=pack["credits"], amount=pack["amount"], currency=pack["currency"]
	)


# Packs are server-side so the amount charged is never client-supplied.
CREDIT_PACKS = [
	{"credits": 1000, "amount": 10.0, "currency": "usd"},
	{"credits": 5500, "amount": 50.0, "currency": "usd"},
	{"credits": 12000, "amount": 100.0, "currency": "usd"},
]


@frappe.whitelist()
def credit_packs() -> list[dict]:
	return CREDIT_PACKS


def find_pack(credits: float):
	return next((p for p in CREDIT_PACKS if p["credits"] == credits), None)


@frappe.whitelist()
def billing_portal() -> dict:
	"""Hand the customer to Stripe for card and cancellation management.

	Stripe owns dunning, SCA and card updates; reproducing any of that here would
	be worse in every respect.
	"""
	tenant = my_tenant()
	if not tenant.subscription:
		frappe.throw(_("No subscription to manage yet."))

	customer_id = frappe.db.get_value("Subscription", tenant.subscription, "stripe_customer_id")
	if not customer_id:
		frappe.throw(_("No Stripe customer on this subscription."))

	base = (frappe.db.get_single_value("OneApp Control Settings", "control_plane_url") or "").rstrip("/")
	session = stripe_client.create_billing_portal_session(customer_id, f"{base}/account")
	return {"url": session.get("url")}


@frappe.whitelist()
def request_custom_domain(domain: str) -> str:
	"""Attach a domain the customer owns.

	Queued rather than applied: press validates DNS synchronously and the
	customer almost certainly has not pointed the CNAME yet.
	"""
	from oneapp_control.provisioning import runner

	tenant = my_tenant()
	domain = (domain or "").strip().lower()

	if not domain or "." not in domain or domain.endswith(".4dl.app"):
		frappe.throw(_("Enter a domain you own, such as app.example.com."))

	return runner.enqueue(
		tenant.name, "Add Domain", {"domain": domain}, idempotency_key=f"domain:{tenant.name}:{domain}"
	).name
