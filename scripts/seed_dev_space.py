"""A manifest-only space on the local sites, so the generic screen has
something to render.

**MockSpace**, on the rail. Two screens under it, over two of Frappe's own
doctypes rather than an invented product:

* **Tasks** (ToDo) — the field list is chosen for coverage: a Text Editor, two
  Selects (badge colours), two Links (the picker, and one that may be created
  from), a Date, and a Color, which has no frappe-ui counterpart and so must be
  shown without ever being offered. It also carries two shared saved views, so
  the sidebar has named layouts to list under it and the switcher has something
  to switch between.
* **Notes** (Note) — a second doctype under one space, which is the point: a
  space is not a doctype, and a screen is one item in its navigation.

Run it against both sites: the manifest lives on the control plane, and the
tenant caches it.

    scripts/dev.sh run scripts/seed_dev_space.py
    ONEAPP_SITE=space.localhost ONEAPP_PORT=8001 \\
      scripts/dev.sh run scripts/seed_dev_space.py

Nothing here runs on Frappe Cloud, and nothing here is a fixture the apps ship.
"""

import json

import frappe

CODE = "zzmock"
LABEL = "MockSpace"
ROLE = "OneSpace Mock"
# Fixtures this one replaces. A dev site keeps whatever a previous fixture
# wrote, so a space that is no longer seeded stays on the rail with a role that
# still grants doctypes — a stale entitlement is a confusing thing to debug
# around and a trivial thing to clear.
RETIRED = ("zztasks",)
RETIRED_ROLES = ("OneSpace Tasks",)

TASK_FIELDS = "description,status,priority,allocated_to,role,date,color"
NOTE_FIELDS = "title,public,content"

# What the space grants. ToDo and Note are what its screens show; Role is a
# link target, granted so the picker's Create row has somewhere to create —
# a link to a doctype the space did not grant is readable and never creatable,
# and both halves are worth having in the fixture.
DOCTYPES = [
	{"document_type": "ToDo", "access": "Manage", "if_owner": 0},
	{"document_type": "Note", "access": "Manage", "if_owner": 0},
	{"document_type": "Role", "access": "Manage", "if_owner": 0},
]

SCREENS = [
	{
		"screen": "tasks", "label": "Tasks", "icon": "lucide-file-text",
		# Oldest first, so the three written-out tasks lead and the forty
		# backlog rows trail them. A fixture reads better as "three real tasks
		# and a long tail" than as forty numbered ones, and it makes the first
		# row a stable thing for a browser test to point at.
		"document_type": "ToDo", "fields": TASK_FIELDS, "order_by": "creation asc",
		# More than one, so the sidebar has something to expand. `board` has no
		# body yet and is dropped on the way out — which is the behaviour worth
		# having in the fixture, not a mistake in it.
		"view_types": "list,board",
		# Where a task stands, which is what the badge beside its name says.
		# A fieldname and nothing else: the colours are ToDo's own.
		"status_field": "status",
	},
	{
		"screen": "notes", "label": "Notes", "icon": "lucide-book-open",
		"document_type": "Note", "fields": NOTE_FIELDS, "order_by": "modified desc",
	},
]

# Shared layouts on the Tasks screen: no user, so the whole workspace sees
# them. These are what the sidebar lists under a screen alongside its view
# types, and what the switcher in the breadcrumb line switches between.
LAYOUTS = [
	# One with an icon and one without, because both render and only one of
	# them proves the fallback still says who a view is for.
	{
		"label": "Open work", "screen": "tasks", "icon": "lucide-clock",
		"filters": json.dumps([["status", "=", "Open"]]),
		"order_by": "priority asc",
	},
	{
		"label": "High priority", "screen": "tasks",
		"filters": json.dumps([["priority", "=", "High"]]),
		"order_by": "modified desc",
	},
]

TODOS = [
	{"description": "Book the van for Thursday", "priority": "Medium", "status": "Open",
	 "allocated_to": "Administrator", "color": "#2490EF"},
	{"description": "Chase the Halloway invoice", "priority": "High", "status": "Open"},
	{"description": "File Q3 returns", "priority": "Low", "status": "Closed"},
]

NOTES = [
	{"title": "Van hire terms", "public": 1,
	 "content": "<p>Collection before nine, or the day counts as two.</p>"},
	{"title": "Halloway contacts", "public": 0,
	 "content": "<p>Chris is the one who signs; Sam answers the phone.</p>"},
]

