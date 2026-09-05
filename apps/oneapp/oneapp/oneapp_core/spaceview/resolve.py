"""One screen, resolved: which doctype, which columns, which views."""

import frappe
from frappe import _
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
from .meta import (
	META_COLUMN,
	PAGE,
	PAGE_SIZES,
	_columns,
	_default_fields,
	_default_order,
	_default_width,
	_fetch_fields,
	_form,
	_json,
	_meta_column,
	_offerable,
	_placed,
	_quick_filters,
	_status_field,
	_tags_column,
	presentation,
)
from .connections import connections
from .viewtypes import _singular, _view_types
from .actions import actions
from .views import _resolve_views, _view_settings


def _space(space_code: str) -> dict:
	"""The space, if this person may open it.

	Two questions, and this used to ask only the first. The site's entitlements
	decide which spaces exist here; the reader's roles decide which of those are
	theirs — and `api.visible_spaces` has always asked both, while this asked
	neither about the reader. So a space code guessed at resolved, and what came
	back was the space's shape: its label, its screens, its navigation.

	Not data — `_granted_doctypes` and Frappe's own permissions still stood
	behind every row, so the answer was an empty list rather than somebody
	else's records. But it is the wrong direction, and it stops being harmless
	the moment two audiences share a site: an operator console and a customer's
	account area on the same control plane, where a customer guessing the
	operator space's code could read its screen list.

	One function, two callers, so the rail and the resolver cannot drift into
	different answers about what a person may open.
	"""
	from oneapp.oneapp_core import sync

	for space in visible(sync.state().get("spaces") or []):
		if space.get("space_code") == space_code:
			return space
	frappe.throw(_("No space named {0} is enabled here.").format(space_code),
	             frappe.PermissionError)


