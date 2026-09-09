"""What OneMobility's screens can do beyond listing and editing.

Two buttons, both on the Sources screen, and both there because the alternative
is the desk — which is the one place this product does not go.

Read by `oneapp.onespace.spaceview.actions`; see that module for why an action
is declared in code rather than stored on a row.
"""


def actions() -> dict:
	"""Keyed `space_code/screen`, which is how the resolver looks one up."""
	return {
		"onemobility/sources": [
			{
				# A source is polled on its own schedule, and the first thing
				# anybody does after filling the form in is want to know
				# whether it works. Waiting an hour to find out is not an
				# answer.
				"key": "fetch",
				"label": "Fetch now",
				"icon": "lucide-refresh-cw",
				"scope": "selection",
				"method": "oneapp.onemobility.fetch_now",
			},
		],
	}
