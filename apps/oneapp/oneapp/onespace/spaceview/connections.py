"""What else in this space is about this record.

Frappe's Connections — the row of "Quotations 3 · Sales Orders 1 · Invoices 2"
under a Customer — is the largest thing the desk does that this did not. A
record here was the form and its own tabs, so the question a project raises
first ("what has been quoted, ordered, invoiced against it?") had one answer:
go back to the rail, open the invoices screen, and filter it by hand.

**Derived rather than declared.** A screen could have named its related screens,
and one already can — `view_settings.showcase.tabs`, which is how RUA's project
page got its four. But a declaration only exists where somebody wrote one, and
the thing worth having is the one that is simply there: every screen in this
space whose doctype carries a Link field pointing back at this one. Which is
exactly what the desk derives, from the same place.

**Bounded by the space, not by the schema.** Frappe's own `get_linked_doctypes`
answers over the whole site, and half of what it returns is a doctype this
workspace has no screen for and no permission on. A connection that opens
nothing is worse than no connection, so this only ever names screens the space
already has — which also caps the cost at one cached `get_meta` per screen.

Nothing here is a permission boundary. A connection is a screen and a fieldname;
the browser then asks `rows` for that screen with that filter, and `rows` is
where the space, the permissions and the filter are checked. A person who may
not open the invoices screen gets an empty tab, for the same reason they get no
invoices in the rail.
"""

import frappe


# How many a record grows. Past this the strip is a menu, and the rail already
# is one — the same number and the same argument as `showcase.TABS`.
CONNECTIONS = 6


def connections(space: dict, screen: str, doctype: str, granted: set,
                declared=()) -> list[dict]:
	"""The other screens in this space that point back at this one.

	Same shape as a declared showcase tab — `{screen, field, label, icon}` —
	plus `where`, which a Dynamic Link needs and a plain Link leaves empty. One
	component draws both, so there is one thing for a reader to learn.

	A screen the showcase already declares is left out rather than repeated: the
	manifest said it first, said it in its own words, and put it in its own
	order — and so is any other screen that would reach the same doctype by the
	same field.

	So is a **component** screen, whatever doctype it names. Such a screen names
	one to say who it is *for* — `spaceview.resolve`, and OnePeople's "Mark the
	day" — and drawing none of it: a tab that opened a register beside one leave
	application would be a tab pointing at a page that is not about this record
	and cannot be narrowed to it.

	And a doctype is reached **once**. OneTask has three screens over `One Task`
	that all point back through `project` — the work, this person's half of it,
	and the ones on no project at all — and a project record drew all three, two
	of them saying the same thing as the first and one of them ("no project")
	guaranteed empty here. A screen carrying its own filters is a lens on the
	space rather than a way of looking at this record, so where two screens
	reach a doctype by the same field the plain one wins and a narrowed one is
	only used when it is the only way there.
	"""
	if not doctype:
		return []

	skip = {screen} | {one.get("screen") for one in declared or ()}
	named, about = [], []
	# A declared tab has taken its way in already, so a narrowed screen reaching
	# the same doctype by the same field is a duplicate of something that is
	# not in this list and cannot be compared against it later.
	seen = {_key(_doctype_of(space, one.get("screen")), one.get("field"), []): False
	        for one in declared or () if one.get("field")}
	for other in space.get("screens") or []:
		code = other.get("screen")
		target = (other.get("document_type") or "").strip()
		if not code or code in skip or not target or target not in granted:
			continue
		if (other.get("component") or "").strip():
			continue
		pointer = points_back(target, doctype)
		if not pointer:
			continue
		row = {
			"screen": code,
			"label": other.get("label") or code,
			"icon": other.get("icon") or "",
			**pointer,
		}
		if _keep(seen, target, pointer, narrowed(other), row):
			(about if pointer["where"] else named).append(row)

	# The named ones first. A Link is a screen saying "this is always about a
	# project"; a Dynamic Link is a screen saying it could be about anything —
	# a task, a letter, a calendar entry — and those turn up on *every* record
	# in the space. Both are worth having and only one of them is a statement
	# about this doctype, so where the ceiling bites it is the vaguer half that
	# loses its place.
	return [one for one in named + about if one][:CONNECTIONS]


