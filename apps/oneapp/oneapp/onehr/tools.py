"""The six HRMS Singles, and the doors this space puts on them.

A Single is a doctype with exactly one document, and Frappe's list engine has
nothing to say about one — there is no list, no record id, no New button. So
every screen mechanism in OneSpace passed straight over them, and the six HRMS
ships were reachable from the desk and from nowhere else:

    HR Settings                        the rules
    Payroll Settings                   the rules about pay
    Leave Control Panel                allocate leave to everybody at once
    Shift Assignment Tool              put everybody on a shift
    Bulk Salary Structure Assignment   put everybody on a structure
    Employee Attendance Tool           mark a day for everybody

The last one is already answered: **Mark the day** — `onehr/roster.py` — which
is ours rather than HRMS's because the register wanted a different default and
a reason beside every row it would not let you mark. The other five are here.

## Two shapes, and they are the same shape

A **settings page** is a Single's own fields, read and written. A **bulk tool**
is a Single's own fields, plus "find the people these describe" and "do it to
the ones I ticked". HRMS built all three tools that way and they differ only in
which two methods they call, so this module is one form renderer and one table,
parameterised twice.

The form comes from `spaceview.meta` — `_columns` and `_form`, the same two
functions a record page uses — so a field is rendered by the control its
fieldtype always gets, `permlevel` is honoured, Frappe's bookkeeping stays out,
and the doctype's own tabs and sections lay the page out. Nothing here draws a
control.

## What is not stored

**The tool's own document is never saved.** HRMS's desk saves it, which makes
the filters at the top of a Leave Control Panel a global that two people
allocating leave in the same week overwrite for each other. Here the browser
sends the values with every call and the document is updated in memory, used,
and dropped. A settings page *is* saved, because that is what a setting is.

## What is a permission and what is not

The screens are component screens naming their doctype, so `spaceview.resolve`
already refuses a reader the space does not grant it to and `navigable` already
keeps the entry out of their rail. This checks again on the way in — a rail is a
suggestion and the URL is a door — and then checks Frappe's own `write`
permission, which is what the desk asks for.

**The method names are never taken from the request.** `TOOLS` below names
them; a screen key arrives from the browser and everything else is looked up
here. So this narrows what HRMS's own whitelisted methods may be called as,
rather than becoming a second way to call anything.

**The field allowlist is the screen's own `fields`**, read out of the manifest
like every other allowlist in this product — which is also what makes the
curation checkable, since the guards that check a screen's fieldnames against
the real doctype now check these five too. A value for a fieldname nobody put on
the page is not a value this page may write.
"""

import frappe
from frappe import _

from oneapp.onehr.presence import installed
from oneapp.onespace.spaceview.meta import _columns, _form

#: The five pages, and the HRMS knowledge behind each.
#:
#: **The fields are not here.** They are the screen's `fields` in the manifest,
#: which is where every other allowlist in this product lives — so the guards
#: that check a screen's fieldnames against the real doctype check these too,
#: and `check_screens` reports an empty picker on one of these pages the same
#: way it reports one on a list. A second list here would be a second list to
#: keep in step.
#:
#: What *is* here is what a manifest cannot say: which two methods a tool calls.
#: `find` and `apply` are HRMS's own whitelisted document methods, named in this
#: file and nowhere else, so a screen key arriving from a browser reaches
#: exactly these and nothing else. `carries` is what `apply` wants per person —
#: the three agree on everything but this, because a salary structure
#: assignment needs a number each and the other two do not. `amounts` are those
#: numbers, which the finder fills in from the employee's grade for somebody to
#: correct.
SETTINGS = {
	"hr-rules": {"doctype": "HR Settings"},
	"payroll-rules": {"doctype": "Payroll Settings"},
}

TOOLS = {
	"allocate": {
		"doctype": "Leave Control Panel",
		"find": "get_employees",
		"apply": "allocate_leave",
		"carries": "id",
		"verb": "Allocate",
		"blurb": "Everybody who has no allocation for this period yet.",
	},
	"assign-shifts": {
		"doctype": "Shift Assignment Tool",
		"find": "get_employees",
		"apply": "bulk_assign",
		"carries": "id",
		"verb": "Assign",
		"blurb": "Everybody who is not already on a shift over these dates.",
	},
	"assign-structures": {
		"doctype": "Bulk Salary Structure Assignment",
		"find": "get_employees",
		"apply": "bulk_assign_structure",
		"carries": "row",
		"amounts": ("base", "variable"),
		"verb": "Assign",
		"blurb": "Everybody with no assignment starting on this date.",
	},
}

