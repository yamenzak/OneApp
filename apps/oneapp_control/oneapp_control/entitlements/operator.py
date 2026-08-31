"""The operator console, declared as a Space.

`/admin` is ~6,000 lines of Vue over eighteen doctypes and a settings dialog.
Almost none of it is doing anything OneSpace's own screen machinery does not
already do better — and every improvement to that machinery (saved views,
filters, the record pane, realtime, the mobile shell) has until now stopped at
the tenant boundary and never reached the console.

So the console becomes a Space on the control site, described here the same way
a customer's space is described: doctypes it may reach, and screens over them.
The two surfaces that are genuinely not lists stay as `component` screens, which
is what that escape hatch is for.

Read by `install.py` at install and by `after_migrate`, so editing this file and
running a migration is how the console changes shape.
"""

import frappe

SPACE_CODE = "onespace-ops"
ROLE = "OneSpace Operator"

# What the console may reach. `Manage` throughout: an operator creating,
# amending and deleting is the job, and narrowing it here would be theatre —
# they are System Managers, and the DocPerms are what make the *screens* work
# rather than what stands between them and the data.
DOCTYPES = (
	"Tenant", "Shard", "Provisioning Job", "Standby Site", "Account Request",
	"Subscription", "Credit Ledger Entry", "Credit Reservation",
	"Stripe Webhook Event", "Plan", "Region", "Storage Bucket",
	"OneSpace Space", "Space Entitlement", "AI Model", "AI Feature",
	"AI Usage Record", "Support Login", "Add-on", "Credit Pack", "Promo Code",
	"Tenant Lifecycle Event", "Workspace Role",
)

# screen, label, icon, doctype, fields, status field
#
# The icon is a closed Select on the Space Screen doctype — the same short list
# a customer's space picks from — so these are chosen out of it rather than
# named freely. A screen icon that is not on that list is a validation error at
# seed time, which is the right place to find out.
#
# `fields` is a starting point rather than a ceiling — the column picker offers
# every field of the doctype, and a saved view is how an operator disagrees with
# this. Chosen to be the four or five somebody scans a page for.
SCREENS = (
	("tenants", "Tenants", "lucide-users", "Tenant",
	 "tenant_name,site_name,status,plan,shard", "status"),
	("provisioning", "Provisioning", "lucide-clock", "Provisioning Job",
	 "tenant,action,state,step,attempts,started_at", "state"),
	("shards", "Shards", "lucide-database", "Shard",
	 "shard_name,status,region,press_release_group,tenant_count,capacity_tenants", "status"),
	("standby", "Standby", "lucide-package", "Standby Site",
	 "press_site,status,shard,claimed_by,created_on", "status"),
	("signups", "Signups", "lucide-user-round", "Account Request",
	 "email,workspace_name,status,plan,region", "status"),
	("subscriptions", "Subscriptions", "lucide-receipt", "Subscription",
	 "tenant,plan,status,current_period_end", "status"),
	("credits", "Credits", "lucide-wallet", "Credit Ledger Entry",
	 "tenant,entry_type,credits,expires_on,remarks", "entry_type"),
	("reservations", "Reservations", "lucide-clock", "Credit Reservation",
	 "tenant,status,credits_reserved,credits_committed,expires_at", "status"),
	("webhooks", "Webhooks", "lucide-mail", "Stripe Webhook Event",
	 "event_type,status,tenant,processed_on", "status"),
	("plans", "Plans", "lucide-briefcase", "Plan",
	 "plan_name,plan_code,audience,is_active,price_monthly,storage_gb", "audience"),
	("addons", "Add-ons", "lucide-package", "Add-on",
	 "addon_name,addon_code,kind,unit_gb,is_active,price_monthly", "kind"),
	("packs", "Credit packs", "lucide-wallet", "Credit Pack",
	 "pack_name,pack_code,credits,amount,currency,is_active", ""),
	("promos", "Promo codes", "lucide-shopping-cart", "Promo Code",
	 "promo_code,description,discount_type,percent_off,duration,times_redeemed,is_active",
	 "discount_type"),
	("regions", "Regions", "lucide-store", "Region",
	 "region_name,region_code,country,is_active", ""),
	("buckets", "Buckets", "lucide-database", "Storage Bucket",
	 "bucket_name,jurisdiction,status,tenant_count,bytes_used", "status"),
	("spaces", "Spaces", "lucide-layout-grid", "OneSpace Space",
	 "space_label,module,role_name,availability,is_active", "availability"),
	("entitlements", "Entitlements", "lucide-shield", "Space Entitlement",
	 "tenant,app,enabled", ""),
	# A workspace's own roles. Read here rather than written: the workspace
	# builds these itself, and an operator's reason to look is a support call
	# about who can reach what.
	("roles", "Workspace roles", "lucide-user-round", "Workspace Role",
	 "tenant,role_label,is_active,created_by_email", ""),
	("models", "AI models", "lucide-sparkles", "AI Model",
	 "display_name,provider,capability,status,is_recommended", "status"),
	("features", "AI features", "lucide-sparkles", "AI Feature",
	 "feature_key,label,app,capability,status", "status"),
	("usage", "AI usage", "lucide-chart-line", "AI Usage Record",
	 "tenant,feature,model,credits_charged,cost_usd", ""),
	("support", "Support logins", "lucide-stethoscope", "Support Login",
	 "tenant,site,operator,reason,logged_in_on,succeeded", ""),
	# The ladder's audit trail. On the rail rather than only on a workspace,
	# because the question it answers most often is fleet-shaped: what did the
	# sweep do last night, and to whom.
	("lifecycle", "Lifecycle", "lucide-clock", "Tenant Lifecycle Event",
	 "tenant,event,occurred_on,to_status,triggered_by,reason", "event"),
)

