"""Per-view-type shaping: the board's columns, the cards, the widgets."""

import frappe
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
from .meta import _fetch_fields
from .viewtypes import DEFAULT_VIEW_TYPE, VIEW_TYPES


# The settings key that is not a view type: how a screen draws one record.
SHOWCASE = "showcase"


def _view_settings(resolved: dict, asked) -> dict:
	"""What a view type needs that columns and filters do not carry.

	Nested by view type — `{"board": {"column_field": "status"}}` — because one
	screen offers several, and a flat blob makes "which field" ambiguous the
	moment a calendar wants one too. The same shape in the manifest and in a
	saved view, so there is one thing to learn.

	Every fieldname in it is checked against the screen's own columns, the same
	way a filter or a sort is: a board's column field reaches a query, and "it
	came from the settings blob" has never been a reason to trust one. A key
	ending in `_field` is one fieldname; one ending in `_fields` is a list of
	them. Anything else is dropped — this is a validator, not a passthrough.
	"""
	if isinstance(asked, str):
		try:
			asked = frappe.parse_json(asked or "null")
		except (TypeError, ValueError):
			# Text that is not JSON is not settings. Dropped rather than fatal:
			# nothing in here is load-bearing enough to refuse a screen over.
			return {}
	if not isinstance(asked, dict):
		return {}

	offered = {c["fieldname"] for c in resolved.get("all_columns") or []}
	kept: dict[str, dict] = {}
	for view_type, settings in asked.items():
		# `showcase` is the one key here that is not a view type. It is how the
		# screen draws *one* record rather than a page of them — the view every
		# screen has and the only one that was never named — and it lives here
		# because it is the same kind of thing: what a way of looking needs
		# that columns and filters do not carry. See `oneapp_core/showcase.py`.
		if view_type == SHOWCASE:
			found = showcase.shape(settings, offered)
			if found:
				kept[SHOWCASE] = found
			continue
		if view_type not in VIEW_TYPES or not isinstance(settings, dict):
			continue
		for key, value in settings.items():
			if not isinstance(key, str):
				continue
			if key == "widgets" and view_type == "dashboard":
				# The one key that is a list of objects rather than a field or
				# a list of them. Still a validator and not a passthrough:
				# `dashboard.shape` drops a widget whose kind, aggregate or
				# fieldnames are not ones this screen has, and drops it whole
				# rather than narrowing it to the parts that were valid.
				widgets = dashboard.shape(value, offered)
				if widgets:
					kept.setdefault(view_type, {})["widgets"] = widgets
			elif key.endswith("_fields") and isinstance(value, list):
				names = [
					one for one in dict.fromkeys(value)
					if isinstance(one, str) and one in offered
				][:MAX_CARD_FIELDS]
				if names:
					kept.setdefault(view_type, {})[key] = names
			elif key.endswith("_field") and isinstance(value, str) and value in offered:
				kept.setdefault(view_type, {})[key] = value
	return kept


# How many fields a board card may carry. A card is a glance: past this it is a
# record rendered badly, and the person wanting the sixth field wants the record.
MAX_CARD_FIELDS = 6


# What a board may make columns of.
#
# A Select is the obvious one — its options *are* the columns, in the doctype's
# own order, and they exist whether or not any record is in them. A Link works
# too and is the one people ask for next ("by assignee", "by customer"), with
# one difference worth being honest about: its columns are the values actually
# present on the page, because the alternative is a column for every row of the
# target doctype and nobody wants four hundred empty ones.
#
# Nothing else. A Date wants a calendar, a Currency wants a chart, and a board
# of two hundred one-card columns is not a board.
BOARDABLE = ("Select", "Link")


def _boardable(column: dict | None) -> bool:
	return bool(column) and column.get("fieldtype") in BOARDABLE


