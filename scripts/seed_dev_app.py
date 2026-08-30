"""A manifest-only app on the local sites, so the generic screen has something
to render.

Points at Frappe's own ToDo rather than inventing a product: the field list is
chosen for coverage — a Text Editor, two Selects (badge colours), a Link (the
picker), a Date, and a Color, which has no frappe-ui counterpart and so must be
shown without ever being offered.

Run it against both sites: the manifest lives on the control plane, and the
tenant caches it.

    scripts/dev.sh run scripts/seed_dev_app.py
    ONEAPP_SITE=space.localhost ONEAPP_PORT=8001 \\
      scripts/dev.sh run scripts/seed_dev_app.py

Nothing here runs on Frappe Cloud, and nothing here is a fixture the apps ship.
"""

import json

import frappe

CODE = "zztasks"
ROLE = "OneApp Tasks"
FIELDS = "description,status,priority,allocated_to,date,color"

VIEWS = [
	{
		"view": "open", "label": "Open", "icon": "lucide-clock",
		"document_type": "ToDo", "fields": FIELDS,
		"filters": json.dumps({"status": "Open"}), "order_by": "modified desc",
	},
	{
		"view": "all", "label": "Everything", "icon": "lucide-layout-grid",
		"document_type": "ToDo", "fields": FIELDS, "order_by": "modified desc",
	},
	# Enough rows to page. Everything else on this fixture is two or three
	# records, which is right for reading a screen and useless for testing what
	# happens at the end of a page — Load More, the count, the windowing
	# threshold. Filtered to Closed so it does not disturb the Open screen.
	{
		"view": "backlog", "label": "Backlog", "icon": "lucide-package",
		"document_type": "ToDo", "fields": FIELDS,
		"filters": json.dumps({"status": "Closed"}), "order_by": "creation asc",
	},
]

TODOS = [
	{"description": "Book the van for Thursday", "priority": "Medium", "status": "Open",
	 "allocated_to": "Administrator", "color": "#2490EF"},
	{"description": "Chase the Halloway invoice", "priority": "High", "status": "Open"},
	{"description": "File Q3 returns", "priority": "Low", "status": "Closed"},
]

# The paging fixture. Deliberately more than one page at the smallest size the
# footer offers, so "load more" has something to load.
BACKLOG = 40
BACKLOG_PREFIX = "Backlog item"


def seed_control():
	"""The manifest itself. Only the control plane has OneApp App."""
	if frappe.db.exists("OneApp App", CODE):
		frappe.delete_doc("OneApp App", CODE, force=True, ignore_permissions=True)

	doc = frappe.get_doc({
		"doctype": "OneApp App", "app_code": CODE, "app_label": "Tasks",
		"module": "Tasks", "role_name": ROLE, "icon": "lucide-file-text",
		"is_active": 1, "availability": "General", "sort_order": 5,
		"description": "Everything on your plate, and who it is waiting on.",
	})
	doc.append("doctypes", {"document_type": "ToDo", "access": "Manage", "if_owner": 0})
	for view in VIEWS:
		doc.append("views", view)
	doc.insert(ignore_permissions=True)
	print(f"control plane: {CODE} with {len(VIEWS)} screens")


def seed_tenant():
	"""The tenant's cached copy, plus records to look at.

	A dev site is not linked to a control plane, so the cache is written here
	directly — the same shape `sync_from_control_plane` would have written.
	"""
	from oneapp.oneapp_core import sync

	state = frappe.get_single("OneApp Site State")
	apps = [a for a in json.loads(state.apps_json or "[]") if a["app_code"] != CODE]
	apps.append({
		"app_code": CODE, "app_label": "Tasks", "module": "Tasks",
		"role_name": ROLE, "icon": "lucide-file-text", "sort_order": 5,
		"description": "Everything on your plate, and who it is waiting on.",
		"views": [dict(v, component=None) for v in VIEWS],
	})
	state.db_set("apps_json", json.dumps(apps), update_modified=False)
	sync.invalidate()

	for row in TODOS:
		if frappe.db.exists("ToDo", {"description": row["description"]}):
			continue
		frappe.get_doc({"doctype": "ToDo", **row}).insert(ignore_permissions=True)

	for n in range(1, BACKLOG + 1):
		description = f"{BACKLOG_PREFIX} {n:02d}"
		if frappe.db.exists("ToDo", {"description": description}):
			continue
		frappe.get_doc({
			"doctype": "ToDo", "description": description, "status": "Closed",
			"priority": ["High", "Medium", "Low"][n % 3],
		}).insert(ignore_permissions=True)

	print(f"tenant: {CODE} cached, {len(TODOS)} todos and {BACKLOG} backlog rows present")


if __name__ == "__main__":
	# Which site this is, by what it has: only the control plane defines the
	# manifest doctype, and only a tenant has the cached copy.
	if frappe.db.exists("DocType", "OneApp App"):
		seed_control()
	elif frappe.db.exists("DocType", "OneApp Site State"):
		seed_tenant()
	else:
		raise SystemExit("neither a control-plane nor a tenant site")
