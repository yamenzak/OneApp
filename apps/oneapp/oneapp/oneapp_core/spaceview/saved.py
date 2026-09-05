"""Reading the layouts somebody saved, and picking which one applies."""

import frappe
from .viewtypes import DEFAULT_VIEW_TYPE


# What a layout carries. `user` empty is Frappe's `for_user` empty: a layout
# everyone on the workspace sees.
LAYOUT_FIELDS = ("name", "label", "icon", "user", "is_default", "filters", "order_by",
                 "columns", "page_length", "group_by", "favourites",
                 "view_type", "view_settings")


# Which icons a view may carry.
#
# Not "any lucide name": Tailwind's lucide plugin only emits CSS for the class
# names it can see in the source, so a name chosen at runtime renders as
# nothing at all. This is the same curated set the rail offers — one list of
# icons that are guaranteed to draw — and `tests/test_screens.py` fails when it
# drifts from `lib/icons.js`.
#
# An emoji needs no build step, which makes it the escape hatch that actually
# works: it is text, so any of them renders. Frappe CRM tolerates an emoji here
# for legacy reasons; for us it is the more capable of the two.
VIEW_ICONS = (
	# General
	"lucide-layout-grid", "lucide-database",
	"lucide-sparkles", "lucide-shield",
	# People
	"lucide-users", "lucide-user-round",
	"lucide-graduation-cap", "lucide-stethoscope",
	# Work
	"lucide-briefcase", "lucide-calendar",
	"lucide-clock", "lucide-wrench",
	# Money
	"lucide-file-text", "lucide-receipt",
	"lucide-wallet", "lucide-shopping-cart",
	# Goods
	"lucide-package", "lucide-truck",
	"lucide-factory", "lucide-store",
	# Talking
	"lucide-message-square", "lucide-mail",
	"lucide-phone",
	# Numbers
	"lucide-chart-line", "lucide-chart-pie",
	"lucide-book-open",
)


# Eight code points at most. One emoji is often several — a flag is two, a skin
# tone adds one, a family joined by zero-width joiners is seven — so a bound of
# one or two would reject emoji people actually use. Eight is short enough that
# nobody puts a sentence in a menu row.
MAX_EMOJI = 8


def _view_icon(value) -> str:
	"""The icon a view may carry, or nothing.

	Two shapes, checked rather than trusted: one of the offered lucide names,
	which reaches the DOM as a class name and so may only ever be one of ours,
	or a short glyph with no ASCII letter or digit in it.

	That second rule is frappe-ui's own definition of an emoji — `Icon` renders
	a name matching it as text and anything else as nothing at all — so this is
	the same question the component will ask, asked before the value is stored
	rather than after.
	"""
	icon = (value or "").strip()
	if not icon:
		return ""
	if icon in VIEW_ICONS:
		return icon
	if len(icon) > MAX_EMOJI or icon.startswith("lucide-"):
		return ""
	if any(char.isascii() and char.isalnum() for char in icon) or any(char.isspace() for char in icon):
		return ""
	return icon


def _can_share() -> bool:
	"""Who may write a layout everyone on this workspace sees.

	Frappe's rule is Administrator or System Manager. Ours is the same shape
	with our own role in it: the workspace owner, whom docs/ONESPACE.md, Roles deliberately
	does *not* make a System Manager, and support, who arrives as one.
	"""
	# Imported here rather than at the top: `workspace` reaches into Frappe's
	# timezone tables at import time, and this module is read by tests that
	# stand up neither.
	from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE})


def _hidden(space_code: str, screen: str) -> set[str]:
	"""Which shared views this person has taken out of their own menu.

	Per person, so it is a table of rows rather than a flag on the view: a
	shared view has one row and many readers, and "I do not want this one" is
	each reader's own answer rather than a change to what everybody sees.
	"""
	return set(frappe.get_all(
		"OneSpace Hidden View",
		filters={"user": frappe.session.user, "space_code": space_code, "screen": screen},
		pluck="layout", ignore_permissions=True,
	))


