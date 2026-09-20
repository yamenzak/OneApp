"""Per-view-type shaping: the board's columns, the cards, the widgets."""

import re

import frappe
from oneapp.onespace import (
	board, collab, dashboard, docflow, fieldtypes, printing, recordviews, showcase,
)
from .meta import _fetch_fields
from .viewtypes import DEFAULT_VIEW_TYPE, VIEW_TYPES


# The settings key that is not a view type: how a screen draws one record.
SHOWCASE = "showcase"

# And the other one: which columns read as tags rather than as what they are.
#
# A Link is a foreign key and the engine draws one as a record — a face, a
# title, an id underneath. That is right for a Link to a *record*: a customer, a
# project, a colleague. It is wrong for the ones that are really categories,
# which is most of the Links on a doctype somebody else designed. A Designation
# and a Department are Links because ERPNext keeps a table of them, not because
# anybody wants to look one up; drawn as records they are three lines of chrome
# per cell saying one word.
#
# So a screen may say which of its columns are words rather than records, and
# they draw as a badge coloured from the value itself — see
# `lib/screen/tags.js`. Declared rather than guessed: whether a Link is a
# category is a judgement about the product, and a rule like "no title field
# means a category" would be a guess that is wrong on the first exception.
TAGS = "tags"

# How many. Past a handful a row of badges is a row of noise, and the point of
# the colour is telling a few things apart.
MOST_TAGS = 8

# Which cells a tag may replace. A word or a record id can read as one; a
# number, a date or a tick cannot — a currency drawn as a coloured pill is a
# number somebody has to decode.
TAGGABLE = ("link", "text", "badge")


def _view_settings(resolved: dict, asked) -> dict:
	"""What each way of looking needs, and which record view draws one.

	A wrapper around `_shaped`, for one reason: "which record view" has an answer
	for every screen — including one whose settings are missing, unparseable or
	not a dict — and a key the browser has to check for before reading is a key
	half its callers will forget to check for. Adding it at the two early
	returns as well would be the same line in three places.
	"""
	kept = _shaped(resolved, asked)
	blob = asked if isinstance(asked, dict) else {}
	kept[recordviews.RECORD] = recordviews.shape(blob.get(recordviews.RECORD), kept)
	_as_tags(resolved, blob.get(TAGS))
	return kept


def _as_tags(resolved: dict, asked) -> None:
	"""Mark the columns a screen wants drawn as tags.

	On the columns rather than in `view_settings`, because a cell kind is what
	every surface already reads to decide how to draw a value — the list cell,
	the card field, the hover panel and the tile all switch on it. Carrying the
	list separately would mean four surfaces each remembering to check it, and
	the fourth one would not.

	Dropped rather than fatal for anything it cannot place: a fieldname the
	screen does not carry, a cell a tag cannot replace, more than a handful.
	"""
	if not isinstance(asked, list):
		return
	wanted = [one.strip() for one in asked
	          if isinstance(one, str) and one.strip()][:MOST_TAGS]
	if not wanted:
		return

	for group in ("columns", "all_columns"):
		for column in resolved.get(group) or []:
			if column.get("fieldname") in wanted and column.get("cell") in TAGGABLE:
				column["cell"] = "tag"


