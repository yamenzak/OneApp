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

#: How many tables one page can hold before it is a rail again. OneHR's is the
#: largest at twelve; past this the honest answer is a second Configuration
#: screen with a narrower name, not a longer strip.
TABS = 16

#: The `view_settings` key, and the key inside it.
CONFIGURATION = "configuration"
SCREENS = "screens"


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
	for name in wanted:
		if not isinstance(name, str):
			continue
		found = by_name.get(name.strip())
		if not found:
			# A name that is not a screen of this space. Dropped rather than
			# drawn empty: an empty tab is a table somebody will report as
			# broken, and a missing one is a manifest somebody will fix.
			continue
		tabs.append({
			"screen": found["screen"],
			"label": found.get("label") or found["screen"],
			"icon": found.get("icon") or "",
			"singular": found.get("singular") or "",
		})
		if len(tabs) >= TABS:
			break

	return {"tabs": tabs} if tabs else {}
