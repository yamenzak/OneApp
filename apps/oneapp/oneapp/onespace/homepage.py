"""What a space puts on its front page, and why it is made of its own screens.

Every space now has a **home**: the screen you land on when you open it, before
you have chosen anything. A space without one lands on whatever its first rail
entry happens to be, which is a list of somebody's records — usually not the
reader's, usually sorted by when they were made, and never the thing the person
came to do.

The obvious way to build one is a component per space, and it is the wrong way
twice over. It is a page of bespoke queries per space, none of which knows the
columns, the states or the permissions the space already declared; and it gives
you no answer at all to "role-specific", so the second version of it grows a
role → layout table that somebody has to maintain beside the roles themselves.

So a home is **blocks, and a block is a screen of this space**:

    "component": "home",
    "view_settings": {"home": {"blocks": ["my-leave", "approvals"]}}

which is the same trick the Configuration page uses and the same trick a
record's tabs use, for the same three reasons: the block draws that screen's own
columns, counts what that screen counts, and is checked where every list is
checked.

**Role-specific comes out of that for free, and this is the whole argument.**
A block is dropped when the reader cannot open its screen, and `navigable`
already narrows a space's screens to the seat — so a salesperson's OneCRM home
and a sales manager's are different pages without either of them being written.
Where the difference is *whose rows* rather than *which screens*, the manifest
names a `@me`-narrowed twin (`mine.py`) and the same block shows each person
their own. Nothing here knows what a role is.

A name that is not a screen of this space is dropped rather than drawn empty,
for the reason `configuration.py` gives: an empty block is a thing somebody
reports as broken, and a missing one is a manifest somebody fixes. So is a
screen that draws itself — a map, a wizard — because a block is a short list
and those are destinations.
"""

#: How many blocks one page can hold. A home is a glance; past six it is a
#: report, and the rail is two inches away.
BLOCKS = 6

#: The `view_settings` key, and the key inside it.
HOME = "home"
BLOCKS_KEY = "blocks"

#: How many rows a block shows. Enough to be a list rather than a sample, few
#: enough that six of them fit on a laptop without scrolling past the last.
ROWS = 5


def shape(asked, screens: list) -> dict:
	"""`view_settings.home`, as a list of blocks.

	`screens` is the space's own screen list as this reader may see it — the
	rows, not the names — so a block needs no label of its own and cannot end
	up calling something what the rail does not call it.
	"""
	if not isinstance(asked, dict):
		return {}

	wanted = asked.get(BLOCKS_KEY)
	if not isinstance(wanted, list):
		return {}

	by_name = {
		one.get("screen"): one
		for one in screens or []
		if isinstance(one, dict) and one.get("screen")
	}

	blocks = []
	for name in wanted:
		if not isinstance(name, str):
			continue
		found = by_name.get(name.strip())
		if not found:
			continue
		# A block is a short list of records, so a screen that draws itself is
		# dropped rather than shown as an empty table: a map, a wizard, another
		# Configuration page. Those are destinations, and the rail is where a
		# destination goes.
		#
		# Both tests, because they catch different things. A `component` screen
		# may still name a doctype — that is how it says who it is for — and a
		# screen with no doctype at all is one nobody has finished.
		if found.get("component") or not (found.get("document_type") or "").strip():
			continue
		blocks.append({
			"screen": found["screen"],
			"label": found.get("label") or found["screen"],
			"icon": found.get("icon") or "",
			"singular": found.get("singular") or "",
		})
		if len(blocks) >= BLOCKS:
			break

	return {"blocks": blocks, "rows": ROWS} if blocks else {}
