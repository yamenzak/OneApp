"""Which screens a space offers, edited from the console.

An app is configuration before it is code: a screen names a doctype and the
fields worth showing, and OneSpace renders it from the tenant site's own
metadata. So this is where an app gets built, and it has to be reachable
without the desk like everything else.
"""

import frappe
from frappe import _
from .guard import _require_manager


APP_VIEW_FIELDS = ("screen", "label", "icon", "document_type", "fields",
                   "component", "filters", "order_by")


@frappe.whitelist(methods=["GET"])
def app_views(app: str) -> list:
	"""Which screens a space offers, as the console edits them."""
	_require_manager()

	return frappe.get_all(
		"OneSpace Space Screen",
		filters={"parent": app, "parenttype": "OneSpace Space"},
		fields=["name", *APP_VIEW_FIELDS, "idx"],
		order_by="idx asc",
	)


@frappe.whitelist(methods=["POST"])
def set_app_views(app: str, screens: str | list) -> dict:
	"""Replace an app's screens with what was sent.

	Replaced rather than patched: the order of these is the order of the app's
	navigation, so a partial update would need a second way to express it.
	"""
	_require_manager()

	if isinstance(screens, str):
		screens = frappe.parse_json(screens)
	if not isinstance(screens, list):
		frappe.throw(_("Expected a list of screens."))

	slugs = [str(row.get("screen") or "").strip() for row in screens]
	if not all(slugs):
		frappe.throw(_("Every screen needs a slug — it is what a bookmark points at."))
	if len(set(slugs)) != len(slugs):
		frappe.throw(_("Two screens share a slug, so one of them is unreachable."))

	doc = frappe.get_doc("OneSpace Space", app)
	doc.set("screens", [
		{field: row.get(field) for field in APP_VIEW_FIELDS} for row in screens
	])
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True, "screens": len(screens)}
