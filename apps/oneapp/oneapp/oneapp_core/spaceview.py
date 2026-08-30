"""Resolving a space's declared screen against this site's own metadata.

A space declares a screen as little more than a doctype and a list of fieldnames.
Everything a screen actually needs to render — what each field is called, what
type it is, what a Select offers, whether this user may create or edit — comes
from the tenant site, because that is where the doctype and the permissions
live. The control plane could not know any of it without keeping a copy that
would be wrong the first time a field changed.

Two rules make it safe to hand a customer:

  * **The manifest is the allowlist, twice over.** A screen can only be reached
    through a space the workspace is entitled to, and can only name a doctype
    that space's permission manifest already granted. So a screen is not a way to
    read something the entitlement did not include.

  * **Permission is Frappe's, not ours.** Every read and write goes through the
    ordinary DocPerms `sync_permissions` writes from that same manifest. This
    reports what the user may do so the UI can hide what it must; it does not
    decide it.
"""

import json

import frappe
from frappe import _

from oneapp.oneapp_core import fieldtypes

# Fetched on every screen and shown on none. `name` is how a record is opened
# and saved, and on most doctypes it is a hash — "8eleplcmv6" as the first thing
# a customer reads is worse than no column at all.
ALWAYS = ("name",)

# Field types a generated form knows how to render. Anything else is shown but
# not offered for editing — better a record with a read-only field on it than a
# control that silently writes the wrong shape.
EDITABLE_TYPES = {
	"Data", "Small Text", "Text", "Long Text", "Text Editor", "Int", "Float",
	"Currency", "Percent", "Date", "Datetime", "Time", "Check", "Select",
	"Link", "Phone", "Read Only",
}

# Never offered, whatever a doctype says: these are Frappe's bookkeeping and a
# customer editing them is always a mistake.
HIDDEN = {
	"owner", "modified", "modified_by", "creation", "idx", "docstatus",
	"parent", "parenttype", "parentfield", "_user_tags", "_comments",
	"_assign", "_liked_by", "naming_series",
}


def _space(space_code: str) -> dict:
	"""The space, if this workspace is entitled to it."""
	from oneapp.oneapp_core import sync

	for space in sync.state().get("spaces") or []:
		if space.get("space_code") == space_code:
			return space
	frappe.throw(_("No space named {0} is enabled here.").format(space_code),
	             frappe.PermissionError)


def _granted_doctypes(space: dict) -> set[str]:
	"""What this space's manifest actually granted, by role.

	Read back off the permissions we wrote rather than from the manifest we were
	sent: those are the rows that decide the answer, and a screen pointing at
	something outside them would fail at the first query anyway.
	"""
	role = space.get("role_name")
	if not role:
		return set()
	return set(frappe.get_all("Custom DocPerm", filters={"role": role}, pluck="parent"))


def _columns(meta, wanted: list[str]) -> list[dict]:
	by_name = {df.fieldname: df for df in meta.fields}
	columns = []

	for fieldname in wanted:
		if fieldname in HIDDEN:
			# Frappe's own bookkeeping. A customer reading `docstatus` or
			# editing `owner` is always an accident, whatever a manifest says.
			continue

		df = by_name.get(fieldname)
		if not df:
			# A field the space named and this site does not have. Skipped rather
			# than fatal: the same manifest serves sites on different versions.
			continue

		columns.append({
			"fieldname": df.fieldname,
			"label": _(df.label or df.fieldname),
			"fieldtype": df.fieldtype,
			"options": df.options,
			"reqd": int(df.reqd or 0),
			"read_only": int(df.read_only or 0),
			"editable": fieldtypes.editable(df.fieldtype) and not df.read_only,
			# How a list cell reads it and what marks the column. A Check is a
			# Switch in a form and a tick in a list, which is why these are two
			# separate answers rather than one.
			"cell": fieldtypes.cell_for(df.fieldtype),
			"icon": fieldtypes.icon_for(df.fieldtype),
			# The rest of what the doctype already says about presentation, so
			# nobody has to repeat it in a manifest.
			"description": df.description or None,
			"placeholder": df.placeholder or None,
			"precision": df.precision or None,
			"non_negative": int(df.non_negative or 0),
			"default": df.default or None,
			"link_filters": df.link_filters or None,
			# Dynamic Link names the field holding its doctype; without it the
			# picker has nothing to search.
			"depends_on_field": df.options if df.fieldtype == "Dynamic Link" else None,
			# The doctype's own emphasis. Frappe's list draws a `bold` field
			# heavier, and a field that matters on one doctype and not on
			# another is exactly the kind of thing a manifest should not have
			# to repeat.
			"bold": int(getattr(df, "bold", 0) or 0),
			# How wide the doctype thinks this column wants to be, in Frappe's
			# own grid units. A default rather than a ceiling, like the field
			# list itself — the picker still has a width box.
			"columns": int(getattr(df, "columns", 0) or 0),
			# A Duration says which of its parts are worth reading. Frappe's own
			# two flags, and the only two it has.
			"hide_days": int(getattr(df, "hide_days", 0) or 0),
			"hide_seconds": int(getattr(df, "hide_seconds", 0) or 0),
			# Set on the way in and never again. Editable on a new record and
			# read-only afterwards, which is a thing only the record knows — so
			# the flag travels and the dialog decides.
			"set_only_once": int(getattr(df, "set_only_once", 0) or 0),
			# Where the value comes from when it is not typed. Shown as the
			# field's own note, because "Company (from Customer)" answers the
			# question a read-only box otherwise raises.
			"fetch_from": getattr(df, "fetch_from", None) or None,
		})

	return columns


def _fetch_fields(columns: list[dict]) -> list[str]:
	"""The columns that are actually fields on the document.

	`__activity` is a column and not a field; asking the database for it is a
	`SQL syntax` error rather than an empty cell, so it is filtered here rather
	than remembered at every call site.
	"""
	return list(dict.fromkeys(
		[c["fieldname"] for c in columns if c["fieldname"] != META_COLUMN] + list(ALWAYS)
	))


def _offerable(meta) -> list[str]:
	"""Every field of this doctype a person may be offered as a column.

	The manifest's field list is a default, not a ceiling. A space declaring
	`customer,status,total` is saying "start here", and someone who wants to see
	the due date should not need a deploy to get it.

	That is a real widening and worth being precise about what it does and does
	not open. The entitlement granted the *doctype*, and the DocPerms written
	for it are what let this user read a row at all; showing another column of a
	row they can already read is not a new permission. What is a new permission
	is a field Frappe protects separately, so:

	* **permlevel is honoured.** `get_permlevel_access("read")` says which
	  levels this user may read, and a field above them is not offered here or
	  anywhere downstream — a screen cannot become a way around field-level
	  permissions.
	* **Frappe's bookkeeping stays out**, as it always has.
	* **Layout and child tables stay out**: neither carries a value in a row.
	"""
	allowed = set(meta.get_permlevel_access("read") or [0])

	return [
		df.fieldname
		for df in meta.fields
		if df.fieldname not in HIDDEN
		and not fieldtypes.is_layout(df.fieldtype)
		and df.fieldtype not in ("Table", "Table MultiSelect")
		and (df.permlevel or 0) in allowed
	]


# The one column that is not a field. Every list carries when a row last
# changed, how many comments are on it and whether this person liked it — and
# a person who does not want that should be able to drop it like any other
# column, which means it has to be in the picker like any other column.
META_COLUMN = "__activity"

# What a column may be. Widths are clamped rather than trusted: the number
# reaches a CSS grid track, and a browser sending 900000 is asking the layout
# to do something silly rather than asking for a wide column.
MIN_WIDTH = 64
MAX_WIDTH = 800
PINS = ("left", "right")


def _meta_column() -> dict:
	return {
		"fieldname": META_COLUMN,
		"label": _("Activity"),
		"fieldtype": "Data",
		"options": None,
		"cell": "meta",
		"icon": "lucide-clock",
		"editable": False,
		"read_only": 1,
		"width": 176,
	}


# What one of Frappe's grid units is worth in pixels. Frappe's list lays a row
# out in ten of them across the width it has; this is that at a comfortable
# desktop width, and it is only where a column *starts* — the picker still has
# a width box, and a saved layout overrides it.
UNIT_WIDTH = 96


