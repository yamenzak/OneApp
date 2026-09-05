"""Spaces, screens, roles — what a workspace is allowed to see.

A space grants doctypes and declares screens over them; a role names a subset. A
saved view is one person's arrangement of a screen, and hiding one is
per-person too.
"""

from app_icons import SPACE_ICONS, DEFAULT_SPACE_ICON
from .spec import column, doctype, f, section


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
        # A screen's label is plural by convention — "Tasks", "Invoices" — and
        # the heading over a create form wants one of these, not all of them.
        # It is derived from the label ("Tasks" → "Task"), so this is only for
        # the plurals a small rule gets wrong. It is never the doctype's own
        # name: that is a Frappe word, and a customer clicking New on a screen
        # called Tasks was reading "New ToDo".
        f("singular", label="One of these is called",
          description="Optional. The screen's label in the singular, where "
                      "trimming an `s` gets it wrong — People, Series, a label "
                      "that is already singular."),
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
        # Narrowing only, deliberately. A screen may refuse to offer New over a
        # doctype that allows it — an ERPNext doctype we do not own, a screen
        # meant as a report — but it may not offer New over a doctype whose own
        # `in_create` says no. A manifest that could grant creation would be a
        # second, weaker answer to a question the doctype already answers.
        f("hide_new", "Check", default="0", label="Never offer New",
          description="Hide New on this screen even where the doctype allows "
                      "one to be made. For a screen that reads records "
                      "something else writes."),
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
                      '{"column_field": "status", "card_fields": ["priority"]}}. '
                      'Nested by view type because one screen offers several. '
                      'A key ending in `_field` is one fieldname and `_fields` '
                      'is a list of them; both are checked against the doctype '
                      'like a filter or a sort, and anything else is dropped. '
                      'A board may name a Select or a Link here instead of the '
                      'status field — and a reader may name another again in a '
                      'saved view, which is where their own choice lives. Each '
                      'card-shaped type keeps its own `card_fields`: a board '
                      'card sits under a heading naming the field it is '
                      'bucketed by and a grid card does not.'),
        # The override, and only an override. Every tab already gets a glyph
        # derived from its own label — Frappe has no icon property on a Tab
        # Break, and a doctype we do not own will never have a manifest entry —
        # so this is for the tab whose words say nothing useful. A name outside
        # the SPA's closed set falls back to the derived one rather than
        # drawing a blank; `tests/test_manifests.py` fails the build on one.
        f("tab_icons", "Code", options="JSON",
          description='An icon per tab of the record form, keyed by the tab\'s '
                      'label: {"Overview": "lucide-list"}. Only where the tab\'s '
                      'own words earn the wrong glyph — every tab has one '
                      'without this. Names come from the SPA\'s TAB_ICONS.'),
        section("sec_view_query"),
        f("filters", "Code", options="JSON",
          description='Always applied, e.g. {"status": "Open"}.'),
        column("cb_view_sort"),
        f("order_by", default="modified desc"),
        # --------------------------------------------------------------- #
        # What a space brings with it besides the screen.
        #
        # Both of these are *fixtures*: applied on the tenant the first time
        # the space is seen and never again, so an app ships a sensible start
        # and the workspace still owns what it does with it. A sync that
        # rewrote them every quarter hour would silently undo the format
        # somebody spent an afternoon on.
        # --------------------------------------------------------------- #
        section("sec_screen_fixtures"),
        f("naming_series", "Small Text",
          description="Prefixes this screen's doctype offers, one per line — "
                      "`ACME-INV-.YYYY.-.#####`. Applied once, when the space "
                      "first arrives; the workspace edits its own afterwards "
                      "under Settings, Naming. Ignored where the doctype has "
                      "no `naming_series` field."),
        column("cb_screen_print"),
        f("print_formats", "Code", options="JSON",
          description='Print formats to ship, as a list: [{"name": "ACME '
                      'Invoice", "default": true, "layout": {...}, "setup": '
                      '{...}}]. `layout` is Frappe\'s own `format_data` — draw '
                      'it in the builder under Settings, Print formats and '
                      'paste it here, so what an app ships and what a '
                      'workspace draws are the same kind of thing. Created '
                      'once, per format, if nothing of that name exists.'),
    ],
)