def _shaped(resolved: dict, asked) -> dict:
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
		# And `timeline`, which is the third: where a record's history *starts*.
		# A deal converted from a lead did not exist before the conversion, so
		# its column begins the day somebody pressed a button and the six weeks
		# of email that got it there are on a record nobody opens again —
		# `docs/ONECRM.md` stage 4. One key, naming the field that points at
		# the record this one came from; `surround._inherited_entries` walks it
		# and checks the reader may read what is on the other end.
		if view_type == TIMELINE:
			found = _timeline(settings, offered)
			if found:
				kept[TIMELINE] = found
			continue
		# And `create`, the fourth non-view-type key: what a New dialog on this
		# screen starts with already filled in. It exists because a screen
		# narrowed by `filters` had a New button that made a record the screen
		# would then not show — the Words page is filtered to one space, and a
		# word saved without one belongs to no space at all. See `_create`.
		if view_type == CREATE:
			found = _create(settings, offered)
			if found:
				kept[CREATE] = found
			continue
		# `tags` is the other non-view-type key, and unlike the showcase it
		# changes the *columns* rather than adding a block — so it is applied
		# to them below rather than carried for the browser to interpret.
		if view_type == TAGS:
			continue
		# And `record` is the other one: which *record view* draws a single
		# record. Shaped last, below, because the back-compatible rule it
		# applies reads the showcase above — a screen that declared one and
		# never heard of this key is a showcase screen, and saying so there
		# rather than in every old manifest is what makes it cost nothing.
		if view_type == recordviews.RECORD:
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
			elif key == "colours" and view_type == "matrix" and isinstance(value, dict):
				# What each value of the matrix's field is painted. Keyed by
				# *value* — a Select option — so it cannot be checked against
				# the screen's fields the way the keys above are, and is
				# bounded instead: a theme a Badge does not have is dropped, so
				# a manifest cannot paint a cell in a word Tailwind never
				# emitted.
				#
				# The one place in the engine where a colour is declared rather
				# than derived, and the reason is that a cell is nothing but
				# its colour: a badge falls back to grey and still carries its
				# word, while a grid of grey squares carries nothing at all.
				painted = {
					str(word): str(theme) for word, theme in value.items()
					if isinstance(word, str) and str(theme) in BADGE_THEMES
				}
				if painted:
					kept.setdefault(view_type, {})["colours"] = painted
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
			elif key == "period_field" and view_type == "dashboard":
				# The date a dashboard's period control narrows by. Checked
				# against the dateable fields rather than merely against the
				# screen's columns, which is all a plain `_field` key gets: a
				# period over a Currency is a control that writes a filter no
				# row can match, and it would render perfectly.
				if _dateable(_column(resolved, value)):
					kept.setdefault(view_type, {})["period_field"] = value
			elif key == "columns_from" and view_type == "board" and isinstance(value, dict):
				# Where a Link board's columns come from. Keyed by the *target*
				# doctype's fieldnames rather than this screen's, which is why
				# it cannot be checked here the way every other key is —
				# `_board` reads it, where the target's own columns are in
				# hand. The same division `arrangement` and the Gantt's
				# `depends_where` make, for the same reason.
				kept.setdefault(view_type, {})["columns_from"] = value
			elif key == "depends_where" and view_type == "gantt" and isinstance(value, dict):
				# Which rows of a dependency table are a sequence. Keyed by the
				# *child's* fieldnames — a link table that carries "blocked by"
				# beside "relates to" has only the first moving a date — so it
				# cannot be checked against this screen's columns the way every
				# other key here is. `_gantt` checks it, where the child's own
				# columns are in hand, which is the same division the board's
				# `arrangement` makes for the same reason.
				kept.setdefault(view_type, {})["depends_where"] = value
			elif key == "diary" and view_type == "calendar":
				# Whether this screen's records belong in the *merged* diary as
				# well as on their own calendar. A flag rather than a field,
				# and the only one here — see `_calendar` for the argument.
				kept.setdefault(view_type, {})["diary"] = bool(value)
			elif key.endswith("_field") and isinstance(value, str) and value in offered:
				kept.setdefault(view_type, {})[key] = value

	return kept


# How many fields a board card may carry. A card is a glance: past this it is a
# record rendered badly, and the person wanting the sixth field wants the record.
MAX_CARD_FIELDS = 6


#: The `view_settings` key that says where a record's history starts.
TIMELINE = "timeline"

#: The `view_settings` key that says what a New dialog starts with.
CREATE = "create"

#: How many fields one may fill in. A dialog that arrives mostly filled is a
#: form somebody stops reading, and this exists for the one or two a narrowed
#: screen cannot do without.
MOST_CREATE_VALUES = 6


def _timeline(asked, offered: set) -> dict:
	"""Which field points at the record this one came from.

	One key and one fieldname, checked against this screen's own columns like
	every other `_field` here. A Link or a Dynamic Link — the second is the one
	this exists for, because ERPNext's `Opportunity.party_name` is a Dynamic
	Link and a deal may come from a Lead, a Customer or a Prospect.

	The *walk* is `surround`'s, where the record is in hand and the reader's
	permission on the far end can be checked. This only says which field.
	"""
	if not isinstance(asked, dict):
		return {}
	field = str(asked.get("inherits") or "").strip()
	return {"inherits": field} if field and field in offered else {}


