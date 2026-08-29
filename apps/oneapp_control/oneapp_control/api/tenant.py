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
			"max_users": tenant.max_users,
		},
		"apps": registry.apps_for_tenant(tenant_name),
		"modules": registry.entitled_modules(tenant_name),
		"credits": {
			"balance": ledger.balance(tenant_name),
			"available": ledger.available(tenant_name),
		},
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

	frappe.db.set_value("Tenant", tenant_name, updates)

	tenant = frappe.get_doc("Tenant", tenant_name)
	return {
		"storage_used_bytes": tenant.storage_used_bytes,
		"storage_quota_bytes": tenant.storage_quota_bytes,
		"fraction_used": round(tenant.storage_fraction_used(), 4),
		"user_count": tenant.user_count,
		"max_users": tenant.max_users,
	}


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
