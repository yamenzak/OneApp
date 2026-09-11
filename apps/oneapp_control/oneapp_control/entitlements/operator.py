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
	"OneSpace Space", "Space Entitlement", "Space Claim Code",
	"Space Claim Redemption", "AI Model", "AI Feature",
	"AI Usage Record", "Support Login", "Add-on", "Credit Pack", "Promo Code",
	"Tenant Lifecycle Event", "Workspace Role",
	# Read-only, and not ours: three virtual doctypes over the press API.
	"Press Site", "Press Server", "Press Bench Group",
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
# screen, label, icon, doctype, fields, status field, group
#
# **Grouped, and that is the whole shape of this rail.** There were thirty-two
# entries on it and one per doctype, which is how it was built and is not how
# anybody reads it: twenty of them were machine state or an audit trail, and
# the only way to find a problem in one was to remember to open it. So the
# groups are the six questions an operator actually asks, and the screens sit
# under whichever one they answer. Attention is above all of them and belongs
# to none.
#
# Screens sharing a group are declared together, because the rail draws a
# heading when the group changes — see `screen_group` on the child doctype.
# `test_operator_console.py` holds them adjacent.
#
# Written out rather than named as constants, for the same reason the
# component keys are: this stays a plain literal that `ast.literal_eval` can
# read without importing Frappe, which is how every test in this file's suite
# reads it.
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
	# --- the fleet: workspaces, the machines under them, and getting there ---
	("tenants", "Workspaces", "lucide-users", "Tenant",
	 "tenant_name,site_name,status,plan,shard", "status", "Fleet"),
	("shards", "Shards", "lucide-database", "Shard",
	 "shard_name,status,region,press_release_group,tenant_count,capacity_tenants",
	 "status", "Fleet"),
	("regions", "Regions", "lucide-store", "Region",
	 "region_name,region_code,country,press_cluster,is_active", "", "Fleet"),
	("buckets", "Buckets", "lucide-database", "Storage Bucket",
	 "bucket_name,jurisdiction,status,tenant_count,bytes_used", "status", "Fleet"),
	# Frappe Cloud's own records, read live. No table behind any of the three —
	# see `press/records.py` — so these are the same screens over somebody
	# else's truth. The orphan they used to be scanned for is an Attention row
	# now; what is left is the whole list, for when you want the whole list.
	("sites", "Cloud sites", "lucide-server", "Press Site",
	 "site_name,status,tenant,bench_group,cluster,plan", "status", "Fleet"),
	("servers", "Cloud servers", "lucide-hard-drive", "Press Server",
	 "server_name,title,status,cluster,plan", "status", "Fleet"),
	("benches", "Bench groups", "lucide-layers", "Press Bench Group",
	 "group_name,title,version", "", "Fleet"),
	("provisioning", "Provisioning", "lucide-clock", "Provisioning Job",
	 "tenant,action,state,step,attempts,started_at", "state", "Fleet"),
	("standby", "Standby", "lucide-package", "Standby Site",
	 "press_site,status,shard,claimed_by,created_on", "status", "Fleet"),

	# --- money: what a workspace pays, and what it spends ---
	("signups", "Signups", "lucide-user-round", "Account Request",
	 "email,workspace_name,status,plan,region", "status", "Money"),
	("subscriptions", "Subscriptions", "lucide-receipt", "Subscription",
	 "tenant,plan,status,current_period_end", "status", "Money"),
	("credits", "Credits", "lucide-wallet", "Credit Ledger Entry",
	 "tenant,entry_type,credits,expires_on,remarks", "entry_type", "Money"),
	("reservations", "Reservations", "lucide-clock", "Credit Reservation",
	 "tenant,status,credits_reserved,credits_committed,expires_at", "status", "Money"),
	("webhooks", "Webhooks", "lucide-mail", "Stripe Webhook Event",
	 "event_type,status,tenant,processed_on", "status", "Money"),

	# --- the catalogue: the six things a person authors and nothing writes ---
	("plans", "Plans", "lucide-briefcase", "Plan",
	 "plan_name,plan_code,audience,is_active,price_monthly,storage_gb",
	 "audience", "Catalogue"),
	("addons", "Add-ons", "lucide-package", "Add-on",
	 "addon_name,addon_code,kind,unit_gb,is_active,price_monthly", "kind", "Catalogue"),
	("packs", "Credit packs", "lucide-wallet", "Credit Pack",
	 "pack_name,pack_code,credits,amount,currency,is_active", "", "Catalogue"),
	("promos", "Promo codes", "lucide-shopping-cart", "Promo Code",
	 "promo_code,description,discount_type,percent_off,duration,times_redeemed,is_active",
	 "discount_type", "Catalogue"),

	# --- apps: who has what, and the two ways they got it ---
	("spaces", "Spaces", "lucide-layout-grid", "OneSpace Space",
	 "space_label,module,role_name,availability,is_active", "availability", "Apps"),
	("entitlements", "Entitlements", "lucide-shield", "Space Entitlement",
	 "tenant,app,enabled,offered", "", "Apps"),
	# The other way a Restricted space reaches a workspace: a string somebody
	# types. Two screens rather than one, because the question is usually "who
	# has RUA and how did they get it", which is a list across codes rather than
	# a list inside one. `docs/MARKETPLACE.md` §4.
	("claims", "Claim codes", "lucide-wallet", "Space Claim Code",
	 "claim_code,app,uses_allowed,uses_spent,expires_on,enabled", "", "Apps"),
	("redemptions", "Claims made", "lucide-receipt", "Space Claim Redemption",
	 "claim_code,tenant,app,redeemed_by,redeemed_on", "", "Apps"),

	# --- AI: two catalogues nobody authors, and what they cost ---
	("models", "Models", "lucide-sparkles", "AI Model",
	 "display_name,provider,capability,status,is_recommended", "status", "AI"),
	("features", "Features", "lucide-sparkles", "AI Feature",
	 "feature_key,label,app,capability,status", "status", "AI"),
	("usage", "Usage", "lucide-chart-line", "AI Usage Record",
	 "tenant,feature,model,credits_charged,cost_usd", "", "AI"),

	# --- the trail: what happened, and who did it ---
	("lifecycle", "Lifecycle", "lucide-clock", "Tenant Lifecycle Event",
	 "tenant,event,occurred_on,to_status,triggered_by,reason", "event", "Trail"),
	("support", "Support logins", "lucide-stethoscope", "Support Login",
	 "tenant,site,operator,reason,logged_in_on,succeeded", "", "Trail"),
	# A workspace's own roles. Read here rather than written: the workspace
	# builds these itself, and an operator's reason to look is a support call
	# about who can reach what.
	("roles", "Workspace roles", "lucide-user-round", "Workspace Role",
	 "tenant,role_label,is_active,created_by_email", "", "Trail"),
)

