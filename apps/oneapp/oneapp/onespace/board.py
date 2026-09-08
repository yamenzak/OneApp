"""How a board is arranged, as opposed to what it is made of.

`view_settings.board.column_field` says the board is columns of `status`; the
doctype says what the statuses are and what colour each one is. Neither says
that this workspace puts Blocked last, calls nothing by its colour, never wants
to see Cancelled, and keeps the two urgent jobs at the top of Open. Those are
arrangement, they belong to the person looking, and until now there was nowhere
to put them — so a board redrew itself in the doctype's order every morning.

Frappe keeps this in a **Kanban Board** doctype: one row per board, with a child
table of columns carrying an order, a colour, an archived flag and a JSON list
of card names. The same four facts, and one fewer doctype: a board arrangement
is a *view*, in the same sense filters and columns are — per person or shared,
switchable, saved by the same button — so it goes in `view_settings` beside the
field it is a board of, and `OneSpace Saved View` already stores that.

**Values, not fieldnames.** Everything here is keyed by a column's value —
`Open`, `HR-EMP-00042` — which is a string this module cannot check against
anything: a Select's options come from the doctype, a Link's from the page. So
it is bounded rather than validated. Lengths, counts and a closed set of
colours; anything else is dropped, and a value naming a column that no longer
exists is simply never looked up.
"""

# The Badge themes, which are frappe-ui's. The same set `STATE_COLORS` in
# `lib/fields.js` maps Frappe's own colour names onto, so a column somebody
# colours by hand and one the doctype coloured are the same nine colours.
THEMES = ("gray", "blue", "green", "orange", "red", "amber", "violet", "pink", "teal")

# A board with more columns than this is a board nobody scrolls, and the
# arrangement of it is not the reason.
COLUMNS = 60

# How many cards keep a remembered position in one column. Past this, order is
# the list's own — which is what it was before any of this, and is the honest
# answer for a column holding a thousand records.
CARDS = 200

# A record's id, and the longest one Frappe issues.
NAME = 140


def shape(asked) -> dict:
	"""One board's arrangement, or nothing.

	Four independent answers, each kept only if it is the right shape. Partial
	is fine here in a way it is not for a showcase: a colour somebody set and an
	order they did not are not halves of one thing.
	"""
	if not isinstance(asked, dict):
		return {}

	kept = {}

	order = _values(asked.get("order"))
	if order:
		kept["order"] = order

	hidden = _values(asked.get("hidden"))
	if hidden:
		kept["hidden"] = hidden

	colours = _colours(asked.get("colours"))
	if colours:
		kept["colours"] = colours

	cards = _cards(asked.get("cards"))
	if cards:
		kept["cards"] = cards

	return kept


def _values(raw) -> list[str]:
	"""Column values, deduplicated and bounded."""
	if not isinstance(raw, list):
		return []
	return [
		one for one in dict.fromkeys(
			str(one) for one in raw if isinstance(one, str | int | float) and str(one)
		)
	][:COLUMNS]


def _colours(raw) -> dict:
	"""A theme per column, out of the closed set the badge draws."""
	if not isinstance(raw, dict):
		return {}
	kept = {}
	for value, theme in list(raw.items())[:COLUMNS]:
		if isinstance(value, str) and value and theme in THEMES:
			kept[value] = theme
	return kept


def _cards(raw) -> dict:
	"""The order of the cards inside each column, by record id.

	A list of ids rather than a position per card, because that is what the
	drag produces and what the browser reads back: a card not in the list sorts
	after the ones that are, in whatever order the list came back in — so a
	column somebody arranged three records of does not lose the other forty.
	"""
	if not isinstance(raw, dict):
		return {}
	kept = {}
	for value, names in list(raw.items())[:COLUMNS]:
		if not isinstance(value, str) or not value or not isinstance(names, list):
			continue
		ordered = [
			one for one in dict.fromkeys(
				str(one) for one in names if isinstance(one, str) and one
			) if len(one) <= NAME
		][:CARDS]
		if ordered:
			kept[value] = ordered
	return kept
