"""Per-view-type shaping: the board's columns, the cards, the widgets."""

import re

import frappe
from oneapp.onespace import board, collab, dashboard, docflow, fieldtypes, printing, showcase
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
		# that columns and filters do not carry. See `onespace/showcase.py`.
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
			if key == "arrangement" and view_type == "board" and isinstance(value, dict):
				# How the board is arranged, as opposed to what it is made of:
				# the order of its columns, their colours, which are archived,
				# and the order of the cards inside them. Keyed by *value* — a
				# Select option, a Link id — so it cannot be checked against
				# the screen's fields the way every other key here is, and is
				# bounded instead. See `onespace/board.py`.
				#
				# Kept whenever the payload *mentions* it, empty included —
				# the same rule filters follow, and for the same reason:
				# unarchiving the last hidden column sends an empty list, and
				# a truthiness check here would leave the saved one standing
				# and the column would never come back.
				kept.setdefault(view_type, {})["arrangement"] = board.shape(value)
			elif key == "widgets" and view_type == "dashboard":
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
		# What this reader has done to the board itself. Validated on the way
		# in by `board.shape`; applied in the browser, because every one of
		# these is about drawing rather than about which rows come back.
		"arrangement": settings.get("arrangement") or {},
		# Every field a board could be columns of, so the picker offers them
		# without asking the doctype a second question.
		"fields": [
			{"fieldname": c["fieldname"], "label": c["label"], "fieldtype": c["fieldtype"]}
			for c in resolved.get("all_columns") or []
			if _boardable(c) and c.get("list_ok", True)
		],
	}


# What a calendar may place a record by.
#
# A Date has no time and is therefore a whole day; a Datetime is a moment. Both
# work and the calendar draws them differently, which is the one thing a
# manifest does not have to say — the fieldtype already does.
#
# Nothing else. A Data field holding "next Tuesday" is not a date to a database
# and a Duration is a length rather than a place, so a screen that names one
# gets no calendar rather than a grid of days with everything on the first.
DATEABLE = ("Date", "Datetime")


def _dateable(column: dict | None) -> bool:
	return bool(column) and column.get("fieldtype") in DATEABLE


def _calendar(resolved: dict) -> dict:
	"""Where a calendar puts a record, and how long it sits there.

	`start_field` is the one answer a screen has to give. `end_field` is
	optional and means what it says — a record with a start and no end is a
	moment on a day rather than a span across several — and naming a field that
	is not a date drops it rather than the whole calendar, because a span that
	cannot be read is still a record with a date on it.

	The pair is settled here rather than read straight off the screen for the
	same reason the board's column field is: a saved view may name another, and
	the reader's answer is the narrowest one.
	"""
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	settings = (resolved.get("view_settings") or {}).get("calendar") or {}

	start = settings.get("start_field") or ""
	start = start if _dateable(offered.get(start)) else ""

	end = settings.get("end_field") or ""
	# Never an end without a start: a span whose beginning nothing knows is not
	# a span, and drawing it from the end backwards would be inventing one.
	end = end if start and _dateable(offered.get(end)) else ""

	# How often it happens again, and until when.
	#
	# Frappe's own Event carries `repeat_on` — a Select of Daily, Weekly,
	# Monthly, Yearly — beside a `repeat_till`, and that is the model this
	# follows rather than inventing an RRULE dialect nothing else on the site
	# reads. A screen names the two fields; the browser draws the occurrences
	# inside the window it is showing. Nothing is written: one record with a
	# rule stays one record, which is what makes deleting a series possible.
	repeat = settings.get("repeat_field") or ""
	repeat = repeat if start and offered.get(repeat, {}).get("fieldtype") == "Select" else ""

	until = settings.get("until_field") or ""
	until = until if repeat and _dateable(offered.get(until)) else ""

	return {
		"start_field": start,
		"end_field": end,
		"repeat_field": repeat,
		"until_field": until,
		# Every field a calendar could be drawn by, so the picker offers them
		# without asking the doctype a second question. Same shape as the
		# board's, and for the same reason.
		"fields": [
			{"fieldname": c["fieldname"], "label": c["label"], "fieldtype": c["fieldtype"]}
			for c in resolved.get("all_columns") or []
			if _dateable(c) and c.get("list_ok", True)
		],
	}


# What a bar's progress may be read from. A Percent is the obvious one; an Int
# or a Float is the same number where somebody stored it without the fieldtype.
# Nothing else: a Select called "Status" is a state rather than a fraction, and
# guessing which of its options means half done is not a mapping to invent.
MEASURED = ("Percent", "Int", "Float")