# Before the lists, because it is the only screen that speaks without being
# asked. Everything else on this rail is somewhere to go *looking* for a
# problem; this is where the problem goes. `attention.py` is the whole of it.
LEADING = (
	("attention", "Attention", "lucide-shield", "onespace-ops/attention"),
)

# Readiness is the seventh question — "is this control plane finished" — and it
# is asked once at bring-up and then when something breaks. Below the six.
#
# `press` and `tenant` carry no group and are not meant to: the first is
# reached from Frappe Cloud's own screens and the second from a workspace
# record through a declared action (`entitlements/actions.py`). They are on the
# rail because the shell resolves a `component` from the manifest, not because
# anybody should navigate to them from there.
COMPONENTS = (
	("readiness", "Readiness", "lucide-file-text", "onespace-ops/readiness", "Setup"),
	("press", "Frappe Cloud", "lucide-factory", "onespace-ops/press", "Setup"),
	("tenant", "Workspace", "lucide-wrench", "onespace-ops/tenant", "Setup"),
)


#: The screens where a person creates a record, and the only ones that offer
#: New. Everything else on this rail is written by machinery — a provisioning
#: job, a ledger entry, a webhook, a lifecycle event — or by somebody else: the
#: press screens are Frappe Cloud's records, `Workspace Role` is the
#: workspace's own, and `OneSpace Space` is rewritten from `spaces/*.py` by
#: `after_migrate`, so a space edited here is silently reverted at the next
#: deploy.
#:
#: A New button over a table nothing reads from is worse than no button: it
#: offers a row that will be ignored, overwritten, or — in the Space case —
#: erased by a migration nobody connected to it.
#:
#: `test_operator_console.py` holds this against which doctypes the code
#: actually inserts, so a new machine-written table cannot quietly acquire one.
AUTHORED = {
	"tenants",       # rare, and the escape hatch when a signup half-finished
	"shards",        # adding capacity
	"regions",       # named and given a country after the sync creates them
	"plans", "addons", "packs", "promos",   # the catalogue
	"entitlements",  # granting an app to a workspace
	"claims",        # a code somebody hands out
}


def _component(row) -> dict:
	screen, label, icon, component, *rest = row
	return {
		"screen": screen, "label": label, "icon": icon, "component": component,
		"screen_group": rest[0] if rest else "",
	}


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
		# Restricted, and entitled to nobody — which is what makes it operator-only
		# rather than merely hidden.
		#
		# It was General, on the argument that there is no tenant on this site to
		# entitle and `visible_spaces` narrows by role anyway. Both halves are
		# true and the conclusion was still wrong: `local_spaces` — the reader
		# that serves *this* site — does not filter on availability at all, so
		# nothing here depended on General; while `spaces_for_tenant` hands every
		# General space to every tenant, so this one was in every workspace's
		# manifest. Each tenant site was being told to create an
		# `OneSpace Operator` role with permissions over Tenant, Subscription and
		# the credit ledger.
		#
		# Inert, because those doctypes do not exist on a tenant site and
		# `sync_permissions` skips what it cannot find. But `allowed_doctypes` is
		# read by the workspace's own role builder now, and a customer offered
		# `Credit Ledger Entry` as something to grant is not a thing to leave
		# resting on a doctype's absence.
		"availability": "Restricted",
		"is_active": 1,
		"description": "Tenants, shards, provisioning, billing and the AI catalogue.",
		"screens": [_component(row) for row in LEADING] + [
			{
				"screen": screen, "label": label, "icon": icon,
				"document_type": doctype, "fields": fields, "status_field": status,
				"screen_group": group,
				"hide_new": 0 if screen in AUTHORED else 1,
			}
			for screen, label, icon, doctype, fields, status, group in SCREENS
		] + [_component(row) for row in COMPONENTS],
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
		from oneapp.onespace import sync
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
