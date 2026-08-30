"""Resolving an app's declared screen against this site's own metadata.

An app declares a view as little more than a doctype and a list of fieldnames.
Everything a screen actually needs to render — what each field is called, what
type it is, what a Select offers, whether this user may create or edit — comes
from the tenant site, because that is where the doctype and the permissions
live. The control plane could not know any of it without keeping a copy that
would be wrong the first time a field changed.

Two rules make it safe to hand a customer:

  * **The manifest is the allowlist, twice over.** A view can only be reached
    through an app the workspace is entitled to, and can only name a doctype
    that app's permission manifest already granted. So a view is not a way to
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


def _app(app_code: str) -> dict:
	"""The app, if this workspace is entitled to it."""
	from oneapp.oneapp_core import sync

	for app in sync.state().get("apps") or []:
		if app.get("app_code") == app_code:
			return app
	frappe.throw(_("No app named {0} is enabled here.").format(app_code),
	             frappe.PermissionError)


def _granted_doctypes(app: dict) -> set[str]:
	"""What this app's manifest actually granted, by role.

	Read back off the permissions we wrote rather than from the manifest we were
	sent: those are the rows that decide the answer, and a view pointing at
	something outside them would fail at the first query anyway.
	"""
	role = app.get("role_name")
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
			# A field the app named and this site does not have. Skipped rather
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
		})

	return columns


def _default_fields(meta) -> list[str]:
	"""What to show when an app named nothing.

	The doctype's own list fields first, then its title, then whatever the first
	few non-hidden data fields are. An app that declares no columns still gets a
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
	the desk reads it. Carrying it here means an app inherits a title, an image
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


def _resolve(app_code: str, view: str | None = None) -> dict:
	"""Everything OneSpace needs to render one screen."""
	app = _app(app_code)
	views = app.get("views") or []

	if not views:
		return {"app": app_code, "label": app.get("app_label"), "views": [], "view": None}

	chosen = next((v for v in views if v.get("view") == view), views[0])

	resolved = {
		"app": app_code,
		"label": app.get("app_label"),
		"views": [{"view": v["view"], "label": v["label"], "icon": v.get("icon")}
		          for v in views],
		"view": chosen["view"],
		"view_label": chosen["label"],
		# The escape hatch. The SPA has a component registered under this name;
		# nothing below applies to it.
		"component": chosen.get("component") or None,
	}

	if resolved["component"]:
		return resolved

	doctype = chosen.get("document_type")
	if not doctype:
		resolved["error"] = _("This screen names neither a doctype nor a component.")
		return resolved

	if doctype not in _granted_doctypes(app):
		# A view outside the app's own grant. Refused here rather than left to
		# fail as an empty list, which reads like there is no data.
		frappe.throw(
			_("{0} is not part of {1}.").format(doctype, app.get("app_label")),
			frappe.PermissionError,
		)

	if not frappe.db.exists("DocType", doctype):
		resolved["error"] = _("{0} is not installed on this workspace.").format(doctype)
		return resolved

	meta = frappe.get_meta(doctype)
	wanted = [f.strip() for f in (chosen.get("fields") or "").split(",") if f.strip()]
	wanted = list(dict.fromkeys(wanted or _default_fields(meta)))
	columns = _columns(meta, wanted)

	resolved.update({
		"doctype": doctype,
		"columns": columns,
		**presentation(meta),
		# What to ask the database for: the columns, plus the identity that is
		# never one.
		"fields": list(dict.fromkeys([c["fieldname"] for c in columns] + list(ALWAYS))),
		"filters": _json(chosen.get("filters")),
		"order_by": chosen.get("order_by") or _default_order(meta),
		"can_create": bool(frappe.has_permission(doctype, "create")),
		"can_write": bool(frappe.has_permission(doctype, "write")),
		"can_delete": bool(frappe.has_permission(doctype, "delete")),
	})
	return resolved


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
# Reads and writes go through the view rather than through a generic document
# API, and that is the point rather than a formality: the view says which
# doctype and which fields, so a screen cannot be used to read a doctype the
# entitlement did not include or to write a field it does not show. Frappe's own
# permissions still decide whether any of it is allowed — this only bounds what
# is asked for.
# --------------------------------------------------------------------------- #

