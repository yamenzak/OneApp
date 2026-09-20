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

import json

import frappe

#: The space's code, which is also the second segment of every address inside
#: it — `/one/space/one`. Short, and it is the product's name.
CODE = "one"

#: The app whose presence means this site is the control plane and not a
#: workspace. Exact rather than a heuristic about tenants: a development bench
#: has no tenant row and is still a workspace.
CONTROL_APP = "oneapp_control"


#: Every settings panel, under the heading it belongs to.
#:
#: The order and the wording are `tabs.py`'s — that module says which panels
#: exist, what each is called and who may open it, and this says where each one
#: sits on the page. Split that way because they are two different questions
#: and only one of them is about permission: a panel dropped from here is a
#: panel nobody can reach, and a panel dropped there is one nobody may.
#:
#: **You** first, and it is not a courtesy. Everybody has these four; half the
#: workspace has none of the rest, and a page that opens on Branding for
#: somebody who cannot write it opens on somebody else's business.
CONFIGURATION = [
	{"label": "You", "screens": [
		{"panel": "profile"}, {"panel": "security"},
		{"panel": "notifications"}, {"panel": "appearance"},
		{"panel": "mailbox"}, {"panel": "legal"},
	]},
	# Who is in this workspace and what they may do. One's rather than any
	# space's, and that is the division the whole restructure turns on: a role
	# is *defined* by the space that needs it and *granted* here, because a
	# person holds one set of roles across every space they open.
	{"label": "People", "screens": [
		{"panel": "people"}, {"panel": "roles"},
	]},
	# The workspace as a thing: what it looks like, how you get into it, where
	# its files are, what it is called on the internet.
	{"label": "Workspace", "screens": [
		{"panel": "branding"}, {"panel": "signin"}, {"panel": "regional"},
		{"panel": "domain"}, {"panel": "books"},
		# And AI, which is here rather than on a space and is the one of the
		# four settings that did not move. A feature belongs to an *app* —
		# `@ai_feature("invoice.summary", …)` — and nothing in a feature says
		# which space it is for, so there is nothing to narrow it by. Alerts,
		# naming and print formats are all keyed on a doctype, which is exactly
		# what a space has already declared.
		{"panel": "ai"},
	]},
	# What it sends and what it prints. Per-workspace because an address and a
	# paper size are not a space's business; a print *format* is, and lives on
	# the space whose records it prints.
	{"label": "Mail and paper", "screens": [
		{"panel": "mail"}, {"panel": "templates"}, {"panel": "printing"},
	]},
	# Where the bytes are.
	{"label": "Storage", "screens": [
		{"panel": "storage"}, {"panel": "backups"}, {"panel": "connections"},
	]},
]


def screens() -> list[dict]:
	"""One's own screens.

	Ordinary screen declarations, in the shape the control plane sends: a
	`component` each, because neither of these is a list of records. Everything
	downstream — the rail, the resolver, the phone's More sheet — reads them the
	way it reads OneHR's.

	Configuration is the same component every other space's is, which is the
	point: the panels that were a dialog are tabs on the page a space already
	had for the tables it is maintained by. Its `view_settings` names panels
	instead of screens, and `configuration.py` drops the ones this reader may
	not open — so a member finds four tabs here and an admin finds twenty.
	"""
	return [
		{
			"screen": "home",
			"label": frappe._("Home"),
			"icon": "lucide-layout-grid",
			"component": "one/home",
		},
		*_waiting(),
		{
			"screen": "configuration",
			"label": frappe._("Configuration"),
			"icon": "lucide-wrench",
			"component": "configuration",
			"view_settings": json.dumps(
				{"configuration": {"screens": CONFIGURATION}}
			),
		},
	]


def _waiting() -> list[dict]:
	"""The approvals inbox, on a site that has something to approve.

	Declared conditionally, which is the one screen here that is. A workflow is
	part of what an app *is* — it ships with whoever owns the doctype, and most
	workspaces have none — so an Approvals entry in every rail from the day it
	is built is a door that opens onto nothing for the majority of them, for
	ever. `is_active` is the whole of the test, and it is the same fact the
	record header reads before it offers a transition.

	It stops being declared again if the last workflow is turned off, which is
	the behaviour worth having: the rail follows the site rather than
	remembering what it used to be.
	"""
	if not frappe.db.exists("Workflow", {"is_active": 1}):
		return []
	return [{
		"screen": "waiting",
		"label": frappe._("Approvals"),
		"icon": "lucide-inbox",
		"component": "one/waiting",
	}]


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
