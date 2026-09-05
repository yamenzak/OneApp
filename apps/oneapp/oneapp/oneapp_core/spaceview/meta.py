"""What a doctype's own metadata says a screen may show."""

import frappe
import json
from frappe import _
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase


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


def _number(value):
	"""A DocField bound as a number, or None.

	Zero is None, which reads wrong until you look at what Frappe does with
	these. `_validate_min_max_value` skips a field entirely when neither bound
	is truthy, and then guards each with `if min_value and ...` — so on the
	server a bound of zero is not a bound at all.

	Sending it as one would make the browser stricter than the database: a
	field with `min_value` unset would refuse a negative number that saves
	perfectly well. `non_negative` is the flag that actually means "not below
	zero", and Frappe enforces that one separately.
	"""
	try:
		number = float(value)
	except (TypeError, ValueError):
		return None
	return number or None


def _columns(meta, wanted: list[str]) -> list[dict]:
	by_name = {df.fieldname: df for df in meta.fields}
	columns = []
	# Frappe protects a field twice by level: one list of levels you may read,
	# another of levels you may write. Only the first was being asked, so a
	# field at a level this person can read and not write rendered as a control
	# that looked editable and was dropped on save — the worst of the three
	# possible answers, because it is the one that looks like it worked.
	writable = set(meta.get_permlevel_access("write") or [0])

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
			"editable": (
				# A child table is a list of rows rather than a value, so
				# `fieldtypes.editable` says False for it — correctly, because
				# no control writes one field. The parent's save assigns the
				# whole list, so the question here is only whether this field
				# may be written at all.
				(fieldtypes.editable(df.fieldtype) or df.fieldtype == "Table")
				and not df.read_only
				and (df.permlevel or 0) in writable
			),
			# Which level protects it, so nothing downstream has to ask the
			# meta again to know why a field is not offered.
			"permlevel": int(df.permlevel or 0),
			# How a list cell reads it and what marks the column. A Check is a
			# Switch in a form and a tick in a list, which is why these are two
			# separate answers rather than one.
			"cell": fieldtypes.cell_for(df.fieldtype),
			# Whether it belongs on a list at all.
			#
			# A child table is rows, an Attachment Gallery is a strip of
			# pictures and a Password is a value nobody may read — each is a
			# real thing on a record and nothing at all in a cell one line high.
			# They are still offered, because the record renders them; the list
			# and its column picker read this instead of the fieldtype, so the
			# next one like them needs no new rule.
			"list_ok": fieldtypes.cell_for(df.fieldtype) != "hidden",
			# The doctype's own answer to "does this belong in a list", which
			# a child table's grid reads to pick its columns.
			"in_list_view": int(getattr(df, "in_list_view", 0) or 0),
			"icon": fieldtypes.icon_for(df.fieldtype),
			# The rest of what the doctype already says about presentation, so
			# nobody has to repeat it in a manifest.
			"description": df.description or None,
			"placeholder": df.placeholder or None,
			"precision": df.precision or None,
			"non_negative": int(df.non_negative or 0),
			# The doctype's own bounds. Hints for the control — Frappe checks
			# all three on save regardless (`_validate_min_max_value`,
			# `_validate_non_negative`, and the column width for `length`),
			# which is the right division: a browser makes a field pleasant to
			# type into, and a database decides what is true.
			"length": int(getattr(df, "length", 0) or 0),
			"min_value": _number(getattr(df, "min_value", None)),
			"max_value": _number(getattr(df, "max_value", None)),
			# A Select whose options the desk shows alphabetically rather than
			# in the order somebody typed them into the doctype.
			"sort_options": int(getattr(df, "sort_options", 0) or 0),
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
			# The doctype's own rules about when this field applies. Each is
			# either a fieldname — "when that one is filled in" — or `eval:`
			# and an expression about `doc`. The SPA reads them against the
			# record being edited; see `lib/rules.js` for why it parses them
			# rather than running them.
			"depends_on": getattr(df, "depends_on", None) or None,
			"mandatory_depends_on": getattr(df, "mandatory_depends_on", None) or None,
			"read_only_depends_on": getattr(df, "read_only_depends_on", None) or None,
			# Set on the way in and never again. Editable on a new record and
			# read-only afterwards, which is a thing only the record knows — so
			# the flag travels and the dialog decides.
			"set_only_once": int(getattr(df, "set_only_once", 0) or 0),
			# Where the value comes from when it is not typed. Shown as the
			# field's own note, because "Company (from Customer)" answers the
			# question a read-only box otherwise raises.
			"fetch_from": getattr(df, "fetch_from", None) or None,
			# ...and whether it will overwrite what you typed. Without this
			# every fetched field reads as "From Customer" whether it fills a
			# blank once or replaces your answer on every save.
			"fetch_if_empty": int(getattr(df, "fetch_if_empty", 0) or 0),
			# Two different ways for a value to be refused, and they deserve
			# two different messages. `reqd` asks; `not_nullable` refuses.
			# `unique` is neither until a save comes back — it is what turns a
			# DuplicateEntryError into a message on this field rather than a
			# red toast about a database constraint.
			"unique": int(getattr(df, "unique", 0) or 0),
			"not_nullable": int(getattr(df, "not_nullable", 0) or 0),
			# Editable after submit. Only matters on a submittable doctype, and
			# without it a submitted record looks fully editable and every save
			# is refused.
			"allow_on_submit": int(getattr(df, "allow_on_submit", 0) or 0),
			# A Link that reopens on your last choice, which is the doctype
			# saying this is a field somebody sets to the same thing all day.
			"remember_last_selected_value": int(
				getattr(df, "remember_last_selected_value", 0) or 0
			),
			# Where the field's own documentation is, and whether its
			# description is inline or behind an icon.
			"documentation_url": getattr(df, "documentation_url", None) or None,
			"show_description_on_click": int(
				getattr(df, "show_description_on_click", 0) or 0
			),
			# An input mask, applied as a display format rather than as a
			# validator: a mask that fights the typist is worse than none.
			"mask": getattr(df, "mask", None) or None,
			# A ceiling on a text control's height, in Frappe's own units.
			"max_height": getattr(df, "max_height", None) or None,
			# The value is user text somebody may translate. No UI reads this
			# yet; it travels so the next audit does not have to rediscover it.
			"translatable": int(getattr(df, "translatable", 0) or 0),
			# Carried, and deliberately not honoured — see `_link_target` and
			# `tests/test_permission_paths.py`. A docfield saying "User
			# Permissions do not apply to this Link" is a legitimate escape
			# hatch inside the desk, where an administrator is reasoning about
			# their own site. Here it would let a doctype we did not write
			# widen what a customer's screen can reach, so the picker keeps
			# asking Frappe with permissions on and this is only ever read to
			# explain why a field looks narrower than the desk's.
			"ignore_user_permissions": int(
				getattr(df, "ignore_user_permissions", 0) or 0
			),
			# A child table's own shape: which columns its grid draws, and the
			# form a row opens into. Resolved here, on the server, inside the
			# parent's payload — one resolve, where the permlevel filter and
			# the offerable rules already live, rather than a second endpoint
			# the browser would have to call per table per record.
			"child": _child(df),
			# A child table is written by assigning the whole list, which the
			# parent's own save does — so it is editable exactly when the
			# parent field is and the child doctype allows writing.

		})

	return columns


