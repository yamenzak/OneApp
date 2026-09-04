"""Reading and writing the records a screen is over."""

import frappe
from frappe import _
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
from .meta import MAX_PAGE, META_FIELDS, PAGE, RECORD_META, _fetch_fields
from .filters import MAX_DELETE, _all_filters, _grouped_order
from .applied import _apply_overrides, _apply_saved
from .resolve import _resolve
from .people import _users, _with_people
from .links import _link_row, _link_shape, _link_target


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
	_with_people(found[:limit])

	# The columns come back with the rows, not only from `spec`. An unsaved
	# change to the column list narrows what is fetched, and a header list that
	# does not follow leaves a column standing over empty cells.
	return {
		"rows": found[:limit],
		"has_more": len(found) > limit,
		"columns": resolved["columns"],
		"order_by": resolved["order_by"],
		"group_by": resolved.get("group_by") or "",
		# The board these rows were fetched for, not the one the screen opened
		# with. Changing the column field changes which field is fetched, so a
		# board drawn from the spec while rows arrive for a different field is a
		# board of empty columns for as long as the request takes.
		"board": resolved.get("board") or {},
		# And what a card says, for the same reason: choosing a card field
		# changes what is fetched, so a card drawn from the spec before the
		# rows arrive is a card of empty fields.
		"cards": resolved.get("cards") or {},
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
		# Frappe's own bookkeeping as well as the fields. It is never a column
		# — `HIDDEN` sees to that, and a customer reading `modified_by` in a
		# list is always an accident — but on the record itself "who made this,
		# and when did it last change" is the question every desk sidebar
		# answers, and there is nowhere else to read it from.
		fields=fields + list(META_FIELDS) + list(RECORD_META),
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
	_with_people(found)
	_with_authors(found[0])
	_with_children(resolved, found[0], name)
	_with_state(resolved, found[0], name)
	return found[0]


def _with_state(resolved: dict, row: dict, name: str) -> None:
	"""Where the record stands, and what may be done to it next.

	On the record rather than in the spec, because it is a property of *this*
	document and not of the screen: two purchase orders on one list are in two
	workflow states, and one is the approver's to move while the other is not.

	Costs a `get_doc` on a doctype that has a workflow or is submittable, and
	nothing at all on one that is neither — which is most of them.
	"""
	meta = frappe.get_meta(resolved["doctype"])
	if not getattr(meta, "is_submittable", 0) and not docflow.workflow_name(meta.name):
		return
	row["_state"] = docflow.state(frappe.get_doc(meta.name, name), meta)


def _with_authors(row: dict) -> None:
	"""Who made it and who touched it last, as people rather than as ids.

	`owner` and `modified_by` are user ids, and a user id is an email address.
	Printing one is printing the database's answer to a question that was about
	a person — so they are resolved to the same face-and-name every other person
	in this product is drawn as, from the same lookup, in one query for both.

	The ids stay on the row. A person removed from the workspace resolves to
	nothing, and "created by somebody who is gone" still has to say who.
	"""
	found = _users([one for one in (row.get("owner"), row.get("modified_by")) if one])
	row["_owner"] = found.get(row.get("owner"))
	row["_editor"] = found.get(row.get("modified_by"))


def _with_children(resolved: dict, row: dict, name: str) -> None:
	"""The record's child rows, in place.

	Read through the parent document rather than by querying the child doctype.
	That is not a shortcut, it is the framework's own model: a child doctype has
	no permissions of its own — Frappe grants access to child rows through the
	parent, which is why `get_doc` returns them and why asking the child
	directly means either an empty grid or `ignore_permissions`, and the second
	is where User Permissions go to die.

	Safe here because of the order. `record()` has already been through
	`get_list` with the screen's filters and User Permissions applied, so by the
	time this runs the reader has been *shown* they may read this record. Rows
	belonging to a record you may read are rows you may read — and one `get_doc`
	for every table beats one query each.

	Only the fields the child offers travel. `get_doc` returns the whole row,
	permlevel-protected fields included, and a grid is not a way around field
	permissions any more than a list is.
	"""
	tables = [c for c in resolved.get("all_columns") or [] if c.get("child")]
	if not tables:
		return

	doc = frappe.get_doc(resolved["doctype"], name)
	for column in tables:
		offered = [c["fieldname"] for c in column["child"]["fields"]]
		wanted = list(dict.fromkeys(offered + ["name", "idx"]))
		row[column["fieldname"]] = [
			{key: child.get(key) for key in wanted}
			for child in (doc.get(column["fieldname"]) or [])
		]


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


def _with_links(resolved: dict, rows: list[dict]) -> None:
	"""Turn the ids in Link columns into records, in place.

	A link is a record, not a string: a cell showing `HR-EMP-00042` is showing
	the database's answer rather than the reader's. So every Link column on the
	page is resolved to the same three things the title column shows — a face, a
	name, an id — and rendered the same way.

	One query per target per column per page, not one per cell: forty rows with
	three link columns is three queries, and the ids repeat. A Dynamic Link can
	spread one column over several doctypes, so it is grouped rather than
	assumed — three targets on a page is three queries, not forty. A target this
	user may not read simply comes back empty and the cell falls back to the id,
	which is the truthful thing to show.
	"""
	links = [
		c for c in resolved.get("columns") or []
		if c["fieldtype"] in ("Link", "Dynamic Link")
	]
	if not links or not rows:
		return

	for column in links:
		for target, ids in _link_groups(resolved, column, rows).items():
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


def _link_groups(resolved: dict, column: dict, rows: list[dict]) -> dict:
	"""{target doctype: the ids on this page that point at it}.

	A plain Link has one target for the whole column, so this is one group. A
	Dynamic Link's target is on each *row* — in whatever field `options` names —
	so a page can point at several doctypes at once, and the grouping is what
	keeps that to one query each.

	Every target goes through `_link_target`, so a row naming a doctype outside
	the space's grant resolves to nothing and its cell falls back to the raw id.
	That is the truthful thing to show: the value is real, we are simply not
	willing to look it up.
	"""
	groups: dict = {}
	fieldname = column["fieldname"]
	dynamic = column["fieldtype"] == "Dynamic Link"
	source = column.get("depends_on_field")

	# A plain Link's doctype is a property of the field, so it is asked once.
	static = None if dynamic else _link_target(resolved, column)
	seen: dict = {}

	for row in rows:
		value = row.get(fieldname)
		if not value:
			continue
		if dynamic:
			named = row.get(source) if source else None
			if not named:
				continue
			# Resolved once per distinct doctype rather than once per row: the
			# check is a doctype lookup and a permission call, and forty rows
			# naming the same target is one question.
			if named not in seen:
				seen[named] = _link_target(resolved, column, named)
			target = seen[named]
		else:
			target = static
		if target:
			groups.setdefault(target, set()).add(value)
	return groups


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
		# Read rather than popped: the same value is the Tags column's cell
		# when somebody has added that column, and a card's tags when nobody
		# has. One fetch, two readers, no second opinion about what it says.
		"tags": collab.parse(row.get("_user_tags")),
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


def _child_changes(resolved: dict, values: dict) -> dict:
	"""Child-table rows from the payload, narrowed to what the child offers.

	Separate from `_writable` because a child table is not one field with one
	value — it is a list of rows, and each row has its own allowlist. Frappe
	replaces the whole table when you assign to it, so what arrives has to be
	the complete list rather than a patch, and every key in every row is
	checked against the child's own offered fields.

	That check is the same one the parent gets and matters for the same reason:
	the child's `_columns` has already dropped fields above this user's
	permlevel and Frappe's bookkeeping, so a row naming `parent` or a
	level-1 field writes neither.

	`name` survives, and only `name`. It is how Frappe tells an edited row from
	a new one — without it every save would delete and recreate the whole table,
	losing each row's identity and anything attached to it.
	"""
	tables = {
		c["fieldname"]: c for c in resolved.get("all_columns") or []
		if c.get("child") and c["child"]["editable"] and c.get("editable")
	}
	changes = {}
	for fieldname, column in tables.items():
		rows = values.get(fieldname)
		if not isinstance(rows, list):
			continue
		allowed = {
			c["fieldname"] for c in column["child"]["fields"] if c.get("editable")
		} | {"name", "idx"}
		changes[fieldname] = [
			{k: v for k, v in row.items() if k in allowed}
			for row in rows if isinstance(row, dict)
		]
	return changes


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
		frappe.throw(_("Those changes could not be read."))

	# The allowlist is the screen. A field the screen does not show is not a field
	# this screen may write, whatever arrives in the payload.
	allowed = _writable(resolved)
	changes = {k: v for k, v in values.items() if k in allowed}
	changes.update(_child_changes(resolved, values))
	if not changes:
		frappe.throw(_("Nothing on this screen can be changed."))

	# A unique-constraint failure is left to Frappe on purpose. It resolves the
	# key that actually collided back to its docfield and says "{label} must be
	# unique" before raising — so it already names the field, and it names the
	# right one. Catching it here to say something friendlier would mean
	# guessing which of a doctype's unique fields broke, which is a worse
	# message that merely sounds better. What is ours to do is the preventive
	# half: `unique` reaches the control as a note, so the collision is avoided
	# rather than explained.
	if name:
		doc = frappe.get_doc(doctype, name)
		# A workflow state can name the role that may edit in it — a purchase
		# order in *Pending Approval* is the approver's and nobody else's. The
		# desk enforces that in the browser alone, which means the API under it
		# does not; ours is the only surface there is, so it is enforced where a
		# write actually happens rather than only where a form is drawn.
		if not docflow.editable(doc):
			frappe.throw(
				_("This is not yours to change while it is where it is."),
				frappe.PermissionError,
			)
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


@frappe.whitelist(methods=["GET"])
def dashboard_data(space_code: str, screen: str | None = None,
                   overrides: str | dict | None = None,
                   layout: str | None = None) -> dict:
	"""The numbers behind one screen's dashboard.

	Its own request, and separate from `spec` on purpose: a spec is read on
	every navigation and this is one aggregate query per widget. A dashboard
	that cost nine `GROUP BY`s to open a list would be a dashboard nobody could
	afford to leave declared.

	Through `_apply_saved` and `_apply_overrides` like the rows are, so a
	filter somebody set in the toolbar narrows the charts as well as the list.
	A dashboard that ignored the filter above it would be a dashboard that
	disagrees with the screen it is on.
	"""
	resolved = _apply_overrides(
		_apply_saved(_resolve(space_code, screen, "dashboard"), layout), overrides
	)
	doctype = resolved.get("doctype")
	widgets = resolved.get("widgets") or []
	if not doctype or not widgets:
		return {"widgets": []}

	# The screen's own filters plus whatever is unsaved above it — the same
	# `_all_filters` the rows go through, so the charts and the list are
	# answering the same question.
	filters = _all_filters(resolved, resolved.get("asked") or [])
	precision = None

	return {
		"widgets": [
			{**widget, **dashboard.compute(widget, doctype, filters, precision)}
			for widget in widgets
		]
	}
