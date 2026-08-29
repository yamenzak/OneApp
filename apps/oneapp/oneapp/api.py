"""Endpoints the SPA calls.

Same-origin, so the ordinary Frappe session cookie authenticates every request —
no tokens, no CORS, no refresh dance.
"""

import frappe
from frappe import _

from oneapp.oneapp_core import sync


@frappe.whitelist()
def session():
	"""Everything the shell needs on boot, in one round trip."""
	state = sync.state()
	user = frappe.session.user

	return {
		"user": {
			"name": user,
			"full_name": frappe.utils.get_fullname(user),
			"roles": frappe.get_roles(user),
			"is_admin": "System Manager" in frappe.get_roles(user),
		},
		"tenant": {
			"name": state.get("tenant"),
			"status": state.get("status"),
			"plan": state.get("plan_code"),
		},
		"apps": visible_apps(),
		"quota": {
			"storage_used_bytes": state.get("storage_used_bytes") or 0,
			"storage_quota_bytes": state.get("storage_quota_bytes") or 0,
			"max_users": state.get("max_users") or 0,
		},
		"credits": {"balance": state.get("credit_balance") or 0},
	}


@frappe.whitelist()
def visible_apps():
	"""Apps this user can actually open.

	Two filters, and both matter. The tenant's entitlements decide what the
	*site* has; the user's roles decide what *they* may open. An entitled app the
	user lacks the role for is correctly absent.
	"""
	state = sync.state()
	roles = set(frappe.get_roles())

	return [
		app
		for app in state.get("apps", [])
		if not app.get("role_name") or app["role_name"] in roles
	]


@frappe.whitelist()
def refresh():
	"""Force a control-plane sync. Used after a plan change or app purchase."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return sync.sync_from_control_plane()
