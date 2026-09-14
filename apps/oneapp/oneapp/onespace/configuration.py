"""The screens a Configuration page puts behind tabs.

Every space ends up with a handful of tables that are maintained rather than
worked in — leave types, project types, sales stages, salary components — and
ERPNext's answer is a rail entry each, interleaved with the transactions, which
is how a salesperson's list of destinations comes to contain Market Segment.
`docs/ERP-SPACES.md` §2 refused that by pushing them into a **Setup** group at
the bottom. That was better and is still six entries somebody scrolls past every
day, and it left a second problem untouched: the doctypes a space grants so its
*pickers* work and gives no screen at all — Leave Policy, Payroll Period,
Interview Type — which can then only be edited from the desk.

One page fixes both. A screen declares:

    "component": "configuration",
    "view_settings": {"configuration": {"screens": ["leave-types", "shift-types"]}}

and each name is another screen *in the same space*, marked `hide_in_nav` so it
keeps its route and leaves the rail. The browser then draws one tab per screen
and the ordinary list inside it — which is the same trick `showcase.tabs` uses,
and for the same reason: a tab that names a screen is a tab whose space,
permissions, columns and filters are all checked where every list checks them.
Nothing here is a second way to reach a doctype.

So this module does one small thing: turn those names into the labels and icons
a tab strip needs, dropping any that are not screens of this space. A typo
should cost its own tab and not the page.
"""

#: How many tables one page can hold. Generous, and it used to be sixteen with
#: a note saying that past it the honest answer was a *second* Configuration
#: screen with a narrower name.
#:
#: That was the wrong second option, and OneHR is what showed it: once every
#: table the space can write has a door — which is the whole point, since the
#: alternative is the desk — there are thirty-odd of them, and four
#: Configuration entries at the bottom of the rail is exactly the interleaving
#: `docs/ERP-SPACES.md` §2 refused. The thing a long list of tables needs is
#: not a shorter list, it is *headings*, which is what the rail above it
#: already has.
TABS = 48

#: The `view_settings` key, and the key inside it.
CONFIGURATION = "configuration"
SCREENS = "screens"

#: And the key a group carries, where the page is grouped.
LABEL = "label"


def shape(asked, screens: list) -> dict:
	"""`view_settings.configuration`, as a tab strip.

	`screens` is the space's own screen list — the rows, not the names — because
	a tab needs the label and the glyph that screen already declares. Reading
	them here rather than letting the manifest restate them is what stops a
	Configuration page calling something "Leave types" while the rail calls it
	something else.
	"""
	if not isinstance(asked, dict):
		return {}

	wanted = asked.get(SCREENS)
	if not isinstance(wanted, list):
		return {}

	by_name = {
		one.get("screen"): one
		for one in screens or []
		if isinstance(one, dict) and one.get("screen")
	}

	tabs = []
	for entry in wanted:
		# Two shapes, and the second is the one a long page needs. A **string**
		# is a screen, which is what this key was and what every space but
		# OneHR still says. A **group** is `{label, screens}` and puts a
		# heading above its own — the same thing the space rail does with
		# `screen_group`, one level in.
		if isinstance(entry, str):
			_tab(tabs, by_name, entry, "")
		elif isinstance(entry, dict):
			heading = str(entry.get(LABEL) or "").strip()
			for name in entry.get(SCREENS) or []:
				if isinstance(name, str):
					_tab(tabs, by_name, name, heading)
		if len(tabs) >= TABS:
			break

	return {"tabs": tabs[:TABS]} if tabs else {}


def _tab(tabs: list, by_name: dict, name: str, group: str) -> None:
	"""One tab, if that name is a screen of this space.

	A name that is not is dropped rather than drawn empty: an empty tab is a
	table somebody will report as broken, and a missing one is a manifest
	somebody will fix.
	"""
	found = by_name.get(name.strip())
	if not found:
		return
	tabs.append({
		"screen": found["screen"],
		"label": found.get("label") or found["screen"],
		"icon": found.get("icon") or "",
		"singular": found.get("singular") or "",
		# Carried on every tab rather than as a separate list, so the browser
		# draws a heading when it *changes* — which is how the rail decides,
		# and means a page with no groups needs no second code path.
		"group": group,
	})
