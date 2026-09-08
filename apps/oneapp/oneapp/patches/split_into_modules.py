"""OneSpace became eight Frappe modules, and the doctypes on a site did not.

A doctype's `module` is a column, not a fact the JSON re-asserts in time: Frappe
resolves a controller as `<app>.<scrubbed module>.doctype.<slug>`, and it does
that while loading the very doctypes the model sync is about to update. So a
site installed before the split looks for `oneapp.oneapp_core`, which is not a
package any more, and every page that touches one of those doctypes is a 500 —
including `bench migrate` itself, which is why this runs `pre_model_sync`.

The mapping is read back off the shipped JSON rather than restated here. There
is exactly one answer to "which module is this doctype in" and it is the file
the generator writes; a second copy of it in a patch is a second thing to keep
in step, and it would be wrong the first time a doctype moved between modules.
"""

import json
import os

import frappe

OLD = "OneApp Core"


def _shipped() -> dict:
	"""`{doctype name: module}` for every doctype this app ships."""
	root = frappe.get_app_path("oneapp")
	out = {}
	for module in os.listdir(root):
		folder = os.path.join(root, module, "doctype")
		if not os.path.isdir(folder):
			continue
		for slug in os.listdir(folder):
			path = os.path.join(folder, slug, f"{slug}.json")
			if not os.path.exists(path):
				continue
			with open(path) as fh:
				doc = json.load(fh)
			if doc.get("name") and doc.get("module"):
				out[doc["name"]] = doc["module"]
	return out


def execute():
	if not frappe.db.exists("Module Def", OLD):
		return

	shipped = _shipped()

	# Every module the app now has, so a doctype can be pointed at one. Frappe
	# creates these during the sync, which is after the crash this avoids.
	for module in sorted(set(shipped.values())):
		if not frappe.db.exists("Module Def", module):
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": module, "app_name": "oneapp"}
			).insert(ignore_permissions=True)

	for name in frappe.get_all("DocType", filters={"module": OLD}, pluck="name"):
		module = shipped.get(name)
		if module:
			frappe.db.set_value("DocType", name, "module", module, update_modified=False)

	# Anything left pointing at it is a doctype this app no longer ships; the
	# sync deletes those, and a Module Def with children cannot be removed. So
	# the old one goes only once nothing names it.
	if not frappe.db.exists("DocType", {"module": OLD}):
		frappe.delete_doc("Module Def", OLD, force=True, ignore_permissions=True)

	frappe.db.commit()

	# The module list itself is cached, and nothing else invalidates it: Frappe
	# builds `app_modules` from `modules.txt` once and keeps it, so a bench that
	# has read the old list goes on resolving `oneapp.oneapp_core` from memory
	# however correct the database now is — a 500 on every page that survives a
	# restart, because the cache does too. Cleared by name rather than by
	# `clear_cache` alone, which does not reach these.
	frappe.cache.delete_value("app_modules")
	frappe.client_cache.delete_value("installed_app_modules")
	frappe.clear_cache()
	frappe.setup_module_map(include_all_apps=False)
