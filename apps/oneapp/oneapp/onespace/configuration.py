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

A tab may also be a **settings panel**:

    "view_settings": {"configuration": {"screens": [{"panel": "ai"}]}}

which is one of `onespace/tabs.py`'s keys — Branding, AI, Alerts, Naming, your
own profile. Those were a dialog: twenty-two tabs with no address, opening over
whatever you happened to be looking at, offered from a menu. Everything wrong
with that is the thing this page already got right for tables, so the panels
come here rather than a second version of this page being built beside the
dialog. A panel is still drawn by the component that always drew it and still
gated by the audience it always declared — `tabs.may_open` — so a member's
Configuration has the four tabs that are theirs and no door that does not open.

So this module does one small thing: turn those names into the labels and icons
a tab strip needs, dropping any that are not screens of this space and any
panel this reader may not open. A typo should cost its own tab and not the page.
"""

#: How many tables one page can hold. Generous, and it used to be sixteen with
#: a note saying that past it the honest answer was a *second* Configuration
#: screen with a narrower name.
#:
#: That was the wrong second option, and OnePeople is what showed it: once every
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

#: The key an entry carries when it is a settings panel rather than a screen.
PANEL = "panel"


#: The panels every *space* has, under the heading they sit behind.
#:
#: Not declared by a manifest, because they are not a manifest's business: an
#: alert is about a doctype, a series names one and a print format is drawn
#: over one, so "this space's" is exactly "the ones its screens show" and the
#: space has already said which those are. A manifest declaring them would be
#: three lines repeated in every space and forgotten in the next one.
#:
#: They used to be three tabs in a dialog, workspace-wide — one list where
#: OnePeople's leave alerts and OneCRM's deal alerts were scrolled past each other.
SPACE_PANELS = ("alerts", "routing", "naming", "print-formats")

#: What they sit under.
SPACE_GROUP = "Settings"


def shape(asked, screens: list, space_code: str = "") -> dict:
	"""`view_settings.configuration`, as a tab strip.

	`screens` is the space's own screen list — the rows, not the names — because
	a tab needs the label and the glyph that screen already declares. Reading
	them here rather than letting the manifest restate them is what stops a
	Configuration page calling something "Leave types" while the rail calls it
	something else.

	`space_code` is which space this is, and it decides one thing: whether the
	three panels every space has are appended. One is the workspace rather than
	a space over some records, so it declares its own and gets none of these —
	an Alerts tab narrowed to One's own doctypes would be an empty page.
	"""
	from oneapp.onespace import words
	from oneapp.onespace.one import CODE as ONE

	# A page that declared nothing is still a page: `sync.configured` gives a
	# Configuration screen to every space, and a space with no tables of its
	# own still has alerts, series and print formats. So an empty declaration
	# means "no tables", not "no page".
	wanted = asked.get(SCREENS) if isinstance(asked, dict) else []
	if not isinstance(wanted, list):
		wanted = []

	by_name = {
		one.get("screen"): one
		for one in screens or []
		if isinstance(one, dict) and one.get("screen")
	}

	tabs = []
	for entry in wanted:
		# Two shapes, and the second is the one a long page needs. A **string**
		# is a screen, which is what this key was and what every space but
		# OnePeople still says. A **group** is `{label, screens}` and puts a
		# heading above its own — the same thing the space rail does with
		# `screen_group`, one level in.
		if isinstance(entry, str):
			_tab(tabs, by_name, entry, "")
		elif isinstance(entry, dict) and entry.get(PANEL):
			_panel(tabs, str(entry[PANEL]), "")
		elif isinstance(entry, dict):
			heading = str(entry.get(LABEL) or "").strip()
			for name in entry.get(SCREENS) or []:
				if isinstance(name, str):
					_tab(tabs, by_name, name, heading)
				elif isinstance(name, dict) and name.get(PANEL):
					_panel(tabs, str(name[PANEL]), heading)
		if len(tabs) >= TABS:
			break

	if space_code and space_code != ONE:
		# What this workspace calls this space's screens — `onespace/words.py`,
		# `docs/ONECRM.md` stage 7. Under the same heading as the rest of a
		# space's own machinery and first in it, because a word is the thing
		# somebody changes before they touch the alerts written in it. An
		# ordinary screen tab rather than a panel: `words.worded` appended the
		# screen, so this is the list engine drawing its own table.
		_tab(tabs, by_name, words.SCREEN, SPACE_GROUP)
		for key in SPACE_PANELS:
			_panel(tabs, key, SPACE_GROUP)

	return {"tabs": tabs[:TABS]} if tabs else {}


def _panel(tabs: list, key: str, group: str) -> None:
	"""One settings panel, if this reader may open it.

	Dropped rather than disabled, and that is the one place this differs from
	an app tile on the board: a tile says "not here yet" because the answer is
	about the *workspace* and is worth knowing. A tab the reader has no
	business on is about them, and a column of doors that will not open is the
	thing `tabs.py` was written to stop.
	"""
	from oneapp.onespace import tabs as settings_tabs

	for one in settings_tabs.TABS:
		if one["key"] != key:
			continue
		if not settings_tabs.may_open(one):
			return
		tabs.append({
			# No `screen`: the browser keys a tab on one or the other, and a
			# panel that also claimed a screen name would be a tab that tried
			# to draw a list of it.
			"panel": key,
			"label": one["label"],
			"icon": one["icon"],
			"kind": one["kind"],
			"group": group,
		})
		return


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
		# And whether that screen is a component rather than a list. A
		# Configuration tab has always been "another screen of this space,
		# drawn the way that screen draws"; for every table so far that meant a
		# list, and OnePeople's HR Settings is the first where it does not. A
		# Single has one document and no list at all, so the tab renders the
		# screen's own component — which is the same sentence as before, and
		# the alternative was a rail entry called Rules sitting between
		# Payslips and Claims.
		"component": found.get("component") or "",
		# Carried on every tab rather than as a separate list, so the browser
		# draws a heading when it *changes* — which is how the rail decides,
		# and means a page with no groups needs no second code path.
		"group": group,
	})
