"""Generate Frappe doctype JSON for oneapp_control.

Doctype JSON is verbose and easy to get subtly wrong by hand. This declares the
schema compactly and emits canonical JSON, so the shape stays consistent across
every doctype and a field change is a one-line edit.

Run: python3 scripts/gen_doctypes.py
"""

import json
import os

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
        column("cb_press"),
        f("accepts_new_tenants", "Check", default="1",
          description="Uncheck to stop the allocator placing new tenants here."),
        f("capacity_tenants", "Int", default="30",
          description="Soft cap. MariaDB is the real ceiling; see docs/ARCHITECTURE.md."),
        f("tenant_count", "Int", read_only=1, in_list_view=1),
        section("sec_press", "Frappe Cloud"),
        f("press_server", label="Press Server",
          description="Server name in press, e.g. n1.frappe.cloud"),
        f("press_release_group", label="Press Bench Group", reqd=1),
        f("press_cluster", label="Press Cluster"),
        column("cb_press2"),
        f("domain", default="4dl.app", reqd=1,
          description="Root domain sites are created under."),
        f("press_site_plan", label="Default Press Site Plan"),
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
        f("background_workers", "Int", default="1"),
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
        f("icon", description="Icon name rendered by the launcher."),
        f("route", description="SPA route, e.g. /crm"),
        f("sort_order", "Int", default="0"),
        section("sec_desc"),
        f("description", "Small Text"),
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
        f("owner_email", "Data", options="Email", reqd=1),
        column("cb_place"),
        f("shard", "Link", options="Shard", in_standard_filter=1),
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
        f("storage_quota_gb_override", "Int",
          description="Overrides the plan quota when non-zero."),
        column("cb_usage"),
        f("user_count", "Int", default="0", read_only=1),
        f("usage_synced_on", "Datetime", read_only=1),
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
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("action", "Select",
          options=("Create Site\nSuspend Site\nResume Site\nBackup Site\nArchive Site\n"
                   "Add Domain\nSet Primary Domain\nChange Plan\nMigrate Site"),
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
        f("press_api_url", label="Press API URL", default="https://frappecloud.com"),
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
        section("sec_ai", "AI Gateway"),
        f("ai_gateway_url", label="AI Gateway URL"),
        f("ai_gateway_token", "Password", label="AI Gateway Token"),
        column("cb_ai"),
        f("ai_markup_multiplier", "Float", default="1.5",
          description="Applied to measured provider cost when converting to credits."),
    ],
)


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
