"""The ways a screen can draw *one* record, by name.

A screen already declares how a *page* of records is looked at — `view_types`,
and `viewtypes.py` is the closed set behind that word. This is the same idea one
level down: the record itself has more than one right shape, and which one a
screen uses is a declaration rather than a fork of the record component.

    "view_settings": {"record": {"as": "person"}}

Not the browser's `lib/screen/surfaces.js`, which answers the other question
about an open record — pane, page or drawer, meaning *how much of the window*.
This is what is drawn inside whichever of those it got.

Three reasons this is a registry and not a `component` escape hatch.

**A record view is reused.** `component` on a screen means "none of the rest of
the manifest applies", which is right for a map of a transit network and wrong
here: an employee page is wanted by OneHR, by whatever HR space a customer gets
next, and by anything else whose records are people. A named entry is reusable;
a component named by one screen is that screen's.

**The engine keeps the verbs.** A record view owns *layout* — what is at the top
of the page, in what order, how big. It never owns saving, permissions, the tab
strip, the record's actions, or inventing a way to read: it may ask for rows
through the same endpoints every list uses, and nothing else. `docs/UNIFICATION.md`
F1 is the argument — every abstraction in this repository was built at the second
caller and abandoned at the third, and a page with its own query would be the
third caller walking past the engine.

**The vocabulary lives in one place.** The SPA has the same table in
`lib/screen/recordViews.js`, and `tests/test_record_views.py` holds the two to
each other. A name in one and not the other is a screen that draws nothing.

Every one of these stands above the tab strip, and Details stays where it is.
A record view that *replaced* the form was built first and taken out again: it
put the fields above the strip, which is the wrong order, and it had one
speculative user. `docs/UNIFICATION.md` F1 and rail 10 — an abstraction with a
single caller is the thing this repository keeps getting wrong, and writing it
for a caller that does not exist yet is the same mistake earlier.
"""

#: Every record view, and what the engine has to know about each.
#:
#: `built` is false for a name that is declared and not yet drawn, exactly as in
#: `viewtypes.py`: a manifest may name one before it ships, and until it does the
#: screen falls back to the record it already had rather than to an empty page.
RECORD_VIEWS = {
	"record": {"built": True},
	"showcase": {"built": True},
	"person": {"built": True},
	"candidate": {"built": True},
	"place": {"built": True},
}

#: What a screen gets when it says nothing: the form and the tabs, which is what
#: every screen drew before this module existed.
DEFAULT_RECORD_VIEW = "record"

BUILT_RECORD_VIEWS = {name for name, one in RECORD_VIEWS.items() if one["built"]}

#: The `view_settings` key that names one, and the key inside it.
RECORD = "record"
AS = "as"

#: The one thing a record view may be *told*, beyond which one it is.
#:
#: A candidate page draws where somebody is in hiring, and the order of those
#: stages is neither the doctype's (which lists Rejected between Shortlisted and
#: Hold) nor anything the engine can work out. The board needs the same list and
#: so does a dashboard widget, and a manifest is a Python file — so all three
#: name one constant and there is nothing to drift.
#:
#: Carried verbatim and capped. A record view that does not read it ignores it,
#: exactly as a board ignores a calendar's keys.
STAGES = "stages"
MOST_STAGES = 12


def named(asked) -> str:
	"""The record view a screen asked for, or the default.

	Silent rather than fatal, the same as an unknown view type: a manifest that
	names `person` on a site whose engine predates it gets the record page it
	had, and starts getting the person page the day the name exists. A screen
	that refused to open over a word in a settings blob would be a deployment
	order nobody can keep.
	"""
	if not isinstance(asked, dict):
		return DEFAULT_RECORD_VIEW
	name = asked.get(AS)
	if not isinstance(name, str):
		return DEFAULT_RECORD_VIEW
	name = name.strip()
	return name if name in BUILT_RECORD_VIEWS else DEFAULT_RECORD_VIEW


def shape(asked, settings: dict) -> dict:
	"""`view_settings.record`, as the engine hands it to the browser.

	`settings` is the rest of the screen's already-shaped `view_settings`, which
	is how the back-compatible rule below can be one line: a screen that
	declared a showcase and never heard of this key *is* a showcase screen, and
	saying so here means nothing in a manifest has to change for the old ones to
	keep working — or to be migrated later by moving one word.
	"""
	name = named(asked)
	if name == DEFAULT_RECORD_VIEW and settings.get("showcase"):
		name = "showcase"

	shaped = {AS: name}
	stages = _stages(asked)
	if stages:
		shaped[STAGES] = stages
	return shaped


def _stages(asked) -> list[str]:
	"""The order a record moves through, where a screen declares one.

	Dropped rather than fatal if it is not a list of words, which is the rule
	every other shaper here follows: a settings blob somebody mistyped should
	cost the drawing it describes and not the screen.
	"""
	if not isinstance(asked, dict):
		return []
	wanted = asked.get(STAGES)
	if not isinstance(wanted, list):
		return []
	found = [one.strip() for one in wanted
	         if isinstance(one, str) and one.strip()]
	return found[:MOST_STAGES]