#: The space these five belong to. One string, because three things read it.
SPACE = "onehr"

#: What a found person is called, in every one of the three. HRMS's three
#: finders return different column sets and agree on these two.
WHO = ("employee", "employee_name")

#: How many people one pass offers. The same argument as `roster.MOST`: past
#: this it is a migration rather than a decision, and HRMS enqueues its own
#: work above thirty anyway.
MOST = 500


def _page(screen: str) -> dict:
	"""The declaration for one screen, or a refusal.

	A screen key arrives from the browser, so this is the gate: a key that is
	not one of the five is not a page, and no doctype or method name reaches
	Frappe from anywhere but the two dictionaries above.
	"""
	found = SETTINGS.get(screen) or TOOLS.get(screen)
	if not found:
		frappe.throw(_("{0} is not a page of this space.").format(screen),
		             frappe.PermissionError)
	return found


def _allowed(spec: dict, write: bool = False) -> None:
	"""Whether this reader may be here at all."""
	if not installed():
		frappe.throw(_("This workspace does not keep people records."))
	doctype = spec["doctype"]
	if not frappe.has_permission(doctype, "write" if write else "read"):
		frappe.throw(
			_("This page is for whoever administers people."),
			frappe.PermissionError,
		)


def _doc(spec: dict, screen: str, values: dict | None = None):
	"""The Single, with whatever the page sent applied on top.

	A Frappe Single nobody has ever saved has no rows at all, and `get_single`
	answers with a document of defaults rather than raising — which is the right
	shape here, because a workspace that has never opened HR Settings has not
	got a broken one.
	"""
	doc = frappe.get_single(spec["doctype"])
	if values:
		allowed = {c["fieldname"] for c in _shown(spec, screen)}
		doc.update({k: v for k, v in (values or {}).items() if k in allowed})
	return doc


def _fields(screen: str) -> list[str]:
	"""What the manifest says this page shows, in the order it says it.

	Read off the screen rather than held here, which is what makes the curation
	checkable: `test_space_screens` asserts every fieldname a screen names is a
	real field of its doctype, and `check_screens` reports a Link on it that
	points at something the space does not grant. Both of those used to pass
	over these five pages entirely, because a component screen declared no
	fields and the whole doctype was therefore implied.

	The cuts are all of one kind. HR Settings names five Email Templates, two
	Email Accounts, a Web Form and a Role, and every one of those pickers would
	be empty here — mail is configured in One, and a Web Form is not a thing a
	customer of this product has. Two more are dropped for a different reason:
	`allow_employee_checkin_from_mobile_app` and `allow_geolocation_tracking`
	are about HRMS's own mobile app, and ours is a browser with the geofence on
	the Shift Location. A switch that governs something this workspace does not
	run is a switch that lies.
	"""
	from oneapp.onespace.spaceview.resolve import _space

	found = next(
		(one for one in (_space(SPACE).get("screens") or [])
		 if one.get("screen") == screen),
		None,
	)
	named = (found or {}).get("fields") or ""
	return [one.strip() for one in str(named).split(",") if one.strip()]


def _shown(spec: dict, screen: str) -> list[dict]:
	"""The page's fields, as columns the browser already knows how to draw."""
	meta = frappe.get_meta(spec["doctype"])
	return _columns(meta, _fields(screen))