def _default_width(column: dict) -> int:
	"""How wide a column starts.

	The doctype's own answer first, where it gave one: `columns` on a DocField
	is what Frappe's list uses, and a doctype that says its description wants
	four units and its status one is saying something worth honouring.

	Otherwise the cell kind, which knows better than the fieldtype: a badge is a
	badge whether it came from a Select or a Link.
	"""
	units = column.get("columns") or 0
	if units:
		return max(MIN_WIDTH, min(units * UNIT_WIDTH, MAX_WIDTH))

	by_cell = {
		"meta": 176,
		"badge": 128,
		"check": 80,
		"date": 128,
		"datetime": 176,
		"time": 96,
		"rating": 128,
		"color": 112,
		"numeric": 112,
		"duration": 128,
		"image": 96,
	}
	return by_cell.get(column.get("cell"), 144)


def _json_list(value):
	"""A stored column list, whichever shape it is in.

	A JSON array parses. Anything else is handed straight back — a
	comma-separated string is the shape this used to be stored in, and `_placed`
	knows how to read it.
	"""
	if not value:
		return []
	if isinstance(value, str) and value.lstrip().startswith("["):
		try:
			return frappe.parse_json(value)
		except Exception:
			return []
	return value


def _placed(offered: dict, wanted) -> list[dict]:
	"""A person's column list, as columns.

	Accepts the shape it is stored in now — `[{fieldname, width, pin}, …]` — and
	the comma-separated fieldnames it used to be, because views saved then are
	still on disk. Anything naming a field the screen does not offer is dropped
	rather than invented, which is the same rule as everywhere else here.
	"""
	# Normalised here rather than at each call site, because there are four and
	# the one that forgot stored an empty list and silently kept the defaults.
	wanted = _json_list(wanted)
	if isinstance(wanted, str):
		wanted = [{"fieldname": f.strip()} for f in wanted.split(",") if f.strip()]
	if not isinstance(wanted, (list, tuple)):
		return []

	placed = []
	for entry in wanted:
		if isinstance(entry, str):
			entry = {"fieldname": entry}
		if not isinstance(entry, dict):
			continue
		column = offered.get(entry.get("fieldname"))
		if not column:
			continue

		width = entry.get("width")
		try:
			width = int(width)
		except (TypeError, ValueError):
			width = _default_width(column)
		pin = entry.get("pin")

		placed.append({
			**column,
			"width": max(MIN_WIDTH, min(width or _default_width(column), MAX_WIDTH)),
			"pin": pin if pin in PINS else None,
		})
	return placed


def _quick_filters(meta, columns: list[dict]) -> list[str]:
	"""Which fields get a box of their own above the list.

	Frappe's own answer: the ones a doctype marks `in_standard_filter`, plus its
	title field. It is a decision the doctype already made — the fields somebody
	actually searches this thing by — so no manifest has to repeat it.
	"""
	offered = {c["fieldname"] for c in columns}
	wanted = [
		df.fieldname
		for df in meta.fields
		if df.fieldname in offered
		and (df.in_standard_filter or df.fieldname == meta.title_field)
	]
	return list(dict.fromkeys(wanted))


def _default_fields(meta) -> list[str]:
	"""What to show when a space named nothing.

	The doctype's own list fields first, then its title, then whatever the first
	few non-hidden data fields are. A space that declares no columns still gets a
	list worth looking at.
	"""
	# The doctype's own answer first: `in_list_view` is what its author already
	# decided belongs in a list.
	listed = [df.fieldname for df in meta.fields
	          if df.in_list_view and not fieldtypes.cell_for(df.fieldtype) == "hidden"]
	if listed:
		return listed[:4]

	title = meta.title_field
	found = [title] if title else []
	for df in meta.fields:
		if len(found) >= 3:
			break
		if df.fieldname in HIDDEN or df.fieldname in found:
			continue
		if df.fieldtype in ("Data", "Select", "Link", "Date", "Datetime", "Currency"):
			found.append(df.fieldname)
	return found


def presentation(meta) -> dict:
	"""What the doctype says about how it should look.

	All of it is already on the doctype — Frappe's own authors filled it in and
	the desk reads it. Carrying it here means a space inherits a title, an image
	and status colours without a manifest repeating any of it.
	"""
	return {
		# The human name of a record. Most doctypes name themselves with a hash,
		# so this is the difference between a list of titles and a list of ids.
		"title_field": meta.title_field or "name",
		"image_field": getattr(meta, "image_field", None) or None,
		"sort_field": meta.sort_field or "modified",
		"sort_order": (meta.sort_order or "DESC").upper(),
		# Colour per status, declared on the doctype. Frappe's desk reads these
		# for its indicators; a badge in OneSpace reads the same ones, so a
		# status is not one colour here and another there.
		"states": [
			{"title": row.title, "color": row.color}
			for row in (getattr(meta, "states", None) or [])
		],
		"is_submittable": int(getattr(meta, "is_submittable", 0) or 0),
		"track_changes": int(getattr(meta, "track_changes", 0) or 0),
		"track_seen": int(getattr(meta, "track_seen", 0) or 0),
		"max_attachments": int(getattr(meta, "max_attachments", 0) or 0),
		# A naming series means the customer does not name records; a prompt
		# means they must. Either way the form should not ask for `name`.
		"naming": _naming(meta),
	}


def _default_order(meta) -> str:
	"""The doctype's own sort, when a screen does not name one. Its author
	already decided what "newest" means for it."""
	return f"{meta.sort_field or 'modified'} {(meta.sort_order or 'desc').lower()}"


def _naming(meta) -> str:
	autoname = (getattr(meta, "autoname", None) or "").lower()
	if not autoname:
		return "hash"
	if autoname.startswith("naming_series"):
		return "series"
	if autoname.startswith("field:"):
		return "field"
	if autoname == "prompt":
		return "prompt"
	return "expression"


def _resolve(space_code: str, screen: str | None = None,
             view_type: str | None = None) -> dict:
	"""Everything OneSpace needs to render one screen."""
	space = _space(space_code)
	screens = space.get("screens") or []

	if not screens:
		return {"space": space_code, "label": space.get("space_label"),
		        "screens": [], "screen": None}

	chosen = next((s for s in screens if s.get("screen") == screen), screens[0])
	offered = _view_types(chosen)

	resolved = {
		"space": space_code,
		"label": space.get("space_label"),
		"screens": [
			{"screen": s["screen"], "label": s["label"], "icon": s.get("icon"),
			 "view_types": _view_types(s)}
			for s in screens
		],
		"screen": chosen["screen"],
		"screen_label": chosen["label"],
		# How this screen may be looked at, and which of those we are rendering.
		# The first is what it opens with; asking for one it does not offer gets
		# that rather than an error, because a stale link is not a failure.
		"view_types": offered,
		"view_type": view_type if view_type in offered else offered[0],
		"view_settings": _json(chosen.get("view_settings")),
		# The escape hatch, and the reason the manifest is a shortcut rather
		# than a cage: name a component and none of the rest of this applies.
		"component": chosen.get("component") or None,
	}

	if resolved["component"]:
		return resolved

	doctype = chosen.get("document_type")
	if not doctype:
		resolved["error"] = _("This screen names neither a doctype nor a component.")
		return resolved

	if doctype not in _granted_doctypes(space):
		# A screen outside the space's own grant. Refused here rather than left to
		# fail as an empty list, which reads like there is no data.
		frappe.throw(
			_("{0} is not part of {1}.").format(doctype, space.get("space_label")),
			frappe.PermissionError,
		)

	if not frappe.db.exists("DocType", doctype):
		resolved["error"] = _("{0} is not installed on this workspace.").format(doctype)
		return resolved

	meta = frappe.get_meta(doctype)
	wanted = [f.strip() for f in (chosen.get("fields") or "").split(",") if f.strip()]
	wanted = list(dict.fromkeys(wanted or _default_fields(meta)))
	columns = _columns(meta, wanted)

	# Everything this person could put on the screen, which is the doctype's own
	# field list rather than the manifest's — see `_offerable`. The manifest
	# decides what is on by default; a person decides what they look at.
	offerable = [*_columns(meta, _offerable(meta)), _meta_column()]
	offered = {c["fieldname"]: c for c in offerable}

	# The manifest's list, plus activity at the end. Widths are defaults and
	# nothing is pinned: where a column sticks is a reading preference, and
	# guessing it for somebody is how the meta column ended up glued to an edge
	# nobody asked for.
	columns = _placed(offered, [c["fieldname"] for c in columns] + [META_COLUMN])

	resolved.update({
		"doctype": doctype,
		"columns": columns,
		"all_columns": [{**c, "width": _default_width(c)} for c in offerable],
		"quick_filters": _quick_filters(meta, offerable),
		**presentation(meta),
		# What to ask the database for: the columns that are fields, plus the
		# identity that is never one. Activity is neither.
		"fields": _fetch_fields(columns),
		"filters": _json(chosen.get("filters")),
		"order_by": chosen.get("order_by") or _default_order(meta),
		# How many rows a page is, and what the footer may offer instead. The
		# screen's default until a saved view says otherwise.
		"page_length": PAGE,
		"page_sizes": list(PAGE_SIZES),
		"can_create": bool(frappe.has_permission(doctype, "create")),
		"can_write": bool(frappe.has_permission(doctype, "write")),
		"can_delete": bool(frappe.has_permission(doctype, "delete")),
	})
	return resolved


