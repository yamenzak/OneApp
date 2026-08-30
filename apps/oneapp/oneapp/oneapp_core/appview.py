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
			"editable": df.fieldtype in EDITABLE_TYPES and not df.read_only,
		})

	return columns


def _default_fields(meta) -> list[str]:
	"""What to show when an app named nothing.

	The doctype's own list fields first, then its title, then whatever the first
	few non-hidden data fields are. An app that declares no columns still gets a
	list worth looking at.
	"""
	listed = [df.fieldname for df in meta.fields if df.in_list_view]
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
		# What to ask the database for: the columns, plus the identity that is
		# never one.
		"fields": list(dict.fromkeys([c["fieldname"] for c in columns] + list(ALWAYS))),
		"filters": _json(chosen.get("filters")),
		"order_by": chosen.get("order_by") or "modified desc",
		"title_field": meta.title_field or "name",
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
	return _resolve(app_code, view)


@frappe.whitelist(methods=["GET"])
def rows(app_code: str, view: str | None = None, limit: int = PAGE,
         start: int = 0) -> dict:
	"""The records a screen lists, and whether there are more of them."""
	resolved = _resolve(app_code, view)
	if not resolved.get("doctype"):
		return {"rows": [], "has_more": False}

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

	return {"rows": found[:limit], "has_more": len(found) > limit}


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
