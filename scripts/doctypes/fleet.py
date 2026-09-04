"""The sites themselves, and the machines under them.

A tenant, the shard it lives on, the region and bucket its data is bound to, the
job that created it, the standby pool that makes creation feel instant, and the
lifecycle events and support logins that happen to it afterwards.
"""

from .spec import GRANTED_GB, READONLY_PERMS, column, doctype, f, section


# --------------------------------------------------------------------------- #
# Shard — where a tenant's site physically lives.
# --------------------------------------------------------------------------- #
doctype(
    "Shard",
    search_fields="shard_name,region,press_release_group",
    states=[
        ("Active", "Green"),
        ("Draining", "Orange"),
        ("Full", "Yellow"),
        ("Maintenance", "Gray"),
    ],
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
          description="Soft cap. MariaDB is the real ceiling; see docs/ONEADMIN.md."),
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
        f("site_apps", default="frappe,erpnext,hrms,oneapp", reqd=1,
          description="Apps installed on sites created here, comma separated. Must "
                      "all be present on the bench group. `hrms` is what makes "
                      "attendance, leave balances and payroll real rather than "
                      "a table of dates."),
        section("sec_notes"),
        f("notes", "Small Text"),
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
    # Not made by hand: every row is written by `admin.support_login` before it hands over a session.
    in_create=1,
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
        # Which roles this person holds, preshipped or custom, as a
        # comma-separated list of keys — `crm:sales`, `books:reader`,
        # `custom:<name>`.
        #
        # A list rather than one, because the useful answer is usually two: the
        # person who raises invoices *and* answers the phone. And a list rather
        # than a child table because Frappe does not nest one child table inside
        # another, and a member is already a row on a Tenant. The picker is
        # ours, so the comma is a storage detail rather than something to type.
        #
        # Empty is not "nothing": every space's default role comes automatically
        # with the entitlement, so an invited member can open what the workspace
        # has without anyone choosing anything.
        f("roles", "Small Text",
          description="Extra roles this person holds, beyond each space's "
                      "default. Comma separated keys; the workspace's own "
                      "People screen is what fills this in."),
        f("invited_on", "Datetime", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Tenant
# --------------------------------------------------------------------------- #
doctype(
    "Tenant",
    search_fields="tenant_name,site_name,owner_email",
    states=[
        ("Draft", "Gray"),
        ("Provisioning", "Blue"),
        ("Active", "Green"),
        ("Suspended", "Orange"),
        ("Archived", "Yellow"),
        ("Purged", "Red"),
        ("Failed", "Red"),
    ],
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
        # undone. See `oneapp_control/lifecycle/` and docs/ONEADMIN.md.
        f("status", "Select",
          options="Draft\nProvisioning\nActive\nSuspended\nArchived\nPurged\nFailed",
          default="Draft", reqd=1, in_list_view=1, in_standard_filter=1),
        # Read-only because it is not a choice: `inherit_environment_from_shard`
        # overwrites it from the shard on every save, so an editable control
        # here is one whose value is discarded the moment it is used. The shard
        # is where this is decided, and `read_only` is a real guard on our own
        # surfaces — `spaceview._writable` drops read-only fields before a save.
        f("environment", "Select", options="Production\nStaging",
          default="Production", reqd=1, read_only=1, in_standard_filter=1,
          description="Taken from the shard, which is where it is decided. "
                      "Staging tenants are ours to break: the dev tooling may "
                      "patch and redeploy the bench they sit on, and refuses "
                      "any bench carrying a Production tenant."),
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
        # The description already said this is fixed at signup; `set_only_once`
        # is what makes that true. A bucket is allocated once, at provisioning,
        # and the tenant keeps it for life — so editing this afterwards moved
        # nothing and changed nothing except what the cold-copy manifest claims
        # about where the data lives.
        f("storage_jurisdiction", "Select", options="Global\nEU", default="Global",
          set_only_once=1,
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
        # subscription rather than anything it uploaded. See docs/ONEADMIN.md, Overage.
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
        # Generated on creation and never typed. Editable, this was the one
        # field on the workspace form where a stray keystroke silently severs
        # the site's only channel back — `ensure_hmac_secret` fills a blank but
        # keeps whatever is already there, so a typo would stick and every
        # signed call from that site would start failing its signature.
        f("hmac_secret", "Password", read_only=1,
          description="Shared secret for signed calls with this tenant's site. "
                      "Generated on creation."),
        f("suspended_reason", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# Provisioning Job — explicit, resumable state machine over the press API.
# --------------------------------------------------------------------------- #
doctype(
    "Provisioning Job",
    search_fields="tenant,action,state",
    states=[
        ("Requested", "Gray"),
        ("Running", "Blue"),
        ("Awaiting Agent", "Light Blue"),
        ("Bootstrapping", "Blue"),
        ("Succeeded", "Green"),
        ("Failed", "Red"),
        ("Cancelled", "Gray"),
    ],
    # Not made by hand: the runner creates these; one made by hand has no idempotency key.
    in_create=1,
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
    states=[
        ("Dunning Started", "Orange"),
        ("Dunning Cleared", "Green"),
        ("Warned", "Yellow"),
        ("Suspended", "Orange"),
        ("Resumed", "Green"),
        ("Cold Copy Taken", "Light Blue"),
        ("Archived", "Yellow"),
        ("Restored", "Green"),
        ("Purge Warned", "Red"),
        ("Purged", "Red"),
        ("Backup Taken", "Green"),
        ("Backup Failed", "Red"),
        ("Over Quota", "Orange"),
        ("Back Under Quota", "Green"),
        ("Held", "Purple"),
        ("Released", "Gray"),
    ],
    # Not made by hand: the ladder's append-only trail.
    in_create=1,
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
# Account Request — the record that exists before a tenant does.
#
# Signup collects a workspace, a plan and a card before there is any site to
# hold that. This carries it from the form through payment to provisioning, and
# is what makes the flow resumable when someone abandons checkout and returns.
# --------------------------------------------------------------------------- #
doctype(
    "Account Request",
    search_fields="email,workspace_name",
    states=[
        ("Pending Payment", "Yellow"),
        ("Paid", "Light Blue"),
        ("Provisioning", "Blue"),
        ("Completed", "Green"),
        ("Failed", "Red"),
        ("Abandoned", "Gray"),
    ],
    # Not made by hand: signup creates these, and carries them through checkout.
    in_create=1,
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
    search_fields="shard,status",
    states=[
        ("Creating", "Blue"),
        ("Ready", "Green"),
        ("Claimed", "Gray"),
        ("Broken", "Red"),
        ("Archived", "Yellow"),
    ],
    # Not made by hand: the pool builder creates these against a real site on Frappe Cloud.
    in_create=1,
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
    search_fields="region_name,country",
    autoname="field:region_code",
    title_field="region_name",
    fields=[
        f("region_code", reqd=1, unique=1, description="e.g. nuremberg"),
        f("region_name", reqd=1, in_list_view=1, description="Shown at signup, e.g. Nuremberg"),
        # A Link, not free text, because this is not decoration: it reaches a
        # tenant through the sync payload, names the Company that is created
        # there, and picks its chart of accounts — `_charts_for(country)` in
        # `oneapp/oneapp_core/books.py` looks up by exactly this string. A typo
        # produced a workspace whose books quietly never got set up.
        #
        # `Country` is core Frappe (`frappe/geo`), so this costs no dependency,
        # and the workspace's own settings dialog already declares country the
        # same way — the two ends now agree instead of one being a picker and
        # the other a text box feeding it.
        f("country", "Link", options="Country", reqd=1, in_list_view=1,
          description="Where this region physically is. Sent to tenants created "
                      "here to set up their company and chart of accounts."),
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
    search_fields="jurisdiction,status",
    states=[
        ("Provisioning", "Blue"),
        ("Active", "Green"),
        ("Full", "Yellow"),
        ("Retired", "Gray"),
    ],
    # Not made by hand: `r2.provision_bucket` makes the bucket first and the row after.
    in_create=1,
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


# --------------------------------------------------------------------------- #
# OneSpace Site State (Single, tenant) — what the control plane last told us.
#
# The tenant end of the signed sync: quotas, usage, credits and the space
# manifest, cached here so every page load is a local read rather than a call
# across the wire to a site that may be unreachable. Nothing here is authored —
# every field is written by `oneapp_core.sync` and read by the app.
#
# It was the one doctype maintained by hand rather than declared here, which
# made it the one doctype `test_every_doctype_on_disk_is_what_the_generator_
# would_write` did not cover — the file could drift and nothing would say so.
# That is the whole failure the generator exists to prevent, so it is declared
# here now and a second test refuses any new doctype directory that is not.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Site State",
    app="tenant",
    issingle=1,
    # A cache the sync rewrites every few minutes. With change tracking on,
    # each of those files a Version row recording a change no person made.
    track_changes=0,
    # Read-only to a person for the same reason the audit trails are: editing
    # the cached copy of a quota does not raise the quota, it just makes this
    # site disagree with the control plane until the next sync overwrites it.
    perms=READONLY_PERMS,
    fields=[
        f("tenant", read_only=1,
          description="Data, not a Link: `Tenant` is a control-plane doctype "
                      "and does not exist on this site."),
        f("site_name", read_only=1),
        f("status", read_only=1),
        f("plan_code", read_only=1),
        column("cb1"),
        f("last_sync", "Datetime", read_only=1),
        f("last_sync_error", "Small Text", read_only=1),
        f("storage_quota_bytes", "Float", read_only=1),
        f("database_quota_bytes", "Float", read_only=1,
          description="Synced from the plan. Zero means unconfigured, not zero "
                      "allowed."),
        f("max_users", "Int", read_only=1),
        f("background_workers", "Int", read_only=1,
          description="Concurrent background jobs this workspace may run."),
        f("backups_per_day", "Int", read_only=1,
          description="How many times a day this workspace copies itself into "
                      "R2. A plan term, so the schedule is a decision the "
                      "control plane makes and this site carries out."),
        section("sec_usage", "Usage"),
        f("storage_used_bytes", "Float", read_only=1),
        f("database_used_bytes", "Float", read_only=1),
        f("quota_json", "Code", label="Quota Enforcement", options="JSON",
          read_only=1,
          description="Whether to enforce quotas at all, and until when if not. "
                      "A workspace over its limit because a line left its "
                      "subscription is given a window rather than a wall."),
        column("cb2"),
        f("credit_balance", "Float", read_only=1),
        section("sec_cache", "Cached manifest"),
        f("spaces_json", "Code", label="Spaces JSON", options="JSON", read_only=1),
        f("roles_json", "Code", label="Roles JSON", options="JSON", read_only=1),
        f("last_notice", read_only=1, label="Last Notice",
          description="The most recent workspace notice this site has already "
                      "turned into a notification. A watermark rather than a "
                      "deduplication key: the control plane is asked for what "
                      "happened after it, so nothing is sent twice and nothing "
                      "in between is missed."),
    ],
)