# Every way a screen can be looked at. Only `list` has a body; the rest are
# named here so a manifest can declare one before it ships — `_view_types`
# drops what is not built, so such a screen opens as a list rather than as
# nothing. `apps/oneapp/frontend/src/lib/viewTypes.js` is the same list, and a
# test fails when the two drift.
VIEW_TYPES = ("list", "board", "calendar", "grid", "map")
BUILT_VIEW_TYPES = ("list",)
DEFAULT_VIEW_TYPE = "list"


def _view_types(screen: dict) -> list[str]:
	"""The types one screen offers, in order, filtered to what is built."""
	declared = [
		one.strip().lower()
		for one in str(screen.get("view_types") or "").split(",")
		if one.strip().lower() in BUILT_VIEW_TYPES
	]
	return list(dict.fromkeys(declared)) or [DEFAULT_VIEW_TYPE]


def _json(raw):
	if not raw:
		return {}
	try:
		value = json.loads(raw)
	except (TypeError, ValueError):
		return {}
	return value if isinstance(value, dict) else {}


# --------------------------------------------------------------------------- #
# Endpoints
#
# Reads and writes go through the screen rather than through a generic document
# API, and that is the point rather than a formality: the screen says which
# doctype and which fields, so a screen cannot be used to read a doctype the
# entitlement did not include or to write a field it does not show. Frappe's own
# permissions still decide whether any of it is allowed — this only bounds what
# is asked for.
# --------------------------------------------------------------------------- #

# A page of records. Large enough that most screens never ask for more, small
# enough that a doctype with a hundred thousand rows does not arrive. The
# reader can change it — the footer offers PAGE_SIZES and remembers the choice
# in their screen — and MAX_PAGE is the ceiling whatever they ask for.
PAGE = 100
MAX_PAGE = 500
PAGE_SIZES = (20, 50, 100, 500)


@frappe.whitelist(methods=["GET"])
def spec(space_code: str, screen: str | None = None, layout: str | None = None,
         view_type: str | None = None) -> dict:
	return _apply_saved(_resolve(space_code, screen, view_type), layout)


@frappe.whitelist(methods=["GET"])
def rows(space_code: str, screen: str | None = None, limit: int = PAGE,
         start: int = 0, overrides: str | dict | None = None,
         layout: str | None = None, view_type: str | None = None) -> dict:
	"""The records a screen lists, and whether there are more of them.

	`overrides` is a filter or sort someone has changed but not saved. Folded in
	the same way a saved view is — narrowing only, and through the same checks —
	so an unsaved change cannot reach further than a saved one.
	"""
	# Through the saved view as well, or the columns and the rows disagree about
	# which fields exist and every cell reads empty.
	resolved = _apply_saved(_resolve(space_code, screen, view_type), layout)
	resolved = _apply_overrides(resolved, overrides)
	if not resolved.get("doctype"):
		return {"rows": [], "has_more": False, "columns": [], "order_by": ""}

	limit = min(int(limit or PAGE), MAX_PAGE)
	filters = _all_filters(resolved, resolved.get("asked") or [])

	# One more than asked for, so "there are more" needs no second count query.
	found = frappe.get_list(
		resolved["doctype"],
		fields=resolved["fields"] + list(META_FIELDS),
		filters=filters,
		order_by=_grouped_order(resolved),
		limit_start=int(start or 0),
		limit_page_length=limit + 1,
	)
	found = [_with_meta(row) for row in found]
	_with_links(resolved, found[:limit])

	# The columns come back with the rows, not only from `spec`. An unsaved
	# change to the column list narrows what is fetched, and a header list that
	# does not follow leaves a column standing over empty cells.
	return {
		"rows": found[:limit],
		"has_more": len(found) > limit,
		"columns": resolved["columns"],
		"order_by": resolved["order_by"],
		"group_by": resolved.get("group_by") or "",
	}


@frappe.whitelist(methods=["GET"])
def record(space_code: str, screen: str, name: str) -> dict:
	"""One row, fetched by id rather than found on a page.

	A record is in the URL now, which means it can be arrived at from a link,
	a bookmark or a reload — none of which have the list it came from. Reading
	it out of `rows` would mean paging until it turned up.

	The same bounds the list has, and one more: `get_list` with a `name` filter
	rather than `get_doc`, so User Permissions and the screen's own filters
	still decide. A record this screen would not list is not a record this
	screen may open by id.
	"""
	resolved = _resolve(space_code, screen)
	if not resolved.get("doctype"):
		return {}

	# Every field the record shows, not the columns the list happens to carry.
	# The dialog renders the doctype's whole field list, and it used to seed
	# itself from the list row — so a field nobody put on the list opened blank
	# on a record that has a value for it.
	fields = _fetch_fields(resolved.get("all_columns") or resolved["columns"])

	found = frappe.get_list(
		resolved["doctype"],
		fields=fields + list(META_FIELDS),
		# The screen's own filters, not a saved view's: you can arrive at a
		# record from one view and open it under another, and a personal filter
		# is not a rule about what exists.
		filters=_all_filters(resolved, []) + [["name", "=", name]],
		limit_page_length=1,
	)
	if not found:
		return {}

	found = [_with_meta(row) for row in found]
	_with_links(resolved, found)
	return found[0]


@frappe.whitelist(methods=["GET"])
def count(space_code: str, screen: str | None = None, overrides: str | dict | None = None,
          layout: str | None = None, view_type: str | None = None) -> dict:
	"""How many rows match — asked separately from the rows themselves.

	Its own request on purpose. A `COUNT(*)` over a filter with no index behind
	it is a full scan, and folding it into the page would put that scan in front
	of every list anybody opens. The rows arrive first and the footer fills in
	its "of 1,240" when this answers; a footer that reads "48" for a moment is a
	fair price for a list that is never held up by a count.
	"""
	resolved = _apply_overrides(
		_apply_saved(_resolve(space_code, screen, view_type), layout), overrides
	)
	if not resolved.get("doctype"):
		return {"total": 0}
	return {"total": _total(resolved, _all_filters(resolved, resolved.get("asked") or []))}


def _total(resolved: dict, filters: list) -> int:
	"""How many rows match, not how many were fetched.

	Through `get_list` rather than `db.count` so it is the same number the rows
	came from: `get_list` applies this user's permissions and their User
	Permissions, and `db.count` does not — a count that is larger than the list
	it labels is worse than no count.
	"""
	# `{"COUNT": "*"}` rather than the string `count(*)`: Frappe refuses a SQL
	# function written as a string in `fields`, and says so at runtime only.
	found = frappe.get_list(
		resolved["doctype"],
		filters=filters,
		fields=[{"COUNT": "*"}],
		as_list=True,
	)
	return int(found[0][0]) if found else 0


# What every list carries beside its columns: when a row last changed, how many
# comments are on it, and who liked it. Frappe keeps all three on the document,
# so this costs no extra query.
META_FIELDS = ("modified", "_comments", "_liked_by")


