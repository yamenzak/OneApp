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

from oneapp_control import portal
from oneapp_control.billing import checkout, stripe_client
from oneapp_control.credits import ledger
from oneapp_control.entitlements import registry


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

	session = stripe_client.create_billing_portal_session(
		customer_id, portal.account_url(tenant.name, "billing")
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


# --------------------------------------------------------------------------- #
# People
#
# The control plane cannot write into a tenant's database — the signed sync is
# the only channel and it runs one way — so an invite is a row here and the
# tenant site reconciles its own Users against it. That is the same route the
# owner account already takes, and it means an invite is live on the next sync
# rather than immediately. `members()` says so rather than pretending otherwise.
# --------------------------------------------------------------------------- #

ACCESS_LEVELS = ("Member", "Admin")


def _seats(tenant) -> dict:
	"""Seats used and allowed. The owner holds one; members hold the rest.

	Counted from this list rather than from `Tenant.user_count`, which is what
	the workspace's site last reported. The two agree once a sync has run, and
	before that this one is right: an invite made a minute ago is a seat that is
	taken, and enforcing against the older number would let a plan be
	over-subscribed in the window between inviting and syncing.
	"""
	used = 1 + len(tenant.members or [])
	quota = tenant.max_users or 0
	return {"used": used, "quota": quota, "remaining": max(quota - used, 0) if quota else None}


@frappe.whitelist(methods=["GET"])
def members(workspace: str) -> dict:
	"""Everyone who can sign in to the workspace, the owner first."""
	tenant = require_workspace(workspace)

	people = [
		{
			"email": tenant.owner_email,
			"full_name": tenant.tenant_name,
			"access": "Owner",
			"is_owner": True,
			"invited_on": tenant.creation,
		}
	]
	people += [
		{
			"email": row.email,
			"full_name": row.full_name or "",
			"access": row.access,
			"is_owner": False,
			"invited_on": row.invited_on,
		}
		for row in (tenant.members or [])
	]

	return {
		"members": people,
		"seats": _seats(tenant),
		"access_levels": list(ACCESS_LEVELS),
		# An invite becomes an account on the workspace's next sync, not now.
		# Saying so is the difference between "slow" and "broken".
		"last_synced": tenant.usage_synced_on,
	}


@frappe.whitelist(methods=["POST"])
def invite_member(workspace: str, email: str, full_name: str = "", access: str = "Member") -> dict:
	"""Add someone to the workspace, within the plan's seat count."""
	tenant = require_workspace(workspace)

	email = (email or "").strip().lower()
	if not email:
		frappe.throw(_("An email address is required."))
	frappe.utils.validate_email_address(email, throw=True)

	if access not in ACCESS_LEVELS:
		frappe.throw(_("Unknown access level {0}.").format(access))

	if email == (tenant.owner_email or "").strip().lower():
		frappe.throw(_("{0} owns this workspace already.").format(email))

	if any((row.email or "").strip().lower() == email for row in tenant.members or []):
		frappe.throw(_("{0} is already a member.").format(email))

	seats = _seats(tenant)
	if seats["quota"] and seats["used"] >= seats["quota"]:
		# Refused here rather than at the tenant site, where the person would
		# already have had a welcome email for an account that cannot exist.
		frappe.throw(
			_("This plan includes {0} seats and all are in use. Change plan to add more.").format(
				seats["quota"]
			)
		)

	tenant.append(
		"members",
		{
			"email": email,
			"full_name": (full_name or "").strip(),
			"access": access,
			"invited_on": frappe.utils.now_datetime(),
		},
	)
	tenant.save(ignore_permissions=True)
	frappe.db.commit()

	return members(workspace)


@frappe.whitelist(methods=["POST"])
def remove_member(workspace: str, email: str) -> dict:
	"""Take someone out of the workspace.

	The row goes; the tenant site disables that User on its next sync rather
	than deleting it, because the documents they created are the workspace's and
	Frappe hangs ownership off the account.
	"""
	tenant = require_workspace(workspace)
	email = (email or "").strip().lower()

	if email == (tenant.owner_email or "").strip().lower():
		frappe.throw(_("The owner cannot be removed from their own workspace."))

	remaining = [row for row in (tenant.members or []) if (row.email or "").strip().lower() != email]
	if len(remaining) == len(tenant.members or []):
		frappe.throw(_("{0} is not a member of this workspace.").format(email))

	tenant.members = []
	for row in remaining:
		tenant.append(
			"members",
			{
				"email": row.email,
				"full_name": row.full_name,
				"access": row.access,
				"invited_on": row.invited_on,
			},
		)
	tenant.save(ignore_permissions=True)
	frappe.db.commit()

	return members(workspace)


# --------------------------------------------------------------------------- #
# What the workspace has, and what changing plan would give it
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def apps(workspace: str) -> dict:
	"""The apps this workspace can open.

	The same manifest the launcher renders, so a customer looking at their
	account sees exactly what they see when they sign in. `included` separates
	what every plan carries from what was granted to them specifically —
	otherwise "why do we have this?" has no answer on this page.
	"""
	tenant = require_workspace(workspace)

	granted = set(
		frappe.get_all(
			"App Entitlement",
			filters={"tenant": tenant.name, "enabled": 1},
			pluck="app",
		)
	)

	return {
		"apps": [
			{
				"code": app["app_code"],
				"label": app["app_label"],
				"icon": app.get("icon"),
				"included": app["app_code"] not in granted,
			}
			for app in registry.apps_for_tenant(tenant.name)
		],
		"workspace_url": f"https://{tenant.primary_domain or tenant.site_name}"
		if (tenant.primary_domain or tenant.site_name)
		else None,
	}


@frappe.whitelist(methods=["GET"])
def plans(workspace: str) -> dict:
	"""What this workspace is on, and what else it could be on.

	Every plan carries every feature — they differ only in quotas, which is why
	no feature flags exist anywhere in this codebase (DECISIONS §3). So the
	comparison is the numbers, and a plan that would not fit what the workspace
	already uses is marked rather than merely listed: finding out a downgrade is
	impossible *after* choosing it is the worst version of this page.
	"""
	tenant = require_workspace(workspace)
	usage = usage_for(tenant)

	fields = [
		"name", "plan_name", "audience", "currency",
		"price_monthly", "price_yearly",
		"storage_gb", "database_gb", "max_users", "monthly_credit_grant",
		"description",
	]

	# Two queries rather than one with `or_filters`: Frappe ANDs or_filters onto
	# filters rather than ORing the whole clause, so `is_active=1` plus
	# `name=<current>` resolved to just the current plan and the page offered
	# nothing to move to.
	rows = frappe.get_all(
		"Plan", filters={"is_active": 1}, fields=fields, order_by="sort_order asc"
	)

	# A workspace on a plan that has since been retired still has to see what it
	# is on — a page that cannot tell you that is worse than one showing a plan
	# nobody else can buy.
	if tenant.plan and not any(row.name == tenant.plan for row in rows):
		retired = frappe.get_all("Plan", filters={"name": tenant.plan}, fields=fields)
		rows = retired + rows

	GB = 1024**3
	available = []
	for row in rows:
		storage_cap = (row.storage_gb or 0) * GB
		database_cap = (row.database_gb or 0) * GB
		too_small = [
			label
			for label, used, cap in (
				("storage", usage["storage"]["used"], storage_cap),
				("database", usage["database"]["used"], database_cap),
				("seats", 1 + len(tenant.members or []), row.max_users or 0),
			)
			if cap and used > cap
		]
		available.append(
			{
				"code": row.name,
				"name": row.plan_name,
				"price_monthly": row.price_monthly,
				"price_yearly": row.price_yearly,
				"storage_gb": row.storage_gb,
				"database_gb": row.database_gb,
				"max_users": row.max_users,
				"monthly_credit_grant": row.monthly_credit_grant,
				"currency": row.currency,
				"audience": row.audience,
				"description": row.description,
				"current": row.name == tenant.plan,
				# Named, not just refused: "storage" tells them what to clear.
				"blocked_by": too_small,
			}
		)

	return {"current": tenant.plan, "plans": available, "usage": usage}