@frappe.whitelist(methods=["GET"])
def page(screen: str) -> dict:
	"""One Single's form, and what it currently says.

	The same shape a record page is handed — `columns` and `form` — so the
	browser renders it with `RecordForm` and nothing here knows what a control
	looks like.
	"""
	spec = _page(screen)
	_allowed(spec)

	columns = _shown(spec, screen)
	doc = frappe.get_single(spec["doctype"])
	return {
		"doctype": spec["doctype"],
		"columns": columns,
		"all_columns": columns,
		"form": _form(frappe.get_meta(spec["doctype"]),
		              {c["fieldname"]: c for c in columns}),
		"values": {c["fieldname"]: doc.get(c["fieldname"]) for c in columns},
		# A tool's own words, absent on a settings page — which is how the
		# browser knows which of the two it is drawing.
		"verb": _(spec["verb"]) if spec.get("verb") else "",
		"blurb": _(spec["blurb"]) if spec.get("blurb") else "",
		"amounts": list(spec.get("amounts") or ()),
		"may_write": bool(frappe.has_permission(spec["doctype"], "write")),
	}


@frappe.whitelist(methods=["POST"])
def save(screen: str, values) -> dict:
	"""Write a settings page. Not a tool: a tool's document is never stored."""
	spec = SETTINGS.get(screen)
	if not spec:
		frappe.throw(_("{0} is not a settings page.").format(screen),
		             frappe.PermissionError)
	_allowed(spec, write=True)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Those changes could not be read."))

	doc = _doc(spec, screen, values)
	doc.save()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def people(screen: str, values) -> dict:
	"""Who the filters at the top of a tool describe.

	HRMS's own finder, which is where the interesting part is: each of the
	three excludes the people the tool would be a no-op for — somebody who
	already holds an allocation for the period, somebody already on a shift
	over those dates, somebody whose structure already starts that day. A list
	that included them would be a list where ticking everybody is wrong.
	"""
	spec = TOOLS.get(screen)
	if not spec:
		frappe.throw(_("{0} is not a tool.").format(screen),
		             frappe.PermissionError)
	_allowed(spec, write=True)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	doc = _doc(spec, screen, values if isinstance(values, dict) else {})

	# `advanced_filters` is the desk's second filter row and this page has no
	# such thing: the quick filters on the form are the filters. Passed empty
	# rather than left out because all three finders take it positionally.
	found = getattr(doc, spec["find"])([]) or []

	rows = []
	for one in found[:MOST]:
		row = {key: one.get(key) for key in WHO}
		if not row.get("employee"):
			# Leave Control Panel answers with `name` as well as `employee`
			# and the other two do not. Both are the Employee's id.
			row["employee"] = one.get("name")
		for key in spec.get("amounts") or ():
			row[key] = one.get(key)
		rows.append(row)
	return {"people": rows, "more": len(found) > MOST}


@frappe.whitelist(methods=["POST"])
def run(screen: str, values, chosen) -> dict:
	"""Do it, to the people who were ticked.

	Through HRMS's own bulk method, which is the solved problem: each of the
	three takes a savepoint per person, rolls that one back on failure, logs
	it, and carries on — so one employee with a broken date does not take the
	other forty with them. Above thirty people two of them enqueue the work and
	say so, which is theirs to decide and not ours to unwind.
	"""
	spec = TOOLS.get(screen)
	if not spec:
		frappe.throw(_("{0} is not a tool.").format(screen),
		             frappe.PermissionError)
	_allowed(spec, write=True)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(chosen, str):
		chosen = frappe.parse_json(chosen)
	if not isinstance(chosen, list) or not chosen:
		frappe.throw(_("Nobody is ticked."))
	if len(chosen) > MOST:
		frappe.throw(_("That is more people than one pass takes."))

	doc = _doc(spec, screen, values if isinstance(values, dict) else {})

	# What `apply` wants per person, and the one place the three differ. An id
	# for two of them; for the third the row itself, because a salary structure
	# assignment carries a number somebody edited on the page.
	if spec["carries"] == "id":
		payload = [str(one.get("employee") if isinstance(one, dict) else one)
		           for one in chosen]
	else:
		amounts = spec.get("amounts") or ()
		payload = [
			{"employee": str(one.get("employee") or ""),
			 **{key: one.get(key) or 0 for key in amounts}}
			for one in chosen if isinstance(one, dict)
		]
	if not all(one if isinstance(one, str) else one.get("employee")
	           for one in payload):
		frappe.throw(_("One of those rows names nobody."))

	getattr(doc, spec["apply"])(payload)
	return {"ok": True, "count": len(payload)}
