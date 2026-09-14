"""One: the space every workspace has, and the only one nobody adds.

Every other space in this product is data on the control plane — a row, an
entitlement, a manifest that arrives over a signed call. That is right for
OneHR and it is wrong for this one, because this one is not something a
workspace *has*. It is the workspace.

What was there before was a page called Spaces: a grid of cards you arrived at
in order to leave. It is the shape a shell takes when there is nowhere that is
not inside something — the front door was a directory of doors. And it left
everything that belongs to no space with nowhere to be: your profile, the
workspace's own settings, who is in it and what they may do, all of it in a
dialog with no address that opened over whatever you happened to be looking
at.

So One is a space. Same rail, same screens, same Configuration page every other
space has — and the things that belong to no space live on it, which is a
sentence that was not sayable before. The front door is a place you can work
rather than a list of places you could.

**Provided rather than entitled.** `sync.local_spaces()` is the seam: an app
registers a provider under `onespace_space_providers` and what it returns is
indistinguishable downstream from what a sync brought. `oneapp` shipped no
provider until now; this is it, and it is the only one it will ship.

**Not on the control plane.** That site is an operator console, not a
workspace: its spaces are the console and the customer's account, and a
Configuration page for "this workspace" would be a Configuration page for the
platform's own bookkeeping. `oneapp_control` being installed is the whole of
the test, and it is exact — that app is on one site.

**No role.** An empty `role_name` means everybody on the site, which is what
`resolve.visible` has always done with one. Narrowing is per *screen* and per
*tab*, where it belongs: a member opening Configuration finds the four tabs
that are theirs, not a door that does not open.
"""

import frappe

#: The space's code, which is also the second segment of every address inside
#: it — `/one/space/one`. Short, and it is the product's name.
CODE = "one"

#: The app whose presence means this site is the control plane and not a
#: workspace. Exact rather than a heuristic about tenants: a development bench
#: has no tenant row and is still a workspace.
CONTROL_APP = "oneapp_control"


def screens() -> list[dict]:
	"""One's own screens.

	Ordinary screen declarations, in the shape the control plane sends: a
	`component` each, because neither of these is a list of records. Everything
	downstream — the rail, the resolver, the phone's More sheet — reads them the
	way it reads OneHR's.
	"""
	return [
		{
			"screen": "home",
			"label": frappe._("Home"),
			"icon": "lucide-layout-grid",
			"component": "one/home",
		},
	]


def local_spaces() -> list[dict]:
	"""One, for every site that is a workspace.

	A list of one rather than a dict, because that is what the hook's contract
	is and because the day something else belongs here it should not be a
	change of shape.
	"""
	if CONTROL_APP in (frappe.get_installed_apps() or []):
		return []

	return [{
		"space_code": CODE,
		"space_label": "One",
		"module": "",
		# Everybody. See the module docstring.
		"role_name": "",
		"icon": "lucide-layout-grid",
		"logo": "",
		"brand": CODE,
		# Before every space a workspace was sold, because it is the one they
		# did not buy. `local_spaces` is concatenated after the synced list and
		# `visible_spaces` keeps the order it is given, so the sort is what puts
		# it first.
		"sort_order": -1000,
		"description": "",
		"theme": "",
		"requires_apps": "",
		"custom_fields": "",
		"alerts": "",
		"field_levels": "",
		"screens": screens(),
	}]
