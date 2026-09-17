"""OneAdmin — the operator console, as a space like any other.

`docs/CLEANUP.md` §5 and stage 8. The console has been a Space since
`entitlements/operator.py` was written — that is what "the operator uses the
same desk as everybody" meant, and it was already true. What was not true is
the half this stage is actually about: it was a space **declared somewhere
else, in a shape of its own, with one role**.

Three things followed from that, and all three are why this file exists.

**None of the manifest guards could read it.** `tests/test_space_screens.py`
checks every field a screen names against the doctype behind it, every view
type against the fields it needs, every dashboard widget against the
vocabulary the server draws — over `spaces/*.py`. The console's declaration was
seven-tuples in another package, so it got `tests/test_operator_console.py`
instead: a second, smaller set of rules, re-deriving what the first one already
knew.

**It had one role where every other space has four.**
`docs/ONEADMIN-SIMPLIFICATION.md` §4 names five things that must stay a
person's decision — purging a workspace, granting an entitlement, a plan's
price, holding a workspace out of the lifecycle, signing in as a customer — and
then had no way to say *which* person. One role means the person who adds
capacity is the person who sets prices.

The old file argued that narrowing the grants "would be theatre — they are
System Managers". That is true of the *data* and beside the point about the
*screens*: a screen is an allowlist derived from the grants, so the seats
decide what each rung is even offered. And it is only true while every operator
is a System Manager, which is a thing this makes it possible to stop doing.

**Its code was `onespace-ops` where the catalogue says `oneadmin`.** The same
disagreement `books` had, found one stage later and fixed the same way.

What is *not* here is the customer's account space. `entitlements/account.py`
stays where it is: four component screens, no doctypes, and one role that is
the customer's rather than a seat. Giving it four seats would create a
`Customer-Manager` that means nothing, and it is the one space on this site the
four-seat installer genuinely does not fit.
"""

import json

SPACE = {
	"space_code": "oneadmin",
	"space_label": "Operations",
	"module": "OneApp Control",
	# So the four seats are `Ops-User`, `Ops-Manager`, `Ops-Audit` and
	# `Ops-Admin`. "Ops" rather than "Admin", because `Admin-Admin` is a
	# sentence nobody should have to read.
	"role_name": "Ops",
	"icon": "lucide-shield",
	# First, and the only space on this site that asks to be: an operator who
	# opens the console is opening it because something needs them.
	"sort_order": 0,
	"brand": "oneadmin",
	# Restricted, and entitled to nobody — which is what makes it operator-only
	# rather than merely hidden.
	#
	# It was General once, on the argument that there is no tenant on this site
	# to entitle and `visible_spaces` narrows by role anyway. Both halves were
	# true and the conclusion was still wrong: `local_spaces` — the reader that
	# serves *this* site — does not filter on availability at all, so nothing
	# depended on General; while `spaces_for_tenant` hands every General space
	# to every tenant, so this one was in every workspace's manifest. Each
	# tenant site was being told to create a role with permissions over Tenant,
	# Subscription and the credit ledger.
	"availability": "Restricted",
	"description": "Tenants, shards, provisioning, billing and the AI catalogue.",
	# Dark, and the only space in the product that is. Not decoration: this is
	# the one surface where somebody is looking at another company's data on
	# their behalf, and a console that does not look like a workspace is a
	# console nobody mistakes for one.
	"theme": json.dumps({
		"mode": "dark",
		"accent": "#6366f1",
		"radius": "soft",
	}),
}

# --------------------------------------------------------------------------- #
# The three jobs, and the fourth that is derived
#
# **User is support.** Somebody is on a call about one workspace. They can read
# everything about it — the fleet, the billing, the trail — and the only thing
# they write is the record of having signed in as the customer. That is the
# widest read in the product and the narrowest write, and it is the right shape:
# answering a question needs the whole picture, and nothing on a support call
# should change a number.
#
# **Manager runs the fleet.** Workspaces, shards, regions, buckets, provisioning,
# standby, and the two ways an app reaches a customer. Everything on this rung
# is about capacity and delivery.
#
# **Admin owns the catalogue and the money.** Plans, add-ons, credit packs,
# promo codes, subscriptions, the credit ledger, reservations, the webhook
# stream, and the two AI catalogues. `docs/ONEADMIN-SIMPLIFICATION.md` §4 says
# "a plan's price, and every other number in the catalogue" is a person's
# decision; this says *which* person.
#
# **Audit reads and writes nothing**, derived by `registry.laddered`. On a
# control plane that is not a formality: this is the seat somebody investigating
# an incident is given, and it is the only one that cannot make the incident
# worse.
# --------------------------------------------------------------------------- #