# The paging fixture. Everything else here is two or three records, which is
# right for reading a screen and useless for testing what happens at the end of
# a page — Load More, the count, the windowing threshold. Closed, so it does
# not crowd the Open work layout.
BACKLOG = 40
BACKLOG_PREFIX = "Backlog item"

# Field metadata the UI honours and stock Frappe never sets. These are
# ERPNext-shaped flags — a doctype there marks the two or three fields worth
# seeing on hover, the one worth reading heavy, and how wide a column wants to
# be — and nothing on a plain bench declares one, so there is nothing to look
# at unless the fixture says so.
PROPERTIES = [
	("User", "email", "in_preview", 1, "Check"),
	("User", "enabled", "in_preview", 1, "Check"),
	("User", "user_type", "in_preview", 1, "Check"),
	("ToDo", "priority", "bold", 1, "Check"),
	("ToDo", "description", "columns", 4, "Int"),
]


def seed_control():
	"""The manifest itself. Only the control plane has OneSpace Space."""
	for code in (CODE, *RETIRED):
		if frappe.db.exists("OneSpace Space", code):
			frappe.delete_doc("OneSpace Space", code, force=True, ignore_permissions=True)

	doc = frappe.get_doc({
		"doctype": "OneSpace Space", "space_code": CODE, "space_label": LABEL,
		"module": "Mock", "role_name": ROLE, "icon": "lucide-briefcase",
		"is_active": 1, "availability": "General", "sort_order": 5,
		"description": "Two screens over two doctypes, for looking at.",
	})
	for grant in DOCTYPES:
		doc.append("doctypes", grant)
	for screen in SCREENS:
		doc.append("screens", screen)
	doc.insert(ignore_permissions=True)
	print(f"control plane: {CODE} with {len(SCREENS)} screens")