def _with_links(resolved: dict, rows: list[dict]) -> None:
	"""Turn the ids in Link columns into records, in place.

	A link is a record, not a string: a cell showing `HR-EMP-00042` is showing
	the database's answer rather than the reader's. So every Link column on the
	page is resolved to the same three things the title column shows — a face, a
	name, an id — and rendered the same way.

	One query per link column per page, not one per cell: forty rows with three
	link columns is three queries, and the ids repeat. A target this user may
	not read simply comes back empty and the cell falls back to the id, which is
	the truthful thing to show.
	"""
	links = [c for c in resolved.get("columns") or [] if c["fieldtype"] == "Link"]
	if not links or not rows:
		return

	for column in links:
		target = column.get("options")
		if not target or not frappe.db.exists("DocType", target):
			continue
		ids = {row.get(column["fieldname"]) for row in rows if row.get(column["fieldname"])}
		if not ids:
			continue

		meta = frappe.get_meta(target)
		shape = _link_shape(meta)
		fields = ["name"] + [f for f in (shape["title"], shape["image"]) if f]
		found = frappe.get_list(
			target, fields=fields, filters={"name": ["in", list(ids)]},
			limit_page_length=len(ids),
		)
		by_id = {row["name"]: _link_row(row, dict(shape, search=[])) for row in found}

		for row in rows:
			value = row.get(column["fieldname"])
			if value and value in by_id:
				row.setdefault("_links", {})[column["fieldname"]] = by_id[value]


def _with_meta(row: dict) -> dict:
	"""Turn Frappe's bookkeeping into the three things a row shows.

	`_comments` holds the comments themselves — author, text, timestamp — and
	only the count belongs in a list, so it is counted here and dropped. That is
	the whole reason this is a rewrite rather than a passthrough.
	"""
	comments = frappe.parse_json(row.pop("_comments", None) or "[]")
	liked = frappe.parse_json(row.pop("_liked_by", None) or "[]")

	row["_meta"] = {
		"modified": row.pop("modified", None),
		"comments": len(comments) if isinstance(comments, list) else 0,
		"likes": len(liked) if isinstance(liked, list) else 0,
		"liked": frappe.session.user in liked if isinstance(liked, list) else False,
	}
	return row


def _writable(resolved: dict) -> set[str]:
	"""Which fields a save may set.

	Everything the screen could show, not the columns currently on the list —
	the record dialog renders the doctype's whole field list, and a control that
	looks editable and is silently discarded is worse than one that is not
	offered.

	That widened when the column picker did, and it is worth saying what still
	holds. The doctype has to be one the space's manifest granted with write
	access; Frappe's own `has_permission(write)` still decides; `read_only`
	fields are not editable; fields above this user's permlevel are not in
	`all_columns` at all; and Frappe's bookkeeping is never in it either. What
	went is our extra narrowing to the manifest's field list, which was a
	presentation default rather than a permission.
	"""
	offered = resolved.get("all_columns") or resolved["columns"]
	return {c["fieldname"] for c in offered if c.get("editable")}


