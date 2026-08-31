"""What an operator screen can *do*, beyond listing and editing.

A screen over a doctype gets a list, filters, a record and a form for free. Two
things it does not get: a method that is not a field write, and a way through to
a bespoke screen that belongs to one record. Both used to live in hand-written
console pages, so retiring those without this would have left them doable only
in the desk — which is the one place this product does not go (DECISIONS §7).

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
