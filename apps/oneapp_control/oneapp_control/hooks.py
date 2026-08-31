app_name = "oneapp_control"
app_title = "OneAdmin"
app_publisher = "Four Degree Labs"
app_description = "OneSpace control plane: tenants, shards, plans, credits and provisioning."
app_email = "hello@fourdegreelabs.com"
app_license = "mit"

# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------
# Without this, a reload on the welcome page serves Frappe's 404 instead of the
# SPA shell: Frappe only resolves the exact route, and the Vue router never gets
# a chance to run.
#
# One surface now. `/admin` and `/portal` were two SPAs over the same bundle;
# both are Spaces rendered by `oneapp` on this site, and what is left is signup
# — the one page somebody reaches before they have an account, which is why it
# could not move with them. See www/signup.py.
website_route_rules = [
	{"from_route": "/signup/<path:app_path>", "to_route": "signup"},
]

# Where a signed-in user lands. Without this Frappe falls through to "me",
# which it rewrites to "desk" for any System User — so signing in as an
# operator dropped you into the desk, which is the one place this product does
# not go.
#
# `one`, for everybody. An operator and a customer are two Spaces in the same
# shell, and which one opens is decided by the roles they hold rather than by
# the URL they were sent to.
#
# Still a function rather than the plain `home_page` string, because `oneapp`
# declares one too and Frappe resolves competing hooks by taking the last app's
# — which would make the answer depend on the order the two were installed in.
# This hook is checked before either, so it is a decision rather than an
# accident.
get_website_user_home_page = "oneapp_control.portal.landing"

# ---------------------------------------------------------------------------
# Spaces, for OneSpace running on this site
# ---------------------------------------------------------------------------
# A tenant learns which spaces it has from the control plane, over HMAC. The
# control plane has no control plane to ask — it is one — so where a tenant
# syncs, this hands `oneapp` the same list in process, read from the registry
# it already holds. Everything downstream cannot tell the two apart, which is
# the point: where a space's description came from is not a property of it.
#
# `oneapp` ships no provider of its own, so a tenant site is unaffected.
onespace_space_providers = ["oneapp_control.entitlements.registry.local_spaces"]

# And its settings, in OneSpace's own settings dialog rather than in a second
# one. Gated on System Manager per group, so a customer signed in to their
# account area on this site sees none of them.
onespace_settings_groups = ["oneapp_control.entitlements.settings.groups"]

# And what its screens can *do* — replaying a Stripe event, moving a workspace
# onto its plan's current terms, opening the workspace screen for a tenant. A
# generic screen lists and edits; these are the calls that are neither, and
# declaring them in code is what keeps the set of invokable methods out of the
# database. See `entitlements/actions.py`.
onespace_screen_actions = ["oneapp_control.entitlements.actions.actions"]

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
		# Compares what we charged for AI against what the gateway's own log says
		# the call cost. Hourly because gateway logs are written after the fact.
		"oneapp_control.ai.reconcile.scheduled_run",
	],
	"daily": [
		# Models and prices change without notice, and the way you find out is a
		# margin rather than an error. Cheap enough to run every day.
		"oneapp_control.ai.catalogue.scheduled_sync",
		# Posts explicit Expiry rows so the ledger reads as a complete history.
		"oneapp_control.credits.ledger.expire_stale_grants",
	],
}

# ---------------------------------------------------------------------------
# Document hooks
# ---------------------------------------------------------------------------
# Editing a space in the console has to reach the shell that renders it, and
# `oneapp`'s state cache holds the space list for five minutes. Without this a
# screen added to a space appears somewhere between now and then, which reads
# as the change not having saved.
doc_events = {
	"OneSpace Space": {
		"on_update": "oneapp_control.entitlements.registry.forget_spaces",
		"on_trash": "oneapp_control.entitlements.registry.forget_spaces",
	},
}

# ---------------------------------------------------------------------------
# Fixtures — the app registry and plans are configuration, not customer data.
# ---------------------------------------------------------------------------
fixtures = [
	{"dt": "OneSpace Space"},
	{"dt": "Plan"},
	{"dt": "Region"},
]

after_install = "oneapp_control.install.after_install"

# The operator console's shape lives in code, so a migration is how it changes.
# Without this an existing control plane would keep whatever console it was
# installed with until somebody remembered to re-seed it by hand.
after_migrate = "oneapp_control.install.after_migrate"
