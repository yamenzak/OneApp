app_name = "oneapp_control"
app_title = "OneApp Control"
app_publisher = "Four Degree Labs"
app_description = "OneApp control plane: tenants, shards, plans, credits and provisioning."
app_email = "hello@fourdegreelabs.com"
app_license = "mit"

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
]

after_install = "oneapp_control.install.after_install"
