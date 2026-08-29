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
	"hourly": ["oneapp.oneapp_core.sync.report_usage_to_control_plane"],
}

after_install = "oneapp.install.after_install"
