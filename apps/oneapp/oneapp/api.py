"""Endpoints the SPA calls.

Same-origin, so the ordinary Frappe session cookie authenticates every request —
no tokens, no CORS, no refresh dance.
"""

import frappe
from frappe import _

from oneapp.oneapp_core import jobs, sync
from oneapp.oneapp_core.storage import quota


@frappe.whitelist()
def session():
	"""Everything the shell needs on boot, in one round trip."""
	from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

	state = sync.state()
	user = frappe.session.user
	roles = set(frappe.get_roles(user))

	return {
		"user": {
			"name": user,
			"full_name": frappe.utils.get_fullname(user),
			"roles": sorted(roles),
			# Two different questions, and the old single `is_admin` answered
			# the wrong one for the SPA: it keyed on System Manager, which the
			# workspace owner deliberately is not (DECISIONS §8). So the person
			# who actually administers the workspace read as not an admin, and
			# our own support read as one.
			"is_workspace_admin": bool(roles & {OWNER_ROLE, SUPPORT_ROLE}),
			"is_support": SUPPORT_ROLE in roles,
		},
		"tenant": {
			"name": state.get("tenant"),
			"status": state.get("status"),
			"plan": state.get("plan_code"),
		},
		"spaces": visible_spaces(),
		# Measured here rather than read from cached state, which holds the
		# allowance and not the consumption. Reading usage from there returned
		# zero every time, so the meter looked empty on a full site.
		"quota": {
			"storage": quota.usage_summary(),
			"database": quota.database_summary(),
			"jobs": jobs.summary(),
			"max_users": state.get("max_users") or 0,
		},
		"credits": {"balance": state.get("credit_balance") or 0},
		# How this site renders a number when the field does not say. Frappe
		# keeps both on System Settings and the desk reads them there; without
		# them a Float column renders with whatever `toLocaleString` defaults
		# to, which is not the same answer twice across two browsers.
		"formats": number_formats(),
	}


def number_formats() -> dict:
	settings = frappe.get_cached_doc("System Settings")
	return {
		"float_precision": int(settings.float_precision or 3),
		# Frappe leaves this unset to mean "follow the float precision", which
		# is a different thing from zero decimal places.
		"currency_precision": int(settings.currency_precision or 0)
		or int(settings.float_precision or 3),
	}


@frappe.whitelist()
def visible_spaces():
	"""Spaces this user can actually open.

	Two filters, and both matter. The tenant's entitlements decide what the
	*site* has; the user's roles decide what *they* may open. An entitled space
	the user lacks the role for is correctly absent.

	Shares its answer with `_space`, which resolves a space code for every
	whitelisted read. They used to disagree — the rail asked about roles and
	the resolver did not — so a space absent from somebody's rail still
	answered when its code was asked for by name.
	"""
	from oneapp.oneapp_core.spaceview import visible

	return visible(sync.state().get("spaces", []))


@frappe.whitelist()
def refresh():
	"""Force a control-plane sync. Used after a plan change or app purchase."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return sync.sync_from_control_plane()
