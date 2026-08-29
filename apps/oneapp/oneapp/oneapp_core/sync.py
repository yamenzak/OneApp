"""Keep this site's view of its tenant fresh.

The control plane is authoritative; this site caches. The cache is a Single
doctype rather than only Redis, deliberately: if the control plane is
unreachable, a tenant should keep working with the last known entitlements
rather than have every app vanish from their launcher.
"""

import json

import frappe
from frappe.utils import now_datetime

from oneapp.oneapp_core import control_client

CACHE_KEY = "oneapp_site_state"
CACHE_TTL = 300


def state() -> dict:
	"""Cached tenant state. Falls back to the durable copy, then to empty."""
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return cached

	doc = frappe.get_single("OneApp Site State")
	data = {
		"tenant": doc.tenant,
		"status": doc.status,
		"plan_code": doc.plan_code,
		"storage_quota_bytes": doc.storage_quota_bytes or 0,
		"max_users": doc.max_users or 0,
		"credit_balance": doc.credit_balance or 0,
		"apps": json.loads(doc.apps_json or "[]"),
		"roles": json.loads(doc.roles_json or "[]"),
		"last_sync": str(doc.last_sync) if doc.last_sync else None,
	}
	frappe.cache().set_value(CACHE_KEY, data, expires_in_sec=CACHE_TTL)
	return data


def invalidate():
	frappe.cache().delete_value(CACHE_KEY)


def sync_from_control_plane() -> dict:
	"""Pull entitlements, quotas and balance. Scheduled, and callable on demand."""
	doc = frappe.get_single("OneApp Site State")

	if not control_client.is_provisioned():
		doc.db_set("last_sync_error", "Site is not provisioned (missing site_config keys).")
		return {"ok": False, "reason": "not_provisioned"}

	try:
		payload = control_client.sync()
	except control_client.ControlPlaneError as e:
		# Keep serving the last known good state rather than degrading the site.
		doc.db_set("last_sync_error", str(e)[:500])
		frappe.log_error(title="OneApp control-plane sync failed", message=str(e))
		return {"ok": False, "reason": "unreachable", "error": str(e)}

	tenant = payload.get("tenant") or {}
	plan = payload.get("plan") or {}
	credits = payload.get("credits") or {}

	doc.db_set(
		{
			"tenant": tenant.get("slug"),
			"site_name": tenant.get("site_name"),
			"status": tenant.get("status"),
			"plan_code": plan.get("code"),
			"storage_quota_bytes": plan.get("storage_quota_bytes") or 0,
			"max_users": plan.get("max_users") or 0,
			"credit_balance": credits.get("balance") or 0,
			"apps_json": json.dumps(payload.get("apps") or []),
			"roles_json": json.dumps(payload.get("roles") or []),
			"last_sync": now_datetime(),
			"last_sync_error": None,
		}
	)

	invalidate()
	sync_roles(payload.get("roles") or [])

	return {"ok": True, "apps": len(payload.get("apps") or [])}


def sync_roles(entitled_roles: list[str]):
	"""Reconcile Frappe Roles against entitlements.

	Enforcement is native permissions, so revoking an app is a role removal that
	applies everywhere — desk, REST, reports — not just the launcher.
	"""
	if not entitled_roles:
		return

	for role in entitled_roles:
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{"doctype": "Role", "role_name": role, "desk_access": 1}
			).insert(ignore_permissions=True)

	# Roles this app manages but the tenant is no longer entitled to.
	managed = set(all_managed_roles())
	revoked = managed - set(entitled_roles)

	for user in frappe.get_all(
		"User", filters={"enabled": 1, "user_type": "System User"}, pluck="name"
	):
		if user in ("Administrator", "Guest"):
			continue
		_reconcile_user_roles(user, entitled_roles, revoked)


def _reconcile_user_roles(user: str, granted: list[str], revoked: set):
	existing = set(
		frappe.get_all("Has Role", filters={"parent": user}, pluck="role")
	)

	to_add = [r for r in granted if r not in existing]
	to_remove = [r for r in revoked if r in existing]

	if not (to_add or to_remove):
		return

	doc = frappe.get_doc("User", user)
	if to_remove:
		doc.set("roles", [r for r in doc.roles if r.role not in to_remove])
	for role in to_add:
		doc.append("roles", {"role": role})
	doc.save(ignore_permissions=True)


def all_managed_roles() -> list[str]:
	"""Roles this app is responsible for, from the last synced manifest.

	Only roles we know about are ever revoked — a role an operator created by
	hand is left alone.
	"""
	doc = frappe.get_single("OneApp Site State")
	try:
		apps = json.loads(doc.apps_json or "[]")
	except (json.JSONDecodeError, TypeError):
		return []
	return [a["role_name"] for a in apps if a.get("role_name")]


def report_usage_to_control_plane() -> dict:
	"""Push storage and seat counts upward."""
	if not control_client.is_provisioned():
		return {"ok": False, "reason": "not_provisioned"}

	storage = (
		frappe.db.sql("SELECT COALESCE(SUM(file_size), 0) FROM `tabFile`")[0][0] or 0
	)
	users = frappe.db.count(
		"User", {"enabled": 1, "user_type": "System User", "name": ("not in", ("Administrator", "Guest"))}
	)

	try:
		result = control_client.report_usage(int(storage), int(users))
	except control_client.ControlPlaneError as e:
		frappe.log_error(title="OneApp usage report failed", message=str(e))
		return {"ok": False, "error": str(e)}

	frappe.get_single("OneApp Site State").db_set("storage_used_bytes", storage)
	invalidate()
	return {"ok": True, **result}
