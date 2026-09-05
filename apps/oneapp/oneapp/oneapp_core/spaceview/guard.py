"""The one check every record-scoped endpoint makes first."""

import frappe
from frappe import _
from .resolve import _resolve
from .records import record


def _reachable(space_code: str, screen: str, name: str) -> str:
	"""The doctype, if this reader may reach this record through this screen."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There are no records on this screen."))
	if not record(space_code, screen, name):
		frappe.throw(_("That record is not on this screen."), frappe.PermissionError)
	return doctype