# A page of records. Large enough that most screens never scroll for more,
# small enough that a doctype with a hundred thousand rows does not arrive.
PAGE = 100


@frappe.whitelist(methods=["GET"])
def spec(app_code: str, view: str | None = None) -> dict:
	return _apply_saved(_resolve(app_code, view))


@frappe.whitelist(methods=["GET"])
def rows(app_code: str, view: str | None = None, limit: int = PAGE,
         start: int = 0, overrides: str | dict | None = None) -> dict:
	"""The records a screen lists, and whether there are more of them.

	`overrides` is a filter or sort someone has changed but not saved. Folded in
	the same way a saved view is — narrowing only, and through the same checks —
	so an unsaved change cannot reach further than a saved one.
	"""
	# Through the saved view as well, or the columns and the rows disagree about
	# which fields exist and every cell reads empty.
	resolved = _apply_saved(_resolve(app_code, view))
	resolved = _apply_overrides(resolved, overrides)
	if not resolved.get("doctype"):
		return {"rows": [], "has_more": False, "columns": [], "order_by": ""}

	limit = min(int(limit or PAGE), 500)

	# One more than asked for, so "there are more" needs no second count query.
	found = frappe.get_list(
		resolved["doctype"],
		fields=resolved["fields"],
		filters=resolved["filters"],
		order_by=resolved["order_by"],
		limit_start=int(start or 0),
		limit_page_length=limit + 1,
	)

	# The columns come back with the rows, not only from `spec`. An unsaved
	# change to the column list narrows what is fetched, and a header list that
	# does not follow leaves a column standing over empty cells.
	return {
		"rows": found[:limit],
		"has_more": len(found) > limit,
		"columns": resolved["columns"],
		"order_by": resolved["order_by"],
	}


def _writable(resolved: dict) -> set[str]:
	return {c["fieldname"] for c in resolved["columns"] if c.get("editable")}


@frappe.whitelist(methods=["POST"])
def save(app_code: str, view: str, values: str | dict, name: str | None = None) -> dict:
	"""Create or update one record, within what the screen declares."""
	resolved = _resolve(app_code, view)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has nothing to save."))

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Expected an object of values."))

	# The allowlist is the screen. A field the view does not show is not a field
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
def remove(app_code: str, view: str, name: str) -> dict:
	resolved = _resolve(app_code, view)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has nothing to delete."))

	frappe.delete_doc(doctype, name)
	return {"ok": True}


# --------------------------------------------------------------------------- #
# Link fields
#
# A Link is a foreign key, and a text box over one asks a customer to know a
# record's name. frappe-ui ships a Combobox; what it needs is something to
# search, and that has to be bounded the same way everything else here is.
# --------------------------------------------------------------------------- #

LINK_PAGE = 20


@frappe.whitelist(methods=["GET"])
def link_options(app_code: str, view: str, fieldname: str, query: str = "") -> list:
	"""Records a Link field may point at.

	Bounded by the screen, like every other read: the field has to be one the
	view shows, and the doctype it points at has to be readable by this user.
	Frappe's own permissions do the second part — `get_list` returns nothing
	rather than raising, which is the right shape for a picker.
	"""
	resolved = _resolve(app_code, view)
	column = next((c for c in resolved.get("columns") or []
	               if c["fieldname"] == fieldname), None)
	if not column:
		frappe.throw(_("{0} is not on this screen.").format(fieldname),
		             frappe.PermissionError)

	target = _link_target(resolved, column)
	if not target or not frappe.db.exists("DocType", target):
		return []

	meta = frappe.get_meta(target)
	title = meta.title_field if meta.title_field and meta.show_title_field_in_link else None
	fields = ["name"] + ([title] if title else [])

	filters = _json(column.get("link_filters"))
	found = frappe.get_list(
		target,
		fields=fields,
		filters=filters,
		or_filters=_search(meta, query, title) if query else None,
		limit_page_length=LINK_PAGE,
		order_by="modified desc",
	)

	return [
		{
			"value": row["name"],
			# What a person recognises, falling back to the id when a doctype
			# has no title — which is most of them.
			"label": (row.get(title) if title else None) or row["name"],
			"description": row["name"] if title and row.get(title) else None,
		}
		for row in found
	]


