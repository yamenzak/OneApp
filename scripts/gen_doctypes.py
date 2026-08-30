"""Generate Frappe doctype JSON for oneapp_control.

Doctype JSON is verbose and easy to get subtly wrong by hand. This declares the
schema compactly and emits canonical JSON, so the shape stays consistent across
every doctype and a field change is a one-line edit.

Run: python3 scripts/gen_doctypes.py
"""

import json
import os

from ai_capabilities import OPTIONS as AI_CAPABILITY_OPTIONS
from app_icons import SPACE_ICONS, DEFAULT_SPACE_ICON

APPS = {
    # key -> (app package dir, module directory, Frappe module name)
    "control": ("oneapp_control", "control_plane", "Control Plane"),
    # "OneApp Core" and not "OneSpace Core": a Frappe module name is plumbing —
    # it has to match `apps/oneapp/oneapp/modules.txt` and the directory beside
    # it, and renaming one is a migration on every site rather than an edit
    # here. The product-facing names are the labels, and those did move.
    "tenant": ("oneapp", "oneapp_core", "OneApp Core"),
}
APPS_ROOT = os.path.join(os.path.dirname(__file__), "..", "apps")
STAMP = "2026-08-29 00:00:00.000000"

MANAGER_PERMS = [
    {
        "create": 1, "delete": 1, "email": 1, "export": 1, "print": 1, "read": 1,
        "report": 1, "role": "System Manager", "share": 1, "write": 1,
    }
]
READONLY_PERMS = [
    {"read": 1, "report": 1, "export": 1, "role": "System Manager"}
]


def f(fieldname, fieldtype="Data", label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype,
         "label": label if label is not None else fieldname.replace("_", " ").title()}
    d.update(kw)
    return d


def section(name, label=""):
    return {"fieldname": name, "fieldtype": "Section Break", "label": label}


def column(name):
    return {"fieldname": name, "fieldtype": "Column Break"}


DOCTYPES = {}


def doctype(name, fields, autoname=None, perms=None, app="control", **kw):
    DOCTYPES[name] = dict(name=name, fields=fields, autoname=autoname,
                          perms=perms or MANAGER_PERMS, app=app, **kw)


# --------------------------------------------------------------------------- #
# Shard — where a tenant's site physically lives.
# --------------------------------------------------------------------------- #
doctype(
    "Shard",
    autoname="field:shard_name",
    title_field="shard_name",
    fields=[
        f("shard_name", reqd=1, unique=1, in_list_view=1,
          description="Human label, e.g. hetzner-cpx42-01"),
        f("status", "Select", options="Active\nDraining\nFull\nMaintenance",
          default="Active", reqd=1, in_list_view=1, in_standard_filter=1),
        f("deploy_ring", "Select", options="Canary\nWave 1\nWave 2\nFleet",
          default="Fleet", reqd=1, in_list_view=1,
          description="Migration order. Canary carries internal tenants and goes first."),
        f("environment", "Select", options="Production\nStaging",
          default="Production", reqd=1, in_standard_filter=1,
          description="Tenants placed here inherit this. Staging shards are ours "
                      "to break — the dev tooling patches and redeploys their "
                      "bench, and refuses any bench carrying a Production "
                      "tenant. Default is the safe one."),
        column("cb_press"),
        f("accepts_new_tenants", "Check", default="1",
          description="Uncheck to stop the allocator placing new tenants here."),
        f("capacity_tenants", "Int", default="30",
          description="Soft cap. MariaDB is the real ceiling; see docs/ARCHITECTURE.md."),
        f("tenant_count", "Int", default="0", read_only=1, in_list_view=1),
        section("sec_press", "Frappe Cloud"),
        f("press_server", label="Press Server",
          description="Server name in press, e.g. n1.frappe.cloud"),
        f("press_release_group", label="Press Bench Group", reqd=1),
        f("press_cluster", label="Press Cluster"),
        f("region", "Link", options="Region", reqd=1, in_list_view=1, in_standard_filter=1,
          description="What customers choose at signup. Several shards may share "
                      "a region."),
        f("press_version", label="Press Version", default="Nightly", reqd=1,
          description="Must match the bench group's version exactly. Without it "
                      "press cannot match the bench on a dedicated server and "
                      "falls back to its public marketplace path, which fails."),
        column("cb_press2"),
        f("domain", default="4dl.app", reqd=1,
          description="Root domain tenants are addressed on."),
        f("domain_mode", "Select", options="Per-tenant\nWildcard", default="Per-tenant",
          reqd=1,
          description="Wildcard: sites are created directly on the root domain, "
                      "one certificate covers all. Per-tenant: sites are created on "
                      "the Frappe Cloud default domain and the root domain is attached "
                      "per site, which costs one Let's Encrypt certificate each."),
        f("press_default_domain", label="Press Default Domain",
          description="Frappe Cloud's own root domain for this server, used to create "
                      "sites in Per-tenant mode. e.g. frappe.cloud"),
        f("press_site_plan", label="Default Press Site Plan"),
        f("standby_target", "Int", default="0",
          description="Warm sites to keep ready here. Zero disables the pool for "
                      "this shard, and signup falls back to creating on demand."),
        f("site_apps", default="frappe,erpnext,oneapp", reqd=1,
          description="Apps installed on sites created here, comma separated. Must "
                      "all be present on the bench group."),
        section("sec_notes"),
        f("notes", "Small Text"),
    ],
)

# --------------------------------------------------------------------------- #
# Plan — quotas only. Never feature flags.
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Plan Price — every Stripe Price a plan has ever had.
#
# Stripe Prices are immutable in amount and currency, so changing what a plan
# costs means minting a new Price and leaving the old one billing whoever is
# already on it. That is how price grandfathering works, and it only works if
# the old ids survive: this table is both the history an operator reads and the
# reverse lookup a webhook needs to answer "which plan is this price?" when a
# subscription changes underneath us.
# --------------------------------------------------------------------------- #
doctype(
    "Plan Price",
    istable=1,
    fields=[
        f("interval", "Select", options="Monthly\nYearly", reqd=1, in_list_view=1),
        f("stripe_price_id", label="Stripe Price ID", in_list_view=1, read_only=1),
        f("unit_amount", "Currency", in_list_view=1, read_only=1,
          description="What Stripe charges. Ours to display, Stripe's to enforce."),
        f("currency", "Data", read_only=1),
        column("cb_price_state"),
        f("is_current", "Check", default="0", in_list_view=1, read_only=1,
          description="The price new subscriptions are sold at. Exactly one per "
                      "interval; the rest are grandfathered."),
        f("created_on", "Datetime", read_only=1),
        f("archived_on", "Datetime", read_only=1,
          description="Archived in Stripe, so it cannot be sold again. Existing "
                      "subscriptions keep billing on it — that is the point."),
    ],
)