# How many fields a child row's grid shows before it needs the form. Frappe's
# own grid stops around here too: past it the columns are narrower than the
# words in them, and the row is better read one at a time.
CHILD_COLUMNS = 5


def _child(df) -> dict | None:
	"""The child doctype behind a Table field, as columns and a form.

	Both, because a grid and an expanded row are two views of the same rows: the
	grid draws the fields the child marks `in_list_view`, and opening one shows
	the whole thing laid out the way the child doctype lays itself out. Reusing
	`_columns` means every property in the parent's fields applies inside a row
	too — `depends_on`, `reqd`, permlevel, the bounds — without a second
	implementation to keep in step.

	A `Table MultiSelect` is the same thing narrowed to one Link per row, so it
	resolves through here as well and its control reads the single field out.

	None for anything that is not a child table, and for a child doctype this
	site does not have — the same tolerance `_columns` has for a field a
	manifest names and a site lacks.
	"""
	if df.fieldtype not in ("Table", "Table MultiSelect"):
		return None
	target = df.options
	if not target or not frappe.db.exists("DocType", target):
		return None

	meta = frappe.get_meta(target)
	offered = _columns(meta, _offerable(meta))
	by_name = {c["fieldname"]: c for c in offered}

	listed = [c["fieldname"] for c in offered if c.get("in_list_view") and c["list_ok"]]
	if not listed:
		# Frappe's grid falls back to the first few editable fields when a child
		# doctype marks none, and an empty grid is worse than an approximate one.
		listed = [c["fieldname"] for c in offered if c["list_ok"]][:CHILD_COLUMNS]

	return {
		"doctype": target,
		"label": _(meta.get("name")),
		"columns": [by_name[name] for name in listed[:CHILD_COLUMNS]],
		"fields": offered,
		"form": _form(meta, by_name),
		"editable": bool(frappe.has_permission(target, "write")),
	}