def _layouts(space_code: str, screen: str, view_type: str | None = None,
             include_hidden: bool = False) -> list[dict]:
	"""Every layout this person can open on this screen: theirs, and the shared.

	Two queries rather than one with `or_filters`. Frappe ANDs `or_filters` with
	`filters` rather than OR-ing the whole thing, which has already cost us once
	— a panel that showed nine plans as one — and two reads of a tiny table are
	cheaper than being wrong about it.
	"""
	where = {"space_code": space_code, "screen": screen}
	fields = list(LAYOUT_FIELDS)
	mine = frappe.get_all("OneSpace Saved View", filters={**where, "user": frappe.session.user},
	                      fields=fields, ignore_permissions=True)
	shared = frappe.get_all("OneSpace Saved View", filters={**where, "user": ["in", ["", None]]},
	                        fields=fields, ignore_permissions=True)
	rows = mine + shared
	for row in rows:
		row["user"] = row.get("user") or ""
		row["shared"] = not row["user"]
		row["mine"] = row["user"] == frappe.session.user
		# A layout written before view types, or by a screen that only has one,
		# belongs to the default.
		row["view_type"] = row.get("view_type") or DEFAULT_VIEW_TYPE
	# Only a shared row can be hidden — your own you delete — so a stale row
	# naming something else changes nothing.
	hidden = _hidden(space_code, screen)
	for row in rows:
		row["hidden"] = bool(row["shared"] and row["name"] in hidden)
	if not include_hidden:
		rows = [row for row in rows if not row["hidden"]]
	if view_type:
		# A board's saved views have no business in a list's switcher: they
		# carry columns and a grouping that mean something else there.
		rows = [row for row in rows if row["view_type"] == view_type]
	rows.sort(key=lambda row: (row["shared"], (row["label"] or "").lower()))
	return rows


def _default_layout(rows: list[dict]):
	"""The layout this screen opens with when nothing is asked for.

	This person's own default first, then a shared default an operator set for
	the workspace — because a personal answer to "what do I look at" outranks
	the house one, and a workspace that sets a default is setting a starting
	point rather than overruling anybody.
	"""
	mine = next((row for row in rows if row["mine"] and row["is_default"]), None)
	if mine:
		return mine
	return next((row for row in rows if row["shared"] and row["is_default"]), None)


def _chosen_layout(rows: list[dict], layout: str | None = None):
	"""Which layout to render: the one asked for, else the default.

	Asking for one that does not exist — a bookmark to a deleted layout — falls
	through rather than throwing: the screen still has a declaration to render.
	"""
	if layout:
		found = next((row for row in rows if row["name"] == layout), None)
		if found:
			return found
	return _default_layout(rows)


def _of_type(view_type: str | None):
	"""A filter value matching the layouts of one view type.

	Empty counts as the default type, in exactly one direction: a row written
	before view types existed, or by a screen that only ever had one, belongs to
	the list. `_layouts` says the same thing when it reads them back, and the
	two have to agree or a save lands on a row the switcher will not show.
	"""
	wanted = view_type or DEFAULT_VIEW_TYPE
	if wanted == DEFAULT_VIEW_TYPE:
		return ["in", [DEFAULT_VIEW_TYPE, "", None]]
	return wanted


def _saved(space_code: str, screen: str, view_type: str | None = None):
	"""This person's unnamed default — the one Save writes when nothing is named.

	Kept as its own lookup because "save what I am looking at" has to land on the
	same row every time, and a named layout is not that row.

	One per *view type*, not one per screen. A screen offering a list and a
	board has two unnamed defaults, because "what I am looking at" is two
	different things — and while this was keyed by screen alone, saving on the
	board rewrote the list's row with the board's columns and re-filed it, so
	the list quietly lost the answers somebody had saved for it.
	"""
	return frappe.db.get_value(
		"OneSpace Saved View",
		{"user": frappe.session.user, "space_code": space_code, "screen": screen,
		 "label": ["in", ["", None]], "view_type": _of_type(view_type)},
		["name"],
		as_dict=True,
	)
