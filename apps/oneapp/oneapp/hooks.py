app_name = "oneapp"
app_title = "OneApp"
app_publisher = "Four Degree Labs"
app_description = "Unified application surface for Four Degree Labs tenants."
app_email = "hello@fourdegreelabs.com"
app_license = "mit"

required_apps = ["erpnext"]

# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------
# The Vue router owns everything under /one. Frappe's desk stays at /app so the
# two never collide, and desk remains available to us for support.
website_route_rules = [
	{"from_route": "/one/<path:app_path>", "to_route": "one"},
]

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
# Attachments go to R2 rather than the server filesystem. The override falls
# back to Frappe's normal behaviour when R2 is not configured, so a site without
# keys still works instead of failing every upload.
override_doctype_class = {
	"File": "oneapp.oneapp_core.storage.file.OneAppFile",
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
scheduler_events = {
	"cron": {
		# Entitlements and balance. Frequent because revoking an app should take
		# effect in minutes, not hours.
		"*/15 * * * *": ["oneapp.oneapp_core.sync.sync_from_control_plane"],
	},
	"hourly": [
		"oneapp.oneapp_core.sync.report_usage_to_control_plane",
		# Re-measures the database and caches the verdict the insert hook reads,
		# so a workspace that frees space is unblocked without waiting out the
		# cache, and one that fills up is caught within the hour.
		"oneapp.oneapp_core.storage.quota.refresh_database_verdict",
	],
}

after_install = "oneapp.install.after_install"