def seed_tenant():
	"""The tenant's cached copy, plus records to look at.

	A dev site is not linked to a control plane, so the cache is written here
	directly — the same shape `sync_from_control_plane` would have written.
	"""
	from oneapp.oneapp_core import sync

	state = frappe.get_single("OneSpace Site State")
	spaces = [
		one for one in json.loads(state.spaces_json or "[]")
		if one.get("space_code") not in (CODE, *RETIRED)
	]
	spaces.append({
		"space_code": CODE, "space_label": LABEL, "module": "Mock",
		"role_name": ROLE, "icon": "lucide-briefcase", "sort_order": 5,
		"description": "Two screens over two doctypes, for looking at.",
		"screens": [dict(v, component=None) for v in SCREENS],
	})
	state.db_set("spaces_json", json.dumps(spaces), update_modified=False)
	sync.invalidate()

	# The role, its permissions, and this session in it. On a real tenant the
	# control plane's permission sync does all three; a dev site has no control
	# plane, and a space whose role holds no DocPerms is refused at the first
	# read with "ToDo is not part of MockSpace" — which reads like a manifest
	# bug and is a fixture that stopped halfway.
	sync.ensure_role(ROLE)
	# `document_type` is the manifest child row's fieldname; `doctype` is what
	# the permission sync reads. They are not the same word, and a row with the
	# wrong one is silently skipped — which surfaces later as "ToDo is not part
	# of MockSpace" and reads like a manifest bug.
	sync.sync_permissions([
		{"role": ROLE, "doctype": grant["document_type"],
		 "access": grant["access"], "if_owner": grant["if_owner"]}
		for grant in DOCTYPES
	])
	user = frappe.get_doc("User", frappe.session.user)
	if ROLE not in {r.role for r in user.roles}:
		user.append("roles", {"role": ROLE})
		user.save(ignore_permissions=True)

	for role in RETIRED_ROLES:
		if frappe.db.exists("Role", role):
			for perm in frappe.get_all("Custom DocPerm", filters={"role": role}, pluck="name"):
				frappe.delete_doc("Custom DocPerm", perm, force=True, ignore_permissions=True)
			frappe.delete_doc("Role", role, force=True, ignore_permissions=True)

	for doctype, fieldname, prop, value, prop_type in PROPERTIES:
		frappe.make_property_setter({
			"doctype": doctype, "fieldname": fieldname, "property": prop,
			"value": value, "property_type": prop_type,
		}, is_system_generated=False)

	for row in TODOS:
		if frappe.db.exists("ToDo", {"description": row["description"]}):
			continue
		frappe.get_doc({"doctype": "ToDo", **row}).insert(ignore_permissions=True)

	for row in NOTES:
		if frappe.db.exists("Note", {"title": row["title"]}):
			continue
		frappe.get_doc({"doctype": "Note", **row}).insert(ignore_permissions=True)

	for n in range(1, BACKLOG + 1):
		description = f"{BACKLOG_PREFIX} {n:02d}"
		if frappe.db.exists("ToDo", {"description": description}):
			continue
		frappe.get_doc({
			"doctype": "ToDo", "description": description, "status": "Closed",
			"priority": ["High", "Medium", "Low"][n % 3],
		}).insert(ignore_permissions=True)

	# And their views. A browser pass that makes a view and fails before
	# deleting it leaves one behind, and three runs later "Only the urgent"
	# matches three rows and every test that names one is ambiguous. The
	# fixture's own views are the ones in LAYOUTS; a named view on this space
	# that is not one of them is litter.
	strays = frappe.get_all(
		"OneSpace Saved View",
		filters={"space_code": CODE, "label": ["not in", [row["label"] for row in LAYOUTS]]},
		fields=["name", "label"],
	)
	for stray in strays:
		if stray["label"]:
			frappe.delete_doc("OneSpace Saved View", stray["name"], ignore_permissions=True)

	# Nobody is hiding anything on a fresh fixture either — a hidden view is
	# invisible, which is the worst thing for a test to inherit.
	frappe.db.delete("OneSpace Hidden View", {"space_code": CODE})

	# And the records they make. A pass that creates one to prove creating
	# works has no reason to keep it, and forty runs later the fixture is forty
	# rows longer than it was written to be. Everything a test makes is named
	# with this prefix on purpose.
	for doctype, field in (("ToDo", "description"), ("Note", "title")):
		for row in frappe.get_all(doctype, filters={field: ["like", "ZZ %"]}, pluck="name"):
			frappe.delete_doc(doctype, row, ignore_permissions=True, force=True)

	# The browser passes leave their comments behind, and Frappe keeps only the
	# last hundred of them on the document itself — which is where the count in
	# the timeline tab comes from, here as in the desk. A fixture that has been
	# commented on two hundred times therefore has a count that no longer
	# moves, and a test that adds one and watches the number goes red for a
	# reason that has nothing to do with what it tests. Every ToDo and Note on
	# a dev site is this fixture's, so this is the fixture sweeping up after
	# itself.
	for doctype in ("ToDo", "Note"):
		names = frappe.get_all(doctype, pluck="name")
		if not names:
			continue
		frappe.db.delete("Comment", {"reference_doctype": doctype, "reference_name": ("in", names)})
		# Written the way Frappe writes it: `_comments` sits beside the document
		# as a cache, and refreshing it must not move `modified`.
		frappe.db.sql(f"update `tab{doctype}` set `_comments` = '[]'")

	for layout in LAYOUTS:
		where = {"space_code": CODE, "screen": layout["screen"], "label": layout["label"]}
		found = frappe.db.exists("OneSpace Saved View", where)
		if found:
			# The icon is the one thing worth re-asserting: a browser test that
			# picks one leaves it behind, and the next run should look like the
			# fixture rather than like whatever the last test did.
			frappe.db.set_value("OneSpace Saved View", found, "icon", layout.get("icon", ""))
			continue
		frappe.get_doc({
			"doctype": "OneSpace Saved View", "space_code": CODE,
			# No user: shared with the whole workspace, which is what makes it
			# something the sidebar can list for anybody.
			"user": "", **layout,
		}).insert(ignore_permissions=True)

	# Again, and last. Everything between the first call and here reads the
	# site state — the permission sync does, the role grant does — and any one
	# of them repopulates the cache from a document this process had already
	# loaded. Clearing it at the end is the only order that leaves the next
	# request reading what was just written.
	sync.invalidate()

	print(
		f"tenant: {CODE} cached — {len(TODOS)} todos, {len(NOTES)} notes, "
		f"{BACKLOG} backlog rows, {len(LAYOUTS)} shared views"
	)


if __name__ == "__main__":
	# Which site this is, by what it has: only the control plane defines the
	# manifest doctype, and only a tenant has the cached copy.
	if frappe.db.exists("DocType", "OneSpace Space"):
		seed_control()
	elif frappe.db.exists("DocType", "OneSpace Site State"):
		seed_tenant()
	else:
		raise SystemExit("neither a control-plane nor a tenant site")
