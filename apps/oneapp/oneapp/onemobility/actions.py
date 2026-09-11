"""What OneMobility's screens can do beyond listing and editing.

One button on the Sources screen because the alternative is the desk — which is
the one place this product does not go — and three that carry a record over to
the screen that can say how it behaved.

Read by `oneapp.onespace.spaceview.actions`; see that module for why an action
is declared in code rather than stored on a row.

The three are the seam between the two halves of this module. A line, a stop
and a vehicle are *documents*: they have a form, a timeline, comments, an
owner. How each of them ran is not — it lives in the fact tiers, outside the
document system on purpose, and no amount of dashboard widgets over `tabTransit
Line` will ever reach it. So the record does not try to draw the analytics; it
hands its own name to the screen that already knows how, and the facet bar
there arrives with that one thing chosen.

Which is also why each names a different `param`. `facets.py` calls them line,
stop and vehicle, Insights reads whichever it was given, and the tab that opens
is the one whose tier can answer for that kind of thing.
"""


def actions() -> dict:
	"""Keyed `space_code/screen`, which is how the resolver looks one up."""
	seen = {
		"key": "how-it-ran",
		"icon": "lucide-chart-pie",
		"scope": "record",
		"screen": "insights",
	}
	return {
		"onemobility/lines": [
			{**seen, "label": "How this line ran", "param": "line"},
		],
		"onemobility/stops": [
			{**seen, "label": "How this stop is served", "param": "stop"},
			{
				# A vehicle stopped somewhere no feed declares a stop, so one
				# was inferred and drawn differently. §6's last paragraph: it
				# is never quietly promoted, and this is the person saying it
				# is real — which is the only thing that should be able to.
				"key": "accept",
				"label": "Accept into the network",
				"icon": "lucide-check",
				"scope": "selection",
				"method": "oneapp.onemobility.accept_stop",
			},
		],
		"onemobility/vehicles": [
			{**seen, "label": "How this vehicle ran", "param": "vehicle"},
		],
		"onemobility/sources": [
			{
				# The Upload door, which README §5 has named since the module
				# was written and which had no surface until now: the endpoint
				# existed and nothing called it, so the one kind of source a
				# manager tries first was the one kind that could not be used.
				#
				# `upload` rather than a screen of its own. A delivery is a
				# thing that happens *to a source* — it is kept against it, it
				# fails against it, it shows on its Deliveries — so the button
				# belongs beside the source and not on a page that would have
				# to ask which one anyway.
				#
				# And `record` rather than `selection`, which is where this
				# first shipped and was wrong twice over. A selection action
				# lives in the floating bar and is reached by ticking a row,
				# which is nobody's guess for where an upload is; and one file
				# delivered to several sources at once would write the same
				# bytes to each, which is not a thing anybody wants. You open
				# the source you are delivering to.
				"key": "upload",
				"label": "Upload a delivery",
				"icon": "lucide-upload",
				"scope": "record",
				"method": "oneapp.onemobility.load_feed",
				"upload": True,
			},
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
			{
				# And the same question for the door that is never asked:
				# a socket is read in windows by the scheduler, so "fetch"
				# means nothing to it and the first five minutes of silence
				# after saving the form look exactly like a wrong endpoint.
				# This opens it for a few seconds and says what came.
				"key": "listen",
				"label": "Listen now",
				"icon": "lucide-radio",
				"scope": "selection",
				"method": "oneapp.onemobility.listen_now",
			},
		],
	}
