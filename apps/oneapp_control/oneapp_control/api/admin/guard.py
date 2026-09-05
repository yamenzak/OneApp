"""The one check every operator endpoint makes first."""

import frappe
from frappe import _


def _require_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)
