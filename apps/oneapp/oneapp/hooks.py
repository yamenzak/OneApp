app_name = "oneapp"
app_title = "OneSpace"
app_publisher = "Four Degree Labs"
app_description = "Unified application surface for Four Degree Labs tenants."
app_email = "hello@fourdegreelabs.com"
app_license = "mit"

# Deliberately not `required_apps = ["erpnext"]`.
#
# Nothing in this app imports erpnext at module level: every import in
# oneapp_core/books.py is deferred inside a function and gated on
# `erpnext_installed()`, and `books.status()` answers `available: False` when it
# is absent — which the workspace's Books panel renders as "No accounting app".
#
# So the hard requirement claimed a dependency the code does not have, and the
# only thing it actually stopped was running OneSpace anywhere erpnext is not
# installed — including every development bench, which is why this SPA went so
# long without being opened in a browser. Tenant benches still carry erpnext.

# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------
# The Vue router owns everything under /one. Without this rule Frappe resolves
# only the exact route, so reloading any deep link serves a 404 before the router
# ever runs. The desk at /app is left alone rather than used — see docs/ONEADMIN.md, No desk.
website_route_rules = [
	{"from_route": "/one/<path:app_path>", "to_route": "one"},
]

# Signing in lands on the workspace, not the desk. Frappe's fallback is "me",
# which it rewrites to "desk" for any System User.
home_page = "one"

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
# Attachments go to R2 rather than the server filesystem. The override falls
# back to Frappe's normal behaviour when R2 is not configured, so a site without
# keys still works instead of failing every upload.
override_doctype_class = {
	"File": "oneapp.oneapp_core.storage.file.OneSpaceFile",
}

# ---------------------------------------------------------------------------
# Document hooks
# ---------------------------------------------------------------------------
doc_events = {
	"File": {
		# Storage quota is enforced at upload time. Discovering you are 3 GB over
		# after the fact is a worse experience than a clear rejection now.
		"before_insert": "oneapp.oneapp_core.storage.quota.enforce_quota",
	},
	"Email Queue": {
		# Frappe queues one document per send, so counting them measures what
		# actually leaves the site.
		"before_insert": "oneapp.oneapp_core.email.outbound.enforce_send_rate",
	},
	# Following a document. Frappe stores the follow and then only ever emails a
	# digest about it, so these two are the in-app half — see
	# `oneapp_core.notifications`, "Following a document".
	#
	# Version and Comment rather than `on_update` for `*`: they are the same two
	# sources the framework's own digest reads, and a Version row exists only
	# where `track_changes` is on, which is exactly the condition a document has
	# to meet to be followable at all.
	"Version": {
		"after_insert": "oneapp.oneapp_core.notifications.on_version",
	},
	"Comment": {
		"after_insert": "oneapp.oneapp_core.notifications.on_comment",
	},
	# Inserts are what grow a database, so they are what pauses when a workspace
	# is over its allowance. Updates and deletes keep working, so deleting
	# something is always a way back. The check reads a cached verdict — the
	# measurement is an information_schema scan and must not run per insert.
	"*": {
		"before_insert": "oneapp.oneapp_core.storage.quota.enforce_database_quota",
	},
}

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# AI features
# ---------------------------------------------------------------------------
# Modules holding @ai_feature declarations. Listed rather than discovered by
# walking the package: a feature that only registers when something happens to
# import its module is a feature missing from the settings page on a cold worker.
#
# Apps built on OneSpace add their own here. Nothing ships one yet — the mechanism
# exists so the first app that needs AI declares it and gets the settings row,
# the credit hold and the operator registry entry for free.
ai_features = []

scheduler_events = {
	"cron": {
		# Entitlements and balance. Frequent because revoking an app should take
		# effect in minutes, not hours.
		"*/15 * * * *": ["oneapp.oneapp_core.sync.sync_from_control_plane"],
	},
	"daily": [
		# The register of things that expire — licences, visas, insurance — and
		# the warning before one does. Daily because a status derived on save
		# goes stale the moment the date changes: a licence that was Valid last
		# night is Expiring this morning and nobody saved it.
		"oneapp.oneapp_core.expiry.sweep",
	],
	"hourly": [
		"oneapp.oneapp_core.sync.report_usage_to_control_plane",
		# Backups, into R2, on the frequency the plan bought. Hourly rather than
		# daily because the frequency is a plan term and cannot be a cron line:
		# this wakes every hour and decides whether this hour is one of the
		# slots. See `oneapp_core/backup.py`.
		"oneapp.oneapp_core.backup.scheduled_backup",
		# Re-measures the database and caches the verdict the insert hook reads,
		# so a workspace that frees space is unblocked without waiting out the
		# cache, and one that fills up is caught within the hour.
		"oneapp.oneapp_core.storage.quota.refresh_database_verdict",
	],
}

after_install = "oneapp.install.after_install"

# Our own Notification Type, seeded the way the framework seeds its five: in
# code, idempotently, on install and on every migrate. A type is a doctype row,
# so an app adds one rather than forking an enum.
after_migrate = "oneapp.oneapp_core.notifications.install_types"

# `Workspace` never sends its own email.
#
# Every notice under it — a declined card, a workspace archived, a quota
# reached — is already an email the *control plane* sent the moment it
# happened, from the side that knows the billing address and owns the wording.
# The in-app notification is the second half of that, not a duplicate of it, and
# `is_email_notifications_enabled_for_type` reads this hook to keep it so.
# `Following` never sends its own email either, and for a different reason:
# following a busy record is one email per save. Frappe's answer to that is the
# Hourly/Daily/Weekly digest in `send_document_follow_mails`, which is the right
# shape for email and needs a frequency preference we have not built — so a
# follow is an in-app subscription and says so, rather than quietly filling an
# inbox. The digest is left alone: `User.document_follow_notify` stays 0.
notification_skip_email_types = ["Workspace", "Following"]
