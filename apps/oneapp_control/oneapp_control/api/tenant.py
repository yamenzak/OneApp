"""Endpoints tenant sites call on the control plane.

Every request is HMAC-signed with the tenant's own secret. There is no session
and no user — the signature *is* the authentication, and it also proves which
tenant is calling, so a tenant cannot read another tenant's state by asking
nicely.
"""

import json

import frappe
from frappe import _

from oneapp_control.credits import ledger
from oneapp_control.entitlements import registry
from oneapp_control.utils.signing import TENANT_HEADER, verify


def _authenticate() -> str:
	"""Verify the signature and return the calling tenant's name."""
	tenant = frappe.request.headers.get(TENANT_HEADER)
	if not tenant:
		frappe.throw(_("Missing tenant header."), frappe.PermissionError)

	if not frappe.db.exists("Tenant", tenant):
		# Deliberately the same error as a bad signature — do not confirm which
		# tenant slugs exist to an unauthenticated caller.
		frappe.throw(_("Invalid or expired signature."), frappe.PermissionError)

	secret = frappe.get_doc("Tenant", tenant).signing_secret()
	body = frappe.request.get_data(as_text=True) or ""

	if not verify(
		secret,
		body,
		frappe.request.headers.get("X-OneApp-Signature"),
		frappe.request.headers.get("X-OneApp-Timestamp"),
	):
		frappe.throw(_("Invalid or expired signature."), frappe.PermissionError)

	return tenant


def _body() -> dict:
	raw = frappe.request.get_data(as_text=True) or "{}"
	try:
		return json.loads(raw) or {}
	except json.JSONDecodeError:
		return {}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def sync():
	"""Everything a tenant site needs to render itself and enforce limits.

	Called on a schedule and on demand. The tenant site caches this; the control
	plane stays authoritative.
	"""
	tenant_name = _authenticate()
	tenant = frappe.get_doc("Tenant", tenant_name)

	return {
		"tenant": {
			"slug": tenant.tenant_slug,
			"name": tenant.tenant_name,
			"status": tenant.status,
			"site_name": tenant.site_name,
			"primary_domain": tenant.primary_domain,
		},
		"plan": {
			"code": tenant.plan,
			"storage_quota_bytes": tenant.storage_quota_bytes,
			"database_quota_bytes": tenant.database_quota_bytes,
			"max_users": tenant.max_users,
			"background_workers": tenant.background_workers,
		},
		"apps": registry.apps_for_tenant(tenant_name),
		"modules": registry.entitled_modules(tenant_name),
		"roles": registry.entitled_roles(tenant_name),
		# One row per (role, doctype). The tenant site writes DocPerms from this
		# because our roles are ours: we use ERPNext for its logic, not for its
		# idea of who an "Accounts Manager" is, so they start with no
		# permissions at all. See DECISIONS §8.
		"permissions": registry.permission_manifest(tenant_name),
		"owner_role": registry.OWNER_ROLE,
		"member_role": registry.MEMBER_ROLE,
		# Who the workspace belongs to. The tenant site creates this account on
		# first sync — nothing else can, since the control plane has no way to
		# write into a tenant's database, and until it exists the customer has
		# a workspace they cannot sign in to.
		"owner": {
			"email": tenant.owner_email,
			"first_name": (tenant.tenant_name or "").split(" ")[0] or "Owner",
		},
		# Everyone else who may sign in. Sent whole rather than as a diff: the
		# tenant site reconciles against it, so a member removed here is
		# disabled there without anything having to remember to send a removal.
		"members": [
			{
				"email": row.email,
				"full_name": row.full_name or "",
				"access": row.access,
			}
			for row in (tenant.members or [])
		],
		"credits": {
			"balance": ledger.balance(tenant_name),
			"available": ledger.available(tenant_name),
		},
		# What signup already answered, so the tenant site can set its books up
		# without asking again. Sent rather than assumed there: the country came
		# from the region they chose and the currency from the plan they bought,
		# and neither is knowable from inside the site.
		"books": _books_hint(tenant),
	}