def _gantt(resolved: dict) -> dict:
	"""Both ends of a bar, and how full it is.

	Falls back to the calendar's pair, because a screen that offers both is
	placing its records by the same two dates and saying so twice is how the
	two drift. `end_field` is required here where the calendar merely likes it:
	a record with no end is a moment, and a chart of moments is a column of
	dots.
	"""
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	settings = resolved.get("view_settings") or {}
	said = {**(settings.get("calendar") or {}), **(settings.get("gantt") or {})}

	start = said.get("start_field") or ""
	end = said.get("end_field") or ""
	if not (_dateable(offered.get(start)) and _dateable(offered.get(end))):
		start = end = ""

	measure = said.get("progress_field") or ""
	if not (start and offered.get(measure, {}).get("fieldtype") in MEASURED):
		measure = ""

	# What this bar waits on. The same check the tree's parent field goes
	# through — a Link *at this doctype* — because "depends on" and "sits
	# under" are the same shape of statement about two records of one kind, and
	# a Link at something else is a relation rather than a sequence.
	#
	# One field rather than Frappe's child table of them. A Task's `depends_on`
	# is a grid, and a grid is a second query per row on a chart that is already
	# fetching a page; one Link says "this comes after that", which is what a
	# schedule drawn from a page of records can honestly show.
	depends = said.get("depends_field") or ""
	if not (start and _nests(offered.get(depends), resolved.get("doctype") or "")):
		depends = ""

	return {
		"start_field": start,
		"end_field": end,
		"progress_field": measure,
		"depends_field": depends,
		"fields": [
			{"fieldname": c["fieldname"], "label": c["label"], "fieldtype": c["fieldtype"]}
			for c in resolved.get("all_columns") or []
			if _dateable(c) and c.get("list_ok", True)
		],
	}


# What a pin's position may be read from. `Geolocation` is Frappe's own and
# holds GeoJSON, which is the right answer for a shape as well as a point. The
# numeric pair is the one every address table in the world actually has —
# ERPNext's Address carries `latitude` and `longitude` as Floats — and refusing
# it would have made this a OneMobility feature wearing an engine's clothes.
POSITIONED = ("Geolocation",)
COORDINATE = ("Float", "Data", "Int")


def _place(resolved: dict) -> dict:
	"""Where a record sits, and what colours the pin once it is there.

	Two shapes, checked in the order a screen would prefer them: a single
	`Geolocation`, or a pair of numeric fields. A screen declaring both gets
	the first, because GeoJSON can say "this is a line" and two numbers cannot.

	`colour_field` is the board's column field by another name — a Select whose
	options carry colours, so a map of stops can be read the way a board is,
	without a legend nobody wrote. Deliberately the same rule as the board's,
	so a doctype that works as one works as the other.
	"""
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	said = (resolved.get("view_settings") or {}).get("map") or {}

	def _is(name: str, kinds) -> bool:
		return (offered.get(name) or {}).get("fieldtype") in kinds

	point = said.get("point_field") or ""
	if not _is(point, POSITIONED):
		point = ""

	lat = said.get("lat_field") or ""
	lon = said.get("lon_field") or ""
	if not (_is(lat, COORDINATE) and _is(lon, COORDINATE)):
		lat = lon = ""

	# A screen that declared neither validly has no map, and `_view_types` will
	# already have dropped it — this is the runtime half, so a saved view made
	# before a field was renamed opens as a list rather than as an empty world.
	label = said.get("label_field") or resolved.get("title_field") or ""
	if label and label not in offered:
		label = ""

	colour = said.get("colour_field") or resolved.get("status_field") or ""
	if not _is(colour, ("Select", "Link")):
		colour = ""

	return {
		"point_field": point,
		"lat_field": lat,
		"lon_field": lon,
		"label_field": label,
		"colour_field": colour,
		# Where to open when nothing has a position yet. A workspace's own
		# country would be a better answer and is not a thing we store, so:
		# the whole world, which is honest, rather than a guess at Berlin.
		"centre": said.get("centre") or None,
		"zoom": said.get("zoom") or None,
		# The basemap, which is a deployment fact rather than a workspace's
		# choice: the tiles are ours and self-hosted, so every workspace on an
		# instance uses the same ones and none of them should be asked. Absent,
		# the map draws its records on a flat ground — which is what a
		# schematic looks like, and is why this works on a bench nobody has
		# pointed at a tile store.
		"style": frappe.conf.get("oneapp_map_style") or "",
	}


