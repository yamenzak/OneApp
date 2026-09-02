"""What an operator screen can *do*, beyond listing and editing.

A screen over a doctype gets a list, filters, a record and a form for free. Two
things it does not get: a method that is not a field write, and a way through to
a bespoke screen that belongs to one record. Both used to live in hand-written
console pages, so retiring those without this would have left them doable only
in the desk — which is the one place this product does not go (docs/ONEADMIN.md, No desk).

Declared in code, behind the `onespace_screen_actions` hook, and that is
deliberate: an action names a method somebody can invoke, so the list of them is
not something an operator should be able to extend by editing a row. The
resolver reads this list twice — once to render the buttons, once to decide
whether a request naming one may run — so what is here is exactly what can be
called, and `spaceview.run_action` still asks Frappe whether this person may
write the record before calling anything.

Read by `oneapp.oneapp_core.spaceview.actions`.
"""

from oneapp_control.entitlements.operator import SPACE_CODE


def actions() -> dict:
	"""Keyed `space_code/screen`, which is how the resolver looks one up."""
	return {
		f"{SPACE_CODE}/tenants": [
			{
				# Not a method: the record's own screen, which shows what
				# Frappe Cloud is running beside what we hold, and carries the
				# backups, domains, support sign-in and billing.
				"key": "open",
				"label": "Open workspace",
				"icon": "lucide-wrench",
				"scope": "record",
				"screen": "tenant",
			},
			{
				# The ladder runs on a timer and destroys data at the end of it,
				# so stopping it has to be one click from the list an operator
				# is already looking at — not a field on a form two screens in.
				"key": "hold",
				"label": "Hold from the lifecycle",
				"icon": "lucide-shield",
				"scope": "selection",
				"method": "oneapp_control.api.admin.hold_lifecycle",
			},
			{
				"key": "release",
				"label": "Release into the lifecycle",
				"icon": "lucide-refresh-cw",
				"scope": "selection",
				"method": "oneapp_control.api.admin.release_lifecycle",
				"confirm": (
					"The clock did not stop while this workspace was held — only "
					"the consequences did. It resumes at whatever rung its dates "
					"say it is on, which may be further down than when it was held."
				),
			},
			{
				# How a policy change is tested: widen a window, run this, read
				# the event log.
				"key": "run-lifecycle",
				"label": "Apply the lifecycle now",
				"icon": "lucide-clock",
				"scope": "record",
				"method": "oneapp_control.api.admin.run_lifecycle",
				"confirm": (
					"This takes exactly the path the nightly sweep takes, "
					"including suspending or archiving the workspace if its "
					"dates say so."
				),
			},
			{
				"key": "cold-copy",
				"label": "Take a cold copy",
				"icon": "lucide-package",
				"scope": "record",
				"method": "oneapp_control.api.admin.take_cold_copy",
			},
			{
				"key": "restore",
				"label": "Restore from cold",
				"icon": "lucide-refresh-cw",
				"scope": "record",
				"method": "oneapp_control.api.admin.restore_from_cold",
				"confirm": (
					"This builds a new site and replaces its database with the "
					"cold copy. Only offered for a workspace that no longer has "
					"a site of its own."
				),
			},
			{
				"key": "purge",
				"label": "Purge everything",
				"icon": "lucide-trash",
				"scope": "record",
				"method": "oneapp_control.api.admin.purge_tenant",
				"confirm": (
					"This permanently deletes the cold copy, every backup and "
					"every file this workspace owns. It cannot be undone, and "
					"afterwards the workspace cannot be restored by anyone."
				),
			},
			{
				"key": "adopt-terms",
				"label": "Move to the plan's current terms",
				"icon": "lucide-refresh-cw",
				"scope": "record",
				"method": "oneapp_control.api.admin.adopt_plan_terms",
				"confirm": (
					"This workspace's quotas were captured when its subscription "
					"was sold. Replacing them with the plan's current terms cannot "
					"be undone from here."
				),
			},
		],
		f"{SPACE_CODE}/webhooks": [
			{
				# The deliberate half of answering Stripe 200 on failure: the
				# stored row is the replay, and without this it is a row nobody
				# can act on.
				"key": "replay",
				"label": "Replay",
				"icon": "lucide-refresh-cw",
				# A failed batch is the usual case — a handler was broken for an
				# hour — so this is offered against a selection as well as one
				# record. The handlers are idempotent by the arguments they
				# already rely on.
				"scope": "selection",
				"method": "oneapp_control.api.admin.replay_webhook",
			},
		],
	}