@frappe.whitelist(methods=["POST"])
def save(space_code: str, screen: str, values: str | dict, name: str | None = None) -> dict:
	"""Create or update one record, within what the screen declares."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has nothing to save."))

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Expected an object of values."))

	# The allowlist is the screen. A field the screen does not show is not a field
	# this screen may write, whatever arrives in the payload.
	allowed = _writable(resolved)
	changes = {k: v for k, v in values.items() if k in allowed}
	if not changes:
		frappe.throw(_("Nothing on this screen can be changed."))

	if name:
		doc = frappe.get_doc(doctype, name)
		doc.update(changes)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": doctype, **changes})
		doc.insert()

	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def remove(space_code: str, screen: str, name: str | list) -> dict:
	"""Delete one record, or a selection of them.

	One call rather than one per row: a selection of forty is forty round trips
	otherwise, and a partial failure halfway through leaves nobody able to say
	what happened. `frappe.delete_doc` runs its own permission check per
	document, and a link somewhere else is a real reason for one to fail — so
	each is attempted, and what could not go is named.
	"""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has nothing to delete."))

	names = frappe.parse_json(name) if isinstance(name, str) and name.startswith("[") else name
	if not isinstance(names, (list, tuple)):
		names = [names]
	if len(names) > MAX_DELETE:
		frappe.throw(_("Too many at once. Delete {0} or fewer.").format(MAX_DELETE))

	deleted, refused = [], []
	for one in names:
		try:
			frappe.delete_doc(doctype, one)
			deleted.append(one)
		except Exception as exc:
			# The usual reason is something else linking to it, which is a fact
			# about the data rather than a bug. Reported per record so a
			# selection of forty does not fail as one opaque error.
			refused.append({"name": one, "reason": str(exc)})

	return {"ok": not refused, "deleted": deleted, "refused": refused}


# --------------------------------------------------------------------------- #
# Link fields
#
# A Link is a foreign key, and a text box over one asks a customer to know a
# record's name. frappe-ui ships a Combobox; what it needs is something to
# search, and that has to be bounded the same way everything else here is.
# --------------------------------------------------------------------------- #

LINK_PAGE = 20


@frappe.whitelist(methods=["GET"])
def link_options(space_code: str, screen: str, fieldname: str, query: str = "") -> list:
	"""Records a Link field may point at.

	Bounded by the screen, like every other read: the field has to be one the
	screen shows, and the doctype it points at has to be readable by this user.
	Frappe's own permissions do the second part — `get_list` returns nothing
	rather than raising, which is the right shape for a picker.
	"""
	resolved = _resolve(space_code, screen)
	column = _link_column(resolved, fieldname)
	target = _link_target(resolved, column)
	if not target or not frappe.db.exists("DocType", target):
		return []

	meta = frappe.get_meta(target)
	shape = _link_shape(meta)
	fields = ["name"] + [f for f in (shape["title"], shape["image"]) if f]
	# The doctype's own search fields, which is what the desk shows under a
	# result: "Contact" without "the one at Halloway" is not a choice anybody
	# can make between two people called Chris.
	extra = [f for f in shape["search"] if f not in fields]

	filters = _json(column.get("link_filters"))
	found = frappe.get_list(
		target,
		fields=fields + extra,
		filters=filters,
		or_filters=_search(meta, query, shape) if query else None,
		limit_page_length=LINK_PAGE,
		order_by="modified desc",
	)

	return [_link_row(row, shape) for row in found]


def _link_shape(meta) -> dict:
	"""How one record of a doctype is shown: its name, its face, its detail.

	The same three things the list's title column shows, because a link *is* a
	record — a person picking one from a menu and reading one in a cell should
	not be looking at two different renderings of it.

	`title_field` regardless of `show_title_field_in_link`: that flag decides
	whether Frappe *stores* the title alongside the id, which is a data
	question. What to show a person is not.
	"""
	return {
		"title": meta.title_field or None,
		"image": meta.image_field or None,
		"search": [f.strip() for f in (meta.search_fields or "").split(",") if f.strip()],
	}


def _link_row(row: dict, shape: dict) -> dict:
	"""One picker row: an id, what to call it, a face, and a line of detail.

	Nothing is said twice. A doctype with no `title_field` shows its id as the
	name rather than under it, and one whose title *is* its id — a User named
	after its own full name, a Role named `field:role_name` — does the same,
	because "Administrator / Administrator / Administrator" is what three
	truthful lookups against Frappe's own metadata produce and it is not a row
	anybody can read.
	"""
	name = row["name"]
	title = (row.get(shape["title"]) if shape["title"] else None) or None
	label = str(title or name)

	seen = {label, str(name)}
	detail = []
	for fieldname in shape["search"]:
		value = row.get(fieldname)
		if value and str(value) not in seen:
			seen.add(str(value))
			detail.append(str(value))

	return {
		"value": name,
		# What a person recognises, falling back to the id when a doctype has no
		# title — which is most of them.
		"label": label,
		# The id, and only where it adds something the name does not.
		"id": name if label != str(name) else None,
		"image": (row.get(shape["image"]) if shape["image"] else None) or None,
		"description": ", ".join(detail) or None,
	}


@frappe.whitelist(methods=["GET"])
def link_new_spec(space_code: str, screen: str, fieldname: str) -> dict:
	"""What creating a record for a Link field would ask for.

	Frappe's quick entry, in our vocabulary: the fields a doctype marks
	`allow_in_quick_entry`, plus anything mandatory, because a form that omits a
	required field is a form that cannot be submitted.

	Refused unless the target is a doctype this space granted *and* this user
	may create. The first is the rule that makes a screen an allowlist; the
	second is Frappe's.
	"""
	resolved = _resolve(space_code, screen)
	target = _link_target(resolved, _link_column(resolved, fieldname))
	if not target or not frappe.db.exists("DocType", target):
		return {"can_create": False, "fields": []}

	space = _space(space_code)
	if target not in _granted_doctypes(space) or not frappe.has_permission(target, "create"):
		return {"can_create": False, "fields": []}

	meta = frappe.get_meta(target)
	wanted = [df.fieldname for df in meta.fields if _quick_entry(df)]
	return {
		"can_create": True,
		"doctype": target,
		"label": _(meta.get("name")),
		# Which field the typed text should land in. Frappe's own quick entry
		# does the same thing: somebody who typed "Halloway" into the picker
		# and pressed Create meant it as the record's name, not as nothing.
		"title_field": meta.title_field or None,
		"fields": _columns(meta, wanted),
	}


def _quick_entry(df) -> bool:
	"""Whether a field belongs on the quick-create form.

	The doctype's own answer, twice over: `allow_in_quick_entry` is what the
	desk asks, and `reqd` is what a save will insist on anyway. A read-only or
	hidden field is neither, whatever the flags say.
	"""
	if df.fieldname in HIDDEN or fieldtypes.is_layout(df.fieldtype):
		return False
	if df.read_only or getattr(df, "hidden", 0):
		return False
	return bool(getattr(df, "allow_in_quick_entry", 0) or df.reqd)


@frappe.whitelist(methods=["POST"])
def link_new(space_code: str, screen: str, fieldname: str, values: str | dict) -> dict:
	"""Create one record for a Link field, and hand back the row to show.

	Bounded the same way the picker is, and then again by Frappe: only fields
	the quick form offered are written, so a payload naming something else
	writes nothing rather than being refused — the same rule `save` follows for
	the screen's own doctype.
	"""
	resolved = _resolve(space_code, screen)
	target = _link_target(resolved, _link_column(resolved, fieldname))
	space = _space(space_code)
	if (
		not target
		or not frappe.db.exists("DocType", target)
		or target not in _granted_doctypes(space)
	):
		frappe.throw(_("Nothing can be created for {0} here.").format(fieldname),
		             frappe.PermissionError)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Expected an object of values."))

	meta = frappe.get_meta(target)
	allowed = {df.fieldname for df in meta.fields if _quick_entry(df)}
	changes = {k: v for k, v in values.items() if k in allowed}

	doc = frappe.get_doc({"doctype": target, **changes})
	doc.insert()

	shape = _link_shape(meta)
	fresh = frappe.db.get_value(
		target, doc.name,
		["name"] + [f for f in (shape["title"], shape["image"], *shape["search"]) if f],
		as_dict=True,
	)
	return _link_row(fresh or {"name": doc.name}, shape)


@frappe.whitelist(methods=["GET"])
def link_preview(space_code: str, screen: str, fieldname: str, name: str) -> dict:
	"""A few facts about the record a link points at, for a card on hover.

	Frappe's own answer to "what would you want to know without leaving the
	list": the target doctype's `in_preview` fields, which is a flag a doctype
	sets once and every screen pointing at it gets for free. A doctype that
	marks none has nothing to preview and says so, rather than showing an empty
	card — which reads as a card that failed to load.

	Bounded like the picker on the way in, and by Frappe on the way out:
	`get_doc` raises where this user may not read the record, and a field above
	their permlevel is not in `_columns` to begin with.
	"""
	resolved = _resolve(space_code, screen)
	target = _link_target(resolved, _link_column(resolved, fieldname))
	if not target or not frappe.db.exists("DocType", target):
		return {"fields": []}

	meta = frappe.get_meta(target)
	wanted = [
		df.fieldname
		for df in meta.fields
		if getattr(df, "in_preview", 0)
		and df.fieldname not in HIDDEN
		and not fieldtypes.is_layout(df.fieldtype)
		and df.fieldtype not in ("Table", "Table MultiSelect")
		and (df.permlevel or 0) in set(meta.get_permlevel_access("read") or [0])
	]
	if not wanted:
		return {"fields": []}

	doc = frappe.get_doc(target, name)
	doc.check_permission("read")

	shape = _link_shape(meta)
	return {
		"record": _link_row(
			{"name": doc.name, **{f: doc.get(f) for f in _preview_shape_fields(shape)}},
			shape,
		),
		# The target's own status colours, not the screen's: a card over a
		# Contact shows Contact's states, and a badge that changes colour
		# between a cell and the card above it is worse than no colour.
		"states": [
			{"title": row.title, "color": row.color}
			for row in (getattr(meta, "states", None) or [])
		],
		"fields": [
			{**column, "value": doc.get(column["fieldname"])}
			for column in _columns(meta, wanted)
		],
	}


def _preview_shape_fields(shape: dict) -> list[str]:
	"""The fields `_link_row` reads, so the header of a card matches a cell."""
	return [f for f in (shape["title"], shape["image"], *shape["search"]) if f]


def _link_column(resolved: dict, fieldname: str) -> dict:
	"""The screen's own column for a field, or a refusal.

	Against everything the screen could show, not only the columns currently on
	the list. The record dialog renders the doctype's whole field list — hiding
	a column says nothing about whether the record has the field — so checking
	the narrower set refused a picker for a field sitting right there on the
	form.
	"""
	offered = resolved.get("all_columns") or resolved.get("columns") or []
	column = next((c for c in offered if c["fieldname"] == fieldname), None)
	if not column:
		frappe.throw(_("{0} is not on this screen.").format(fieldname),
		             frappe.PermissionError)
	return column


def _link_target(resolved: dict, column: dict) -> str | None:
	"""Which doctype a Link points at.

	A Link says so in `options`. A Dynamic Link names another field that holds
	the answer, so it can only be resolved against a record — which the picker
	does not have, so it is refused rather than guessed at.
	"""
	if column["fieldtype"] == "Link":
		return column.get("options")
	return None


def _search(meta, query: str, shape: dict) -> list:
	"""Match the id, the title, or anything the doctype calls searchable.

	`like` rather than a full-text search: this is a twenty-row picker, not a
	search page. `search_fields` is the doctype's own answer to "what would
	somebody type to find one of these", so it is the right list to use.
	"""
	term = f"%{query}%"
	clauses = [["name", "like", term]]
	for fieldname in [shape["title"], *shape["search"]]:
		if fieldname and [fieldname, "like", term] not in clauses:
			clauses.append([fieldname, "like", term])
	return clauses


# --------------------------------------------------------------------------- #
# What surrounds a record
#
# Comments, the change log, who liked it. All of it is Frappe's own, on every
# doctype, and none of it needs a space to ask for it.
# --------------------------------------------------------------------------- #

TIMELINE_PAGE = 50


@frappe.whitelist(methods=["GET"])
def timeline(space_code: str, screen: str, name: str) -> dict:
	"""A record's comments and its history, newest first."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		return {"comments": [], "changes": [], "likes": [], "liked": False}

	# Reading the document is the permission check: `get_doc` raises when this
	# user may not, and a timeline is no less private than the record it is on.
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	comments = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": name,
		         "comment_type": "Comment"},
		fields=["name", "content", "comment_email", "comment_by", "creation"],
		order_by="creation desc",
		limit_page_length=TIMELINE_PAGE,
	)

	changes = []
	if resolved.get("track_changes"):
		changes = frappe.get_all(
			"Version",
			filters={"ref_doctype": doctype, "docname": name},
			fields=["name", "owner", "creation", "data"],
			order_by="creation desc",
			limit_page_length=TIMELINE_PAGE,
		)
		changes = [_change(row, resolved) for row in changes]
		changes = [row for row in changes if row["entries"]]

	liked = frappe.parse_json(doc.get("_liked_by") or "[]")

	return {
		"comments": comments,
		# How many there are, not how many came back. The page is capped at 50,
		# so on a record with more than that the count derived from the list
		# stopped moving when a comment was added — the badge said 50 for ever.
		# Frappe keeps the same number on the document itself.
		#
		# It keeps the last hundred and no more, so past that this saturates.
		# The desk's number is this number, and the alternative — a count query
		# per row — is a query per row.
		"comment_count": len(frappe.parse_json(doc.get("_comments") or "[]")),
		"changes": changes,
		"more_comments": len(comments) >= TIMELINE_PAGE,
		"likes": liked,
		"liked": frappe.session.user in liked,
		"can_comment": True,
	}


def _change(row: dict, resolved: dict) -> dict:
	"""One version, in the words of the screen rather than of the database.

	Frappe stores a Version as raw field names and values. Rendering that as-is
	gives a customer `grand_total: 120.0 → 140.0` for a field their screen calls
	"Total"; the labels are already resolved on the columns, so use them.
	"""
	labels = {c["fieldname"]: c["label"] for c in resolved.get("columns") or []}

	try:
		data = frappe.parse_json(row.get("data") or "{}")
	except Exception:
		data = {}

	entries = []
	for fieldname, before, after in (data.get("changed") or []):
		if fieldname in HIDDEN or fieldname not in labels:
			# Only what this screen shows. A change to a field the customer
			# cannot see reads as noise about something that does not exist.
			continue
		entries.append({"label": labels[fieldname], "from": before, "to": after})

	return {
		"name": row["name"],
		"by": row["owner"],
		"on": row["creation"],
		"entries": entries,
	}