def _board(resolved: dict) -> dict:
	"""Which field a board draws columns of, and what its cards say.

	Three answers, narrowest last. The screen's `status_field` is the default,
	because a manifest that offers a board has already said where a record
	stands. The manifest's own `view_settings` may name another. A saved view
	may name another again — that is the reader's, and it is why this is
	resolved here rather than read straight off the screen.

	Empty `column_field` means no board: the type is dropped on the way out and
	the screen opens as a list, which is what `_view_types` already does for a
	screen that never had a status field.
	"""
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	settings = (resolved.get("view_settings") or {}).get("board") or {}

	asked = settings.get("column_field") or ""
	status = resolved.get("status_field") or ""
	# `_view_settings` already checked the name is a column this screen offers;
	# what it cannot check is that a board can be made of it, because that is a
	# question about the fieldtype rather than about the name.
	column = asked if _boardable(offered.get(asked)) else ""
	if not column and _boardable(offered.get(status)):
		column = status

	return {
		"column_field": column,
		# Every field a board could be columns of, so the picker offers them
		# without asking the doctype a second question.
		"fields": [
			{"fieldname": c["fieldname"], "label": c["label"], "fieldtype": c["fieldtype"]}
			for c in resolved.get("all_columns") or []
			if _boardable(c) and c.get("list_ok", True)
		],
	}


# The view types that draw a record as a card rather than as a line.
#
# A board and a grid are the same card twice: an identity, then the few fields
# worth reading without opening the record. What differs is the arrangement —
# a board buckets its cards by a field and lets you drag one between buckets,
# a grid lays the same cards out flat — and arrangement is not something a
# card knows about. `apps/oneapp/frontend/src/lib/cards.js` is the browser's
# half of exactly this.
#
# Each keeps its own list, because the two have different room and different
# context: a board card sits in a column already labelled with the field it is
# bucketed by, so repeating that field on it says nothing, and a grid card has
# no such heading and often wants it.
CARD_VIEW_TYPES = ("board", "grid")


def _cards(resolved: dict) -> dict:
	"""What a card says, on whichever card-shaped view this is.

	Empty is not "nothing": it is "the browser decides", from the columns the
	reader is already looking at. That is the right default and the one thing a
	manifest should not have to repeat — a screen that lists four columns has
	described its card by listing them.

	`list_ok` is the same rule the column picker uses, and here it is also what
	keeps the query valid: a child table and an attachment gallery are not
	fields the database has, and a card field is fetched whether or not it is a
	column somebody is looking at.
	"""
	view_type = resolved.get("view_type") or DEFAULT_VIEW_TYPE
	if view_type not in CARD_VIEW_TYPES:
		return {"card_fields": []}

	settings = (resolved.get("view_settings") or {}).get(view_type) or {}
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	chosen = [
		one for one in settings.get("card_fields") or []
		if one in offered and offered[one].get("list_ok", True)
	]
	return {"card_fields": chosen[:MAX_CARD_FIELDS]}


def _widgets(resolved: dict) -> list[dict]:
	"""What the dashboard draws, checked against this screen's own columns.

	Only the declaration travels to the browser — a kind, a label, a width, the
	fieldnames — and never the numbers. A screen's spec is read on every
	navigation and a dashboard is nine aggregate queries; folding them into it
	would put nine `GROUP BY`s in front of every list anybody opens. The
	numbers come from `dashboard()`, once, when the dashboard is the thing
	being looked at.
	"""
	settings = resolved.get("view_settings") or {}
	found = settings.get("dashboard") if isinstance(settings, dict) else None
	if not isinstance(found, dict):
		return []

	offered = {c["fieldname"] for c in resolved.get("all_columns") or []}
	return dashboard.shape(found.get("widgets"), offered)


def _resolve_views(resolved: dict) -> dict:
	"""Settle what the view types need, and what has to be fetched for them.

	Three callers — the screen's own settings, a saved view's, and a change
	somebody has made and not saved — and all three change the same three
	answers together, because they are one answer: which field a board is
	columns of, what a card says, and therefore what the query asks for.

	The fetch is the part that is easy to forget and silent when it is wrong.
	A card field nobody has as a column is still a field the card draws, and
	without it here every such card renders blank in exactly the case somebody
	went to the trouble of choosing one.
	"""
	resolved["board"] = _board(resolved)
	resolved["cards"] = _cards(resolved)
	resolved["widgets"] = _widgets(resolved)
	resolved["fields"] = _fetch_fields(
		resolved["columns"],
		resolved.get("status_field") or "",
		resolved["board"]["column_field"],
		# What a record *is*, which every surface draws and none of them asked
		# for. The doctype's own `title_field` and `image_field`: the title cell
		# reads one and the card reads the other, and neither is a column
		# unless a manifest happened to list it. Missing, a screen shows a page
		# of ids and a gallery of empty frames — which is what it did, quietly,
		# because a doctype whose title field is also a column looks right.
		resolved.get("title_field") or "",
		resolved.get("image_field") or "",
		*resolved["cards"]["card_fields"],
	)
	return resolved
