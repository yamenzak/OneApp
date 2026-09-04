"""The ways a screen can be looked at, and what each one needs."""

from frappe import _
from .meta import _json


# Every way a screen can be looked at. Only `list` has a body; the rest are
# named here so a manifest can declare one before it ships — `_view_types`
# drops what is not built, so such a screen opens as a list rather than as
# nothing. `apps/oneapp/frontend/src/lib/viewTypes.js` is the same list, and a
# test fails when the two drift.
VIEW_TYPES = ("list", "board", "calendar", "dashboard", "grid", "map")


BUILT_VIEW_TYPES = ("list", "board", "grid", "dashboard")


DEFAULT_VIEW_TYPE = "list"


# View types that are a way of reading one field, and are nothing without it.
# A board is columns of a status: no status field, no columns, and a board of
# one column called "everything" is not a board. Declaring one without a
# `status_field` is caught by the manifest check; this is the runtime half of
# the same rule, because a manifest is not the only way a screen is written.
NEEDS_STATUS = ("board",)


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
