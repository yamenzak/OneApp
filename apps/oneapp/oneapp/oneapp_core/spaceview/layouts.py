"""Writing a saved view: creating, renaming, hiding, resetting."""

import frappe
import json
from frappe import _
from .meta import _placed
from .filters import _asked_filters, _filterable, _group_by, _page_length, _safe_order
from .saved import _can_share, _layouts, _of_type, _saved, _view_icon
from .views import _view_settings
from .resolve import _resolve, _space


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

	doc = _layout_doc(space_code, screen, layout, label, resolved["view_type"])
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
		#
		# Settled when the row is made and never rewritten. A view *belongs* to
		# a view type — renaming one, or sharing it, is not a decision to move
		# it, and those writes carry no view type of their own. Before this, a
		# rename re-filed the view under whatever the screen happened to open
		# with, which for a board view meant it vanished from the board.
		"view_type": doc.view_type or resolved["view_type"],
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


def _layout_doc(space_code: str, screen: str, layout: str | None, label: str | None,
                view_type: str | None = None):
	"""The row a save lands on — an existing one, or a new one."""
	if layout:
		doc = frappe.get_doc("OneSpace Saved View", layout)
		if (doc.space_code, doc.screen) != (space_code, screen):
			# A layout belongs to one screen. Naming another screen's row would
			# otherwise move it, silently, out from under whoever saved it.
			frappe.throw(_("That view belongs to a different screen."), frappe.PermissionError)
		return doc
	if not label:
		existing = _saved(space_code, screen, view_type)
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
	"""One default per person per screen per view type, and one shared each.

	Per view type because a default is "what this screen opens with", and a
	screen opens differently as a list and as a board. Without it, marking a
	board view the default un-marked the list's — so the list went back to the
	manifest's answer because somebody had chosen a favourite board.
	"""
	siblings = frappe.get_all(
		"OneSpace Saved View",
		filters={"space_code": doc.space_code, "screen": doc.screen,
		         "user": doc.user or ["in", ["", None]], "is_default": 1,
		         "view_type": _of_type(doc.view_type)},
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
		frappe.throw(_("That view belongs to a different screen."), frappe.PermissionError)
	_may_write(doc)
	frappe.delete_doc("OneSpace Saved View", doc.name, ignore_permissions=True)
	# Whoever had hidden it is no longer hiding anything. Swept here rather
	# than left to point at nothing: a stale row would be counted as a view
	# waiting to be brought back, and bringing it back would produce nothing.
	frappe.db.delete("OneSpace Hidden View", {"layout": doc.name})
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def hide_layout(space_code: str, screen: str, layout: str) -> dict:
	"""Take a shared view out of this person's own menu.

	Not a delete, and never offered as one: a shared view belongs to the
	workspace and somebody else may be living in it. This says only that one
	reader would rather not see it — the row is theirs, and `show_layouts`
	takes it back.

	A view of your own is not hideable. You made it; delete it.
	"""
	doc = frappe.get_doc("OneSpace Saved View", layout)
	if (doc.space_code, doc.screen) != (space_code, screen):
		frappe.throw(_("That view belongs to a different screen."), frappe.PermissionError)
	if doc.user:
		frappe.throw(_("That view is yours — delete it rather than hiding it."))
	if not frappe.db.exists("OneSpace Hidden View",
	                        {"user": frappe.session.user, "layout": layout}):
		frappe.get_doc({
			"doctype": "OneSpace Hidden View", "user": frappe.session.user,
			"space_code": space_code, "screen": screen, "layout": layout,
		}).insert(ignore_permissions=True)
		frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def show_layouts(space_code: str, screen: str) -> dict:
	"""Bring back every shared view this person hid on this screen.

	All of them at once rather than one at a time: a hidden view is not in the
	menu, so a menu is the wrong place to pick one out of. What the person
	wants at this point is to see what they turned off.
	"""
	frappe.db.delete("OneSpace Hidden View", {
		"user": frappe.session.user, "space_code": space_code, "screen": screen,
	})
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
		frappe.throw(_("That view belongs to a different screen."), frappe.PermissionError)
	_may_write(doc)
	doc.is_default = 1
	doc.save(ignore_permissions=True)
	_only_default(doc)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def reset_layout(space_code: str, screen: str, view_type: str | None = None) -> dict:
	"""Back to what the screen declares, for the way you are looking at it.

	Only this person's unnamed default, and only this view type's: a named
	layout is a thing somebody made and is deleted deliberately rather than by a
	button that means "undo my tinkering", and the board's tinkering is not the
	list's.
	"""
	existing = _saved(space_code, screen, view_type)
	if existing:
		frappe.delete_doc("OneSpace Saved View", existing["name"], ignore_permissions=True)
		frappe.db.commit()
	return {"ok": True}