def _fetch_fields(columns: list[dict], *always: str) -> list[str]:
	"""The columns that are actually fields on the document.

	`__activity` is a column and not a field; asking the database for it is a
	`SQL syntax` error rather than an empty cell, so it is filtered here rather
	than remembered at every call site.

	A Dynamic Link brings a second field with it. Its target doctype is not on
	the field — it is in whatever other field `options` names — so fetching the
	link without its companion gives a column of ids and no way to say what any
	of them is. Asked for even when that companion is not itself a column,
	because whether somebody chose to *look* at the type field has nothing to do
	with whether the link beside it can be resolved.
	"""
	wanted = [
		c["fieldname"] for c in columns
		if c["fieldname"] != META_COLUMN
		# A child table is rows in another table, so asking the database for it
		# by name is a `SQL syntax` error rather than an empty cell — the same
		# reason `__activity` is filtered here. Its rows are fetched separately,
		# by `_with_children`.
		and c["fieldtype"] not in ("Table", "Table MultiSelect")
		# An Attachment Gallery holds nothing at all; there is no column behind
		# it to select.
		and c["fieldtype"] != "Attachment Gallery"
	]
	wanted += [
		c["depends_on_field"] for c in columns
		if c["fieldtype"] == "Dynamic Link" and c.get("depends_on_field")
	]
	# Fields something else on the screen needs, whether or not anybody is
	# looking at that column: where the record stands, and whatever a board is
	# making columns of. A reader who dropped the status column from the list
	# has not stopped a board from being made of it — the same rule a Dynamic
	# Link's companion field already had. Each is validated before it gets
	# here, by `_status_field` and by `_board`.
	wanted += [one for one in always if one]
	return list(dict.fromkeys(wanted + list(ALWAYS)))


