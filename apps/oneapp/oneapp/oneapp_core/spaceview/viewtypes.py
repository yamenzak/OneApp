"""The ways a screen can be looked at, and what each one needs."""

from frappe import _
from .meta import _json


# Every way a screen can be looked at. Only `list` has a body; the rest are
# named here so a manifest can declare one before it ships — `_view_types`
# drops what is not built, so such a screen opens as a list rather than as
# nothing. `apps/oneapp/frontend/src/lib/viewTypes.js` is the same list, and a
# test fails when the two drift.
VIEW_TYPES = ("list", "board", "calendar", "dashboard", "gantt", "grid", "map")


BUILT_VIEW_TYPES = ("list", "board", "grid", "dashboard", "calendar", "gantt")


DEFAULT_VIEW_TYPE = "list"


# View types that are a way of reading one field, and are nothing without it.
# A board is columns of a status: no status field, no columns, and a board of
# one column called "everything" is not a board. Declaring one without a
# `status_field` is caught by the manifest check; this is the runtime half of
# the same rule, because a manifest is not the only way a screen is written.
NEEDS_STATUS = ("board",)


# And a calendar is a way of reading one date, so the same rule again: a
# screen that offers one and names no date field has nothing to put on a grid
# of days. The field is named in `view_settings.calendar`, the way the
# dashboard's widgets are, rather than on the screen itself — a date field is
# read by the calendar and by nothing else, where `status_field` is also the
# badge on a record and earns its place on the screen.
NEEDS_DATES = ("calendar",)


# And a Gantt is a bar down time, so it needs both ends of one. A record with a
# start and no end is a moment, and a chart of moments is a column of dots.
#
# Its fields are declared under `gantt`, falling back to the calendar's: a
# screen offering both is placing its records by the same two dates, and making
# it say so twice is how the two drift.
NEEDS_SPANS = ("gantt",)


# And the same rule for the dashboard, which is nothing without something to
# measure. A screen that offers one and declares no widgets would open on an
# empty page — so the type is dropped and the screen opens on its list, the
# way a board is dropped where there is no field to make columns of.
NEEDS_WIDGETS = ("dashboard",)


# Plural endings, longest first, and their singular. Not a stemmer: this is
# only ever applied to a screen's own label, which is a short noun phrase
# somebody in this repo wrote, and a screen whose plural these get wrong says
# so with `singular`.
PLURALS = (
	("ies", "y"),     # Companies, Currencies
	("ches", "ch"),   # Batches
	("shes", "sh"),   # Dishes
	("sses", "ss"),   # Addresses
	("xes", "x"),     # Taxes
	("s", ""),        # Tasks, Notes, Invoices
)


def _singular(screen: dict) -> str:
	"""One of these, in the words a customer reads.

	The heading over a create form, and the noun in the toast after it saves. It
	used to be the doctype's own name, which meant a customer clicking New on a
	screen called Tasks got a dialog headed **New ToDo** — a Frappe word, on the
	one surface where this product promises there are none.

	So it comes from the screen instead, singularised: screen labels are plural
	by convention, and "New Tasks" is not a sentence. The rule is deliberately
	small and covers the labels this repo actually writes; anything it gets
	wrong — People, Series, an already-singular label — says so by declaring
	`singular` on the screen, which is one word beside the label it corrects.
	"""
	said = (screen.get("singular") or "").strip()
	if said:
		return _(said)

	label = (screen.get("label") or "").strip()
	for ending, instead in PLURALS:
		if label.lower().endswith(ending) and len(label) > len(ending):
			return _(label[: len(label) - len(ending)] + instead)
	return _(label)


def _view_types(screen: dict) -> list[str]:
	"""The types one screen offers, in order, filtered to what is built."""
	declared = [
		one.strip().lower()
		for one in str(screen.get("view_types") or "").split(",")
		if one.strip().lower() in BUILT_VIEW_TYPES
	]
	if not _has_column_field(screen):
		declared = [one for one in declared if one not in NEEDS_STATUS]
	if not _has_widgets(screen):
		declared = [one for one in declared if one not in NEEDS_WIDGETS]
	if not _has_date_field(screen):
		declared = [one for one in declared if one not in NEEDS_DATES]
	if not _has_span(screen):
		declared = [one for one in declared if one not in NEEDS_SPANS]
	return list(dict.fromkeys(declared)) or [DEFAULT_VIEW_TYPE]


def _has_widgets(screen: dict) -> bool:
	"""Whether this screen declares anything for a dashboard to draw.

	A declaration check, like `_has_column_field`: whether each widget is
	*valid* is decided in `_dashboard`, where there are columns to check the
	fieldnames against.
	"""
	settings = _json(screen.get("view_settings"))
	found = settings.get("dashboard") if isinstance(settings, dict) else None
	return bool(isinstance(found, dict) and found.get("widgets"))


def _has_date_field(screen: dict) -> bool:
	"""Whether this screen names a field a calendar could place a record by.

	A declaration check, like the two above: whether the field is one a
	calendar can *read* is a question about the fieldtype, and it is asked in
	`_calendar`, where the columns are.
	"""
	settings = _json(screen.get("view_settings"))
	found = settings.get("calendar") if isinstance(settings, dict) else None
	return bool(isinstance(found, dict) and (found.get("start_field") or "").strip())


def _has_span(screen: dict) -> bool:
	"""Whether this screen names both ends of a bar.

	A declaration check like the others; the fieldtypes are checked in `_gantt`.
	"""
	settings = _json(screen.get("view_settings"))
	if not isinstance(settings, dict):
		return False
	for key in ("gantt", "calendar"):
		found = settings.get(key)
		if not isinstance(found, dict):
			continue
		if (found.get("start_field") or "").strip() and (found.get("end_field") or "").strip():
			return True
	return False


def _has_column_field(screen: dict) -> bool:
	"""Whether this screen names a field a board could make columns of.

	The `status_field` is the usual answer and the one a manifest should give.
	A screen may instead name another in its own `view_settings`, which is what
	a doctype with no status but an obvious grouping field wants — and either
	way this is a *declaration* check, not a fieldtype one: the fieldtype is
	checked in `_board`, where there are columns to check it against.

	A reader's own choice does not appear here on purpose. A saved view narrows
	what a screen offers; it cannot add a view type the screen never offered.
	"""
	if (screen.get("status_field") or "").strip():
		return True
	settings = _json(screen.get("view_settings"))
	board = settings.get("board") if isinstance(settings, dict) else None
	return bool(isinstance(board, dict) and (board.get("column_field") or "").strip())