def _link_target(resolved: dict, column: dict) -> str | None:
	"""Which doctype a Link points at.

	A Link says so in `options`. A Dynamic Link names another field that holds
	the answer, so it can only be resolved against a record — which the picker
	does not have, so it is refused rather than guessed at.
	"""
	if column["fieldtype"] == "Link":
		return column.get("options")
	return None


def _search(meta, query: str, title: str | None) -> list:
	"""Match the id or the title. `like` rather than a full-text search: this is
	a twenty-row picker, not a search page."""
	term = f"%{query}%"
	clauses = [["name", "like", term]]
	if title:
		clauses.append([title, "like", term])
	return clauses


# --------------------------------------------------------------------------- #
# What surrounds a record
#
# Comments, the change log, who liked it. All of it is Frappe's own, on every
# doctype, and none of it needs an app to ask for it.
# --------------------------------------------------------------------------- #

TIMELINE_PAGE = 50


@frappe.whitelist(methods=["GET"])
def timeline(app_code: str, view: str, name: str) -> dict:
	"""A record's comments and its history, newest first."""
	resolved = _resolve(app_code, view)
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
		"changes": changes,
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
def comment(app_code: str, view: str, name: str, content: str) -> dict:
	resolved = _resolve(app_code, view)
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
def toggle_like(app_code: str, view: str, name: str) -> dict:
	"""Frappe keeps likes in `_liked_by` on the document itself."""
	resolved = _resolve(app_code, view)
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
# Saved views
#
# What Frappe calls a List View Setting: the filters, the sort and the columns
# one person settled on, restored when they come back. Per screen rather than
# per doctype, because two screens over one doctype are two questions.
#
# A saved view narrows; it never widens. Its columns are intersected with the
# screen's, and its filters are applied on top of the screen's rather than
# instead of them — so a person cannot save their way to a column the app did
# not offer or a row the screen filtered out.
# --------------------------------------------------------------------------- #

def _saved(app_code: str, view: str):
	return frappe.db.get_value(
		"OneApp Saved View",
		{"user": frappe.session.user, "app_code": app_code, "view": view,
		 "is_default": 1},
		["name", "filters", "order_by", "columns", "page_length"],
		as_dict=True,
	)


def _apply_saved(resolved: dict) -> dict:
	"""Fold this person's saved answers into a resolved screen."""
	saved = _saved(resolved["app"], resolved["view"])
	resolved["saved"] = None
	# What the screen offers, before this person narrowed it. The column picker
	# needs the full set or it can only ever remove.
	resolved["all_columns"] = list(resolved.get("columns") or [])
	if not saved or not resolved.get("doctype"):
		return resolved

	offered = {c["fieldname"]: c for c in resolved["columns"]}
	chosen = [f.strip() for f in (saved.get("columns") or "").split(",") if f.strip()]
	# Intersected, not substituted: a saved column list that names something the
	# screen no longer offers quietly drops it rather than reintroducing it.
	kept = [offered[f] for f in chosen if f in offered]
	if kept:
		resolved["columns"] = kept
		resolved["fields"] = list(dict.fromkeys(
			[c["fieldname"] for c in kept] + list(ALWAYS)))

	# Bounded again on the way out, not only when it was saved: the row is a
	# doctype an operator can write, and a filter that reached the table another
	# way is still a filter this screen never offered.
	asked = _asked_filters(offered, _json(saved.get("filters")))
	if asked:
		# The screen's filters win on a clash. Theirs narrow within ours.
		resolved["filters"] = {**_as_query_filters(offered, asked), **resolved["filters"]}

	if saved.get("order_by"):
		resolved["order_by"] = _safe_order(resolved, saved["order_by"])

	resolved["saved"] = {
		"filters": asked,
		"order_by": saved.get("order_by") or "",
		"columns": chosen,
		"page_length": saved.get("page_length") or 0,
	}
	return resolved


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