@frappe.whitelist(methods=["POST"])
def comment(space_code: str, screen: str, name: str, content: str) -> dict:
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to comment on here."))

	content = (content or "").strip()
	if not content:
		frappe.throw(_("A comment needs something in it."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	added = frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Comment",
		"reference_doctype": doctype,
		"reference_name": name,
		"content": content[:5000],
		"comment_email": frappe.session.user,
		"comment_by": frappe.utils.get_fullname(frappe.session.user),
	}).insert(ignore_permissions=True)

	return {"name": added.name}


@frappe.whitelist(methods=["POST"])
def toggle_like(space_code: str, screen: str, name: str) -> dict:
	"""Frappe keeps likes in `_liked_by` on the document itself."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to like here."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	from frappe.desk.like import toggle_like as frappe_toggle

	liked = frappe.parse_json(doc.get("_liked_by") or "[]")
	frappe_toggle(doctype, name, add="No" if frappe.session.user in liked else "Yes")

	# Re-read rather than assume: the like is written by Frappe, and reporting
	# the state we intended rather than the state that exists is how a toggle
	# ends up out of step with its own icon.
	after = frappe.parse_json(
		frappe.db.get_value(doctype, name, "_liked_by") or "[]")
	return {"liked": frappe.session.user in after, "likes": after}


# --------------------------------------------------------------------------- #
# Saved views, as named layouts
#
# Frappe's own answer to this is the `List Filter` doctype, and it is worth
# following rather than approximating: a layout has a name, it belongs to one
# person or to everybody (`for_user` empty means global), and the filters, the
# sort and the columns travel together as one saved thing. Frappe CRM built its
# own before the framework had one; the framework's is the one to follow.
#
# What we keep from ours: it is per screen rather than per doctype, because two
# screens over one doctype are two questions.
#
# A layout narrows; it never widens. Its columns are intersected with the
# screen's, and its filters are applied on top of the screen's rather than
# instead of them — so a person cannot save their way to a column the space did
# not offer or a row the screen filtered out. That holds for a shared layout
# too: sharing does not raise what a layout may reach, and every filter in one
# is re-checked against the screen on the way out, not only when it was saved.
# --------------------------------------------------------------------------- #

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
	"lucide-layout-grid", "lucide-users", "lucide-user-round",
	"lucide-briefcase", "lucide-file-text", "lucide-receipt",
	"lucide-wallet", "lucide-shopping-cart", "lucide-package",
	"lucide-truck", "lucide-factory", "lucide-store", "lucide-calendar",
	"lucide-clock", "lucide-message-square", "lucide-mail",
	"lucide-phone", "lucide-chart-line", "lucide-chart-pie",
	"lucide-database", "lucide-book-open", "lucide-graduation-cap",
	"lucide-stethoscope", "lucide-wrench", "lucide-shield",
	"lucide-sparkles",
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
	with our own role in it: the workspace owner, whom DECISIONS §8 deliberately
	does *not* make a System Manager, and support, who arrives as one.
	"""
	# Imported here rather than at the top: `workspace` reaches into Frappe's
	# timezone tables at import time, and this module is read by tests that
	# stand up neither.
	from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE})


def _layouts(space_code: str, screen: str, view_type: str | None = None) -> list[dict]:
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
	if view_type:
		# A board's saved views have no business in a list's switcher: they
		# carry columns and a grouping that mean something else there.
		rows = [row for row in rows if row["view_type"] == view_type]
	rows.sort(key=lambda row: (row["shared"], (row["label"] or "").lower()))
	return rows


@frappe.whitelist(methods=["GET"])
def space_layouts(space_code: str) -> dict:
	"""Every named layout in a space, keyed by the screen it belongs to.

	The sidebar's question, and a different one from the screen's. A screen
	spec answers "what is on this list"; the sidebar has to say what the
	*other* screens can be looked at as, before anybody has opened one — so it
	asks once for the space rather than fetching a spec per screen to draw a
	menu.

	Only what a layout is called and which view type it belongs to. The filters
	and columns are the screen's business, and they are re-checked when the
	screen opens rather than trusted from here.
	"""
	space = _space(space_code)
	found = {}
	for screen in space.get("screens") or []:
		rows = _layouts(space_code, screen["screen"])
		if rows:
			found[screen["screen"]] = [
				{"name": row["name"], "label": row["label"] or "",
				 "icon": row.get("icon") or "",
				 "view_type": row["view_type"], "shared": row["shared"]}
				for row in rows
				if row["label"]
			]
	return found


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


def _saved(space_code: str, screen: str):
	"""This person's unnamed default — the one Save writes when nothing is named.

	Kept as its own lookup because "save what I am looking at" has to land on the
	same row every time, and a named layout is not that row.
	"""
	return frappe.db.get_value(
		"OneSpace Saved View",
		{"user": frappe.session.user, "space_code": space_code, "screen": screen,
		 "label": ["in", ["", None]]},
		["name"],
		as_dict=True,
	)


def _apply_saved(resolved: dict, layout: str | None = None) -> dict:
	"""Fold a layout's saved answers into a resolved screen."""
	saved = None
	resolved["layouts"] = []
	resolved["can_share"] = False
	if resolved.get("screen"):
		rows = _layouts(resolved["space"], resolved["screen"], resolved.get("view_type"))
		# `opens` rather than `is_default`: two rows can both be marked — one
		# personal, one shared — and only one of them actually opens the screen.
		# A menu that pins both is telling the reader something untrue.
		opens = _default_layout(rows)
		resolved["layouts"] = [
			{"name": row["name"], "label": row["label"] or "",
			 "icon": row.get("icon") or "", "shared": row["shared"],
			 "mine": row["mine"], "is_default": bool(row["is_default"]),
			 "view_type": row["view_type"],
			 "opens": bool(opens and opens["name"] == row["name"])}
			for row in rows
		]
		resolved["can_share"] = _can_share()
		saved = _chosen_layout(rows, layout)
	resolved["layout"] = saved["name"] if saved else ""
	resolved["layout_label"] = (saved.get("label") or "") if saved else ""
	resolved["layout_icon"] = (saved.get("icon") or "") if saved else ""
	resolved["saved"] = None
	# Always present, so nothing downstream has to ask whether a saved view
	# exists before reading it.
	resolved["asked"] = []
	resolved["favourites"] = False
	resolved["group_by"] = ""
	if not saved or not resolved.get("doctype"):
		return resolved

	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or resolved["columns"]}
	# Intersected, not substituted: a saved column list that names something the
	# screen no longer offers quietly drops it rather than reintroducing it.
	kept = _placed(offered, saved.get("columns"))
	if kept:
		resolved["columns"] = kept
		resolved["fields"] = _fetch_fields(kept)

	# Bounded again on the way out, not only when it was saved: the row is a
	# doctype an operator can write, and a filter that reached the table another
	# way is still a filter this screen never offered.
	resolved["asked"] = _asked_filters(_filterable(resolved), saved.get("filters"))

	if saved.get("order_by"):
		resolved["order_by"] = _safe_order(resolved, saved["order_by"])

	resolved["favourites"] = bool(saved.get("favourites"))
	resolved["group_by"] = _group_by(resolved, saved.get("group_by"))
	resolved["page_length"] = (
		_page_length(saved.get("page_length")) or resolved.get("page_length") or PAGE
	)

	resolved["saved"] = {
		"filters": resolved["asked"],
		"favourites": resolved["favourites"],
		"group_by": resolved["group_by"],
		"order_by": saved.get("order_by") or "",
		"columns": [
			{"fieldname": c["fieldname"], "width": c["width"], "pin": c["pin"]}
			for c in kept
		],
		"page_length": saved.get("page_length") or 0,
	}
	return resolved


def _page_length(value) -> int:
	"""One of the sizes the footer offers, or nothing.

	Not clamped to a range: the footer is a set of buttons, so a number that is
	not one of them did not come from the footer, and `limit` is bounded again
	where it is used anyway.
	"""
	try:
		asked = int(value or 0)
	except (TypeError, ValueError):
		return 0
	return asked if asked in PAGE_SIZES else 0


