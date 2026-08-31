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


# Both operator-granted quota fields say the same thing, so they say it once.
GRANTED_GB = (
    "Extra {resource} granted by an operator, on top of the plan and any add-ons. "
    "Never billed and never expires: this is the goodwill lever, not a product."
)

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
# Catalogue Price — every Stripe Price anything we sell has ever had.
#
# Stripe Prices are immutable in amount and currency, so changing what something
# costs means minting a new Price and leaving the old one billing whoever is
# already on it. That is how price grandfathering works, and it only works if
# the old ids survive: this table is both the history an operator reads and the
# reverse lookup a webhook needs to answer "which of ours is this price?" when a
# subscription changes underneath us.
#
# One table for plans, add-ons and credit packs rather than three near-identical
# ones. Every row already carries `parenttype`, so the lookups say which
# catalogue they mean and a plan's price can never resolve to an add-on.
# --------------------------------------------------------------------------- #
doctype(
    "Catalogue Price",
    istable=1,
    fields=[
        # `One-off` is what a credit pack is: bought once, so it has no cadence.
        # Said rather than left blank, because a price with no interval and a
        # price whose interval nobody filled in are different problems.
        f("interval", "Select", options="Monthly\nYearly\nOne-off", reqd=1, in_list_view=1),
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


# --------------------------------------------------------------------------- #
# Promo Code — a discount on anything we sell, including all of it.
#
# Ours to declare, Stripe's to enforce. Saving one creates a Stripe **Coupon**
# (the money: percent or amount, and for how long) and a **Promotion Code** (the
# string somebody types, its redemption limit and its expiry). Nobody pastes a
# `promo_...` id between two systems, for the same reason nobody pastes a price.
#
# A coupon's terms are immutable in Stripe once created. So changing a percentage
# mints a new coupon and a new promotion code and deactivates the old one:
# anybody already redeemed keeps what they were given, which is the same
# grandfathering shape a plan price has, for the same reason.
#
# 100% off forever is how a demo or training workspace exists. It is a real
# subscription at zero — real terms, real quotas, real monthly credit grants —
# rather than a comped tenant on a second lifecycle. Stripe asks for no card when
# the total is zero, and `handle_signup_paid` already accepts the
# `no_payment_required` that comes back.
# --------------------------------------------------------------------------- #
doctype(
    "Promo Code",
    autoname="field:promo_code",
    fields=[
        f("promo_code", label="Code", reqd=1, unique=1, in_list_view=1,
          description="What somebody types. Upper-cased on save, because nobody "
                      "types a code the way it was written down."),
        f("description", "Small Text", reqd=1,
          description="What it is for. An operator reads this in six months and "
                      "has to know whether it can be retired."),
        f("is_active", "Check", default="1", in_list_view=1,
          description="Unchecking deactivates the promotion code in Stripe. "
                      "Anybody already redeemed keeps their discount — that is "
                      "Stripe's behaviour and it is the right one."),
        column("cb_promo_money"),
        f("discount_type", "Select", options="Percent\nAmount", default="Percent",
          reqd=1, in_list_view=1),
        f("percent_off", "Float", depends_on="eval:doc.discount_type=='Percent'",
          description="1 to 100. A hundred is free — which is the point."),
        f("amount_off", "Currency", depends_on="eval:doc.discount_type=='Amount'"),
        f("currency", "Link", options="Currency", default="USD",
          depends_on="eval:doc.discount_type=='Amount'",
          description="An amount-off coupon only applies to purchases in its own "
                      "currency. Stripe enforces that, not us."),
        f("duration", "Select", options="Once\nRepeating\nForever", default="Once",
          reqd=1,
          description="How many billing periods it lasts. Irrelevant to a "
                      "one-off purchase, which only ever has one."),
        f("duration_in_months", "Int", depends_on="eval:doc.duration=='Repeating'"),
        section("sec_promo_scope", "What it applies to"),
        f("on_subscriptions", "Check", default="1",
          description="Plans. This is the one a free demo instance needs."),
        f("on_addons", "Check", default="0",
          description="Extra storage, bought per month."),
        f("on_credit_packs", "Check", default="0"),
        column("cb_promo_limits"),
        f("max_redemptions", "Int", default="0",
          description="Total times it may be used, across everybody. Zero for no "
                      "limit."),
        f("expires_on", "Date", description="Stripe stops accepting it after this."),
        f("first_time_only", "Check", default="0",
          description="Only for a customer who has never paid us before."),
        section("sec_promo_stripe"),
        f("stripe_coupon_id", label="Stripe Coupon ID", read_only=1),
        f("stripe_promotion_code_id", label="Stripe Promotion Code ID", read_only=1),
        f("times_redeemed", "Int", default="0", read_only=1, in_list_view=1,
          description="Counted by Stripe, refreshed from it. Not incremented "
                      "here — two systems counting the same thing disagree."),
        f("sync_error", "Small Text", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Credit Pack — AI credits, bought once.
#
# The other half of how credits arrive. A plan grants some every period and they
# expire at the end of it; a pack is bought outright and rolls over, which is
# what makes it worth buying — `ledger.open_grants` spends the soonest-expiring
# grant first and never-expiring purchases last.
#
# One price, not two: a pack is bought once, so it has no cadence. It still
# carries the full price history, because repricing one has to archive the old
# Stripe price like everything else.
# --------------------------------------------------------------------------- #
doctype(
    "Credit Pack",
    autoname="field:pack_code",
    title_field="pack_name",
    fields=[
        f("pack_code", reqd=1, unique=1, description="Stable id, e.g. credits-5k"),
        f("pack_name", reqd=1, in_list_view=1),
        f("credits", "Float", reqd=1, in_list_view=1,
          description="What the buyer receives. Never expires."),
        f("is_active", "Check", default="1"),
        f("sort_order", "Int", default="0"),
        column("cb_pack_price"),
        f("currency", "Link", options="Currency", default="USD"),
        f("amount", "Currency", reqd=1, in_list_view=1),
        f("stripe_product_id", label="Stripe Product ID", read_only=1),
        f("stripe_price_id", label="Stripe Price ID", read_only=1,
          description="The current price. History is in Prices below."),
        f("sync_error", "Small Text", read_only=1,
          description="Why the last sync to Stripe did not finish. Saving again "
                      "retries; the pack stays sellable on whatever price it "
                      "already has."),
        section("sec_pack_copy"),
        f("description", "Small Text",
          description="What a customer reads next to the price."),
        section("sec_pack_prices", "Prices"),
        f("prices", "Table", options="Catalogue Price", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Add-on — extra quota, bought per month on the subscription.
#
# An add-on is a second recurring line on the same Stripe subscription, so the
# customer gets one invoice, one dunning cycle and one card. It is not a plan:
# plans differ only in quotas and every feature is on every one of them, while an
# add-on adds to a quota without changing what plan somebody is on.
#
# Sold per unit. "+50 GB" bought three times is one line with quantity 3, which
# is what lets somebody grow without a new product every time.
# --------------------------------------------------------------------------- #
doctype(
    "Add-on",
    autoname="field:addon_code",
    title_field="addon_name",
    fields=[
        f("addon_code", reqd=1, unique=1, description="Stable id, e.g. storage-50"),
        f("addon_name", reqd=1, in_list_view=1),
        # A Select and not free text: the quota layer switches on this, and a
        # third kind is a code change either way. Better to fail at save time.
        f("kind", "Select", options="File Storage\nDatabase Storage", reqd=1,
          in_list_view=1, in_standard_filter=1,
          description="Which quota a unit of this adds to."),
        f("unit_gb", "Int", label="Unit GB", default="50", reqd=1, in_list_view=1,
          description="How much one unit buys. Quantity multiplies it."),
        f("max_units", "Int", default="0",
          description="Most units one workspace may hold. Zero for no ceiling."),
        f("is_active", "Check", default="1"),
        f("sort_order", "Int", default="0"),
        column("cb_addon_price"),
        f("currency", "Link", options="Currency", default="USD"),
        # Both cadences, because Stripe requires every recurring line on one
        # subscription to share an interval. A yearly workspace cannot be sold a
        # monthly add-on, so an add-on priced only monthly is simply not offered
        # to them.
        f("price_monthly", "Currency", in_list_view=1),
        f("price_yearly", "Currency"),
        f("stripe_product_id", label="Stripe Product ID", read_only=1),
        f("stripe_price_id_monthly", label="Stripe Price ID (Monthly)", read_only=1,
          description="The current monthly price. History is in Prices below."),
        f("stripe_price_id_yearly", label="Stripe Price ID (Yearly)", read_only=1),
        f("sync_error", "Small Text", read_only=1,
          description="Why the last sync to Stripe did not finish. Saving again "
                      "retries; the add-on stays sellable on whatever prices it "
                      "already has."),
        section("sec_addon_copy"),
        f("description", "Small Text",
          description="What a customer reads next to the price."),
        section("sec_addon_prices", "Prices"),
        f("prices", "Table", options="Catalogue Price", read_only=1,
          description="Every Stripe price this add-on has had. Subscriptions "
                      "holding an older one keep billing on it."),
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
        section("sec_backups", "Backups"),
        # Ours, into R2, alongside whatever Frappe Cloud keeps. R2 storage is
        # cheap enough that the frequency is a product lever rather than a cost
        # one — which is why it is a plan term and not a constant.
        f("backups_per_day", "Int", default="1",
          description="How often this plan's workspaces back themselves up to "
                      "R2. The first run of each day takes files as well; the "
                      "rest are database-only, which is what actually changes."),
        column("cb_backups"),
        f("backup_retention_days", "Int", default="7",
          description="How long those backups are kept. The cold copy taken "
                      "when a workspace is suspended is exempt — it lives under "
                      "its own prefix and answers to the lifecycle windows."),
        section("sec_press_plan"),
        f("press_site_plan", label="Press Site Plan",
          description="Overrides the shard default when set."),
        f("description", "Small Text"),
        section("sec_prices", "Prices"),
        f("prices", "Table", options="Catalogue Price", read_only=1,
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
        f("status_field",
          description="Which field says where a record stands — the one whose "
                      "value goes on the badge beside a record's name. A "
                      "fieldname, checked against the doctype like any other; "
                      "the colours are the doctype's own Document States, not "
                      "something to repeat here. Empty is no badge."),
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
    # Read-only, like the credit ledger and the lifecycle log. An audit trail an
    # operator can write by hand is not an audit trail — and every row is
    # inserted by `admin.support_login` with `ignore_permissions`, so nothing
    # legitimate went through the create permission this removes.
    #
    # It is also what `validate_doctypes` was objecting to: `tenant`, `operator`
    # and `logged_in_on` are all required *and* read-only, which on a doctype
    # somebody can press New on is a form that cannot be saved. On one nobody
    # can create, it is the correct shape.
    perms=READONLY_PERMS,
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
        # The rungs of the lifecycle ladder, in the order a workspace walks
        # them. `Suspended` still has its site on Frappe Cloud and comes back in
        # seconds; `Archived` does not, and comes back from the cold copy in
        # minutes; `Purged` has nothing left and is the one that cannot be
        # undone. See `oneapp_control/lifecycle/` and docs/LIFECYCLE.md.
        f("status", "Select",
          options="Draft\nProvisioning\nActive\nSuspended\nArchived\nPurged\nFailed",
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
        f("promo_code", "Link", options="Promo Code", read_only=1,
          description="What this workspace was signed up under, if anything. "
                      "The answer to 'which of these are free demos'."),
        f("provisioned_on", "Datetime", read_only=1),
        f("suspended_on", "Datetime", read_only=1),
        f("archived_on", "Datetime", read_only=1),
        section("sec_lifecycle", "Lifecycle"),
        # One clock, and every rung is derived from it. Set the first time a
        # subscription is seen unpaid (or a trial lapses with nothing bought),
        # and cleared the moment it recovers — so recovering and failing again
        # restarts the ladder from the top rather than resuming mid-fall.
        f("dunning_started_on", "Date", read_only=1, in_standard_filter=1,
          description="When this workspace stopped being paid for. Empty means "
                      "it is not on the ladder."),
        f("dunning_stage", "Select",
          options="\nGrace\nSuspended\nArchived\nPurged",
          read_only=1, in_standard_filter=1,
          description="Which rung the sweep last acted on. Distinct from status: "
                      "an operator can suspend a paid-up workspace, and that is "
                      "not the ladder."),
        f("lifecycle_hold", "Check", default="0",
          description="Freeze this workspace out of the ladder entirely. A demo "
                      "instance, a billing dispute, a legal hold. Nothing is "
                      "suspended, archived or purged while this is set."),
        f("purge_after", "Date", read_only=1,
          description="The date the cold copy and every object this workspace "
                      "owns may be deleted. Set when it is archived."),
        f("purge_warned_on", "Date", read_only=1,
          description="When the final warning went out. Purging refuses without "
                      "one, so a bad window cannot delete a workspace that was "
                      "never told."),
        f("purged_on", "Datetime", read_only=1),
        column("cb_lifecycle"),
        # The cold copy: the last full backup, promoted to a prefix retention
        # never touches. Archiving refuses without one.
        f("cold_storage_key", "Data", read_only=1,
          description="R2 prefix holding the database, files and config this "
                      "workspace can be rebuilt from."),
        # Every wire between here and a tenant site runs the other way, over
        # HMAC, so asking for a final backup is a flag the site picks up on its
        # next sync rather than a call. This is when we started asking — and
        # what stops us asking forever, because a site that has not synced in
        # days is not about to.
        f("cold_copy_requested_on", "Datetime", read_only=1),
        f("cold_stored_on", "Datetime", read_only=1),
        f("cold_storage_bytes", "Float", default="0", read_only=1),
        f("restored_on", "Datetime", read_only=1,
          description="When it last came back from cold."),
        # Over-quota is a grace window rather than an instant block, because the
        # usual way a workspace gets here is a line disappearing from its
        # subscription rather than anything it uploaded. See DECISIONS §2b.
        f("over_quota_since", "Date", read_only=1,
          description="When what it holds first exceeded what it is allowed. "
                      "Enforcement bites after the overage grace window."),
        f("over_quota_bytes", "Float", default="0", read_only=1,
          description="What it was holding at that moment, and the ceiling it "
                      "may not grow past while the window is open. Taken then "
                      "rather than at the first refused upload, which would "
                      "ratchet upward every time one more file got through."),
        section("sec_backups", "Backups"),
        f("last_backup_on", "Datetime", read_only=1, in_standard_filter=1,
          description="Reported by the site after each successful push to R2."),
        f("last_backup_key", "Data", read_only=1),
        column("cb_backups"),
        f("last_backup_bytes", "Float", default="0", read_only=1),
        f("last_backup_error", "Small Text", read_only=1,
          description="Why the last attempt did not finish. A workspace that "
                      "has not backed up in twice its interval is a fault, not "
                      "a quiet gap."),
        section("sec_usage", "Usage"),
        f("storage_used_bytes", "Float", default="0", read_only=1),
        f("database_used_bytes", "Float", default="0", read_only=1,
          description="Reported by the site. The resource that actually threatens "
                      "the server, so it is capped like file storage."),
        # Grants, not purchases. An add-on is bought against the subscription
        # and lives in its own table there; these two are the lever an operator
        # pulls by hand — goodwill, a migration allowance, room on a demo
        # instance — and nothing ever bills for them.
        f("extra_storage_gb", "Int", label="Extra Storage GB", default="0",
          description=GRANTED_GB.format(resource="file storage")),
        f("extra_database_gb", "Int", label="Extra Database GB", default="0",
          description=GRANTED_GB.format(resource="database")),
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
# Subscription Add-on — an add-on line as this subscription actually holds it.
#
# Captured, not looked up. `unit_gb` and the rate are copied at purchase for the
# same reason the plan's terms are: editing the catalogue must change what the
# *next* purchase buys and nothing else. Somebody who bought three lots of 50 GB
# keeps 150 GB when the add-on is redefined as 100 GB a unit.
#
# `stripe_subscription_item_id` is how a quantity change addresses the right
# line. Without it the only way to raise a quantity would be to guess which of
# the subscription's items this row meant.
# --------------------------------------------------------------------------- #
doctype(
    "Subscription Add-on",
    istable=1,
    fields=[
        f("addon", "Link", options="Add-on", reqd=1, in_list_view=1),
        f("kind", "Select", options="File Storage\nDatabase Storage", reqd=1,
          in_list_view=1,
          description="Captured, so a retired add-on's rows still add up."),
        f("quantity", "Int", default="1", reqd=1, in_list_view=1),
        f("unit_gb", "Int", label="Unit GB", default="0", in_list_view=1,
          description="GB per unit at the moment of purchase."),
        column("cb_addon_line"),
        f("stripe_subscription_item_id", label="Stripe Subscription Item ID",
          read_only=1,
          description="The line on the Stripe subscription this row is."),
        f("stripe_price_id", label="Stripe Price ID", read_only=1),
        f("unit_amount", "Currency", read_only=1,
          description="What one unit costs. Grandfathered like a plan price."),
        f("currency", "Data", read_only=1),
        f("added_on", "Datetime", read_only=1),
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
        f("backups_per_day", "Int", default="0"),
        f("backup_retention_days", "Int", default="0"),
        f("terms_captured_on", "Datetime", read_only=1,
          description="When these were copied from the plan. Empty means this "
                      "subscription predates the snapshot and still reads the "
                      "plan live."),
        # ------------------------------------------------------------------ #
        # And what was bought on top of the plan.
        #
        # Separate from the terms above rather than folded into them, because
        # they answer different questions: the terms are what this plan gave at
        # purchase and never move, while add-ons are held and released as the
        # workspace grows. `quotas.for_subscription` adds the two.
        # ------------------------------------------------------------------ #
        section("sec_addons", "Add-ons"),
        f("addons", "Table", options="Subscription Add-on",
          description="Extra quota this workspace is paying for, as lines on "
                      "the same Stripe subscription."),
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
                   "Restore Site\nPurge Tenant\n"
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
# Tenant Lifecycle Event — what the ladder did, and why.
#
# Append-only, and read-only to everyone including an operator. The ladder
# suspends sites and eventually deletes data on a timer, so "when did this
# happen and what decided it" cannot be a thing you reconstruct from logs that
# rotate. A row is written before the work is attempted and completed after, so
# a transition that failed halfway still leaves its intent behind.
# --------------------------------------------------------------------------- #
doctype(
    "Tenant Lifecycle Event",
    autoname="naming_series:",
    perms=READONLY_PERMS,
    fields=[
        f("naming_series", "Select", options="TLE-.YYYY.-", default="TLE-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("event", "Select",
          options=("Dunning Started\nDunning Cleared\nWarned\nSuspended\nResumed\n"
                   "Cold Copy Taken\nArchived\nRestored\nPurge Warned\nPurged\n"
                   "Backup Taken\nBackup Failed\nOver Quota\nBack Under Quota\n"
                   "Held\nReleased"),
          reqd=1, in_list_view=1, in_standard_filter=1),
        f("occurred_on", "Datetime", reqd=1, in_list_view=1),
        column("cb_event"),
        f("from_status", "Data", read_only=1),
        f("to_status", "Data", read_only=1),
        f("triggered_by", "Select",
          options="Sweep\nWebhook\nOperator\nTenant Site\nSignup",
          default="Sweep", in_standard_filter=1,
          description="A timer and a person are answerable for different things, "
                      "so the row says which one this was."),
        section("sec_detail"),
        f("reason", "Small Text",
          description="Written for somebody reading it a year later, in a "
                      "dispute. Say what was true, not what the code called it."),
        f("detail", "Code", options="JSON", read_only=1),
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
        # ------------------------------------------------------------------ #
        # The lifecycle ladder's windows.
        #
        # Here rather than as constants because an operator has to be able to
        # widen them without a deploy — the day somebody's card fails over a
        # weekend is the day you want the grace period to be a field. Every one
        # is in days, and each is measured from the rung before it.
        # ------------------------------------------------------------------ #
        section("sec_lifecycle_set", "Lifecycle"),
        f("dunning_grace_days", "Int", default="7",
          description="From the first failed payment to suspension. The site "
                      "works throughout; Stripe is still retrying."),
        f("suspended_days", "Int", default="14",
          description="From suspension to archiving. The site is off but intact "
                      "and comes back in seconds."),
        f("cold_retention_days", "Int", default="60",
          description="From archiving to purge. The site is gone from Frappe "
                      "Cloud and we hold a cold copy in R2."),
        column("cb_lifecycle_set"),
        f("purge_warning_days", "Int", default="7",
          description="How long before a purge the final warning goes out. "
                      "Purging refuses on a workspace that was not warned."),
        f("overage_grace_days", "Int", default="7",
          description="How long a workspace may sit over its quota before "
                      "uploads are blocked. The usual cause is a line leaving "
                      "their subscription rather than anything they did."),
        f("auto_purge_enabled", "Check", default="1",
          description="Whether the sweep may delete a cold copy and a "
                      "workspace's objects once every window and warning has "
                      "passed. Turning it off keeps everything forever, which "
                      "is a bill rather than a policy."),
        f("lifecycle_note", "Small Text", read_only=1,
          description="What the last sweep did."),
        f("lifecycle_swept_on", "Datetime", read_only=1),
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
        f("promo_code", "Link", options="Promo Code",
          description="Validated when the request is made and applied to the "
                      "checkout. A hundred-percent code is how a demo workspace "
                      "signs up without a card."),
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
        # Frappe's own `scrub`: spaces and hyphens both become underscores, so
        # "Add-on" is looked for at add_on/add_on.json. Getting this wrong
        # produces a directory Frappe never reads and a doctype that silently
        # does not exist.
        slug = name.lower().replace(" ", "_").replace("-", "_")
        d = os.path.join(base, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "__init__.py"), "a").close()
        with open(os.path.join(d, f"{slug}.json"), "w") as fh:
            json.dump(build(spec), fh, indent=1, sort_keys=True)
            fh.write("\n")
        ctrl = os.path.join(d, f"{slug}.py")
        if not os.path.exists(ctrl):
            # The class name Frappe looks for is the doctype with spaces and
            # hyphens removed — `base_document.get_controller` builds it that
            # way, so "Add-on" is `Addon` and anything else is an ImportError at
            # the first read.
            cls = name.replace(" ", "").replace("-", "")
            with open(ctrl, "w") as fh:
                fh.write(CONTROLLER.format(cls=cls))
        written.append(name)
    print(f"{len(written)} doctypes: " + ", ".join(sorted(written)))


if __name__ == "__main__":
    main()