doctype(
    "OneSpace Space",
    search_fields="space_label,module",
    states=[
        ("General", "Green"),
        ("Restricted", "Orange"),
    ],
    autoname="field:space_code",
    title_field="space_label",
    fields=[
        f("space_code", reqd=1, unique=1, description="Stable id, e.g. crm"),
        f("space_label", reqd=1, in_list_view=1),
        f("module", reqd=1, in_list_view=1,
          description="Frappe module inside the oneapp app that implements this."),
        # What the site under this space has to be carrying. A tenant's site is
        # the union of what its granted spaces need, so a space that names
        # nothing costs nothing — and a grant onto a site whose bench cannot
        # carry the app is refused with the app named, rather than succeeding
        # into screens that are silently empty.
        f("requires_apps", label="Requires Apps",
          description="Frappe apps this space's screens are written against, "
                      "comma separated — e.g. erpnext,hrms. A tenant's site is "
                      "the union of what its granted spaces need, so a space "
                      "that names none adds nothing to it."),
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
        section("sec_space_roles", "Roles"),
        f("roles", "Table", options="OneSpace Space Role",
          description="What this app offers a workspace to hand out. None is "
                      "the old shape: one role, everything in the manifest."),
        section("sec_manifest", "Doctypes"),
        f("doctypes", "Table", options="OneSpace Space Doctype",
          description="Everything this app exposes. One list, three jobs: the "
                      "DocPerms we write for our own roles, what an entitlement "
                      "grants, and the allowlist a customer's custom role may "
                      "draw from. A doctype in no manifest is reachable by "
                      "nobody, without anyone having to remember to exclude it."),
        # The schema its screens read that the doctype does not ship. Declared
        # beside the screens that read it, because the alternative is where
        # RUA's ten fields lived until now — in its *import plan*, so a tenant
        # granted the space who never imported anything got the screens without
        # the fields, and nothing anywhere said so.
        f("custom_fields", "Code", options="JSON",
          description='JSON list of Custom Field rows this space\'s screens '
                      'read but the doctype does not ship, e.g. [{"dt": "Sales '
                      'Invoice", "fieldname": "custom_retention_percentage", '
                      '"fieldtype": "Percent", "label": "Retention %"}]. '
                      'Applied by the tenant sync the first time it sees them, '
                      'and never again.'),
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
        # A space's own look, as four words rather than a stylesheet: a mode, an
        # accent, a ground and how sharp its corners are. Validated on the
        # tenant by `oneapp_core/theming.py` and expanded into CSS variables by
        # the browser, so a manifest declares an intent and never a token.
        f("theme", "Small Text",
          description='JSON. e.g. {"mode": "dark", "accent": "#E50914", '
                      '"ground": "#0F0F10", "radius": "sharp"}'),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace Space Role — a role a space ships with.
#
# A space used to carry exactly one role and hand every doctype in its manifest
# to it, so "has this app" and "may do everything in this app" were the same
# sentence. They are not: a shop wants someone who raises invoices and someone
# who only reads them, and neither of those is a second app.
#
# So a space ships a handful of named roles, and each grant row says which of
# them it belongs to. The workspace picks from these; it never edits them —
# a preshipped role is part of what the app *is*, and a customer who wants a
# different mix builds their own (see Workspace Role) rather than quietly
# redefining what "Sales" means everywhere.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Space Role",
    istable=1,
    fields=[
        f("role_key", reqd=1, in_list_view=1,
          description="Stable id inside this space, e.g. `sales`. What a grant "
                      "row and a member's role list name."),
        f("label", reqd=1, in_list_view=1,
          description="What a workspace manager reads when handing it out."),
        column("cb_space_role"),
        # Everyone entitled to the space gets this one without anybody choosing
        # it. Without a default, entitling an app would grant an app nobody can
        # open — which is how the single-role model behaved by accident and
        # what this has to keep doing on purpose.
        f("is_default", "Check", default="0", in_list_view=1,
          description="Given to every member of a workspace that has this "
                      "space. One role per space should be this, and it should "
                      "be the least of them."),
        f("description", "Small Text",
          description="What somebody holding it can do, in a sentence."),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace Space Doctype — the manifest row.
#
# We ignore the roles ERPNext, HRMS and Payments ship with: we use those apps for
# the logic they implement, not for their idea of who an "Accounts Manager" is.
# Our own roles therefore start with no permissions, and these rows are where
# they come from. See docs/ONESPACE.md, Roles.
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
        # Which of the space's roles this grant belongs to.
        #
        # Empty means every role in the space, which is exactly what a manifest
        # written before roles existed meant — one role, everything in the list.
        # So an untouched space keeps behaving the way it did, and a space that
        # wants two roles says so row by row.
        f("role", in_list_view=1,
          description="The `role_key` of a role this space ships. Empty grants "
                      "it to every role in the space."),
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
# Workspace Role Grant — one line of a custom role.
#
# The same three words a preshipped grant uses, so the two kinds of role are
# the same shape and one screen renders both. `space` is here and not on the
# parent because a custom role is allowed to reach across apps — "Bookkeeper"
# reads invoices in Books and contacts in CRM, and splitting that into two
# roles to satisfy a schema would be the schema showing through.
# --------------------------------------------------------------------------- #
doctype(
    "Workspace Role Grant",
    istable=1,
    fields=[
        # Not required: it labels the row, it does not identify it. The doctype
        # is what the grant is *about*, and one doctype can be exposed by two
        # spaces — insisting on one answer would make a true row unsaveable.
        f("space", in_list_view=1,
          description="Which space this doctype came from, for grouping. Data "
                      "rather than a Link so a space retired from the catalogue "
                      "leaves a row that reads instead of a delete that fails."),
        f("document_type", label="Doctype", reqd=1, in_list_view=1),
        f("access", "Select", options="Read\nWrite\nManage", default="Read",
          reqd=1, in_list_view=1),
        column("cb_role_grant"),
        f("if_owner", "Check", default="0", in_list_view=1,
          description="Only documents this person created."),
    ],
)


# --------------------------------------------------------------------------- #
# Workspace Role — a role the workspace made for itself.
#
# The preshipped roles are what an app thinks the jobs are. A workspace that
# disagrees builds its own out of the same parts: `entitlements.allowed_doctypes`
# is the allowlist, and it is the union of every doctype the workspace's own
# spaces expose — so a custom role can never reach a doctype an entitlement did
# not already grant, and never reach `User`, `Role` or `DocType`, which appear
# in no manifest.
#
# Held here rather than on the tenant site for the same reason members are: the
# signed sync runs one way, and whoever holds a role has to be decided beside
# whoever the members are.
# --------------------------------------------------------------------------- #
doctype(
    "Workspace Role",
    search_fields="tenant,role_label",
    autoname="hash",
    title_field="role_label",
    fields=[
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("role_label", reqd=1, in_list_view=1,
          description="What the workspace calls it. Shown wherever roles are "
                      "handed out."),
        f("is_active", "Check", default="1", in_list_view=1,
          description="Unchecking takes it off everyone holding it at the next "
                      "sync, without losing what it was."),
        column("cb_workspace_role"),
        f("created_by_email", "Data", options="Email", read_only=1,
          description="Who built it. A role that grants more than somebody "
                      "expected is a question with an answer."),
        f("description", "Small Text"),
        section("sec_workspace_role_grants", "What it may reach"),
        f("grants", "Table", options="Workspace Role Grant",
          description="Bounded by what this workspace's spaces already expose. "
                      "A doctype outside that list is refused on save."),
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
        # `credits_per_currency_unit` was here and is gone: a Credit Pack names
        # the credits it grants, so there was nothing left for a conversion rate
        # to convert. Nothing had read it since the pack catalogue landed, and a
        # settings field an operator can set that changes nothing is worse than
        # no field at all.
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