def _offerable(meta, keep=()) -> list[str]:
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
	* **Layout stays out**: it carries no value anywhere.

	Child tables are offered here and kept off the *list* by `list_ok` on the
	column rather than by being absent — a Table is rows, which is a real thing
	to render on a record and nothing at all in a cell. They used to be excluded
	outright, which is why `Table MultiSelect` was mapped to a control nobody
	could ever reach: `_placed` intersects the manifest with what is offered,
	so a screen naming one got nothing.
	* **`hidden` is honoured.** A field the doctype hides holds plumbing nobody
	  should be asked about — Frappe hides these for presentation, not for
	  secrecy, so this is not a permission fix. It was still wrong: `hidden` was
	  checked on the quick-create form (`_quick_entry`) and nowhere else, which
	  put every hidden field of a busy doctype into the column picker, the list
	  and the record form.

	`keep` is the one exception, and it names the manifest's own field list. A
	space declaring a hidden field is a considered choice about a doctype we do
	not own, made in code we wrote — so the picker narrows and an explicit
	intent still stands.
	"""
	allowed = set(meta.get_permlevel_access("read") or [0])
	keep = set(keep or ())

	return [
		df.fieldname
		for df in meta.fields
		if df.fieldname not in HIDDEN
		and not fieldtypes.is_layout(df.fieldtype)
		and (df.permlevel or 0) in allowed
		and (not getattr(df, "hidden", 0) or df.fieldname in keep)
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


# The other column that is not a field. `_user_tags` is a real column on the
# doctype's own table — Frappe adds it the first time anything on that doctype
# is tagged — so once it exists it filters, sorts and pages like any other, and
# a tag is a first-class way to find a record rather than a decoration on one.
#
# Offered only where the column exists, because a filter on a column that is
# not there is a SQL error rather than an empty list. The first tag on a
# doctype creates it.
TAGS_COLUMN = "_user_tags"


def _tags_column() -> dict:
	return {
		"fieldname": TAGS_COLUMN,
		"label": _("Tags"),
		"fieldtype": "Data",
		"options": None,
		"cell": "tags",
		"icon": "lucide-tag",
		"editable": False,
		"read_only": 1,
		"width": 200,
	}


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


# What the record form is laid out as, when the doctype says nothing: one tab,
# one section, every field in it.
DEFAULT_TAB = "Details"


def _form(meta, offered: dict) -> list[dict]:
	"""The doctype's own form, as tabs and sections.

	Frappe's desk reads `Tab Break` and `Section Break` out of the field list
	and lays the form out with them; a record here reads the same two, so a
	doctype whose author grouped its fields is grouped the same way in OneSpace
	without a manifest repeating any of it. A doctype that groups nothing gets
	one tab called Details, which is what the desk does too.

	Fieldnames rather than the columns themselves: the spec already carries
	every column once in `all_columns`, and a form that repeated them would
	send a sixty-field doctype twice.
	"""
	tabs: list[dict] = []
	section: dict | None = None

	def start_tab(label: str) -> None:
		nonlocal section
		tabs.append({"key": f"t{len(tabs)}", "label": label or DEFAULT_TAB, "sections": []})
		section = None

	def start_section(label: str, df=None) -> None:
		nonlocal section
		if not tabs:
			start_tab(DEFAULT_TAB)
		section = {
			"label": label or "",
			"columns": [[]],
			# The doctype's own answer to "does this start folded". Frappe's
			# `collapsible_depends_on` is the same expression dialect as
			# `depends_on`, so the browser reads it with the same parser.
			"collapsible": int(getattr(df, "collapsible", 0) or 0) if df else 0,
			"collapsible_depends_on": (
				getattr(df, "collapsible_depends_on", None) or None if df else None
			),
			# A section that draws no rule above it. Presentation, and the one
			# thing that makes a two-section form read as one.
			"hide_border": int(getattr(df, "hide_border", 0) or 0) if df else 0,
		}
		tabs[-1]["sections"].append(section)

	def start_column() -> None:
		if section is None:
			start_section("")
		section["columns"].append([])

	for df in meta.fields:
		if df.fieldtype == "Tab Break":
			start_tab(_(df.label) if df.label else DEFAULT_TAB)
		elif df.fieldtype == "Section Break":
			# A new section, opened lazily: a doctype that starts with three
			# section breaks in a row should produce one section, not three
			# empty ones.
			start_section(_(df.label) if df.label else "", df)
		elif df.fieldtype == "Column Break":
			# The third of Frappe's three layout fields, and the one this used
			# to drop — so a doctype whose author put four fields in two
			# columns got one tall column of four.
			start_column()
		elif df.fieldname in offered:
			if section is None:
				start_section("")
			section["columns"][-1].append(df.fieldname)

	# Layout with nothing in it is not layout. A tab break before fields this
	# screen does not offer leaves a tab nobody can open; an empty section
	# leaves a heading over nothing; and an empty column leaves a gap the width
	# of the fields that are not there — which is what a trailing column break
	# on a doctype whose last fields are read-only would draw.
	for tab in tabs:
		for one in tab["sections"]:
			one["columns"] = [column for column in one["columns"] if column]
		tab["sections"] = [one for one in tab["sections"] if one["columns"]]
	return [tab for tab in tabs if tab["sections"]]


def _status_field(screen: dict, offered: dict) -> str:
	"""The field whose value goes on the badge beside a record's name.

	Named in the manifest and checked here, so a screen over Contact does not
	badge a field Contact does not have. Empty where the manifest says nothing,
	which is most screens: a record with no status is a record with no badge
	rather than one with an empty one.
	"""
	asked = (screen.get("status_field") or "").strip()
	return asked if asked in offered else ""


def _json(raw):
	if not raw:
		return {}
	try:
		value = json.loads(raw)
	except (TypeError, ValueError):
		return {}
	return value if isinstance(value, dict) else {}


def _filter_rows(raw, target: str) -> list:
	"""`link_filters` off a docfield, as filter rows Frappe will accept.

	Frappe stores this as a JSON *array* of `[doctype, fieldname, operator,
	value]` rows — the shape its own link query and its Attachment Gallery both
	read. It was being parsed with `_json`, which answers `{}` for anything that
	is not an object, so every `link_filters` on the site silently narrowed
	nothing: a picker that should have offered active customers offered all of
	them, with no error anywhere to say so.

	Two rows are dropped rather than obeyed:

	* one naming a doctype other than the target, which is a join nobody asked
	  for and the same refusal Frappe makes for a gallery
	* one whose value is `eval:` — the desk runs that as JavaScript against the
	  record, and we do not run expressions (see `lib/rules.js`). A filter we
	  cannot evaluate narrows nothing rather than being guessed at.
	"""
	if not raw:
		return []
	try:
		rows = json.loads(raw) if isinstance(raw, str) else raw
	except (TypeError, ValueError):
		return []
	if not isinstance(rows, list):
		return []

	kept = []
	for row in rows:
		if not isinstance(row, (list, tuple)) or len(row) != 4:
			continue
		doctype, fieldname, operator, value = row
		if doctype != target:
			frappe.throw(
				_("A filter on {0} may only narrow {0}.").format(target),
				frappe.PermissionError,
			)
		if isinstance(value, str) and value.startswith("eval:"):
			continue
		kept.append([doctype, fieldname, operator, value])
	return kept


# A page of records. Large enough that most screens never ask for more, small
# enough that a doctype with a hundred thousand rows does not arrive. The
# reader can change it — the footer offers PAGE_SIZES and remembers the choice
# in their screen — and MAX_PAGE is the ceiling whatever they ask for.
PAGE = 100


MAX_PAGE = 500


PAGE_SIZES = (20, 50, 100, 500)


# What every list carries beside its columns: when a row last changed, how many
# comments are on it, who liked it, and who it is on. Frappe keeps all four on
# the document, so reading them costs no extra query — resolving `_assign`'s
# ids into faces costs one for the whole page, in `_with_people`.
# `_user_tags` rides with them and is *not* consumed by `_with_meta`: it stays
# on the row under its own name, because it is a column like any other when
# somebody has added it to the list — and it is on every row regardless, so a
# card can show a record's tags without the reader having gone to the picker
# first. Frappe's `db_query` drops it from the field list on a doctype whose
# table has no such column, so asking for it is always safe.
# `docstatus` rides along for the reason `RECORD_META` carries it below, one
# surface over: a report's cells are typed into in place, and a table that does
# not know a row is submitted offers an edit the server will refuse. It is
# fetched and never a column — `HIDDEN` keeps it out of the picker, because a
# customer reading a docstatus is always an accident.
META_FIELDS = (
	"modified", "_comments", "_liked_by", "_assign", "_user_tags", "docstatus",
)


# Read for a record and never for a row. Who made it and who last touched it is
# the question every desk sidebar answers, and it is the one thing on a record
# that no field carries.
#
# `docstatus` rides along for a different reason: on a submittable doctype a
# submitted record is editable only in the fields marked `allow_on_submit`, and
# a form that does not know it is looking at one offers every field and has
# every save refused.
RECORD_META = ("owner", "creation", "modified_by", "docstatus")