doctype(
    "Plan",
    autoname="field:plan_code",
    title_field="plan_name",
    fields=[
        f("plan_code", reqd=1, unique=1, description="Stable id, e.g. personal-starter"),
        f("plan_name", reqd=1, in_list_view=1),
        f("audience", "Select", options="Personal\nCommercial", reqd=1,
          in_list_view=1, in_standard_filter=1),
        f("is_active", "Check", default="1"),
        f("sort_order", "Int", default="0"),
        column("cb_price"),
        f("currency", "Link", options="Currency", default="USD"),
        f("price_monthly", "Currency", in_list_view=1),
        f("price_yearly", "Currency"),
        # Written by the Stripe sync, never by hand. Saving a plan creates the
        # product and prices it needs; a changed amount mints a new price and
        # archives the old one. Two people typing the same id into two systems
        # is how a page advertises one number while the card is charged another.
        f("stripe_product_id", label="Stripe Product ID", read_only=1),
        f("stripe_price_id_monthly", label="Stripe Price ID (Monthly)", read_only=1,
          description="The current monthly price. History is in Prices below."),
        f("stripe_price_id_yearly", label="Stripe Price ID (Yearly)", read_only=1),
        f("sync_error", "Small Text", read_only=1,
          description="Why the last sync to Stripe did not finish. Saving again "
                      "retries; the plan stays sellable on whatever prices it "
                      "already has."),
        section("sec_quota", "Quotas"),
        f("storage_gb", "Int", default="10", description="Hard cap enforced at upload."),
        f("max_users", "Int", default="3"),
        column("cb_quota"),
        f("monthly_credit_grant", "Float", default="0",
          description="Non-rollover. Expires at the end of each billing period."),
        f("background_workers", "Int", default="1",
          description="Concurrent background jobs. Caps what one workspace can "
                      "take from a shared bench — the fleet cannot preempt, so it "
                      "limits instead."),
        f("database_gb", "Int", default="2",
          description="Database size cap. Separate from files: this is the one "
                      "that constrains how many sites fit on a server."),
        section("sec_press_plan"),
        f("press_site_plan", label="Press Site Plan",
          description="Overrides the shard default when set."),
        f("description", "Small Text"),
        section("sec_prices", "Prices"),
        f("prices", "Table", options="Plan Price", read_only=1,
          description="Every Stripe price this plan has had. Subscriptions sold "
                      "on an older one keep billing on it."),
    ],
)

# --------------------------------------------------------------------------- #
# OneSpace Space — the registry the SPA launcher reads.
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# OneSpace Space Screen — one screen an app puts in front of a customer.
#
# An app is configuration before it is code. A screen names a doctype and the
# fields worth showing, and OneSpace renders the list and the record from the
# tenant site's own metadata — so a new app is a registration plus its doctypes,
# with no OneSpace release and nothing hand-written per app.
#
# `component` is the way out for a screen that generic list-and-record cannot
# be. It names a component the SPA has registered; everything else on the row is
# then the app's business rather than ours.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Space Screen",
    istable=1,
    fields=[
        f("screen", reqd=1, in_list_view=1,
          description="Slug in the URL, e.g. `invoices`. Stable: it is what a "
                      "bookmark points at."),
        f("label", reqd=1, in_list_view=1, description="Shown in the app's navigation."),
        f("icon", "Select", options="\n".join(SPACE_ICONS),
          default="lucide-layout-grid"),
        column("cb_view_source"),
        f("document_type", label="Doctype", in_list_view=1,
          description="What the list shows. Data rather than a Link: the doctype "
                      "belongs to a tenant site and need not exist here."),
        f("fields", "Small Text",
          description="Comma-separated fieldnames for the columns. Labels and "
                      "types come from the tenant site's own metadata, so this "
                      "is the only thing worth writing down. Empty shows the "
                      "doctype's own list fields."),
        f("component",
          description="Escape hatch: a component the SPA registered under "
                      "`spaceCode/screen`. Set this and the doctype above is ignored."),
        f("view_types", default="list",
          description="How this screen may be looked at, in order — `list`, "
                      "`board`, `calendar`, `grid`, `map`. The first is what "
                      "it opens with. Anything the SPA does not build yet is "
                      "ignored rather than refused, so a manifest can name one "
                      "before it ships."),
        f("view_settings", "Code", options="JSON",
          description='Per type, what that type needs: {"board": '
                      '{"column_field": "status"}, "calendar": {"start_field": '
                      '"date"}}. Every fieldname in here is checked against the '
                      'doctype like any other.'),
        section("sec_view_query"),
        f("filters", "Code", options="JSON",
          description='Always applied, e.g. {"status": "Open"}.'),
        column("cb_view_sort"),
        f("order_by", default="modified desc"),
    ],
)