DOCTYPES = [
	# ----- Everybody: support reads the lot -------------------------------- #
	("Tenant", "Read", 0),
	("Shard", "Read", 0),
	("Region", "Read", 0),
	("Storage Bucket", "Read", 0),
	("Provisioning Job", "Read", 0),
	("Standby Site", "Read", 0),
	("Account Request", "Read", 0),
	("Subscription", "Read", 0),
	("Credit Ledger Entry", "Read", 0),
	("Credit Reservation", "Read", 0),
	("Stripe Webhook Event", "Read", 0),
	("Plan", "Read", 0),
	("Add-on", "Read", 0),
	("Credit Pack", "Read", 0),
	("Promo Code", "Read", 0),
	("Space Entitlement", "Read", 0),
	("Space Claim Code", "Read", 0),
	("Space Claim Redemption", "Read", 0),
	("AI Model", "Read", 0),
	("AI Feature", "Read", 0),
	("AI Usage Record", "Read", 0),
	("Tenant Lifecycle Event", "Read", 0),
	("Support Login", "Read", 0),
	# Three doctypes that are Read at every rung because nothing here may write
	# them at all. `OneSpace Space` is rewritten from `spaces/*.py` on every
	# migration, so a row edited in the console is silently reverted at the next
	# deploy; `Workspace Role` is the workspace's own; and the three press
	# doctypes are virtual — `press/records.py` — with no table underneath.
	("OneSpace Space", "Read", 0),
	("Workspace Role", "Read", 0),
	("Press Site", "Read", 0),
	("Press Server", "Read", 0),
	("Press Bench Group", "Read", 0),
	# The engine's own two, as every space has them. A saved view is the
	# operator's own — `if_owner` — because a console is a set of personal
	# searches; a screen's name is everybody's, so renaming one is Admin's.
	("OneSpace Saved View", "Write", 1),
	("OneSpace Word", "Read", 0),

	# ----- Manager: the fleet ---------------------------------------------- #
	("Tenant", "Manage", 0, "manager"),
	("Shard", "Manage", 0, "manager"),
	("Region", "Manage", 0, "manager"),
	("Storage Bucket", "Manage", 0, "manager"),
	("Provisioning Job", "Manage", 0, "manager"),
	("Standby Site", "Manage", 0, "manager"),
	("Account Request", "Manage", 0, "manager"),
	# How an app reaches a customer: granted directly, or claimed with a code.
	("Space Entitlement", "Manage", 0, "manager"),
	("Space Claim Code", "Manage", 0, "manager"),

	# ----- Admin: the catalogue and the money ------------------------------ #
	("Plan", "Manage", 0, "admin"),
	("Add-on", "Manage", 0, "admin"),
	("Credit Pack", "Manage", 0, "admin"),
	("Promo Code", "Manage", 0, "admin"),
	("Subscription", "Manage", 0, "admin"),
	("Credit Ledger Entry", "Manage", 0, "admin"),
	("Credit Reservation", "Manage", 0, "admin"),
	("Stripe Webhook Event", "Manage", 0, "admin"),
	("AI Model", "Manage", 0, "admin"),
	("AI Feature", "Manage", 0, "admin"),
	("OneSpace Word", "Write", 0, "admin"),
]

#: The screens where a person creates a record, and the only ones that offer
#: New. Everything else on this rail is written by machinery — a provisioning
#: job, a ledger entry, a webhook, a lifecycle event — or by somebody else.
#:
#: A New button over a table nothing reads from is worse than no button: it
#: offers a row that will be ignored, overwritten, or — in the `OneSpace Space`
#: case — erased by a migration nobody connected to it.
#:
#: `tests/test_operator_console.py` holds this against which doctypes the code
#: actually inserts, so a new machine-written table cannot quietly acquire one.
AUTHORED = {
	"tenants",       # rare, and the escape hatch when a signup half-finished
	"shards",        # adding capacity
	"regions",       # named and given a country after the sync creates them
	"plans", "addons", "packs", "promos",   # the catalogue
	"entitlements",  # granting an app to a workspace
	"claims",        # a code somebody hands out
}