def points_back(target: str, doctype: str) -> dict | None:
	"""How `target` names a `doctype`, if it does.

	Two shapes, and the second is the one worth having. A **Link** is a column
	holding an id, and the connection is `field = this record`. A **Dynamic
	Link** is a pair — a field holding a doctype and a field holding an id —
	which is how Frappe writes "about anything": a letter about a licence, a
	task against a project. Half the framework's own linking is this shape, so
	answering only the first would have left the tab off exactly the screens
	that are about other screens.

	A Link wins where a doctype has both. It is the narrower statement — this
	field is always a project — and a screen that carries one meant it.

	Among Links, the field named after the doctype wins: a Sales Invoice carries
	`project` and `cost_center`, both Links, and only one of them is what
	somebody means by "this project's invoices". Otherwise the first, which is
	the doctype's own field order and so is at least its author's.

	Parent fields only. A link on a child row — an invoice line naming an item —
	is a connection the desk draws and this does not, because `rows` filters on
	the parent's own fields and a child filter is a different query. The absence
	is a smaller lie than a tab that comes back empty.
	"""
	try:
		meta = frappe.get_meta(target)
	except Exception:
		# A screen over a doctype this site has not got. Ordinary — the space
		# may name more than the tenant installed — and not worth a traceback.
		return None

	fields = meta.fields or []

	links = [df for df in fields if df.fieldtype == "Link" and df.options == doctype]
	if links:
		wanted = frappe.scrub(doctype)
		chosen = next((df for df in links if df.fieldname == wanted), links[0])
		return {"field": chosen.fieldname, "where": []}

	for df in fields:
		if df.fieldtype != "Dynamic Link" or not df.options:
			continue
		# `options` on a Dynamic Link is the *fieldname* holding the doctype,
		# not a doctype. One that names nothing is a broken field rather than a
		# connection.
		if not meta.get_field(df.options):
			continue
		return {"field": df.fieldname, "where": [[df.options, "=", doctype]]}

	return None


def narrowed(screen: dict) -> bool:
	"""Whether a screen carries filters of its own.

	Such a screen is a *lens on the space* — "mine", "unassigned", "this
	quarter's" — and narrowing it again to one record asks a question nobody
	asked: OneTask's Inbox is the tasks on no project, and on a project it is
	the empty set by construction. Read off the manifest, before
	`spaceview.resolve` has turned `@me` into an id, because both shapes are
	the same fact and only one of them is still legible.
	"""
	filters = screen.get("filters")
	if isinstance(filters, str):
		try:
			filters = frappe.parse_json(filters or "null")
		except (TypeError, ValueError):
			return False
	return bool(filters) if isinstance(filters, (dict, list)) else False


def _keep(seen: dict, target: str, pointer: dict, is_narrow: bool, row: dict) -> bool:
	"""One row per way into a doctype, and the plain screen is the way.

	`seen` is written through: a narrowed screen takes the place while it is
	the only one, and steps aside in it the moment a plain screen arrives, so
	the order the space declares its screens in does not decide which of them a
	record is read through.
	"""
	key = _key(target, pointer["field"], pointer["where"])
	held = seen.get(key)
	if held is None:
		seen[key] = row if is_narrow else False
		return True
	if is_narrow or held is False:
		return False
	# A plain screen where a narrowed one got here first: the narrowed row is
	# already in the list, so it is emptied in place rather than removed, and
	# `connections` drops what it emptied.
	held.clear()
	seen[key] = False
	return True


def _key(target: str, field: str, where) -> tuple:
	"""One way into a doctype: what to filter, on which column, alongside what."""
	return (target or "", field or "", repr(where or []))


def _doctype_of(space: dict, screen: str) -> str:
	"""What a screen of this space is over, by its code."""
	for one in space.get("screens") or []:
		if one.get("screen") == screen:
			return (one.get("document_type") or "").strip()
	return ""