def _create(asked, offered: set) -> dict:
	"""What a New dialog on this screen starts with in it.

	Fieldnames checked against the screen's own columns, like everything else
	here: a manifest may pre-fill a field the screen offers and nothing else.
	The *value* is not checked and cannot be — it is a Data, a Link id, a
	number — but it is a manifest's, not a request's, and the dialog it lands
	in is the screen's own with the screen's own permissions behind Save. This
	does not write anything; it fills a box somebody can still change.
	"""
	if not isinstance(asked, dict):
		return {}
	values = asked.get("values")
	if not isinstance(values, dict):
		return {}
	kept = {name: value for name, value in values.items()
	        if isinstance(name, str) and name in offered}
	if not kept:
		return {}
	return {"values": dict(list(kept.items())[:MOST_CREATE_VALUES])}


# What a board may make columns of.
#
# A Select is the obvious one — its options *are* the columns, in the doctype's
# own order, and they exist whether or not any record is in them. A Link works
# too and is the one people ask for next ("by assignee", "by customer"), with
# one difference: its columns are the values actually present on the page,
# because the alternative is a column for every row of the target doctype and
# nobody wants four hundred empty ones.
#
# Unless the screen says otherwise. `columns_from` is a manifest saying "the
# rows of the thing this links to *are* the columns, in this order" — which is
# exactly right where that doctype is a small table a workspace maintains for
# the purpose: the stages of a pipeline, the columns of a board. It is what
# makes an empty column droppable and what lets a team rename one and have the
# board follow, and it is the only way a Link board can do either. See
# `_columns_from`.
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
		# The columns themselves, where the screen says they are the rows of
		# the doctype this field links to rather than the values on the page.
		# Empty everywhere else, and the browser falls back to what it always
		# did — which is also what a reader who may not read that table gets.
		"columns": _columns_from(offered.get(column), settings.get("columns_from")),
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


#: The field a column row carries its colour on, where it carries one.
#:
#: Named rather than declared, because every table in this repository that is a
#: set of board columns spells it the same way — `One Task State.colour`,
#: `One Deal Stage.colour` — and a manifest saying so again would be a manifest
#: that can get it wrong.
COLUMN_COLOUR = "colour"


def _columns_from(column: dict | None, asked) -> list[dict]:
	"""A Link board's columns, read off the doctype it links to.

	`frappe.get_list` and not `get_all`: this is a read on the reader's behalf,
	so a person who may not read the stage table gets an empty answer and the
	board falls back to the values on their own page. That is the right
	failure — a narrower board rather than a refused screen.

	The order is the table's own, which is the whole point: a workspace moves
	In review before Done by editing a row, and every board over that field
	moves with it. A manifest declaring the order instead is a second place for
	it to be true, and it was.
	"""
	if not (column and column.get("fieldtype") == "Link" and isinstance(asked, dict)):
		return []
	doctype = column.get("options") or ""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []

	meta = frappe.get_meta(doctype)
	order_by = str(asked.get("order_by") or "").strip()
	# Checked against the target's own fields, because it is a fieldname there
	# and this is the one place that can tell. Anything else falls back to the
	# order a list would come back in anyway.
	wanted = order_by.split()[0] if order_by else ""
	if wanted and not (meta.get_field(wanted) or wanted in ("name", "creation", "modified")):
		order_by = ""

	fields = ["name"]
	# `meta.title_field` and not `get_title_field()`: the attribute is what a
	# doctype declared, and the method answers `name` when it declared nothing —
	# which would put `name` in the field list twice.
	title = getattr(meta, "title_field", "") or ""
	if title and title != "name" and meta.get_field(title):
		fields.append(title)
	if meta.get_field(COLUMN_COLOUR):
		fields.append(COLUMN_COLOUR)

	try:
		rows = frappe.get_list(
			doctype, fields=fields, order_by=order_by or "name asc",
			limit_page_length=board.COLUMNS, ignore_ifnull=True,
		)
	except frappe.PermissionError:
		return []

	return [{
		"value": one.get("name"),
		"label": (one.get(title) if title else "") or one.get("name"),
		"colour": one.get(COLUMN_COLOUR) or "",
	} for one in rows]


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