def _books_hint(tenant) -> dict:
	"""Country, currency and company name for the accounting setup.

	The tenant site decides whether to act on it — it is the only side that can
	see whether ERPNext is installed or a company already exists.
	"""
	country = (
		frappe.db.get_value("Region", tenant.region, "country") if tenant.region else None
	)
	currency = frappe.db.get_value("Plan", tenant.plan, "currency") if tenant.plan else None

	return {
		"company_name": tenant.tenant_name,
		"country": country,
		"currency": currency,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def report_usage():
	"""Tenant site reports its own storage and seat consumption."""
	tenant_name = _authenticate()
	data = _body()

	updates = {"usage_synced_on": frappe.utils.now_datetime()}
	if "storage_used_bytes" in data:
		updates["storage_used_bytes"] = float(data["storage_used_bytes"] or 0)
	if "user_count" in data:
		updates["user_count"] = int(data["user_count"] or 0)
	if "database_used_bytes" in data:
		updates["database_used_bytes"] = float(data["database_used_bytes"] or 0)

	frappe.db.set_value("Tenant", tenant_name, updates)

	tenant = frappe.get_doc("Tenant", tenant_name)

	# Warn once per threshold crossing rather than on every report, which is
	# hourly and would be noise.
	_maybe_warn(tenant)

	return {
		"storage_used_bytes": tenant.storage_used_bytes,
		"storage_quota_bytes": tenant.storage_quota_bytes,
		"fraction_used": round(tenant.storage_fraction_used(), 4),
		"database_used_bytes": tenant.database_used_bytes,
		"database_quota_bytes": tenant.database_quota_bytes,
		"user_count": tenant.user_count,
		"max_users": tenant.max_users,
	}


def _maybe_warn(tenant):
	"""Email once as each resource crosses the warning threshold.

	The flag resets when usage drops back below, so freeing space and filling up
	again warns again — but steady-state usage does not mail every hour.
	"""
	from oneapp_control.control_plane.doctype.tenant.tenant import WARN_FRACTION
	from oneapp_control.notifications import emails

	for resource, fraction in (
		("storage", tenant.storage_fraction_used()),
		("database", tenant.database_fraction_used()),
	):
		key = f"oneapp_warned:{tenant.name}:{resource}"
		warned = frappe.cache().get_value(key)

		if fraction >= WARN_FRACTION and not warned:
			emails.quota_warning(tenant.name, resource, fraction)
			frappe.cache().set_value(key, 1, expires_in_sec=7 * 24 * 3600)
		elif fraction < WARN_FRACTION and warned:
			frappe.cache().delete_value(key)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reserve_credits():
	"""Hold credits before an expensive operation."""
	tenant_name = _authenticate()
	data = _body()

	credits = float(data.get("credits") or 0)
	purpose = data.get("purpose") or "unspecified"

	try:
		reservation = ledger.reserve(tenant_name, credits, purpose)
	except ledger.InsufficientCredits:
		return {
			"ok": False,
			"reason": "insufficient_credits",
			"available": ledger.available(tenant_name),
		}

	return {
		"ok": True,
		"reservation": reservation.name,
		"expires_at": str(reservation.expires_at),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def commit_credits():
	"""Settle a reservation against what was actually used."""
	tenant_name = _authenticate()
	data = _body()

	reservation = frappe.get_doc("Credit Reservation", data["reservation"])
	if reservation.tenant != tenant_name:
		frappe.throw(_("Reservation does not belong to this tenant."), frappe.PermissionError)

	if data.get("release"):
		reservation.release(data.get("reason") or "released by tenant")
	else:
		reservation.commit_usage(float(data.get("credits") or 0), data.get("remarks"))

	return {
		"ok": True,
		"status": reservation.status,
		"committed": reservation.credits_committed,
		"balance": ledger.balance(tenant_name),
	}