def visible(spaces: list) -> list:
	"""The spaces this reader may open, out of the ones this site has.

	A space with no role is open to everybody on the site, which is what an
	empty `role_name` has always meant — the manifest declares one when it
	wants the space narrowed.
	"""
	roles = set(frappe.get_roles())
	return [s for s in spaces if not s.get("role_name") or s["role_name"] in roles]


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
		# One of these, in the customer's words. See `_singular`.
		"singular": _singular(chosen),
		# How this screen may be looked at, and which of those we are rendering.
		# The first is what it opens with; asking for one it does not offer gets
		# that rather than an error, because a stale link is not a failure.
		"view_types": offered,
		"view_type": view_type if view_type in offered else offered[0],
		# Raw here, validated once the columns are known — see `_board`. A
		# fieldname is only checkable against a field list, and that list is
		# built forty lines below this.
		"view_settings": _json(chosen.get("view_settings")),
		# An icon per tab of the record form, keyed by the tab's label, and an
		# override rather than the answer: every tab already gets a glyph
		# derived from its own words in the browser, because Frappe has no icon
		# property on a Tab Break and a doctype we do not own will never have a
		# manifest entry. Carried verbatim and checked there against the closed
		# set the build emits — a name outside it draws nothing at all, so the
		# derived glyph is the better answer to a typo.
		"tab_icons": _json(chosen.get("tab_icons")),
		# The escape hatch, and the reason the manifest is a shortcut rather
		# than a cage: name a component and none of the rest of this applies.
		"component": chosen.get("component") or None,
		# What this screen can *do* to a record, beyond editing its fields —
		# see the Actions section at the end of this module.
		"actions": actions(space_code, chosen["screen"]),
	}

	if resolved["component"]:
		return resolved

	doctype = chosen.get("document_type")
	if not doctype:
		resolved["error"] = _("This screen has nothing to show yet.")
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
	offerable = [*_columns(meta, _offerable(meta, keep=wanted)), _meta_column()]
	if collab.has_tags_column(meta.name):
		offerable.append(_tags_column())
	offered = {c["fieldname"]: c for c in offerable}
	# What the list may draw, which is not everything the record may show.
	listable = {name: c for name, c in offered.items() if c.get("list_ok", True)}

	# The manifest's list, plus activity at the end. Widths are defaults and
	# nothing is pinned: where a column sticks is a reading preference, and
	# guessing it for somebody is how the meta column ended up glued to an edge
	# nobody asked for.
	columns = _placed(listable, [c["fieldname"] for c in columns] + [META_COLUMN])

	resolved.update({
		"doctype": doctype,
		# The doctype's own name, for the places that are about the doctype
		# rather than about the screen — a print format belongs to `ToDo`
		# whichever screen opened it. Never a heading a customer reads: see
		# `_singular`.
		"doctype_label": _(meta.get("name")),
		"columns": columns,
		# Everything the *record* may show, child tables included.
		"all_columns": [{**c, "width": _default_width(c)} for c in offerable],
		# What the column picker may offer, which is the subset a list can
		# draw. Two lists rather than one flag read in three places: the picker
		# is a list of columns, and handing it fields it must then filter out
		# is how one of them eventually slips through.
		"list_columns": [
			{**c, "width": _default_width(c)} for c in offerable if c.get("list_ok", True)
		],
		"quick_filters": _quick_filters(meta, offerable),
		**presentation(meta),
		# What to ask the database for: the columns that are fields, plus the
		# identity that is never one. Activity is neither.
		# Replaced below, once the board is resolved. Set here so the key exists
		# in the same place as everything else the screen answers with.
		"fields": _fetch_fields(columns, _status_field(chosen, offered)),
		"filters": _json(chosen.get("filters")),
		"order_by": chosen.get("order_by") or _default_order(meta),
		# How many rows a page is, and what the footer may offer instead. The
		# screen's default until a saved view says otherwise.
		"page_length": PAGE,
		"page_sizes": list(PAGE_SIZES),
		# Which field says where a record stands. Checked against the doctype's
		# own fields like a filter or a sort is: it names a fieldname and ends
		# up on a badge, and "an operator typed it into the manifest" has never
		# been a reason to trust one. The colours are not here — they are the
		# doctype's own Document States, read by `presentation` above, so a
		# status is one colour in the list, the badge and the desk alike.
		"status_field": _status_field(chosen, offered),
		# How the record form is laid out — the doctype's own tabs and
		# sections, over every field the record shows. Not only the editable
		# ones: a Color or a Signature is shown and never offered, and dropping
		# it here would take it off the record rather than leaving it read-only.
		# What may be *written* is `_writable`, which is a different question
		# and is asked on the way in.
		"form": _form(meta, {
			c["fieldname"]: c for c in offerable if c["fieldname"] != META_COLUMN
		}),
		# Three answers, and the narrowest wins.
		#
		# The permission is the first, and on its own it was the only one — which
		# is why New sat over the credit ledger, the webhook log and the
		# provisioning queue. `has_permission(create)` is true for all of them:
		# the code that owns those rows writes them through this same
		# permission, so taking it away would break the writer to tidy a button.
		#
		# `in_create` is Frappe's own answer to exactly that — "User Cannot
		# Create", a flag that hides New while leaving the permission intact.
		# The desk reads it in `perm.js` and `toolbar.js`, and now so does this.
		#
		# `hide_new` is the manifest's, and it can only narrow: a screen over a
		# doctype we do not own — ERPNext's, on a tenant site — may still be a
		# reading surface.
		"can_create": (
			bool(frappe.has_permission(doctype, "create"))
			and not int(getattr(meta, "in_create", 0) or 0)
			and not int(chosen.get("hide_new") or 0)
		),
		"can_write": bool(frappe.has_permission(doctype, "write")),
		# Frappe's own `print`, which is a permission like any other and which
		# the manifest's Write and Manage levels both grant. A screen over a
		# doctype nobody may print draws no printer.
		"can_print": bool(frappe.has_permission(doctype, "print")),
		"can_delete": bool(frappe.has_permission(doctype, "delete")),
		# Frappe's own gate, and the whole of it: `allow_rename` on the doctype
		# plus write on the document. A doctype that names its records by hash
		# or by a series says `allow_rename` is off, and the desk hides its
		# rename for the same reason — an id somebody chose is a different kind
		# of thing from an id the framework issued.
		"can_rename": (
			bool(int(getattr(meta, "allow_rename", 0) or 0))
			and bool(frappe.has_permission(doctype, "write"))
		),
	})

	# Now that there are columns to check names against. The screen's own
	# settings are validated here rather than where they were read, and the
	# board is resolved from them; a saved view narrows both again in
	# `_apply_saved`.
	resolved["view_settings"] = _view_settings(resolved, resolved.get("view_settings"))

	# What else in this space is about one of these. Derived from the schema
	# rather than declared, and computed here because it needs the settings
	# above it: a screen the showcase already names as a tab is not repeated.
	resolved["connections"] = connections(
		space,
		chosen["screen"],
		doctype,
		_granted_doctypes(space),
		(resolved["view_settings"].get("showcase") or {}).get("tabs") or [],
	)
	return _resolve_views(resolved)