def _column(resolved: dict, fieldname) -> dict | None:
	"""One of the screen's own columns, by name."""
	if not isinstance(fieldname, str):
		return None
	for one in resolved.get("all_columns") or resolved.get("columns") or []:
		if one.get("fieldname") == fieldname:
			return one
	return None


#: The themes a Badge draws, which is the vocabulary a manifest may paint in.
#: Mirrors `STATE_COLORS`' values in `scripts/field_types.py` — Frappe's own
#: colour names mapped onto frappe-ui's — so a cell and a badge can only ever
#: be coloured from one list.
BADGE_THEMES = ("gray", "blue", "green", "orange", "red", "amber", "violet",
                "teal", "pink")


def _matrix(resolved: dict) -> dict:
	"""What a matrix puts down the side, across the top, and in a cell.

	`row_field` and `date_field` are the two a screen has to give; naming
	either badly drops the whole view, because a grid missing one of its two
	axes is not a thinner grid, it is a list with extra steps. `value_field` is
	optional and is what colours a cell — the screen's own status where it has
	one, which is what an attendance grid actually wants.

	Settled here rather than read off the screen, the same as the board's
	column field: a saved view may name another, and the reader's answer is the
	narrowest one.
	"""
	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or []}
	settings = (resolved.get("view_settings") or {}).get("matrix") or {}

	row = settings.get("row_field") or ""
	# A Link, and only a Link. A grid down the side of a free-text field is a
	# row per spelling, which is not a grid, it is the same list sorted.
	row = row if offered.get(row, {}).get("fieldtype") in ("Link", "Dynamic Link") else ""

	date = settings.get("date_field") or ""
	date = date if row and _dateable(offered.get(date)) else ""
	# Never a row without a date either: the two are one declaration.
	row = row if date else ""

	value = settings.get("value_field") or resolved.get("status_field") or ""
	value = value if row and offered.get(value) else ""

	# Already validated in `_shaped`, which is where every other bounded-by-value
	# key is checked. Dropped here only when there is nothing to colour.
	colours = settings.get("colours") if value else {}
	colours = colours if isinstance(colours, dict) else {}

	# What the row's label is, where the Link's id is not it. An Employee is
	# `HR-EMP-00003` and nobody reads a grid down the side of those; the
	# doctype's own title field is resolved into `_links` for every row, so
	# the browser has the words without another query.
	return {"row_field": row, "date_field": date, "value_field": value,
	        "colours": colours}


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
		# Whether this screen belongs in `/one/calendar` as well as on its own.
		#
		# Opt-in, and it has to be: the merged diary reads every calendar in
		# the workspace, and "every record with a date on it" is not a diary.
		# OneHR alone declares eleven calendars — attendance, check-ins, shift
		# requests — and eight people's attendance is sixty-three entries in a
		# month that belong to nobody reading it. They flooded the grid to the
		# point where the fixture's own meeting was behind a "+7 more".
		#
		# So a screen says. What earns a place is a record that happens *at* a
		# time to somebody: a leave, an interview, a booked call, a milestone.
		# What does not is a record that merely carries a date.
		"diary": bool(settings.get("diary")),
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
	doctype = resolved.get("doctype") or ""
	column = offered.get(depends) or {}
	# Two shapes, and the second is the one a real plan needs. A **Link** is
	# one predecessor — enough for a register of stages and honest about being
	# one. A **Table** is a task's own edges, which is how anything with a
	# critical path stores them: ERPNext's `Task Depends On`, whose rows name
	# what this task waits for. The child's own Link back at this doctype is the column
	# that carries the id, and it is found the same way a connection's is.
	through = _sequenced(column, doctype)
	if not start or not (through or _nests(column, doctype)):
		depends = through = ""
	where = _sequence_where(said.get("depends_where"), column) if through else {}

	# Which of these are dates rather than work. A Check, because "is this a
	# milestone" is a yes or a no and a screen that had to name a status value
	# for it would be naming one per workspace.
	marker = said.get("milestone_field") or ""
	if offered.get(marker, {}).get("fieldtype") != "Check":
		marker = ""

	return {
		"start_field": start,
		"end_field": end,
		"progress_field": measure,
		"depends_field": depends,
		# Where the id is, inside a row of that table, and what else has to be
		# true of the row. Empty for a plain Link, which is read off the record.
		"depends_child": through,
		"depends_doctype": (column.get("child") or {}).get("doctype", "") if through else "",
		"depends_where": where,
		"milestone_field": marker,
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


def _sequenced(column: dict | None, doctype: str) -> str:
	"""The column inside a child table that names another record of this kind.

	A task's dependencies are rows, not a field, and the row has to say which
	task it is about. The field named after the doctype wins where there is
	one, exactly as `spaceview/connections.py` picks between two Links — it is
	the same question asked one level down.
	"""
	child = (column or {}).get("child") or {}
	if not (doctype and child):
		return ""
	links = [one for one in (child.get("columns") or [])
	         if one.get("fieldtype") == "Link" and one.get("options") == doctype]
	if not links:
		return ""
	wanted = frappe.scrub(doctype)
	chosen = next((one for one in links if one["fieldname"] == wanted), links[0])
	return chosen["fieldname"]


#: How many conditions a screen may put on which rows of that table count.
SEQUENCE_WHERE = 3


def _sequence_where(asked, column: dict) -> dict:
	"""What else has to be true of a row for it to be a sequence.

	A link table that carries both "blocked by" and "relates to" has only the
	first as a schedule: a chart that drew an arrow for "see also" would push
	dates around for a note somebody left. So the screen says which rows it
	means, in the child's own words. No manifest here needs it since
	`docs/WORK.md` §12 — ERPNext's `Task Depends On` is sequences and nothing
	else — and it stays because the shape is a real one and a register of
	stages with a "see also" column is the next space that has it.

	Checked against the child's columns like every other fieldname in a
	settings blob, and equality only — this narrows a set of rows to the ones
	that are a sequence, and anything cleverer is a query the manifest should
	not be writing.
	"""
	if not isinstance(asked, dict):
		return {}
	offered = {one["fieldname"] for one in (column.get("child") or {}).get("columns") or []}
	kept = {}
	for field, value in list(asked.items())[:SEQUENCE_WHERE]:
		if field in offered and isinstance(value, (str, int, float)):
			kept[field] = value
	return kept


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
	# The calendar's field, or the matrix's — whichever this screen has. Both
	# ask the same question ("the days on screen") and a screen that offers
	# both names the same field twice, so taking the first that resolves is
	# the whole of the rule.
	field = ((resolved.get("calendar") or {}).get("start_field")
	         or (resolved.get("matrix") or {}).get("date_field") or "")
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


def _dashboard(resolved: dict) -> dict:
	"""What a dashboard needs beyond its widgets.

	Lifted to the top of the spec like the board's and the matrix's, because
	that is where a body reads its own settings from — `spec.board`,
	`spec.matrix`, `spec.dashboard`. The widgets are lifted separately and have
	been since before this key existed, which is why they are not in here.

	No checking here, and that is not an omission: `resolve` replaces
	`view_settings` with the validated one before `_resolve_views` runs, so
	`period_field` has already been through `_view_settings` — where it is held
	to being a *date* the screen carries rather than merely a column, because
	it reaches a `between` filter. Pinned by
	`test_a_dashboards_period_has_to_be_a_date`, which is the ordering as much
	as the rule.
	"""
	settings = resolved.get("view_settings") or {}
	found = settings.get("dashboard") if isinstance(settings, dict) else None
	if not isinstance(found, dict):
		return {"period_field": ""}
	return {"period_field": found.get("period_field") or ""}


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
	resolved["matrix"] = _matrix(resolved)
	resolved["cards"] = _cards(resolved)
	resolved["widgets"] = _widgets(resolved)
	resolved["dashboard"] = _dashboard(resolved)
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
		# And which rows are milestones, which is never a column: a Check
		# nobody lists is what turns a bar into the diamond a plan is measured
		# by, and without this every date reads as a stretch of work.
		resolved["gantt"]["milestone_field"],
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
		# And what a matrix puts down the side and across the top. The date is
		# usually a column already and the row field usually is not — nobody
		# lists the employee column on an attendance screen they read one
		# person at a time — and without this the grid has rows for nothing.
		resolved["matrix"]["row_field"],
		resolved["matrix"]["date_field"],
		resolved["matrix"]["value_field"],
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
