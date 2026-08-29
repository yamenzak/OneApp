app_name = "oneapp_control"
app_title = "OneApp Control"
app_publisher = "Four Degree Labs"
app_description = "OneApp control plane: tenants, shards, plans, credits and provisioning."
app_email = "hello@fourdegreelabs.com"
app_license = "mit"

# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------
# Without these, a page reload on any deep link serves Frappe's 404 instead of
# the SPA shell: Frappe only resolves the exact route, and the Vue router never
# gets a chance to run.
#
# Two surfaces, one bundle. /admin is the staff console and /portal is the
# customer's; they are separate website routes so www/admin.py and www/portal.py
# can apply different access rules to the same built assets.
website_route_rules = [
	{"from_route": "/admin/<path:app_path>", "to_route": "admin"},
	{"from_route": "/portal/<path:app_path>", "to_route": "portal"},
]

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
scheduler_events = {
	"cron": {
		# Provisioning jobs are resumable; this drives them forward and retries
		# whatever failed transiently.
		"*/2 * * * *": [
			"oneapp_control.provisioning.runner.process_pending_jobs",
		],
		# Keeps each shard's warm pool topped up. Slow by design — a couple of
		# sites per run, so a mistyped target cannot flood the server with builds.
		"*/10 * * * *": [
			"oneapp_control.provisioning.standby.top_up",
		],
		# Bucket rollups drive rotation, so they run often enough that a bucket
		# cannot quietly overshoot its cap between sweeps.
		"*/30 * * * *": [
			"oneapp_control.cloudflare.r2.refresh_usage",
		],
	},
	"hourly": [
		# A crashed worker must not strand a tenant's credits behind an open
		# reservation forever.
		"oneapp_control.control_plane.doctype.credit_reservation.credit_reservation.sweep_expired_reservations",
	],
	"daily": [
		# Posts explicit Expiry rows so the ledger reads as a complete history.
		"oneapp_control.credits.ledger.expire_stale_grants",
	],
}

# ---------------------------------------------------------------------------
# Fixtures — the app registry and plans are configuration, not customer data.
# ---------------------------------------------------------------------------
fixtures = [
	{"dt": "OneApp App"},
	{"dt": "Plan"},
	{"dt": "Region"},
]

after_install = "oneapp_control.install.after_install"
