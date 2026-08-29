"""Customer self-service.

One account may own several workspaces — signing up for a company and later for
something at home is ordinary, and forcing a second email for it is friction
people remember. Each workspace carries its own plan, subscription and ledger.

That makes the isolation rule slightly weaker than "no parameter at all", so it
is concentrated in one function rather than repeated at every call site:

    every endpoint that touches a workspace calls require_workspace(),
    which verifies ownership before returning anything.

There is no path that trusts a name from the request. Tests read this module and
fail the build if an endpoint reaches a workspace any other way.
"""

import frappe
from frappe import _

from oneapp_control.billing import checkout, stripe_client
from oneapp_control.credits import ledger


def require_workspace(workspace: str):
	"""Resolve a workspace the caller owns, or refuse.

	The single ownership check in the customer surface. Raises rather than
	returning None so no caller can proceed on an empty result.
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in."), frappe.PermissionError)

	if not workspace:
		frappe.throw(_("No workspace specified."), frappe.PermissionError)

	owner = frappe.db.get_value("Tenant", workspace, "owner_user")

	# Same error whether the workspace belongs to someone else or does not
	# exist: a customer must not be able to probe for which names are taken.
	if owner != user:
		frappe.throw(_("Workspace not found."), frappe.PermissionError)

	return frappe.get_doc("Tenant", workspace)


@frappe.whitelist()
def my_workspaces() -> list[dict]:
	"""Every workspace this account owns. The switcher reads this."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in."), frappe.PermissionError)

	rows = frappe.get_all(
		"Tenant",
		filters={"owner_user": user},
		fields=["name", "tenant_name", "tenant_slug", "status", "plan", "site_name", "region"],
		order_by="creation asc",
	)
	for row in rows:
		row["url"] = f"https://{row['site_name']}" if row["site_name"] else None
	return rows


@frappe.whitelist()
def overview(workspace: str) -> dict:
	"""Everything the account page shows for one workspace, in one call."""
	tenant = require_workspace(workspace)
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

	return {
		"workspace": {
			"name": tenant.name,
			"title": tenant.tenant_name,
			"slug": tenant.tenant_slug,
			"status": tenant.status,
			"url": f"https://{tenant.site_name}" if tenant.site_name else None,
			"custom_domain": tenant.primary_domain,
			"region": tenant.region,
			"storage_jurisdiction": tenant.storage_jurisdiction,
		},
		"plan": {
			"code": tenant.plan,
			"name": plan.plan_name if plan else None,
			"audience": plan.audience if plan else None,
			"price_monthly": plan.price_monthly if plan else None,
		},
		"subscription": subscription,
		"usage": usage_for(tenant),
		"credits": {
			"balance": ledger.balance(tenant.name),
			"available": ledger.available(tenant.name),
		},
	}


def usage_for(tenant) -> dict:
	"""Usage against quota, with the warning threshold already applied.

	Computed server-side so both SPAs and any future surface agree on when a
	workspace is 'nearly full'.
	"""
	from oneapp_control.control_plane.doctype.tenant.tenant import WARN_FRACTION

	def bucket(used, quota):
		fraction = (used / quota) if quota else 0
		return {
			"used": used,
			"quota": quota,
			"fraction": round(fraction, 4),
			"warn": bool(quota) and fraction >= WARN_FRACTION,
			"exceeded": bool(quota) and used >= quota,
		}

	return {
		"storage": bucket(tenant.storage_used_bytes or 0, tenant.storage_quota_bytes),
		"database": bucket(tenant.database_used_bytes or 0, tenant.database_quota_bytes),
		"users": bucket(tenant.user_count or 0, tenant.max_users),
	}