doctype(
    "OneSpace Space",
    autoname="field:space_code",
    title_field="space_label",
    fields=[
        f("space_code", reqd=1, unique=1, description="Stable id, e.g. crm"),
        f("space_label", reqd=1, in_list_view=1),
        f("module", reqd=1, in_list_view=1,
          description="Frappe module inside the oneapp app that implements this."),
        f("is_active", "Check", default="1"),
        column("cb_app"),
        f("availability", "Select", options="General\nRestricted", default="General",
          reqd=1, in_list_view=1, in_standard_filter=1,
          description="General: every tenant. Restricted: only via Space Entitlement."),
        f("role_name", reqd=1,
          description="Frappe Role gating this app's doctypes. Entitlement grants "
                      "and revokes this role, so enforcement is native permissions "
                      "rather than a bespoke hook."),
        section("sec_views", "Screens"),
        f("screens", "Table", options="OneSpace Space Screen",
          description="What the customer sees. An app with none of these is an "
                      "entitlement with no interface, which is a real thing to "
                      "be — it still grants its roles and doctypes."),
        section("sec_manifest", "Doctypes"),
        f("doctypes", "Table", options="OneSpace Space Doctype",
          description="Everything this app exposes. One list, three jobs: the "
                      "DocPerms we write for our own roles, what an entitlement "
                      "grants, and the allowlist a customer's custom role may "
                      "draw from. A doctype in no manifest is reachable by "
                      "nobody, without anyone having to remember to exclude it."),
        # A Select, not free text: an icon name that exists only in the
        # database is in no source file, so Tailwind's JIT emits no CSS
        # for it and the launcher renders an empty box. The options come
        # from scripts/app_icons.py, which also writes the SPA's literals.
        f("icon", "Select", options="\n".join(SPACE_ICONS),
          default="lucide-layout-grid",
          description="Rendered by the launcher and the app sidebar."),
        f("logo", "Attach Image",
          description="Shown on the rail. Without one the icon is drawn "
                      "instead."),
        f("sort_order", "Int", default="0"),
        section("sec_desc"),
        f("description", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace Space Doctype — the manifest row.
#
# We ignore the roles ERPNext, HRMS and Payments ship with: we use those apps for
# the logic they implement, not for their idea of who an "Accounts Manager" is.
# Our own roles therefore start with no permissions, and these rows are where
# they come from. See DECISIONS §8.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Space Doctype",
    istable=1,
    fields=[
        f("document_type", "Data", reqd=1, in_list_view=1,
          label="Doctype",
          description="Name of the doctype, e.g. Sales Invoice."),
        f("access", "Select", options="Read\nWrite\nManage", default="Write",
          reqd=1, in_list_view=1,
          description="Read: see it. Write: create and edit. Manage: also "
                      "delete, submit and cancel."),
        column("cb_manifest_row"),
        f("if_owner", "Check", default="0", in_list_view=1,
          description="Restrict to documents the user created. For per-user "
                      "records inside a shared workspace."),
        f("notes", "Small Text",
          description="Why this doctype is exposed, when it is not obvious — "
                      "usually a dependency of something the UI does show."),
    ],
)

# --------------------------------------------------------------------------- #
# Support Login — every time an operator signed in to a customer's workspace.
#
# Break-glass access to someone else's data. The record is written *before* the
# session is handed over, so a login that succeeds is always logged: writing it
# afterwards would lose exactly the ones worth having if anything failed in
# between. `reason` is required for the same purpose — an audit trail of
# unexplained entries is a list, not an account.
# --------------------------------------------------------------------------- #
doctype(
    "Support Login",
    autoname="hash",
    fields=[
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1, read_only=1),
        f("site", "Data", read_only=1, in_list_view=1),
        f("operator", "Link", options="User", reqd=1, in_list_view=1,
          in_standard_filter=1, read_only=1),
        column("cb_support_login"),
        f("reason", "Small Text", reqd=1, in_list_view=1,
          description="Why this workspace was entered. Required: an audit trail "
                      "of unexplained entries is a list, not an account."),
        f("logged_in_on", "Datetime", reqd=1, read_only=1),
        # Set after Frappe Cloud hands over the session. The row is written
        # first so a successful login can never go unrecorded, which leaves the
        # window where the record exists and the login did not happen — this is
        # what tells the two apart, rather than the reader assuming.
        f("succeeded", "Check", default="0", read_only=1, in_list_view=1),
    ],
)

# --------------------------------------------------------------------------- #
# Tenant Member — who else may sign in to a workspace.
#
# Held here rather than on the tenant site because the control plane has no way
# to write into a tenant's database: the signed sync is the only channel, and it
# runs one way. So an invite is a row here, and the tenant site reconciles its
# own Users against this list on every sync — the same route the owner account
# already takes.
#
# The owner is not a row. `Tenant.owner_email` is load-bearing in provisioning
# and billing, so it stays authoritative for that one seat and this table holds
# everyone else. Seats used = 1 + rows.
# --------------------------------------------------------------------------- #
doctype(
    "Tenant Member",
    istable=1,
    fields=[
        f("email", "Data", options="Email", reqd=1, in_list_view=1),
        f("full_name", "Data", in_list_view=1,
          description="Shown in the workspace. The member can change it themselves "
                      "once they have signed in."),
        column("cb_member"),
        f("access", "Select", options="Member\nAdmin", default="Member", reqd=1,
          in_list_view=1,
          description="Member: use the apps the workspace is entitled to. Admin: "
                      "also manage the workspace — the owner's role, without "
                      "being the billing contact."),
        f("invited_on", "Datetime", read_only=1),
    ],
)

# --------------------------------------------------------------------------- #
# Tenant
# --------------------------------------------------------------------------- #
doctype(
    "Tenant",
    autoname="field:tenant_slug",
    title_field="tenant_name",
    allow_rename=0,
    fields=[
        f("tenant_slug", reqd=1, unique=1, in_list_view=1,
          description="Subdomain label. Immutable once provisioned."),
        f("tenant_name", reqd=1, in_list_view=1),
        f("status", "Select",
          options="Draft\nProvisioning\nActive\nSuspended\nArchived\nFailed",
          default="Draft", reqd=1, in_list_view=1, in_standard_filter=1),
        f("environment", "Select", options="Production\nStaging",
          default="Production", reqd=1, in_standard_filter=1,
          description="Staging tenants are ours to break: the dev tooling may "
                      "patch and redeploy the bench they sit on. It refuses to "
                      "touch a bench carrying a Production tenant, so the "
                      "default is the safe one."),
        f("owner_email", "Data", options="Email", reqd=1),
        f("owner_user", "Link", options="User", read_only=1,
          description="Control-plane account for the workspace owner. Customer "
                      "endpoints resolve the tenant from this, never from a "
                      "parameter — that is what keeps one customer out of "
                      "another's billing."),
        column("cb_place"),
        f("shard", "Link", options="Shard", in_standard_filter=1),
        f("region", "Link", options="Region", description="Chosen at signup."),
        f("storage_bucket", "Link", options="Storage Bucket", read_only=1),
        f("storage_jurisdiction", "Select", options="Global\nEU", default="Global",
          description="Fixed at signup; moving objects between jurisdictions later "
                      "is a migration, not a setting."),
        f("site_name", read_only=1, in_list_view=1,
          description="Permanent internal address. Never the custom domain."),
        f("press_site", label="Press Site", read_only=1),
        f("primary_domain", description="Customer-owned domain, once verified."),
        section("sec_plan", "Plan and billing"),
        f("plan", "Link", options="Plan", in_standard_filter=1),
        f("subscription", "Link", options="Subscription", read_only=1),
        f("customer", "Link", options="Customer",
          description="ERPNext Customer. Created on first successful payment."),
        column("cb_plan"),
        f("trial_ends_on", "Date"),
        f("provisioned_on", "Datetime", read_only=1),
        f("suspended_on", "Datetime", read_only=1),
        f("archived_on", "Datetime", read_only=1),
        section("sec_usage", "Usage"),
        f("storage_used_bytes", "Float", default="0", read_only=1),
        f("database_used_bytes", "Float", default="0", read_only=1,
          description="Reported by the site. The resource that actually threatens "
                      "the server, so it is capped like file storage."),
        f("extra_storage_gb", "Int", default="0",
          description="Purchased add-on, added to the plan quota. Does not expire "
                      "— storage is never paid for with AI credits, which would "
                      "make a large upload silently drain the AI budget."),
        column("cb_usage"),
        f("user_count", "Int", default="0", read_only=1),
        f("usage_synced_on", "Datetime", read_only=1),
        section("sec_members", "People"),
        # Everyone but the owner, who is `owner_email` above. The tenant site
        # creates and disables Users from this on every sync, because nothing
        # here can reach into its database directly.
        f("members", "Table", options="Tenant Member",
          description="Who else may sign in. Seats used is this plus the owner, "
                      "and the plan's max_users is what caps it."),
        section("sec_secret", "Integration"),
        f("hmac_secret", "Password",
          description="Shared secret for signed calls with this tenant's site."),
        f("suspended_reason", "Small Text"),
    ],
)

# --------------------------------------------------------------------------- #
# Subscription — mirrors Stripe. Stripe owns the schedule; this reflects it.
# --------------------------------------------------------------------------- #
doctype(
    "Subscription",
    autoname="naming_series:",
    fields=[
        f("naming_series", "Select", options="SUB-.YYYY.-", default="SUB-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("plan", "Link", options="Plan", reqd=1, in_list_view=1),
        f("status", "Select",
          options="Incomplete\nTrialing\nActive\nPast Due\nCanceled",
          default="Incomplete", reqd=1, in_list_view=1, in_standard_filter=1),
        f("interval", "Select", options="Monthly\nYearly", default="Monthly", reqd=1),
        column("cb_stripe"),
        f("stripe_customer_id", label="Stripe Customer ID", read_only=1),
        f("stripe_subscription_id", label="Stripe Subscription ID", read_only=1,
          unique=1),
        f("cancel_at_period_end", "Check", default="0"),
        f("last_invoice_id", label="Last Stripe Invoice ID", read_only=1),
        section("sec_period", "Current period"),
        f("current_period_start", "Datetime", read_only=1),
        f("current_period_end", "Datetime", read_only=1,
          description="Non-rollover grants expire here."),
        column("cb_period"),
        f("last_grant_period_end", "Datetime", read_only=1,
          description="Guards against double-granting on webhook replay."),
        # ------------------------------------------------------------------ #
        # The plan's terms as they were when this subscription was sold.
        #
        # Enforcement reads these, not the Plan doc. Quotas read live meant that
        # editing a plan silently re-quotaed everyone already on it — someone who
        # bought 50GB could wake up with 20GB because a price sheet was being
        # tidied. Stripe already grandfathers the price by leaving the old Price
        # on the subscription; this is the same promise for everything the price
        # bought.
        #
        # Same field names as Plan, so the copy is field-for-field and a reader
        # can see at a glance that nothing was reinterpreted on the way across.
        # `oneapp_control.billing.quotas` is the only thing that reads them.
        # ------------------------------------------------------------------ #
        section("sec_terms", "Plan terms at purchase"),
        f("storage_gb", "Int", default="0"),
        f("database_gb", "Int", default="0"),
        f("max_users", "Int", default="0"),
        column("cb_terms"),
        f("monthly_credit_grant", "Float", default="0"),
        f("background_workers", "Int", default="0"),
        f("press_site_plan", label="Press Site Plan"),
        f("terms_captured_on", "Datetime", read_only=1,
          description="When these were copied from the plan. Empty means this "
                      "subscription predates the snapshot and still reads the "
                      "plan live."),
    ],
)

# --------------------------------------------------------------------------- #
# Space Entitlement
# --------------------------------------------------------------------------- #
doctype(
    "Space Entitlement",
    autoname="hash",
    fields=[
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("app", "Link", options="OneSpace Space", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("enabled", "Check", default="1", in_list_view=1),
        column("cb_ent"),
        f("granted_on", "Datetime", read_only=1),
        f("note", "Small Text"),
    ],
)

# --------------------------------------------------------------------------- #
# Provisioning Job — explicit, resumable state machine over the press API.
# --------------------------------------------------------------------------- #
doctype(
    "Provisioning Job",
    autoname="naming_series:",
    fields=[
        f("naming_series", "Select", options="PJOB-.YYYY.-", default="PJOB-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", in_list_view=1, in_standard_filter=1,
          description="Empty for standby pool builds, which belong to no tenant yet."),
        f("action", "Select",
          options=("Create Site\nSuspend Site\nResume Site\nBackup Site\nArchive Site\n"
                   "Add Domain\nSet Primary Domain\nChange Plan\nMigrate Site\n"
                   "Create Standby Site\nClaim Standby Site"),
          reqd=1, in_list_view=1, in_standard_filter=1),
        f("state", "Select",
          options=("Requested\nRunning\nAwaiting Agent\nBootstrapping\nSucceeded\n"
                   "Failed\nCancelled"),
          default="Requested", reqd=1, in_list_view=1, in_standard_filter=1),
        f("step", read_only=1,
          description="Resume cursor. Each step is idempotent."),
        column("cb_job"),
        f("idempotency_key", unique=1, read_only=1,
          description="Prevents a retry after timeout from creating a second site."),
        f("attempts", "Int", default="0", read_only=1),
        f("next_retry_at", "Datetime", read_only=1),
        f("started_at", "Datetime", read_only=1),
        f("finished_at", "Datetime", read_only=1),
        section("sec_press_job", "Press"),
        f("press_site", label="Press Site", read_only=1),
        f("agent_job_id", label="Agent Job ID", read_only=1),
        f("agent_job_status", read_only=1),
        column("cb_press_job"),
        f("payload", "Code", options="JSON"),
        section("sec_err"),
        f("last_error", "Text", read_only=1),
    ],
)

# --------------------------------------------------------------------------- #
# Credit Ledger Entry — append-only. Balance is a sum, never a stored field.
# --------------------------------------------------------------------------- #
doctype(
    "Credit Ledger Entry",
    autoname="naming_series:",
    perms=READONLY_PERMS,
    fields=[
        f("naming_series", "Select", options="CLE-.YYYY.-", default="CLE-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("entry_type", "Select",
          options="Grant\nPurchase\nSpend\nRefund\nExpiry\nAdjustment",
          reqd=1, in_list_view=1, in_standard_filter=1),
        f("credits", "Float", reqd=1, in_list_view=1,
          description="Signed. Positive adds, negative consumes."),
        column("cb_cle"),
        f("expires_on", "Date", in_list_view=1,
          description="Grants only. Blank means it never expires."),
        f("consumed_from", "Link", options="Credit Ledger Entry",
          description="For Spend and Expiry rows, the grant they draw down."),
        f("reservation", "Link", options="Credit Reservation"),
        section("sec_src", "Source"),
        f("source_doctype", "Link", options="DocType"),
        f("source_name", "Dynamic Link", options="source_doctype"),
        column("cb_src"),
        f("remarks", "Small Text"),
    ],
)

# --------------------------------------------------------------------------- #
# Credit Reservation — reserve/commit so concurrent spend cannot overdraw.
# --------------------------------------------------------------------------- #
doctype(
    "Credit Reservation",
    autoname="naming_series:",
    fields=[
        f("naming_series", "Select", options="CRES-.YYYY.-", default="CRES-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("status", "Select", options="Open\nCommitted\nReleased\nExpired",
          default="Open", reqd=1, in_list_view=1, in_standard_filter=1),
        f("credits_reserved", "Float", reqd=1, in_list_view=1),
        f("credits_committed", "Float", default="0", read_only=1),
        column("cb_res"),
        f("purpose", description="e.g. ai:chat, ai:embedding"),
        f("expires_at", "Datetime", reqd=1,
          description="Swept and released if still Open past this time."),
        f("committed_on", "Datetime", read_only=1),
        f("released_on", "Datetime", read_only=1),
    ],
)

# --------------------------------------------------------------------------- #
# Settings (Single)
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Control Settings",
    issingle=1,
    fields=[
        section("sec_press_set", "Frappe Cloud"),
        f("press_api_url", label="Press API URL", default="https://cloud.frappe.io",
          description="Canonical host. frappecloud.com 308-redirects here and the "
                      "redirect drops the Authorization header."),
        f("press_api_key", label="Press API Key"),
        f("press_api_secret", "Password", label="Press API Secret"),
        column("cb_set1"),
        f("default_shard", "Link", options="Shard"),
        f("tenant_domain", default="4dl.app", reqd=1),
        f("control_plane_url", description="Base URL tenant sites call back on."),
        section("sec_slug", "Tenant naming"),
        f("reserved_slugs", "Small Text",
          description="Additional comma or newline separated slugs to block."),
        section("sec_stripe", "Stripe"),
        f("stripe_webhook_secret", "Password",
          description="Signing secret for the Stripe webhook endpoint."),
        column("cb_stripe_set"),
        f("credits_per_currency_unit", "Float", default="100",
          description="Credits granted per unit of currency on a pack purchase."),
        # Control-plane only. Deliberately NOT pushed to bench groups: a token
        # that can rewrite the tenant routing map has no business sitting in
        # config that every tenant site can read.
        section("sec_cfkv", "Cloudflare KV (control plane only)"),
        f("cf_kv_namespace_id", label="KV Namespace ID",
          description="Namespace the email worker reads to route inbound mail."),
        f("cf_kv_token", "Password", label="KV API Token",
          description="Needs Workers KV Storage: Edit. Never pushed to tenant benches."),
        column("cb_cfkv"),
        f("cf_kv_account_id", label="Cloudflare Account ID",
          description="Falls back to the account id below when blank."),
        section("sec_cfdns", "Cloudflare DNS (control plane only)"),
        f("cf_zone_id", label="DNS Zone ID",
          description="Zone for the tenant root domain. Only needed in Per-tenant mode."),
        f("cf_dns_token", "Password", label="DNS API Token",
          description="Needs Zone.DNS: Edit. Never pushed to tenant benches."),
        # ------------------------------------------------------------------ #
        # Everything below is pushed to a shard's bench group as common site
        # config, where every tenant site inherits it through frappe.conf.
        # Set once here, propagated with "Push Bench Config".
        # ------------------------------------------------------------------ #
        section("sec_bench", "Tenant bench config"),
        f("bench_config_html", "HTML",
          options="<p class='text-muted'>These values are pushed to each shard's "
                  "bench group as common site config. Every tenant site inherits "
                  "them, so a rotation here reaches all tenants without touching "
                  "any site.</p>"),
        section("sec_r2", "R2 storage"),
        f("r2_account_id", label="R2 Account ID"),
        f("r2_bucket", label="R2 Bucket"),
        f("r2_public_base", label="R2 Public Base URL",
          description="e.g. https://cdn.4dl.app"),
        column("cb_r2"),
        f("r2_access_key", label="R2 Access Key"),
        f("r2_secret_key", "Password", label="R2 Secret Key"),
        f("r2_admin_token", "Password", label="R2 Admin API Token",
          description="Creates buckets, so it is control-plane only and never "
                      "pushed to a bench. The S3 keys above are what tenant "
                      "sites use to read and write objects."),
        f("bucket_max_tenants", "Int", default="200",
          description="Rotation threshold for new buckets. Bounded buckets bound "
                      "the blast radius of losing one."),
        section("sec_mail", "Email"),
        f("cf_email_token", "Password", label="Cloudflare Email Token",
          description="API token with Email Sending: Edit."),
        f("mail_domain", default="mail.4dl.app"),
        column("cb_mail"),
        f("mail_hourly_limit", "Int", default="200",
          description="Per-tenant outbound cap. Protects shared sending reputation."),
        section("sec_ai", "AI Gateway"),
        f("cf_account_id", label="Cloudflare Account ID"),
        f("ai_gateway", label="AI Gateway Name", default="oneapp"),
        f("ai_gateway_token", "Password", label="AI Gateway Token"),
        column("cb_ai"),
        f("google_ai_key", "Password", label="Google AI Studio Key"),
        f("cf_api_token", "Password", label="Cloudflare API Token",
          description="For Workers AI."),
        f("ai_markup_multiplier", "Float", default="1.5",
          description="Applied to measured provider cost when converting to credits. "
                      "A model may override it; see AI Model."),
        f("ai_catalogue_synced_on", "Datetime", read_only=1,
          description="Last successful model and price sync."),
        f("ai_catalogue_note", "Small Text", read_only=1,
          description="What the last sync did, and what it could not parse."),
    ],
)


# --------------------------------------------------------------------------- #
# AI Model Price — one rate, in the unit the provider actually bills in.
#
# There is no single unit. Gemini bills images and speech in tokens; Workers AI
# bills images per 512x512 tile and per diffusion step, and speech per audio
# minute. A schema with `input_price` and `output_price` can only hold the first
# of those, which is how a text-shaped price table quietly becomes wrong the day
# someone generates a picture.
#
# The rate is stored the way the provider publishes it — cost for N units, not
# cost per unit — because "$0.75 per 1,000,000 tokens" survives a round trip
# through a Float and 0.00000075 does not.
# --------------------------------------------------------------------------- #
doctype(
    "AI Model Price",
    istable=1,
    fields=[
        f("kind", "Select", reqd=1, in_list_view=1,
          options="Input\nCached Input\nCache Write\nOutput\nReasoning\nRequest\nSearch",
          description="What is being charged for. Reasoning is Gemini's thinking "
                      "tokens, which bill at the output rate but are counted "
                      "separately."),
        f("modality", "Select", reqd=1, default="Text", in_list_view=1,
          options="Text\nImage\nAudio\nVideo\nFile\nAny",
          description="Which modality of that kind. A multimodal model has "
                      "several rows here and they do not cost the same."),
        f("unit", "Select", reqd=1, default="Token", in_list_view=1,
          options="Token\nImage\nTile\nStep\nSecond\nMinute\nCharacter\nRequest\nSearch",
          description="What the provider counts."),
        column("cb_price_rate"),
        f("cost_usd", "Float", precision="9", reqd=1, in_list_view=1,
          description="USD for `per_units` of them."),
        f("per_units", "Int", default="1000000", reqd=1, in_list_view=1,
          description="1,000,000 for token rates, 1 for an image or a minute."),
        f("tier", "Select", options="Standard\nBatch\nFlex\nPriority",
          default="Standard", reqd=1,
          description="Only Standard is charged unless a call asks for another."),
        section("sec_price_window"),
        f("effective_from", "Date",
          description="Providers publish dated rate changes. The row in effect "
                      "on the day of the call is the one that prices it."),
        f("effective_to", "Date"),
        column("cb_price_src"),
        f("note", "Data", description="The published wording this row came from."),
    ],
)


# --------------------------------------------------------------------------- #
# AI Model — the catalogue, synced rather than typed.
#
# Providers add models weekly and re-price them without telling anyone. A
# hand-maintained table is wrong within a month and nobody notices until a
# margin does. So this is fetched: Cloudflare's model search API and Google's
# models API for what exists and what it can do, their published price pages for
# what it costs.
#
# A model nothing could price lands as Needs Review and is not sellable. That is
# deliberate: the failure mode of a default price is charging a customer a
# number we made up.
# --------------------------------------------------------------------------- #
doctype(
    "AI Model",
    autoname="field:model_key",
    title_field="display_name",
    fields=[
        f("model_key", reqd=1, unique=1,
          description="provider:model_id. Set on sync."),
        f("display_name", in_list_view=1),
        f("provider", "Select", options="workers-ai\ngoogle-ai-studio", reqd=1,
          in_list_view=1, in_standard_filter=1,
          description="The AI Gateway provider slug, used verbatim in the URL."),
        f("model_id", reqd=1,
          description="What goes in the request, e.g. @cf/meta/llama-3.3-70b-instruct-fp8-fast."),
        f("status", "Select", reqd=1, default="Needs Review", in_list_view=1,
          in_standard_filter=1,
          options="Available\nPreview\nNeeds Review\nDeprecated\nRetired",
          description="Only Available and Preview models can be chosen or "
                      "called. Needs Review means the sync could not price it."),
        column("cb_model_cap"),
        f("capability", "Select", reqd=1, default="Text Generation", in_list_view=1,
          in_standard_filter=1, options=AI_CAPABILITY_OPTIONS,
          description="What the model is for. A feature declares the capability "
                      "it needs and only matching models are offered."),
        f("input_modalities", default="text",
          description="Comma-separated: text, image, audio, video, file."),
        f("output_modalities", default="text"),
        f("is_recommended", "Check", default="0",
          description="Pre-selected for features that do not pin a model."),
        section("sec_model_limits", "Limits and features"),
        f("context_window", "Int"),
        f("max_output_tokens", "Int"),
        f("supports_tools", "Check", default="0"),
        column("cb_model_feat"),
        f("supports_json", "Check", default="0", label="Supports Structured Output"),
        f("supports_reasoning", "Check", default="0"),
        f("supports_streaming", "Check", default="0"),
        section("sec_model_price", "Pricing"),
        f("markup_override", "Float", default="0",
          description="Multiplier applied instead of the global one. 0 uses the global."),
        f("prices", "Table", options="AI Model Price"),
        section("sec_model_sync", "Sync"),
        f("source", "Select", default="Manual",
          options="Cloudflare API\nCloudflare Docs\nGoogle API\nGoogle Docs\nManual"),
        f("last_synced", "Datetime", read_only=1),
        f("deprecation_date", "Date", read_only=1),
        column("cb_model_sync"),
        f("sync_note", "Small Text", read_only=1,
          description="Why this model is where it is — including what could not "
                      "be priced."),
        f("description", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# AI Feature — what the apps declare, reported up rather than configured here.
#
# Features live in app code behind @ai_feature, which is the only place that
# knows a feature exists at all. Tenant sites report their registry on sync and
# this is the upsert of it, so an operator sees the whole surface without anyone
# maintaining a list, and can pin a default model or take a feature off the air
# without a deploy.
# --------------------------------------------------------------------------- #
doctype(
    "AI Feature",
    autoname="field:feature_key",
    title_field="label",
    fields=[
        f("feature_key", reqd=1, unique=1,
          description="app.module.name, from the decorator."),
        f("label", in_list_view=1),
        f("app", in_list_view=1, in_standard_filter=1),
        f("capability", "Select", reqd=1, default="Text Generation",
          in_list_view=1, in_standard_filter=1, options=AI_CAPABILITY_OPTIONS),
        column("cb_feat_policy"),
        f("status", "Select", reqd=1, default="Active", in_list_view=1,
          in_standard_filter=1, options="Active\nWithdrawn\nSuspended",
          description="Suspended stops every tenant calling it, without a deploy."),
        f("tenant_can_disable", "Check", default="1",
          description="Declared by the decorator. Off means AI is the process, "
                      "not a garnish on it, and a tenant cannot switch it off."),
        f("allow_prompt_addendum", "Check", default="1",
          description="Whether a tenant may append to our system prompt."),
        f("default_model", "Link", options="AI Model",
          description="Used when a tenant has not chosen. Empty falls back to "
                      "the recommended model for the capability."),
        section("sec_feat_ceiling", "Ceiling"),
        f("max_input_tokens", "Int", default="0",
          description="0 falls back to the model's context window, which is the "
                      "most the provider would accept anyway."),
        f("max_output_tokens", "Int", default="0"),
        f("max_images", "Int", default="0"),
        f("max_outputs", "Int", default="0",
          description="Generations per call, for a model billed per generation "
                      "rather than per token — Lyria charges per song whatever "
                      "its length. 0 means one."),
        column("cb_feat_ceiling"),
        f("max_audio_seconds", "Int", default="0"),
        f("max_credits", "Float", default="0",
          description="Hard cap per call, whatever the model. 0 means the "
                      "ceiling is whatever the limits above cost."),
        section("sec_feat_meta"),
        f("description", "Small Text"),
        f("last_seen", "Datetime", read_only=1,
          description="Last sync that reported this feature. A feature that "
                      "stops being reported has been removed from the app."),
    ],
)


# --------------------------------------------------------------------------- #
# AI Usage Record — one row per call, and the answer to "where did my credits go".
#
# Also the reconciliation anchor: `gateway_log_id` is what AI Gateway returned
# in cf-aig-log-id, so a job can go back and compare what we charged against
# what Cloudflare says the call cost.
# --------------------------------------------------------------------------- #
doctype(
    "AI Usage Record",
    autoname="naming_series:",
    perms=READONLY_PERMS,
    fields=[
        f("naming_series", "Select", options="AIU-.YYYY.-", default="AIU-.YYYY.-",
          hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("feature", "Data", in_list_view=1, in_standard_filter=1),
        f("model", "Link", options="AI Model", in_list_view=1),
        f("provider", "Data", in_standard_filter=1),
        column("cb_usage_money"),
        f("credits_charged", "Float", in_list_view=1),
        f("cost_usd", "Float", precision="9",
          description="Measured provider cost before markup."),
        f("markup", "Float"),
        f("reservation", "Link", options="Credit Reservation"),
        section("sec_usage_units", "What was counted"),
        f("units", "Code", options="JSON",
          description="The metered units, as reported by the provider."),
        column("cb_usage_log"),
        f("gateway_log_id", label="Gateway Log ID",
          description="cf-aig-log-id. The handle for reconciliation."),
        f("cached", "Check", default="0"),
        section("sec_usage_recon", "Reconciliation"),
        f("reconciled_on", "Datetime", read_only=1),
        f("gateway_cost_usd", "Float", precision="9", read_only=1,
          description="What AI Gateway's log says the call cost."),
        column("cb_usage_recon"),
        f("adjustment", "Link", options="Credit Ledger Entry", read_only=1,
          description="Posted when the gateway disagreed with us."),
        f("recon_note", "Small Text", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace Saved View — how one person likes to look at one screen.
#
# Frappe calls this a List View Setting and keeps it per doctype; here it is per
# screen, because two screens over the same doctype are two different questions
# and a filter that belongs to one does not belong to the other.
#
# Per user, not per workspace: a colleague's idea of which columns matter is not
# a setting to inherit.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Saved View",
    app="tenant",
    autoname="hash",
    fields=[
        # Not required: an empty user is Frappe's own `for_user` empty on List
        # Filter — a view everyone on the workspace sees rather than one
        # person's.
        f("user", "Link", options="User", in_list_view=1,
          description="Whose screen this is. Empty is a screen everyone on "
                      "the workspace sees — Frappe's `for_user` empty, on "
                      "List Filter."),
        f("space_code", reqd=1, in_list_view=1),
        f("screen", reqd=1, in_list_view=1,
          description="The screen's slug, so two screens over one doctype keep "
                      "their own answers."),
        column("cb_saved_view"),
        f("label", description="The screen's name. Empty is the person's own "
                               "unnamed default for this screen — what Save "
                               "writes."),
        # Free text and not a Select of SPACE_ICONS, because the other half of
        # what may go here is an emoji — and the reason for both is the build:
        # Tailwind only emits CSS for the lucide class names it saw in the
        # source, so the offered set is the one that draws, while an emoji is
        # text and needs no build step at all. `spaceview._view_icon` is where
        # the two rules are enforced.
        f("icon", description="A lucide name from the offered set, or an "
                              "emoji. Anything else is dropped on the way in — "
                              "a lucide name reaches the DOM as a class."),
        f("is_default", "Check", default="0",
          description="Opens this screen for whoever this screen belongs to."),
        section("sec_saved_query"),
        f("filters", "Code", options="JSON"),
        f("order_by"),
        column("cb_saved_columns"),
        f("columns", "Code", options="JSON",
          description="Which columns, in order, each with a width and an "
                      "optional left/right pin. Empty follows the screen. The "
                      "comma-separated fieldnames this used to hold still read."),
        f("page_length", "Int", default="0", description="0 follows the screen."),
        f("group_by", "Data",
          description="Which column the rows are grouped under. Empty is no "
                      "grouping."),
        f("favourites", "Check", default="0",
          description="Only rows this person liked. A flag rather than a filter "
                      "on _liked_by: that column holds user ids, so a filter "
                      "naming it could ask what a colleague liked."),
        f("view_type", description="Which of the screen's view types this view "
                                   "is of. Empty is the screen's first."),
        f("view_settings", "Code", options="JSON",
          description="What this view type needs that columns and filters do "
                      "not carry."),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace Hidden View — a shared view one person does not want to see.
#
# A row here rather than a flag on the view itself, because the view is shared:
# one row, many readers, and "I do not want this in my menu" is each reader's
# own answer. Hiding is not deleting and is never offered as it — a shared view
# somebody else relies on stays where it is.
#
# Only shared views are hideable. Your own you delete.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Hidden View",
    app="tenant",
    autoname="hash",
    fields=[
        f("user", "Link", options="User", reqd=1, in_list_view=1),
        f("space_code", reqd=1, in_list_view=1),
        f("screen", reqd=1, in_list_view=1),
        f("layout", reqd=1, in_list_view=1,
          description="The OneSpace Saved View this hides. Data rather than a "
                      "Link so deleting the view cannot fail on a row that "
                      "only says somebody stopped looking at it — the delete "
                      "sweeps these up itself."),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace AI Feature Setting — a workspace's answer for one declared feature.
#
# Rows are created from the registry, not typed: the decorator is the only thing
# that knows a feature exists, so a workspace's settings page is whatever its
# installed apps declare. A row for a feature that is no longer declared is
# ignored rather than deleted, so uninstalling and reinstalling an app does not
# lose the customer's wording.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace AI Feature Setting",
    app="tenant",
    istable=1,
    fields=[
        f("feature_key", reqd=1, in_list_view=1),
        f("enabled", "Check", default="1", in_list_view=1),
        f("model_key", label="Model", in_list_view=1,
          description="Empty means whatever the platform recommends for this "
                      "capability, which is also what tracks a better model "
                      "arriving without anyone changing a setting."),
        section("sec_feat_prompt"),
        f("prompt_addendum", "Small Text",
          description="Appended to our instructions. The model receives both; "
                      "this field never contains ours."),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace AI Settings — the workspace's AI switch and its per-feature answers.
#
# The catalogue is cached here from the control plane rather than fetched per
# request: choosing a model must work while the control plane is unreachable,
# and pricing a call must not depend on a network hop in the middle of one.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace AI Settings",
    app="tenant",
    issingle=1,
    fields=[
        f("ai_enabled", "Check", default="1",
          description="Off stops every feature a workspace is allowed to stop. "
                      "Features declared as critical keep running — they are "
                      "the process, not an assistant beside it."),
        f("credit_balance", "Float", read_only=1),
        column("cb_ai_set"),
        f("last_sync", "Datetime", read_only=1),
        section("sec_ai_features", "Features"),
        f("features", "Table", options="OneSpace AI Feature Setting"),
        section("sec_ai_cache", "Cached from the control plane"),
        f("catalogue_json", "Code", options="JSON", read_only=1,
          description="Models the workspace may choose, with prices."),
        f("registry_json", "Code", options="JSON", read_only=1,
          description="Platform policy per feature: what may be disabled, what "
                      "model is pinned, what the ceiling is."),
    ],
)


# --------------------------------------------------------------------------- #
# Stripe Webhook Event — Stripe retries aggressively and delivers out of order.
# Recording every event id makes replay a no-op instead of a double charge.
# --------------------------------------------------------------------------- #
doctype(
    "Stripe Webhook Event",
    autoname="field:event_id",
    perms=READONLY_PERMS,
    fields=[
        f("event_id", reqd=1, unique=1, in_list_view=1),
        f("event_type", in_list_view=1, in_standard_filter=1),
        f("status", "Select", options="Received\nProcessed\nIgnored\nFailed",
          default="Received", reqd=1, in_list_view=1, in_standard_filter=1),
        column("cb_evt"),
        f("tenant", "Link", options="Tenant"),
        f("subscription", "Link", options="Subscription"),
        f("processed_on", "Datetime", read_only=1),
        section("sec_evt"),
        f("payload", "Code", options="JSON"),
        f("error", "Text"),
    ],
)


# --------------------------------------------------------------------------- #
# Account Request — the record that exists before a tenant does.
#
# Signup collects a workspace, a plan and a card before there is any site to
# hold that. This carries it from the form through payment to provisioning, and
# is what makes the flow resumable when someone abandons checkout and returns.
# --------------------------------------------------------------------------- #
doctype(
    "Account Request",
    autoname="hash",
    title_field="workspace_name",
    fields=[
        f("email", "Data", options="Email", reqd=1, in_list_view=1, in_standard_filter=1),
        f("workspace_name", reqd=1, in_list_view=1),
        f("requested_slug", reqd=1, in_list_view=1,
          description="Validated at request time, re-checked at claim: someone else "
                      "may have taken it while this one sat in checkout."),
        f("status", "Select",
          options="Pending Payment\nPaid\nProvisioning\nCompleted\nFailed\nAbandoned",
          default="Pending Payment", reqd=1, in_list_view=1, in_standard_filter=1),
        column("cb_ar"),
        f("plan", "Link", options="Plan", reqd=1),
        f("interval", "Select", options="Monthly\nYearly", default="Monthly", reqd=1),
        f("region", "Link", options="Region", reqd=1),
        f("storage_jurisdiction", "Select", options="Global\nEU", default="Global", reqd=1),
        f("tenant", "Link", options="Tenant", read_only=1,
          description="Set once provisioning starts."),
        f("user", "Link", options="User", read_only=1,
          description="The owner account, created after payment clears."),
        section("sec_ar_pay", "Payment"),
        f("stripe_checkout_session", label="Stripe Checkout Session", read_only=1, unique=1),
        f("stripe_customer_id", label="Stripe Customer ID", read_only=1),
        f("stripe_subscription_id", label="Stripe Subscription ID", read_only=1),
        column("cb_ar_pay"),
        f("paid_on", "Datetime", read_only=1),
        f("completed_on", "Datetime", read_only=1),
        f("failure_reason", "Small Text", read_only=1),
        section("sec_ar_meta"),
        f("source", description="Where the signup came from, for attribution."),
        f("ip_address", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Standby Site — a warm site waiting to be claimed.
#
# Creating an ERPNext site takes minutes. Someone who has just entered card
# details should not watch a spinner for that long, so sites are built ahead of
# demand under throwaway names and claimed on signup. The customer never sees
# the underlying name: in Per-tenant domain mode they reach their workspace on
# <slug>.4dl.app regardless.
# --------------------------------------------------------------------------- #
doctype(
    "Standby Site",
    autoname="field:press_site",
    fields=[
        f("press_site", label="Press Site", reqd=1, unique=1, in_list_view=1),
        f("status", "Select",
          options="Creating\nReady\nClaimed\nBroken\nArchived",
          default="Creating", reqd=1, in_list_view=1, in_standard_filter=1),
        f("shard", "Link", options="Shard", reqd=1, in_list_view=1, in_standard_filter=1),
        column("cb_sb"),
        f("claimed_by", "Link", options="Tenant", read_only=1),
        f("claimed_on", "Datetime", read_only=1),
        f("created_on", "Datetime", read_only=1),
        f("provisioning_job", "Link", options="Provisioning Job", read_only=1),
        section("sec_sb"),
        f("last_error", "Small Text", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Region — what a customer picks at signup.
# --------------------------------------------------------------------------- #
doctype(
    "Region",
    autoname="field:region_code",
    title_field="region_name",
    fields=[
        f("region_code", reqd=1, unique=1, description="e.g. nuremberg"),
        f("region_name", reqd=1, in_list_view=1, description="Shown at signup, e.g. Nuremberg"),
        f("country", in_list_view=1),
        f("is_active", "Check", default="1", in_list_view=1),
        column("cb_region"),
        f("sort_order", "Int", default="0"),
        f("description", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# Storage Bucket — one R2 bucket, deliberately bounded.
#
# A single bucket holding every tenant's files is one credential, one
# misconfiguration or one bad lifecycle rule away from losing everything. Every
# bucket is capped and rotated so the worst case stays bounded.
# --------------------------------------------------------------------------- #
doctype(
    "Storage Bucket",
    autoname="field:bucket_name",
    fields=[
        f("bucket_name", reqd=1, unique=1, in_list_view=1),
        f("jurisdiction", "Select", options="Global\nEU", default="Global", reqd=1,
          in_list_view=1, in_standard_filter=1,
          description="R2 pins EU buckets to EU data centres. Chosen by the "
                      "customer at signup and never changed afterwards."),
        f("status", "Select", options="Provisioning\nActive\nFull\nRetired",
          default="Provisioning", reqd=1, in_list_view=1, in_standard_filter=1),
        column("cb_bucket"),
        f("tenant_count", "Int", default="0", read_only=1, in_list_view=1),
        f("max_tenants", "Int", default="200",
          description="Rotation threshold. Reaching it marks the bucket Full and "
                      "a fresh one is created."),
        f("bytes_used", "Float", default="0", read_only=1),
        f("max_bytes", "Float", default="0",
          description="Optional secondary cap. Zero means tenant count only."),
        section("sec_bucket_cf", "Cloudflare"),
        f("public_base_url", description="CDN host bound to this bucket, for public objects."),
        f("created_on", "Datetime", read_only=1),
        column("cb_bucket_cf"),
        f("last_error", "Small Text", read_only=1),
    ],
)


# Every key build() understands. Adding one to a doctype() call without adding
# it here is a hard error rather than a silent omission.
HANDLED_SPEC_KEYS = {
    "name", "fields", "perms", "autoname", "title_field",
    "allow_rename", "issingle", "istable", "app",
}


def build(spec):
    fields = spec["fields"]
    doc = {
        "actions": [],
        "allow_rename": spec.get("allow_rename", 1),
        "creation": STAMP,
        "doctype": "DocType",
        "editable_grid": 1,
        "engine": "InnoDB",
        "field_order": [x["fieldname"] for x in fields],
        "fields": fields,
        "index_web_pages_for_search": 1,
        "links": [],
        "modified": STAMP,
        "modified_by": "Administrator",
        "module": APPS[spec["app"]][2],
        "name": spec["name"],
        "owner": "Administrator",
        "permissions": spec["perms"],
        "sort_field": "modified",
        "sort_order": "DESC",
        "states": [],
        "track_changes": 1,
    }
    if spec.get("autoname"):
        doc["autoname"] = spec["autoname"]
    if spec.get("title_field"):
        doc["title_field"] = spec["title_field"]
        doc["show_title_field_in_link"] = 1
    if spec.get("issingle"):
        doc["issingle"] = 1
        doc.pop("allow_rename", None)

    if spec.get("istable"):
        # A child table is not a doctype with a parent field bolted on: without
        # this Frappe builds an ordinary table with no parent/parenttype/idx
        # columns, and every read through the parent fails with
        # "Unknown column 'parent' in 'WHERE'".
        doc["istable"] = 1
        doc["editable_grid"] = 1
        doc.pop("allow_rename", None)
        doc["permissions"] = []

    # Anything in the spec this function does not know about was silently
    # dropped before now — istable was, and the doctype generated as a normal
    # table that nothing could read. Fail instead.
    unknown = set(spec) - HANDLED_SPEC_KEYS
    if unknown:
        raise SystemExit(f"{spec['name']}: build() ignores {sorted(unknown)}")

    return doc


CONTROLLER = '''import frappe
from frappe.model.document import Document


class {cls}(Document):
\tpass
'''


CAPABILITIES_MODULE = '''"""Capabilities, and the provider task names that map onto them.

Generated by scripts/gen_doctypes.py from scripts/ai_capabilities.py. Do not
edit: the same list fills the AI Model and AI Feature Selects, and a second
hand-maintained copy is how a model ends up in a bucket the settings page does
not offer.
"""

CAPABILITIES = {caps}

CAPABILITY_NAMES = list(CAPABILITIES)


def for_task(task: str) -> str | None:
	"""The capability a provider's task name means, or None if we do not know.

	None is a real answer. A model whose task we cannot place is left for review
	rather than filed under the nearest-looking capability, because the cost of
	guessing is a feature calling a model that cannot do the job.
	"""
	if not task:
		return None

	needle = task.strip().lower()
	for capability, aliases in CAPABILITIES.items():
		if needle == capability.lower() or needle in aliases:
			return capability
	return None
'''


FIELDTYPES_MODULE = '''"""Every Frappe fieldtype, and whether we offer to write it.

Generated by scripts/gen_doctypes.py from scripts/field_types.py. Do not edit:
the browser reads the same table out of `src/lib/fields.js`, and the one thing
worse than the two disagreeing is them disagreeing about `editable` — the form
would offer a control the server then refuses.
"""

# fieldtype -> (control, cell, icon, editable)
FIELD_TYPES = {fields}

LAYOUT_TYPES = {layout}

DATA_OPTIONS = {data_options}

# Frappe's own bookkeeping. Never a column, never a control: a customer editing
# `owner` or `docstatus` is always a mistake.
RESERVED = {reserved}


def editable(fieldtype: str) -> bool:
	"""Whether a field of this type can be offered for editing at all.

	Unknown is not editable. If we do not know what it is, we do not know how to
	write it, and a text box over an unknown type saves the wrong shape.
	"""
	row = FIELD_TYPES.get(fieldtype)
	return bool(row and row[3])


def icon_for(fieldtype: str) -> str:
	return (FIELD_TYPES.get(fieldtype) or (None, None, "lucide-circle-help", False))[2]


def cell_for(fieldtype: str) -> str:
	return (FIELD_TYPES.get(fieldtype) or (None, "text", None, False))[1]


def is_layout(fieldtype: str) -> bool:
	"""A section break, a column break, a heading. Carries no value, so it is
	never a column and never something to filter."""
	return fieldtype in LAYOUT_TYPES


# --------------------------------------------------------------------------- #
# Filter operators, ported from Frappe's own filter UI and inverted from its
# per-fieldtype deny list into an allow list. `tests/test_field_types.py` reads
# `filter.js` back and fails when the two disagree.
# --------------------------------------------------------------------------- #

# operator -> label, in the order Frappe lists them.
OPERATORS = {operators}

# Frappe relabels the comparisons for a date: "Before" reads better than "<".
OPERATOR_LABELS_BY_TYPE = {operator_labels}

# operator -> whether a fieldtype may use it.
VALID_OPERATORS = {valid_operators}

# Frappe's relative-date vocabulary. Handed to its `timespan` operator verbatim,
# so a value it does not know is a filter that returns nothing and says nothing.
TIMESPANS = {timespans}

DEFAULT_OPERATORS = {default_operators}

_EQUALITY = ("=", "!=")
_IN = ("in", "not in")


def operators_for(fieldtype: str) -> tuple:
	"""Which operators a filter on this fieldtype may use.

	A fieldtype nobody listed gets equality and `is`. An allow list rather than
	Frappe's deny list precisely so that is the answer: on a server, a fieldtype
	nobody thought about must not inherit every operator.
	"""
	return VALID_OPERATORS.get(fieldtype, ("=", "!=", "is"))


def default_operator(fieldtype: str, fieldname: str = "") -> str:
	"""What a filter opens on. A Data field is almost always a substring
	search, a date almost always a range."""
	if fieldname in ("_assign", "_liked_by"):
		# Stored as a JSON array, so an exact match can never hit.
		return "like"
	return DEFAULT_OPERATORS.get(fieldtype, "=")


def value_shape(fieldtype: str, operator: str) -> str:
	"""What the value has to be, once the operator is known.

	Frappe does this by rewriting the docfield in `set_fieldtype`; the same
	decision, named, so the server can check a value without rendering one.
	"""
	if operator == "is":
		return "set"
	if operator == "timespan":
		return "timespan"
	if operator == "between":
		return "range"
	if operator in _IN:
		return "multi"
	if fieldtype in ("Check", "Select"):
		return "choice"
	if fieldtype in ("Link", "Dynamic Link") and operator in _EQUALITY:
		return "link"
	# Everything else is a plain box, a Link under `like` included: matching
	# part of a name is a text question.
	return "value"
'''


def write_fieldtypes():
    """Emit the fieldtype table into the tenant app."""
    import pprint
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import field_types
    from field_types import DATA_OPTIONS, FIELD_TYPES, LAYOUT_TYPES

    reserved = (
        "doctype", "name", "owner", "creation", "modified", "modified_by",
        "docstatus", "idx", "parent", "parenttype", "parentfield",
        "_user_tags", "_comments", "_assign", "_liked_by", "_seen",
        "naming_series",
    )

    valid = {t: field_types.operators_for(t) for t in FIELD_TYPES}
    defaults = {t: field_types.default_operator(t) for t in FIELD_TYPES}

    body = FIELDTYPES_MODULE.format(
        fields=pprint.pformat(FIELD_TYPES, width=92, sort_dicts=True),
        layout=pprint.pformat(LAYOUT_TYPES, width=88),
        data_options=pprint.pformat(DATA_OPTIONS, width=88, sort_dicts=True),
        reserved=pprint.pformat(frozenset(reserved), width=88),
        operators=pprint.pformat(field_types.OPERATORS, width=88, sort_dicts=False),
        operator_labels=pprint.pformat(
            field_types.OPERATOR_LABELS_BY_TYPE, width=88, sort_dicts=False),
        valid_operators=pprint.pformat(valid, width=92, sort_dicts=True),
        timespans=pprint.pformat(dict(field_types.TIMESPANS), width=88, sort_dicts=False),
        default_operators=pprint.pformat(defaults, width=88, sort_dicts=True),
    )
    path = os.path.join(APPS_ROOT, "oneapp", "oneapp", "oneapp_core")
    with open(os.path.join(path, "fieldtypes.py"), "w") as fh:
        fh.write(body)


def write_capabilities():
    """Emit the capability map into the control plane app."""
    import pprint

    from ai_capabilities import CAPABILITIES

    body = CAPABILITIES_MODULE.format(caps=pprint.pformat(CAPABILITIES, width=88))
    path = os.path.join(APPS_ROOT, "oneapp_control", "oneapp_control", "ai")
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, "__init__.py"), "a").close()
    with open(os.path.join(path, "capabilities.py"), "w") as fh:
        fh.write(body)


def main():
    write_capabilities()
    write_fieldtypes()
    written = []
    for name, spec in DOCTYPES.items():
        pkg, module_dir, _ = APPS[spec["app"]]
        base = os.path.join(APPS_ROOT, pkg, pkg, module_dir, "doctype")
        slug = name.lower().replace(" ", "_")
        d = os.path.join(base, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "__init__.py"), "a").close()
        with open(os.path.join(d, f"{slug}.json"), "w") as fh:
            json.dump(build(spec), fh, indent=1, sort_keys=True)
            fh.write("\n")
        ctrl = os.path.join(d, f"{slug}.py")
        if not os.path.exists(ctrl):
            cls = name.replace(" ", "")
            with open(ctrl, "w") as fh:
                fh.write(CONTROLLER.format(cls=cls))
        written.append(name)
    print(f"{len(written)} doctypes: " + ", ".join(sorted(written)))


if __name__ == "__main__":
    main()