def _tree(resolved: dict) -> dict:
	"""Which field points a record at the one above it.

	The check is the board's, one property over: a board's column field has to
	be a Select or a Link, and a tree's parent field has to be a Link *at this
	doctype*. A Link to something else is a relation and not a hierarchy, and
	drawing it as one would nest a licence under its issuer.

	No fallback to a nested set's `parent_<doctype>`, unlike the desk. See
	`viewtypes.NEEDS_PARENT` for why the manifest is made to say it.
	"""
	doctype = resolved.get("doctype") or ""
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	said = (resolved.get("view_settings") or {}).get("tree") or {}

	parent = said.get("parent_field") or ""
	if not _nests(offered.get(parent), doctype):
		parent = ""

	return {
		"parent_field": parent,
		# Which records may hold others. Frappe's nested-set doctypes carry
		# `is_group` and the desk refuses a child under a leaf; a doctype that
		# nests through an ordinary Link — which is what this view is for — may
		# or may not have one. So: the field a screen names, else Frappe's own
		# name where the doctype has it, else nothing and every node may hold
		# children, which is what a plain Link means.
		#
		# The difference it makes is visible: a group with nothing in it is a
		# folder rather than a leaf, so an empty cost centre reads as somewhere
		# to put something.
		"group_field": _grouping(offered, said.get("group_field")),
		# Every field that could be one, so a picker needs no second question.
		"fields": [
			{"fieldname": c["fieldname"], "label": c["label"], "fieldtype": c["fieldtype"]}
			for c in resolved.get("all_columns") or []
			if _nests(c, doctype)
		],
	}


# What Frappe calls it on every nested-set doctype it ships.
GROUP_FIELD = "is_group"


def _grouping(offered: dict, asked: str | None) -> str:
	"""The Check field saying a record may hold others, if there is one."""
	for name in (asked or "", GROUP_FIELD):
		column = offered.get(name)
		if column and column.get("fieldtype") == "Check":
			return name
	return ""


def _nests(column: dict | None, doctype: str) -> bool:
	"""Whether one column points a record at another of its own kind."""
	return bool(
		column
		and doctype
		and column.get("fieldtype") == "Link"
		and column.get("options") == doctype
	)


def _window(resolved: dict, since: str, until: str) -> list:
	"""The days on screen, as a filter, or nothing.

	A calendar is not a page. The desk's own calendar asks for the visible
	range and ignores pagination, and it is right to: a month drawn from
	whichever hundred rows sorted first is a month with holes in it, and the
	holes move as you page.

	So the range is a property of the *request*, like `start` and `limit`, and
	never of the view: a saved view that quietly carried "March" would be a
	saved view that shows nothing in April. The field is the screen's own,
	resolved above — the browser sends two dates and cannot name a column.
	"""
	field = (resolved.get("calendar") or {}).get("start_field") or ""
	if not field or not _a_date(since) or not _a_date(until):
		return []
	return [[resolved["doctype"], field, "between", [since, until]]]


# `YYYY-MM-DD`, and optionally a time after it. Not a parse — a shape check, so
# that whatever a query string carries reaches the database as a date or not at
# all. It has already carried the string "undefined" once.
A_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")


def _a_date(value) -> bool:
	return bool(isinstance(value, str) and A_DATE.match(value.strip()))


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
	resolved["calendar"] = _calendar(resolved)
	resolved["gantt"] = _gantt(resolved)
	resolved["tree"] = _tree(resolved)
	resolved["place"] = _place(resolved)
	resolved["cards"] = _cards(resolved)
	resolved["widgets"] = _widgets(resolved)
	resolved["fields"] = _fetch_fields(
		resolved["columns"],
		resolved.get("status_field") or "",
		resolved["board"]["column_field"],
		# The dates the calendar places a record by. Fetched for the same
		# reason a card field is: the calendar draws them whether or not
		# anybody made them columns, and without this every event lands on
		# nothing at all.
		resolved["calendar"]["start_field"],
		resolved["calendar"]["end_field"],
		# And the Gantt's, which are usually the same two and need not be.
		resolved["gantt"]["start_field"],
		resolved["gantt"]["end_field"],
		resolved["gantt"]["progress_field"],
		# And the field a tree nests by, which is almost never a column: a
		# register's parent link is bookkeeping until somebody looks at the
		# hierarchy, and without this every record comes back with an empty
		# parent and the tree is one flat list of roots.
		resolved["tree"]["parent_field"],
		# And where a map puts the pin, which is never a column: a coordinate
		# is not something anybody reads in a table, so without this every
		# record arrives without one and the map is an empty world.
		resolved["place"]["point_field"],
		resolved["place"]["lat_field"],
		resolved["place"]["lon_field"],
		resolved["place"]["label_field"],
		resolved["place"]["colour_field"],
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