def _group_by(resolved: dict, fieldname) -> str:
	"""Which column the rows are grouped under.

	A column the screen offers, or nothing. Not `name` — grouping by the id
	makes a group per row — and not the activity column, which is not a field
	and has no value to group on.
	"""
	if not isinstance(fieldname, str) or not fieldname:
		return ""
	offered = {c["fieldname"] for c in resolved.get("all_columns") or resolved.get("columns") or []}
	if fieldname not in offered or fieldname in (META_COLUMN, "name"):
		return ""
	return fieldname


def _grouped_order(resolved: dict) -> str:
	"""The sort, with the group column in front of it.

	Rows have to arrive grouped for the list to render them that way — the page
	is one query and a group whose rows are scattered through it would render as
	the same heading three times.
	"""
	order = resolved["order_by"]
	group = resolved.get("group_by")
	if not group or order.split(" ")[0] == group:
		return order
	return f"{group} asc, {order}"


def _safe_order(resolved: dict, order_by: str) -> str:
	"""Only a field the screen shows, only a direction we recognise.

	`order_by` reaches the query layer, so it is rebuilt from parts rather than
	passed through — a string a browser sent is not a fragment of SQL.
	"""
	parts = (order_by or "").split()
	fieldname = parts[0] if parts else ""
	direction = (parts[1] if len(parts) > 1 else "desc").lower()

	offered = resolved.get("all_columns") or resolved.get("columns") or []
	known = {c["fieldname"] for c in offered} | set(ALWAYS) | {"modified", "creation"}
	if fieldname not in known or direction not in ("asc", "desc"):
		return resolved["order_by"]
	return f"{fieldname} {direction}"


# How many values one `in` filter may carry, and how many filters one screen
# may be asked. Neither is a security boundary on its own — every one of them is
# already bounded to a field the screen shows — but an unbounded list is a way
# to make one request cost a great deal.
# A selection is a person clicking checkboxes, so this is generous. It exists
# because one request that deletes ten thousand rows is a different thing.
MAX_DELETE = 100

MAX_FILTERS = 20
MAX_IN_VALUES = 100


def _filterable(resolved: dict) -> dict:
	"""The fields a filter may name, keyed by fieldname.

	The columns, plus `name`. The id is not a column — it lives in the title
	cell, under the title — but it is the one thing everybody searches by, and
	Frappe's own list gives it a box of its own above every list. Described here
	rather than looked up, because `name` is not a DocField.
	"""
	offered = {c["fieldname"]: c
	           for c in resolved.get("all_columns") or resolved.get("columns") or []}
	offered.setdefault("name", {
		"fieldname": "name",
		"label": _("ID"),
		"fieldtype": "Data",
		"options": None,
	})
	return offered


def _asked_filters(offered: dict, extra) -> list:
	"""What someone asked to filter by, reduced to something a screen may ask.

	A filter is `[fieldname, operator, value]`, which is Frappe's own shape. The
	operator being a named part rather than something smuggled inside the value
	is what lets this be checked at all: it is looked up against the operators
	that fieldtype allows — Frappe's own table, inverted from a deny list into
	an allow list in `fieldtypes.OPERATORS` — and anything else is dropped.

	Three bounds, and all three matter:

	* **Only fields the screen shows.** A filter on a hidden field narrows the
	  list, which sounds harmless — but a customer who can watch which rows come
	  back can read a field they were never shown, one guess at a time.
	* **Only operators that fieldtype allows.** `descendants of` runs a subquery
	  against another doctype's tree; `regex` is a way to spend a lot of database
	  time. Neither is in Frappe's own filter menu, so neither is here.
	* **Only values of the shape the operator takes.** `between` is exactly two,
	  `is` is one of two words, `in` is a bounded list, everything else is a
	  scalar. A list arriving where a scalar belongs is dropped rather than
	  reinterpreted.

	This is the form that gets stored and echoed back to the controls: what
	someone chose, not the query it turns into.
	"""
	if isinstance(extra, str):
		extra = frappe.parse_json(extra or "null")

	# The shape this used to be, before operators: `{fieldname: value}`. Saved
	# screens written then are still on disk, so they are read as what they meant.
	if isinstance(extra, dict):
		extra = [
			[fieldname, fieldtypes.default_operator(
				offered[fieldname]["fieldtype"] if fieldname in offered else "Data", fieldname),
			 value]
			for fieldname, value in extra.items()
			if fieldname in offered
		]
	if not isinstance(extra, (list, tuple)):
		return []

	asked = []
	for row in extra[:MAX_FILTERS]:
		clean = _asked_filter(offered, row)
		if clean:
			asked.append(clean)
	return asked


def _asked_filter(offered: dict, row) -> list | None:
	"""One filter, or None if it is not one this screen may be asked."""
	if not isinstance(row, (list, tuple)) or len(row) != 3:
		return None

	fieldname, operator, value = row
	column = offered.get(fieldname)
	if not column or not isinstance(operator, str):
		return None

	operator = operator.strip().lower()
	if operator not in fieldtypes.operators_for(column["fieldtype"]):
		return None

	shape = fieldtypes.value_shape(column["fieldtype"], operator)

	if shape == "set":
		return [fieldname, operator, value] if value in ("set", "not set") else None

	if shape == "timespan":
		return [fieldname, operator, value] if value in fieldtypes.TIMESPANS else None

	if shape == "range":
		if not isinstance(value, (list, tuple)) or len(value) != 2:
			return None
		if any(_not_a_value(v) for v in value):
			return None
		return [fieldname, operator, [value[0], value[1]]]

	if shape == "multi":
		if isinstance(value, str):
			# Frappe's own filter splits a typed list on commas.
			value = [v.strip() for v in value.split(",") if v.strip()]
		if not isinstance(value, (list, tuple)) or not value:
			return None
		values = [v for v in value[:MAX_IN_VALUES] if not _not_a_value(v)]
		return [fieldname, operator, values] if values else None

	return None if _not_a_value(value) else [fieldname, operator, value]


def _not_a_value(value) -> bool:
	"""A scalar someone could have typed. Anything else is a shape we did not
	ask for, and reinterpreting it is how a filter becomes a query."""
	return (
		value in ("", None)
		or isinstance(value, (list, tuple, dict, set))
	)


def _as_query_filters(offered: dict, asked: list) -> list:
	"""The same filters, as questions the query layer can be asked.

	Only two rewrites, both Frappe's own (`get_selected_value`): a `like` gets
	wildcards unless the person wrote their own, so a box labelled "Contains"
	contains; and a Check is stored as the word someone picked and asked as the
	0 or 1 the column holds.
	"""
	query = []
	for fieldname, operator, value in asked:
		if operator in ("like", "not like") and isinstance(value, str):
			if not (value.startswith("%") or value.endswith("%")):
				value = f"%{value}%"
		elif offered[fieldname]["fieldtype"] == "Check":
			value = 1 if str(value) in ("1", "Yes", "true", "True") else 0
		query.append([fieldname, operator, value])
	return query


def _favourite_filter() -> list:
	"""Rows this person liked.

	A flag rather than a filter on `_liked_by`, and the difference matters: the
	column is a JSON array of user ids, so a filter naming it could be pointed
	at a colleague and would answer what *they* had liked. The flag can only
	ever mean the session's own user, which is the only version of this question
	anyone should be able to ask.
	"""
	return ["_liked_by", "like", f"%{frappe.session.user}%"]


def _all_filters(resolved: dict, asked: list) -> list:
	"""The screen's own filters and this person's, as one list.

	Both are applied; neither replaces the other. That is what makes the
	narrowing rule hold without a special case: two filters on one field are
	ANDed, so a saved `status = Closed` on a screen filtered to `status = Open`
	returns nothing rather than quietly returning the screen's rows. Frappe's
	desk behaves the same way, and "no rows, and there is my filter" reads
	better than a filter that appears to be ignored.
	"""
	offered = _filterable(resolved)
	own = [[fieldname, "=", value] if not isinstance(value, (list, tuple))
	       else [fieldname, value[0], value[1]]
	       for fieldname, value in (resolved.get("filters") or {}).items()]
	mine = [_favourite_filter()] if resolved.get("favourites") else []
	return own + mine + _as_query_filters(offered, asked)


