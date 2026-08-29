"""Generate Frappe doctype JSON for oneapp_control.

Doctype JSON is verbose and easy to get subtly wrong by hand. This declares the
schema compactly and emits canonical JSON, so the shape stays consistent across
every doctype and a field change is a one-line edit.

Run: python3 scripts/gen_doctypes.py
"""

import json
import os

from app_icons import APP_ICONS, DEFAULT_APP_ICON

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "apps", "oneapp_control", "oneapp_control")
MODULE = "Control Plane"
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


def doctype(name, fields, autoname=None, perms=None, **kw):
    DOCTYPES[name] = dict(name=name, fields=fields, autoname=autoname,
                          perms=perms or MANAGER_PERMS, **kw)


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
        f("stripe_price_id_monthly", label="Stripe Price ID (Monthly)"),
        f("stripe_price_id_yearly", label="Stripe Price ID (Yearly)"),
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
    ],
)

# --------------------------------------------------------------------------- #
# OneApp App — the registry the SPA launcher reads.
# --------------------------------------------------------------------------- #
doctype(
    "OneApp App",
    autoname="field:app_code",
    title_field="app_label",
    fields=[
        f("app_code", reqd=1, unique=1, description="Stable id, e.g. crm"),
        f("app_label", reqd=1, in_list_view=1),
        f("module", reqd=1, in_list_view=1,
          description="Frappe module inside the oneapp app that implements this."),
        f("is_active", "Check", default="1"),
        column("cb_app"),
        f("availability", "Select", options="General\nRestricted", default="General",
          reqd=1, in_list_view=1, in_standard_filter=1,
          description="General: every tenant. Restricted: only via App Entitlement."),
        f("role_name", reqd=1,
          description="Frappe Role gating this app's doctypes. Entitlement grants "
                      "and revokes this role, so enforcement is native permissions "
                      "rather than a bespoke hook."),
        section("sec_manifest", "Doctypes"),
        f("doctypes", "Table", options="OneApp App Doctype",
          description="Everything this app exposes. One list, three jobs: the "
                      "DocPerms we write for our own roles, what an entitlement "
                      "grants, and the allowlist a customer's custom role may "
                      "draw from. A doctype in no manifest is reachable by "
                      "nobody, without anyone having to remember to exclude it."),
        # A Select, not free text: an icon name that exists only in the
        # database is in no source file, so Tailwind's JIT emits no CSS
        # for it and the launcher renders an empty box. The options come
        # from scripts/app_icons.py, which also writes the SPA's literals.
        f("icon", "Select", options="\n".join(APP_ICONS),
          default="lucide-layout-grid",
          description="Rendered by the launcher and the app sidebar."),
        f("route", description="SPA route, e.g. /crm"),
        f("sort_order", "Int", default="0"),
        section("sec_desc"),
        f("description", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# OneApp App Doctype — the manifest row.
#
# We ignore the roles ERPNext, HRMS and Payments ship with: we use those apps for
# the logic they implement, not for their idea of who an "Accounts Manager" is.
# Our own roles therefore start with no permissions, and these rows are where
# they come from. See DECISIONS §8.
# --------------------------------------------------------------------------- #
doctype(
    "OneApp App Doctype",
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
    ],
)

# --------------------------------------------------------------------------- #
# App Entitlement
# --------------------------------------------------------------------------- #
doctype(
    "App Entitlement",
    autoname="hash",
    fields=[
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("app", "Link", options="OneApp App", reqd=1, in_list_view=1,
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
    "OneApp Control Settings",
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
          description="Applied to measured provider cost when converting to credits."),
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
    "allow_rename", "issingle", "istable",
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
        "module": MODULE,
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


def main():
    base = os.path.join(APP_DIR, "control_plane", "doctype")
    written = []
    for name, spec in DOCTYPES.items():
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