@frappe.whitelist()
def credit_history(workspace: str, limit: int = 50) -> list[dict]:
	tenant = require_workspace(workspace)
	return frappe.get_all(
		"Credit Ledger Entry",
		filters={"tenant": tenant.name},
		fields=["creation", "entry_type", "credits", "expires_on", "remarks"],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist()
def invoices(workspace: str, limit: int = 24) -> list[dict]:
	tenant = require_workspace(workspace)
	if not tenant.customer:
		return []

	return frappe.get_all(
		"Sales Invoice",
		filters={"customer": tenant.customer, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", "currency", "status"],
		order_by="posting_date desc",
		limit=min(int(limit), 100),
	)


# Packs live server-side so the amount charged is never client-supplied —
# accepting both size and price would let anyone buy a million credits for a
# penny.
CREDIT_PACKS = [
	{"code": "credits-1k", "credits": 1000, "amount": 10.0, "currency": "usd"},
	{"code": "credits-5k", "credits": 5500, "amount": 50.0, "currency": "usd"},
	{"code": "credits-12k", "credits": 12000, "amount": 100.0, "currency": "usd"},
]

# Storage is bought outright rather than drawn from credits: a large upload
# silently draining the AI budget is a bill nobody can predict.
STORAGE_PACKS = [
	{"code": "storage-50", "gb": 50, "amount": 5.0, "currency": "usd"},
	{"code": "storage-250", "gb": 250, "amount": 20.0, "currency": "usd"},
	{"code": "storage-1000", "gb": 1000, "amount": 70.0, "currency": "usd"},
]


@frappe.whitelist()
def packs() -> dict:
	return {"credits": CREDIT_PACKS, "storage": STORAGE_PACKS}


@frappe.whitelist()
def buy_credits(workspace: str, pack: str) -> dict:
	tenant = require_workspace(workspace)
	chosen = next((p for p in CREDIT_PACKS if p["code"] == pack), None)
	if not chosen:
		frappe.throw(_("Unknown credit pack."))

	return checkout.start_credit_pack(
		tenant.name,
		credits=chosen["credits"],
		amount=chosen["amount"],
		currency=chosen["currency"],
	)


@frappe.whitelist()
def buy_storage(workspace: str, pack: str) -> dict:
	tenant = require_workspace(workspace)
	chosen = next((p for p in STORAGE_PACKS if p["code"] == pack), None)
	if not chosen:
		frappe.throw(_("Unknown storage pack."))

	return checkout.start_storage_pack(
		tenant.name, gb=chosen["gb"], amount=chosen["amount"], currency=chosen["currency"]
	)


@frappe.whitelist()
def billing_portal(workspace: str) -> dict:
	"""Hand the customer to Stripe for card and cancellation management."""
	tenant = require_workspace(workspace)
	if not tenant.subscription:
		frappe.throw(_("No subscription to manage yet."))

	customer_id = frappe.db.get_value("Subscription", tenant.subscription, "stripe_customer_id")
	if not customer_id:
		frappe.throw(_("No Stripe customer on this subscription."))

	base = (
		frappe.db.get_single_value("OneApp Control Settings", "control_plane_url") or ""
	).rstrip("/")
	session = stripe_client.create_billing_portal_session(
		customer_id, f"{base}/account/{tenant.name}/billing"
	)
	return {"url": session.get("url")}


@frappe.whitelist()
def domain_instructions(workspace: str) -> dict:
	"""What the customer has to do in their own DNS, and how it is going.

	Written out rather than linked because the two ways this fails — a proxied
	record and an apex domain — are both invisible from our side and produce an
	error that points elsewhere.
	"""
	tenant = require_workspace(workspace)

	pending = frappe.get_all(
		"Provisioning Job",
		filters={
			"tenant": tenant.name,
			"action": "Add Domain",
			"state": ("in", ("Requested", "Running", "Awaiting Agent")),
		},
		fields=["name", "state", "last_error", "payload"],
		order_by="creation desc",
		limit=1,
	)

	return {
		"target": tenant.site_name,
		"current": tenant.primary_domain,
		"pending": pending[0] if pending else None,
		"steps": [
			{
				"title": "Add a CNAME in your DNS",
				"detail": f"Point your subdomain at {tenant.site_name}.",
			},
			{
				"title": "Turn the proxy off",
				"detail": (
					"On Cloudflare the record must be DNS-only — grey cloud. A "
					"proxied record resolves to Cloudflare instead of your site, "
					"and the certificate cannot be issued."
				),
			},
			{
				"title": "Use a subdomain",
				"detail": (
					"app.yourcompany.com works; yourcompany.com on its own cannot, "
					"because an apex domain cannot hold a CNAME."
				),
			},
			{
				"title": "Add it here",
				"detail": "We verify the record and issue a certificate. Usually a minute or two.",
			},
		],
	}


@frappe.whitelist()
def request_custom_domain(workspace: str, domain: str) -> str:
	tenant = require_workspace(workspace)
	domain = (domain or "").strip().lower().rstrip(".")

	if not domain or "." not in domain or " " in domain:
		frappe.throw(_("Enter a domain such as app.yourcompany.com."))
	if domain.endswith(".4dl.app"):
		frappe.throw(_("That is already your workspace address."))

	from oneapp_control.provisioning import runner

	return runner.enqueue(
		tenant.name,
		"Add Domain",
		{"domain": domain},
		idempotency_key=f"domain:{tenant.name}:{domain}",
	).name
