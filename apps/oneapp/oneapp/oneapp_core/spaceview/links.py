"""Link fields: searching a target doctype, and creating into one.

A Link is a foreign key, and a text box over one asks a customer to know a
record's name. frappe-ui ships a Combobox; what it needs is something to
search, and that has to be bounded the same way everything else here is.
"""

import frappe
from frappe import _
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
from .meta import HIDDEN, _columns, _filter_rows
from .resolve import _granted_doctypes, _resolve, _space


LINK_PAGE = 20


@frappe.whitelist(methods=["GET"])
def link_options(space_code: str, screen: str, fieldname: str, query: str = "",
                 target: str | None = None) -> list:
	"""Records a Link field may point at.

	Bounded by the screen, like every other read: the field has to be one the
	screen shows, and the doctype it points at has to be readable by this user.
	Frappe's own permissions do the second part — `get_list` returns nothing
	rather than raising, which is the right shape for a picker.

	`target` is only read for a Dynamic Link, whose doctype lives on the record
	rather than on the field. It is validated in `_link_target` against the
	space's own grant and this user's permissions before anything is fetched,
	and ignored entirely for a plain Link — a client cannot redirect one of
	those by asking.
	"""
	resolved = _resolve(space_code, screen)
	column = _link_column(resolved, fieldname)
	target = _link_target(resolved, column, target)
	if not target or not frappe.db.exists("DocType", target):
		return []

	meta = frappe.get_meta(target)
	shape = _link_shape(meta)
	fields = ["name"] + [f for f in (shape["title"], shape["image"]) if f]
	# The doctype's own search fields, which is what the desk shows under a
	# result: "Contact" without "the one at Halloway" is not a choice anybody
	# can make between two people called Chris.
	extra = [f for f in shape["search"] if f not in fields]

	filters = _filter_rows(column.get("link_filters"), target)
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
def link_new_spec(space_code: str, screen: str, fieldname: str,
                  target: str | None = None) -> dict:
	"""What creating a record for a Link field would ask for.

	Frappe's quick entry, in our vocabulary: the fields a doctype marks
	`allow_in_quick_entry`, plus anything mandatory, because a form that omits a
	required field is a form that cannot be submitted.

	Refused unless the target is a doctype this space granted *and* this user
	may create. The first is the rule that makes a screen an allowlist; the
	second is Frappe's.
	"""
	resolved = _resolve(space_code, screen)
	target = _link_target(resolved, _link_column(resolved, fieldname), target)
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
def link_new(space_code: str, screen: str, fieldname: str, values: str | dict,
             target: str | None = None) -> dict:
	"""Create one record for a Link field, and hand back the row to show.

	Bounded the same way the picker is, and then again by Frappe: only fields
	the quick form offered are written, so a payload naming something else
	writes nothing rather than being refused — the same rule `save` follows for
	the screen's own doctype.
	"""
	resolved = _resolve(space_code, screen)
	target = _link_target(resolved, _link_column(resolved, fieldname), target)
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
		frappe.throw(_("Those changes could not be read."))

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
def link_preview(space_code: str, screen: str, fieldname: str, name: str,
                 target: str | None = None) -> dict:
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
	target = _link_target(resolved, _link_column(resolved, fieldname), target)
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

	And inside its child tables, which is the same argument one level down and
	was missing entirely: an invoice's lines are a grid of the child doctype's
	own fields, `item_code` among them, and `item_code` is not a field on Sales
	Invoice. So every Link inside every grid in the product answered 403 —
	shipped, rendered, and never once able to open. The child fields come from
	`_child`, so they have been through `_columns` like the parent's: permlevel,
	bounds and `link_filters` all apply, and a field the child doctype hides is
	not offered here either.

	Parent first, then the tables in the order the screen offers them. Two child
	tables on one doctype can share a fieldname — a Sales Invoice has
	`item_code` on both `items` and `packed_items` — and the fix for that is the
	browser saying which grid is asking. In ERPNext the two always point at the
	same doctype, so the picker is right either way; `docs/ONESPACE.md` carries
	it as the gap it is.
	"""
	offered = resolved.get("all_columns") or resolved.get("columns") or []
	column = next((c for c in offered if c["fieldname"] == fieldname), None)
	if not column:
		for table in offered:
			child = table.get("child")
			if not child:
				continue
			column = next(
				(c for c in child["fields"] if c["fieldname"] == fieldname), None
			)
			if column:
				break
	if not column:
		frappe.throw(_("{0} is not on this screen.").format(fieldname),
		             frappe.PermissionError)
	return column


def _link_target(resolved: dict, column: dict, target: str | None = None) -> str | None:
	"""Which doctype a Link points at.

	A Link says so in `options`. A Dynamic Link names *another field* that holds
	the answer, so the doctype is not a property of the field at all — it is a
	property of the record being edited, and only the form holds that. So the
	browser sends it, and this decides whether to believe it.

	It is checked rather than trusted, and the check is the whole feature. A
	Dynamic Link is a pointer to an arbitrary doctype, so a client naming its
	own target is precisely the widening the screen allowlist exists to stop:

	* it has to be a real doctype
	* it has to be one this space's manifest granted
	* Frappe has to agree this user may read it

	Fail any of those and the answer is None, which every caller renders as an
	empty picker — the same thing an unreadable target has always produced.
	"""
	if column["fieldtype"] == "Link":
		return column.get("options")

	if column["fieldtype"] != "Dynamic Link":
		return None

	target = (target or "").strip()
	if not target or not frappe.db.exists("DocType", target):
		return None
	if target not in _granted_doctypes(_space(resolved["space"])):
		return None
	if not frappe.has_permission(target, "read"):
		return None
	return target


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
