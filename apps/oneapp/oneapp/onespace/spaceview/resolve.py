"""One screen, resolved: which doctype, which columns, which views."""

import frappe
from frappe import _
from oneapp.onespace import (
	collab,
	configuration,
	dashboard,
	docflow,
	fieldtypes,
	mine,
	printing,
	showcase,
)
from .meta import (
	META_COLUMN,
	PAGE,
	PAGE_SIZES,
	_child_columns,
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
	from oneapp.onespace import sync

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


def _refuse_ungranted(space: dict, doctype: str) -> None:
	"""Stop here unless this space grants that doctype to a seat this person has.

	Refused rather than left to fail as an empty list, which reads like there is
	no data.

	Two refusals, because there are two reasons and only one of them is a
	mistake. A screen the space does not grant at all is a manifest that does
	not add up; a screen it grants to a seat this person does not hold is the
	permission model working, and saying "not part of OneHR" about a screen
	sitting in the rail in front of them is the kind of message that costs
	somebody an afternoon.
	"""
	if doctype in _granted_doctypes(space):
		return
	if doctype in _granted_doctypes(space, held=False):
		frappe.throw(
			_("{0} is part of {1}, and not of your role in it.").format(
				doctype, space.get("space_label")),
			frappe.PermissionError,
		)
	frappe.throw(
		_("{0} is not part of {1}.").format(doctype, space.get("space_label")),
		frappe.PermissionError,
	)


def navigable(space: dict) -> list:
	"""The screens of one space that belong in this reader's rail.

	The rail has always listed every screen a space declares, whatever seat you
	hold — so an employee in OneHR saw Payslips and Job Applicants under their
	own headings and was refused both on the way in. The refusal is a good
	sentence now (`_resolve` says "part of OneHR, and not of your role in it")
	but a good sentence about a door that should not have been drawn is still a
	door that should not have been drawn.

	Narrowed here rather than in `visible`, which `_space` also reads: a screen
	missing from the rail must still *refuse* when its link is followed, and
	filtering the space itself would silently resolve an old bookmark to
	whatever screen happened to be first.

	Two things are deliberately kept:

	* A screen with no doctype — a component screen, or one not finished. There
	  is no grant to consult, so there is nothing to hide it by.
	* A screen whose doctype no role in the space grants at all. That is the
	  *other* refusal: a manifest that does not add up, and hiding it would
	  turn a mistake somebody can see into one nobody can. Same reason the
	  resolver keeps the two sentences apart.
	"""
	screens = space.get("screens") or []
	if not screens:
		return screens

	anyone = _granted_doctypes(space, held=False)
	if not anyone:
		# Nothing granted to any of the space's roles — a site whose
		# permissions have never been written. Narrowing against that would
		# empty the rail of a space that works, so it is left alone.
		return screens

	granted = _granted_doctypes(space)
	return [
		one for one in screens
		if (one.get("document_type") or "").strip() not in anyone
		or one["document_type"] in granted
	]


def _space_roles(space: dict) -> list[str]:
	"""Every Frappe role this space's manifest became.

	A space declares *jobs* — a viewer, a planner, a feed manager — and each
	becomes a role named after the space's own: `OneSpace Mobility`, then
	`OneSpace Mobility Planner` beside it. That naming is
	`entitlements.registry.frappe_role_for`, and it is the only thing a tenant
	has to go on: the child table of roles does not travel in the sync payload,
	so the cached space carries the base name and nothing else.

	So the list is read back off the roles that exist, by the convention they
	were written under. Which is the honest shape of it — a role somebody
	deleted is a role this space no longer has.
	"""
	base = (space.get("role_name") or "").strip()
	if not base:
		return []
	return [base] + frappe.get_all(
		"Role", filters={"name": ["like", f"{base} %"]}, pluck="name"
	)


def _granted_doctypes(space: dict, held: bool = True) -> set[str]:
	"""What this space's manifest actually granted.

	Read back off the permissions we wrote rather than from the manifest we were
	sent: those are the rows that decide the answer, and a screen pointing at
	something outside them would fail at the first query anyway.

	`held` narrows it to the roles this person actually has, which is the
	question a screen is asking. Every role in the space is the other question —
	"is this screen part of the space at all" — and the two have different
	answers the moment a space ships more than one job. Until now only the
	*base* role was consulted, so a doctype granted to a named role was granted
	to nobody as far as this was concerned: OneHR's Attendance belongs to the
	people officer, and every seat, that one included, opened the screen and was
	told Attendance is not part of OneHR.
	"""
	roles = _space_roles(space)
	if held:
		theirs = set(frappe.get_roles())
		roles = [one for one in roles if one in theirs]
	if not roles:
		return set()
	return set(frappe.get_all(
		"Custom DocPerm", filters={"role": ["in", roles]}, pluck="parent"
	))


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
		# A component screen may name a doctype, and it means one thing: who
		# this screen is for. There is nothing to resolve — the component
		# fetches what it draws — but `navigable` keeps a screen out of the
		# rail by consulting the grant on its doctype, and a component screen
		# without one is therefore in *everybody's* rail. "Mark the day" is a
		# page for whoever administers attendance, and naming `Attendance` is
		# how it says so. Refused here as well as hidden, or the rail is a
		# suggestion and the URL is the door.
		named = chosen.get("document_type")
		if named:
			_refuse_ungranted(space, named)

		# A component screen is handed its declaration and nothing else — that
		# is what naming one means. The one exception is a Configuration page,
		# whose tabs are *other screens of this space*: resolving those names to
		# the label and glyph each already declares has to happen where the
		# space's screen list is, and doing it here rather than in the browser
		# means a tab cannot end up called something the rail does not call it.
		#
		# Asked only of that one component, and by name. Every space has a
		# Configuration page now — `sync.configured` gives one to any space
		# that did not declare it — and `shape` appends the three panels a
		# space always has, so asking it about `onehr/home` would put an Alerts
		# tab on somebody's employee page.
		if resolved["component"] == configuration.CONFIGURATION:
			found = configuration.shape(
				(resolved.get("view_settings") or {}).get(configuration.CONFIGURATION),
				screens,
				space_code,
			)
			if found:
				resolved[configuration.CONFIGURATION] = found
		return resolved

	doctype = chosen.get("document_type")
	if not doctype:
		resolved["error"] = _("This screen has nothing to show yet.")
		return resolved

	_refuse_ungranted(space, doctype)

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
		# What a filter may name on a child table. Beside `all_columns` rather
		# than in it — see `_child_columns` for why a thing you filter by is
		# not a thing a list can draw.
		"child_columns": _child_columns(offerable),
		"quick_filters": _quick_filters(meta, offerable),
		**presentation(meta),
		# What to ask the database for: the columns that are fields, plus the
		# identity that is never one. Activity is neither.
		# Replaced below, once the board is resolved. Set here so the key exists
		# in the same place as everything else the screen answers with.
		"fields": _fetch_fields(columns, _status_field(chosen, offered)),
		# Narrowed here rather than where they are used, so the list, the
		# board, the calendar, the dashboard widgets and the count all read one
		# answer about whose rows these are — `onespace/mine.py`. A value the
		# site cannot resolve becomes one nothing can equal, never nothing at
		# all: a screen narrowed to a reader nobody can identify has to be
		# empty, and the silent version of that bug shows one person the
		# company's pay.
		"filters": mine.resolve(_json(chosen.get("filters"))),
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
		# Whether these records have a docstatus, and whether a workflow owns
		# the moving of it. Two facts about the *doctype*, so they belong on
		# the screen rather than on every row — a list of forty carries them
		# forty times otherwise, and `_with_state` costs a `get_doc` each.
		#
		# The pair rather than one: a bulk Submit is refused outright where a
		# workflow governs (`docflow._no_workflow`), and a button that fails on
		# every record is worse than no button.
		"submittable": bool(int(getattr(meta, "is_submittable", 0) or 0)),
		"workflow": docflow.workflow_name(doctype) or "",
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


def routes(doctypes) -> dict:
	"""Doctype → the space and screen this reader would open it in.

	The framework's answer to "where does this record live" is a desk form
	URL, which is not a place this product has. Ours is derived rather than
	stored: a Space is a manifest over doctypes, not a Frappe app, and the same
	doctype may be granted to several — so nothing on the record could carry it
	even if every producer set it.

	Resolved against `visible`, which is the same gate the rail and every
	whitelisted read use — so a doctype that comes back with no route is one
	this person has nowhere to open, which is also the answer to "may they be
	offered it": the notification panel draws such a row without a link, and
	mail filing drops the candidate entirely.

	First match wins, in the order the manifest lists them, so a doctype two
	spaces show opens in the one the reader sees first rather than in whichever
	the dictionary happened to hold.
	"""
	from oneapp.onespace import sync

	wanted = {one for one in doctypes if one}
	if not wanted:
		return {}

	found = {}
	for space in visible(sync.state().get("spaces") or []):
		for screen in space.get("screens") or []:
			doctype = screen.get("document_type")
			if doctype in wanted and doctype not in found:
				found[doctype] = {
					"space": space.get("space_code"),
					"screen": screen.get("screen"),
				}
	return found