def _asked_filters(offered: dict, extra) -> dict:
	"""What someone asked to filter by, reduced to something a screen may ask.

	Two separate bounds, and both matter:

	* **Only fields the screen shows.** A filter on a hidden field narrows the
	  list, which sounds harmless — but a customer who can watch which rows come
	  back can read a field they were never shown, one guess at a time.
	* **Only a value, never an operator.** Frappe's filter syntax lets a value
	  be `["like", …]`, `["in", […]]`, `["descendants of", …]`. Passing one
	  through hands the query layer a question the screen never granted, so
	  anything that is not a plain scalar is dropped rather than reinterpreted.

	This is the form that gets stored and echoed back to the controls: the words
	someone typed, not the query they turn into.
	"""
	if isinstance(extra, str):
		extra = frappe.parse_json(extra or "null")
	if not isinstance(extra, dict):
		return {}

	return {
		fieldname: value
		for fieldname, value in extra.items()
		if fieldname in offered
		and value not in ("", None)
		and not isinstance(value, (list, tuple, dict))
	}


def _as_query_filters(offered: dict, asked: dict) -> dict:
	"""The same filters, as a question the query layer can be asked.

	A choice matches exactly; anything else is a contains match, because a
	customer typing into a box labelled "Contains…" means contains.
	"""
	return {
		fieldname: (value if offered[fieldname]["fieldtype"] in ("Select", "Link", "Check")
		            else ["like", f"%{value}%"])
		for fieldname, value in asked.items()
	}


def _apply_overrides(resolved: dict, overrides) -> dict:
	"""Fold in what the controls are currently asking for."""
	if isinstance(overrides, str):
		overrides = frappe.parse_json(overrides or "null")
	if not overrides or not resolved.get("doctype"):
		return resolved

	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or resolved["columns"]}

	chosen = [f for f in (overrides.get("columns") or []) if f in offered]
	if chosen:
		resolved["columns"] = [offered[f] for f in chosen]
		resolved["fields"] = list(dict.fromkeys(chosen + list(ALWAYS)))

	asked = _asked_filters(offered, overrides.get("filters"))
	if asked:
		# The screen's own filters still win: theirs narrow within ours.
		resolved["filters"] = {**_as_query_filters(offered, asked), **resolved["filters"]}

	if overrides.get("order_by"):
		resolved["order_by"] = _safe_order(resolved, overrides["order_by"])

	return resolved


@frappe.whitelist(methods=["POST"])
def save_view(app_code: str, view: str, filters: str | dict | None = None,
              order_by: str | None = None, columns: str | list | None = None,
              page_length: int = 0) -> dict:
	"""Remember how this person likes this screen."""
	resolved = _resolve(app_code, view)
	if not resolved.get("doctype"):
		frappe.throw(_("There is nothing to save a view for here."))

	if isinstance(columns, str):
		columns = [f.strip() for f in columns.split(",") if f.strip()]

	offered = {c["fieldname"]: c for c in resolved["columns"]}
	columns = [f for f in (columns or []) if f in offered]
	filters = _asked_filters(offered, filters)

	existing = _saved(app_code, view)
	doc = (frappe.get_doc("OneApp Saved View", existing["name"]) if existing
	       else frappe.new_doc("OneApp Saved View"))

	doc.update({
		"user": frappe.session.user,
		"app_code": app_code,
		"view": view,
		"is_default": 1,
		"filters": json.dumps(filters),
		"order_by": _safe_order(resolved, order_by or "") if order_by else "",
		"columns": ",".join(columns),
		"page_length": int(page_length or 0),
	})
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def reset_view(app_code: str, view: str) -> dict:
	"""Back to what the screen declares."""
	existing = _saved(app_code, view)
	if existing:
		frappe.delete_doc("OneApp Saved View", existing["name"], ignore_permissions=True)
		frappe.db.commit()
	return {"ok": True}