# The three that are not lists, and the reason the manifest is a shortcut rather
# than a cage. Readiness is a checklist with blockers; the Press panel is a live
# view of Frappe Cloud's own state, fetched from Press rather than stored here;
# and Workspace is one tenant seen from both sides at once — what we hold beside
# what Frappe Cloud is running, plus the backups, domains, support sign-in and
# billing that are calls rather than fields. It is reached from the Tenants
# screen through a declared action (`entitlements/actions.py`) rather than from
# the rail, because it is about a record.
# Keyed `spaceCode/screen`, which is the convention `screens/index.js`
# documents — so two spaces can each have an `overview` and neither has to know
# about the other.
# Written out rather than interpolated from SPACE_CODE, so this stays a plain
# literal that a test can read without importing Frappe — and the test asserts
# the prefix, which is what a rename would break.
COMPONENTS = (
	("readiness", "Readiness", "lucide-file-text", "onespace-ops/readiness"),
	("press", "Frappe Cloud", "lucide-factory", "onespace-ops/press"),
	("tenant", "Workspace", "lucide-wrench", "onespace-ops/tenant"),
)


def manifest() -> dict:
	"""The Space, as the doctype stores one."""
	return {
		"doctype": "OneSpace Space",
		"space_code": SPACE_CODE,
		"space_label": "Operations",
		"module": "OneApp Control",
		"role_name": ROLE,
		"icon": "lucide-shield",
		"sort_order": 0,
		# General on this site, and narrowed by the role rather than by an
		# entitlement: there is no tenant here to entitle. `visible_spaces` and
		# `_space` both filter on `role_name`, so a customer signed in to their
		# account area never sees this and cannot resolve it by name.
		"availability": "General",
		"is_active": 1,
		"description": "Tenants, shards, provisioning, billing and the AI catalogue.",
		"screens": [
			{
				"screen": screen, "label": label, "icon": icon,
				"document_type": doctype, "fields": fields, "status_field": status,
			}
			for screen, label, icon, doctype, fields, status in SCREENS
		] + [
			{"screen": screen, "label": label, "icon": icon, "component": component}
			for screen, label, icon, component in COMPONENTS
		],
		"doctypes": [
			{"document_type": doctype, "access": "Manage", "if_owner": 0}
			for doctype in DOCTYPES
		],
	}


def seed() -> None:
	"""Write the Space, replacing what is there.

	Replaced rather than merged, and that is the decision worth stating: this
	file owns the operator Space. Editing it in the console is a
	development-time act whose result belongs back here, exactly like editing a
	doctype — otherwise a hand-edit and a deploy fight, and the deploy wins
	silently on a day nobody expects it to.

	A customer's space is the opposite: the control plane owns those rows and an
	operator edits them in the console. Only this one is code.
	"""
	spec = manifest()
	if frappe.db.exists("OneSpace Space", SPACE_CODE):
		frappe.delete_doc("OneSpace Space", SPACE_CODE, ignore_permissions=True, force=True)
	frappe.get_doc(spec).insert(ignore_permissions=True)


def sync_permissions() -> None:
	"""Write the DocPerms the operator Space's screens depend on.

	`_granted_doctypes` reads Custom DocPerm rows for a space's role — that is
	what makes a screen an allowlist rather than a label — so without these the
	console resolves and every screen refuses.

	A tenant gets these from `sync.sync_permissions` off the control plane's
	manifest. This is the same function fed the same shape from the local
	registry, so there is one implementation of what a manifest means.
	"""
	try:
		from oneapp.oneapp_core import sync
	except ImportError:
		# `oneapp` is not installed here, so there is no console to grant for.
		return

	from oneapp_control.entitlements import registry

	manifest_rows = []
	for space in registry.local_spaces():
		role = space.get("role_name")
		if not role:
			continue
		rows = frappe.get_all(
			"OneSpace Space Doctype",
			filters={"parent": space["space_code"], "parenttype": "OneSpace Space"},
			fields=["document_type", "access", "if_owner"],
		)
		manifest_rows += [
			{
				"role": role,
				"doctype": row["document_type"],
				"access": row["access"],
				"if_owner": bool(row["if_owner"]),
			}
			for row in rows
		]

	sync.sync_permissions(manifest_rows)