def _apply_overrides(resolved: dict, overrides) -> dict:
	"""Fold in what the controls are currently asking for."""
	if isinstance(overrides, str):
		overrides = frappe.parse_json(overrides or "null")
	if not overrides or not resolved.get("doctype"):
		return resolved

	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or resolved["columns"]}

	chosen = _placed(offered, overrides.get("columns"))
	if chosen:
		resolved["columns"] = chosen
		resolved["fields"] = _fetch_fields(chosen)

	# Set whenever the payload mentions filters at all, empty list included:
	# clearing the filters in the controls has to clear them in the list, and a
	# truthiness check would leave the saved ones standing.
	if "filters" in overrides:
		resolved["asked"] = _asked_filters(_filterable(resolved), overrides.get("filters"))

	if "favourites" in overrides:
		resolved["favourites"] = bool(overrides.get("favourites"))

	if "group_by" in overrides:
		resolved["group_by"] = _group_by(resolved, overrides.get("group_by"))

	if overrides.get("order_by"):
		resolved["order_by"] = _safe_order(resolved, overrides["order_by"])

	return resolved


@frappe.whitelist(methods=["POST"])
def save_layout(space_code: str, screen: str, filters: str | list | dict | None = None,
              order_by: str | None = None, columns: str | list | None = None,
              page_length: int = 0, favourites: str | bool | int = False,
              group_by: str | None = None, layout: str | None = None,
              label: str | None = None, icon: str | None = None,
              shared: str | bool | int | None = None,
              is_default: str | bool | int | None = None,
              view_type: str | None = None,
              view_settings: str | dict | None = None) -> dict:
	"""Write what this person is looking at into a layout.

	Three things it can be asked to do, and which one is decided by what it is
	given rather than by a mode flag:

	  * `layout` names a row — update that one, if this person may.
	  * `label` without `layout` — a new named layout.
	  * neither — this person's unnamed default for the screen, which is what
	    the Save button on the toolbar writes.

	The annotations are wide on purpose, and `list` in particular is load-
	bearing: Frappe validates a whitelisted method's arguments against them and
	answers a mismatch with a 417 before the body runs. A filter is a list of
	triples now, and while this still said `str | dict` every save from the
	browser was refused before reaching a line of it — which no test that calls
	this function directly can see, because a direct call skips the check.
	"""
	resolved = _resolve(space_code, screen, view_type)
	if not resolved.get("doctype"):
		frappe.throw(_("There is nothing to save a view for here."))

	offered = {c["fieldname"]: c for c in resolved["all_columns"]}
	columns = _placed(offered, columns)
	filters = _asked_filters(_filterable(resolved), filters)

	doc = _layout_doc(space_code, screen, layout, label)
	# Sharing is a permission, so it is checked against what the row will be
	# rather than what it was: taking a personal layout public is the same
	# decision as writing a public one.
	if shared is not None:
		doc.user = "" if frappe.utils.sbool(shared) else frappe.session.user
	_may_write(doc)

	if label is not None:
		doc.label = frappe.utils.strip_html(str(label)).strip()[:140]

	if icon is not None:
		doc.icon = _view_icon(icon)

	doc.update({
		"space_code": space_code,
		"screen": screen,
		"filters": json.dumps(filters),
		"order_by": _safe_order(resolved, order_by or "") if order_by else "",
		# JSON now: a column carries a width and a pin, and a comma-separated
		# list of fieldnames has nowhere to put either. The old shape is still
		# read — see `_placed` — because views saved then are still on disk.
		"columns": json.dumps([
			{"fieldname": c["fieldname"], "width": c["width"], "pin": c["pin"]}
			for c in columns
		]),
		"page_length": _page_length(page_length),
		# Which way of looking this view is of. Checked against the screen's own
		# list rather than taken: a layout tagged with a type the screen does
		# not offer would be invisible in every switcher.
		"view_type": resolved["view_type"],
		"view_settings": json.dumps(_view_settings(resolved, view_settings)),
		"favourites": 1 if frappe.utils.sbool(favourites) else 0,
		"group_by": _group_by(resolved, group_by),
	})

	# An unnamed layout is always this person's default — it is the only thing
	# "save what I am looking at" could mean.
	if is_default is None:
		doc.is_default = 1 if not doc.label else (doc.is_default or 0)
	else:
		doc.is_default = 1 if frappe.utils.sbool(is_default) else 0

	doc.save(ignore_permissions=True)
	if doc.is_default:
		_only_default(doc)
	frappe.db.commit()

	return {"ok": True, "layout": doc.name}


def _view_settings(resolved: dict, asked) -> dict:
	"""What a view type needs that columns and filters do not carry.

	Every value in it that names a field is checked against the screen's own
	columns, the same way a filter or a sort is — a board's column field is a
	fieldname reaching a query, and "it came from the settings blob" is not a
	reason to trust one.
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
	kept = {}
	for key, value in asked.items():
		if not isinstance(key, str) or not key.endswith("_field"):
			continue
		if isinstance(value, str) and value in offered:
			kept[key] = value
	return kept


def _layout_doc(space_code: str, screen: str, layout: str | None, label: str | None):
	"""The row a save lands on — an existing one, or a new one."""
	if layout:
		doc = frappe.get_doc("OneSpace Saved View", layout)
		if (doc.space_code, doc.screen) != (space_code, screen):
			# A layout belongs to one screen. Naming another screen's row would
			# otherwise move it, silently, out from under whoever saved it.
			frappe.throw(_("That screen belongs to a different screen."), frappe.PermissionError)
		return doc
	if not label:
		existing = _saved(space_code, screen)
		if existing:
			return frappe.get_doc("OneSpace Saved View", existing["name"])
	doc = frappe.new_doc("OneSpace Saved View")
	doc.user = frappe.session.user
	doc.label = ""
	# Not a default until something says so. The doctype's own default is 1,
	# which was right when one unnamed row was the whole feature and is wrong
	# now: making a screen would quietly change which screen the screen opens with.
	doc.is_default = 0
	return doc


def _may_write(doc) -> None:
	"""Frappe's `_can_update_list_filter`, in our vocabulary.

	A shared layout needs the workspace's own admin rights; a personal one needs
	only to be yours. Assigning one to somebody else is not offered at all —
	Frappe allows it for a System Manager and we have no surface that wants it.
	"""
	if not doc.user:
		if not _can_share():
			frappe.throw(_("Only a workspace admin can change a shared screen."),
			             frappe.PermissionError)
		return
	if doc.user != frappe.session.user:
		frappe.throw(_("That screen belongs to someone else."), frappe.PermissionError)


def _only_default(doc) -> None:
	"""One default per person per screen, and one shared default per screen."""
	siblings = frappe.get_all(
		"OneSpace Saved View",
		filters={"space_code": doc.space_code, "screen": doc.screen,
		         "user": doc.user or ["in", ["", None]], "is_default": 1},
		pluck="name", ignore_permissions=True,
	)
	for name in siblings:
		if name != doc.name:
			frappe.db.set_value("OneSpace Saved View", name, "is_default", 0,
			                    update_modified=False)


@frappe.whitelist(methods=["POST"])
def delete_layout(space_code: str, screen: str, layout: str) -> dict:
	"""Remove a layout. Whose it is decides who may."""
	doc = frappe.get_doc("OneSpace Saved View", layout)
	if (doc.space_code, doc.screen) != (space_code, screen):
		frappe.throw(_("That screen belongs to a different screen."), frappe.PermissionError)
	_may_write(doc)
	frappe.delete_doc("OneSpace Saved View", doc.name, ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def default_layout(space_code: str, screen: str, layout: str) -> dict:
	"""Open this screen with this layout from now on.

	Marking a shared layout the default is a workspace-wide decision, so it
	needs the rights to write that layout. Marking your own is not.
	"""
	doc = frappe.get_doc("OneSpace Saved View", layout)
	if (doc.space_code, doc.screen) != (space_code, screen):
		frappe.throw(_("That screen belongs to a different screen."), frappe.PermissionError)
	_may_write(doc)
	doc.is_default = 1
	doc.save(ignore_permissions=True)
	_only_default(doc)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def reset_layout(space_code: str, screen: str) -> dict:
	"""Back to what the screen declares.

	Only this person's unnamed default: a named layout is a thing somebody made
	and is deleted deliberately, not by a button that means "undo my tinkering".
	"""
	existing = _saved(space_code, screen)
	if existing:
		frappe.delete_doc("OneSpace Saved View", existing["name"], ignore_permissions=True)
		frappe.db.commit()
	return {"ok": True}