def _list(screen, label, icon, doctype, fields, status, group) -> dict:
	"""One list screen, with New offered only where a person authors the rows."""
	return {
		"screen": screen, "label": label, "icon": icon,
		"document_type": doctype, "fields": fields, "status_field": status,
		"screen_group": group,
		"hide_new": 0 if screen in AUTHORED else 1,
	}


# The rail, and the shape of it is the whole of
# `docs/ONEADMIN-SIMPLIFICATION.md`. There were thirty-two entries and one per
# doctype, which is how it was built and is not how anybody reads it: twenty
# were machine state or an audit trail, and the only way to find a problem in
# one was to remember to open it. So the groups are the six questions an
# operator actually asks, and each screen sits under whichever one it answers.
#
# Attention is above all of them and belongs to none.
#
# `fields` is a starting point rather than a ceiling — the column picker offers
# every field of the doctype, and a saved view is how an operator disagrees
# with this. Chosen to be the four or five somebody scans a page for.
SCREENS = [
	# Before the lists, because it is the only screen that speaks without being
	# asked. Everything else here is somewhere to go *looking* for a problem;
	# this is where the problem goes. `attention.py` is the whole of it.
	{
		"screen": "attention", "label": "Attention", "icon": "lucide-shield",
		"component": "oneadmin/attention",
	},

	# ----- Fleet: workspaces, the machines under them, and getting there ---- #
	_list("tenants", "Workspaces", "lucide-users", "Tenant",
	      "tenant_name,site_name,status,plan,shard", "status", "Fleet"),
	_list("shards", "Shards", "lucide-database", "Shard",
	      "shard_name,status,region,press_release_group,tenant_count,"
	      "capacity_tenants", "status", "Fleet"),
	_list("regions", "Regions", "lucide-store", "Region",
	      "region_name,region_code,country,press_cluster,is_active", "", "Fleet"),
	_list("buckets", "Buckets", "lucide-database", "Storage Bucket",
	      "bucket_name,jurisdiction,status,tenant_count,bytes_used", "status",
	      "Fleet"),
	# Frappe Cloud's own records, read live. No table behind any of the three —
	# see `press/records.py` — so these are the same screens over somebody
	# else's truth. The orphan they used to be scanned for is an Attention row
	# now; what is left is the whole list, for when you want the whole list.
	_list("sites", "Cloud sites", "lucide-server", "Press Site",
	      "site_name,status,tenant,bench_group,cluster,plan", "status", "Fleet"),
	_list("servers", "Cloud servers", "lucide-hard-drive", "Press Server",
	      "server_name,title,status,cluster,plan", "status", "Fleet"),
	_list("benches", "Bench groups", "lucide-layers", "Press Bench Group",
	      "group_name,title,version", "", "Fleet"),
	_list("provisioning", "Provisioning", "lucide-clock", "Provisioning Job",
	      "tenant,action,state,step,attempts,started_at", "state", "Fleet"),
	_list("standby", "Standby", "lucide-package", "Standby Site",
	      "press_site,status,shard,claimed_by,created_on", "status", "Fleet"),

	# ----- Money: what a workspace pays, and what it spends ----------------- #
	_list("signups", "Signups", "lucide-user-round", "Account Request",
	      "email,workspace_name,status,plan,region", "status", "Money"),
	_list("subscriptions", "Subscriptions", "lucide-receipt", "Subscription",
	      "tenant,plan,status,current_period_end", "status", "Money"),
	_list("credits", "Credits", "lucide-wallet", "Credit Ledger Entry",
	      "tenant,entry_type,credits,expires_on,remarks", "entry_type", "Money"),
	_list("reservations", "Reservations", "lucide-clock", "Credit Reservation",
	      "tenant,status,credits_reserved,credits_committed,expires_at",
	      "status", "Money"),
	_list("webhooks", "Webhooks", "lucide-mail", "Stripe Webhook Event",
	      "event_type,status,tenant,processed_on", "status", "Money"),

	# ----- Catalogue: the six things a person authors and nothing writes ---- #
	_list("plans", "Plans", "lucide-briefcase", "Plan",
	      "plan_name,plan_code,audience,is_active,price_monthly,storage_gb",
	      "audience", "Catalogue"),
	_list("addons", "Add-ons", "lucide-package", "Add-on",
	      "addon_name,addon_code,kind,unit_gb,is_active,price_monthly", "kind",
	      "Catalogue"),
	_list("packs", "Credit packs", "lucide-wallet", "Credit Pack",
	      "pack_name,pack_code,credits,amount,currency,is_active", "",
	      "Catalogue"),
	_list("promos", "Promo codes", "lucide-shopping-cart", "Promo Code",
	      "promo_code,description,discount_type,percent_off,duration,"
	      "times_redeemed,is_active", "discount_type", "Catalogue"),

	# ----- Apps: who has what, and the two ways they got it ---------------- #
	_list("spaces", "Spaces", "lucide-layout-grid", "OneSpace Space",
	      "space_label,module,role_name,availability,is_active", "availability",
	      "Apps"),
	_list("entitlements", "Entitlements", "lucide-shield", "Space Entitlement",
	      "tenant,app,enabled,offered", "", "Apps"),
	# The other way a Restricted space reaches a workspace: a string somebody
	# types. Two screens rather than one, because the question is usually "who
	# has RUA and how did they get it", which is a list across codes rather
	# than a list inside one. `docs/MARKETPLACE.md` §4.
	_list("claims", "Claim codes", "lucide-wallet", "Space Claim Code",
	      "claim_code,app,uses_allowed,uses_spent,expires_on,enabled", "",
	      "Apps"),
	_list("redemptions", "Claims made", "lucide-receipt",
	      "Space Claim Redemption",
	      "claim_code,tenant,app,redeemed_by,redeemed_on", "", "Apps"),

	# ----- AI: two catalogues nobody authors, and what they cost ------------ #
	_list("models", "Models", "lucide-sparkles", "AI Model",
	      "display_name,provider,capability,status,is_recommended", "status",
	      "AI"),
	_list("features", "Features", "lucide-sparkles", "AI Feature",
	      "feature_key,label,app,capability,status", "status", "AI"),
	_list("usage", "Usage", "lucide-chart-line", "AI Usage Record",
	      "tenant,feature,model,credits_charged,cost_usd", "", "AI"),

	# ----- Trail: what happened, and who did it ---------------------------- #
	_list("lifecycle", "Lifecycle", "lucide-clock", "Tenant Lifecycle Event",
	      "tenant,event,occurred_on,to_status,triggered_by,reason", "event",
	      "Trail"),
	_list("support", "Support logins", "lucide-stethoscope", "Support Login",
	      "tenant,site,operator,reason,logged_in_on,succeeded", "", "Trail"),
	# A workspace's own roles. Read here rather than written: the workspace
	# builds these itself, and an operator's reason to look is a support call
	# about who can reach what.
	_list("roles", "Workspace roles", "lucide-user-round", "Workspace Role",
	      "tenant,role_label,is_active,created_by_email", "", "Trail"),

	# ----- Setup ------------------------------------------------------------ #
	#
	# Readiness is the seventh question — "is this control plane finished" —
	# asked once at bring-up and then when something breaks.
	#
	# `press` and `tenant` carry the same heading and are not meant to be
	# navigated to: the first is reached from Frappe Cloud's own screens and
	# the second from a workspace record through a declared action
	# (`entitlements/actions.py`). They are on the rail because the shell
	# resolves a `component` from the manifest.
	{
		"screen": "readiness", "label": "Readiness", "icon": "lucide-file-text",
		"component": "oneadmin/readiness", "screen_group": "Setup",
	},
	{
		"screen": "press", "label": "Frappe Cloud", "icon": "lucide-factory",
		"component": "oneadmin/press", "screen_group": "Setup",
	},
	{
		"screen": "tenant", "label": "Workspace", "icon": "lucide-wrench",
		"component": "oneadmin/tenant", "screen_group": "Setup",
	},
]
