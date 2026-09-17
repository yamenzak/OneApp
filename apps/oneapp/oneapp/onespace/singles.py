"""A doctype with exactly one document, as a screen.

Frappe calls it a Single, and the list engine has nothing to say about one:
there is no list, no record id, no New button. So every screen mechanism in
OneSpace passed straight over them, and a Single was reachable from the desk
and from nowhere else.

`oneapp/onehr/tools.py` answered that for OnePeople first, because HRMS ships
six of them and five had no door. This is the same page, moved to the engine,
because the shape has nothing to do with people: a Single's own fields, read
and written, is what HR Settings is and it is also what an Opening Invoice
Creation Tool is. OneBook wanted the second one and the honest choice was one
page in the engine or two pages that drift.

A space declares it the way it declares any component screen:

    {"screen": "opening-invoices", "component": "single",
     "document_type": "Opening Invoice Creation Tool",
     "fields": "company,invoice_type,create_missing_party,invoices"}

and everything else follows from those three. The form comes from
`spaceview.meta` — `_columns` and `_form`, the same two functions a record page
uses — so a field is rendered by the control its fieldtype always gets, a Table
is the child grid it is everywhere, `permlevel` is honoured, Frappe's
bookkeeping stays out, and the doctype's own tabs and sections lay the page
out. Nothing here draws a control.

## What is checked, and where

`document_type` on a component screen already means "who this screen is for" —
`spaceview.resolve` refuses a reader the space does not grant it to, and
`navigable` keeps the entry out of their rail. This checks the same two things
again on the way in, because a rail is a suggestion and the URL is a door, and
then checks Frappe's own `read` or `write` permission, which is what the desk
asks for.

**Nothing about the page is taken from the request.** A space code and a screen
key arrive from the browser and are looked up in the manifest; the doctype is
the manifest's, the field allowlist is the manifest's `fields`, and the screen
has to be a `single` component or this is not its endpoint. So a value for a
fieldname nobody put on the page is not a value this page may write, and this
is not a second way to open any doctype.

**A verb beyond Save is named here and nowhere else** — `VERBS`, keyed by
doctype. A manifest can mount a Single as a screen; it cannot say what method
to call on it, because a manifest that could would be a manifest that can call
anything.

## What is stored

A settings page saves, because that is what a setting is. A **tool** does not:
its document is updated in memory, used, and dropped. The desk saves one, which
is what makes the filters at the top of a bulk tool a global that two people
running it in the same week overwrite for each other.
"""

import frappe
from frappe import _

from oneapp.onespace.spaceview.meta import _columns, _form

#: The `component` a screen names to become one of these. Engine-level and so
#: keyed with no slash, like `home` and `configuration`: any space may say it,
#: and keying it per space would be the same entry once per app — which is the
#: shape `docs/UNIFICATION.md` F1 is entirely about.
SINGLE = "single"

#: The Singles that do something, and the one method each does it with.
#:
#: Keyed by **doctype** rather than by screen, because the verb belongs to the
#: document and not to the name a space mounted it under: two spaces putting a
#: door on the same tool should not be able to disagree about what its button
#: does.
#:
#: `call` is the whole dotted path — module, class, method — rather than a bare
#: method name, and it is checked against the document before it is called. Two
#: things follow. An upgrade that moves the class fails at the button with a
#: sentence naming it, instead of reaching whatever else answers to that method
#: name. And the path is a string in this file, which is what
#: `oneapp/adapters/` is read against: a seam into somebody else's app that no
#: adapter declares fails `test_every_foreign_function_we_import_is_declared`.
#:
#: A doctype absent from here is a settings page: its one verb is Save.
VERBS = {
	# ERPNext's own opening-balance importer. A workspace arriving from another
	# system has a trial balance on the day it leaves and a list of who owed it
	# what; the journal takes the first and this takes the second, raising one
	# opening invoice per party against the Temporary Opening account so that
	# the receivables ledger starts out agreeing with the balance.
	#
	# `make_invoices` is where the knowledge is: it fills in the temporary
	# account, the party type, the quantity and the dates, creates a missing
	# party where the page said to, scopes each invoice to its own savepoint so
	# one bad row does not undo the forty before it, and enqueues the work past
	# fifty rows. Every one of those is a thing to get wrong twice.
	"Opening Invoice Creation Tool": {
		"call": "erpnext.accounts.doctype.opening_invoice_creation_tool"
		        ".opening_invoice_creation_tool"
		        ".OpeningInvoiceCreationTool.make_invoices",
		"verb": "Create the invoices",
		"blurb": "One opening invoice per party, posted against the "
		         "Temporary Opening account. What each row needs is a party, "
		         "a date and what was outstanding on it.",
	},
}

def _space(space_code: str) -> dict:
	"""The space, if this person may open it. `spaceview.resolve`'s own gate."""
	from oneapp.onespace.spaceview.resolve import _space as opened

	return opened(space_code)


def _screen(space_code: str, screen: str) -> tuple[dict, dict]:
	"""The space and the screen's declaration, or a refusal.

	A screen key arrives from the browser, so this is the gate: a key that is
	not a screen of this space is not a page, and a screen that is not a
	`single` is somebody trying this endpoint on a list.
	"""
	space = _space(space_code)
	found = next(
		(one for one in (space.get("screens") or [])
		 if one.get("screen") == screen),
		None,
	)
	if not found or (found.get("component") or "") != SINGLE:
		frappe.throw(_("{0} is not a page of this space.").format(screen),
		             frappe.PermissionError)
	if not found.get("document_type"):
		frappe.throw(_("{0} names nothing to show.").format(screen))
	return space, found


def _allowed(space: dict, doctype: str, write: bool = False) -> None:
	"""Whether this reader may be here at all.

	The space's own grant first — the same refusal `spaceview.resolve` gives a
	component screen naming a doctype — and then Frappe's, which is what the
	desk asks for and what a `permlevel` is read against.
	"""
	from oneapp.onespace.spaceview.resolve import _refuse_ungranted

	_refuse_ungranted(space, doctype)
	if not frappe.has_permission(doctype, "write" if write else "read"):
		frappe.throw(
			_("This page is for whoever administers {0}.").format(
				space.get("space_label") or space.get("space_code")),
			frappe.PermissionError,
		)


def fields_of(found: dict) -> list[str]:
	"""What the manifest says this page shows, in the order it says it.

	Read off the screen rather than held in Python, which is what makes the
	curation checkable: `test_space_screens` asserts every fieldname a screen
	names is a real field of its doctype, and `check_screens` reports a Link on
	it that points at something the space does not grant. Both of those pass
	over a component screen that declares no fields, because the whole doctype
	is then implied.
	"""
	named = found.get("fields") or ""
	return [one.strip() for one in str(named).split(",") if one.strip()]


def columns_of(doctype: str, found: dict) -> list[dict]:
	"""The page's fields, as columns the browser already knows how to draw."""
	return _columns(frappe.get_meta(doctype), fields_of(found))


def apply_values(doc, columns: list[dict], values) -> None:
	"""Put what the page sent onto the document, and nothing else.

	The allowlist is the columns, which are the manifest's `fields` — so a
	fieldname nobody put on the page is dropped here rather than written.
	"""
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		return
	allowed = {one["fieldname"] for one in columns}
	doc.update({key: value for key, value in values.items() if key in allowed})


def shape(doctype: str, found: dict, columns: list[dict]) -> dict:
	"""The answer a Single's page is, as `RecordForm` already reads it.

	`columns` and `form` under the names a screen spec uses, so the browser
	renders this with the component a record page uses and nothing here knows
	what a control looks like.
	"""
	# A Single nobody has ever saved has no row at all, and `get_single`
	# answers with a document of defaults rather than raising — which is the
	# right shape, because a workspace that has never opened its settings has
	# not got broken ones.
	doc = frappe.get_single(doctype)
	verb = VERBS.get(doctype) or {}
	return {
		"doctype": doctype,
		"columns": columns,
		"all_columns": columns,
		"form": _form(frappe.get_meta(doctype),
		              {one["fieldname"]: one for one in columns}),
		"values": {one["fieldname"]: doc.get(one["fieldname"])
		           for one in columns},
		# A tool's own words, absent on a settings page — which is how the
		# browser knows which of the two it is drawing.
		"verb": _(verb["verb"]) if verb.get("verb") else "",
		"blurb": _(verb["blurb"]) if verb.get("blurb") else "",
		"may_write": bool(frappe.has_permission(doctype, "write")),
	}


@frappe.whitelist(methods=["GET"])
def page(space_code: str, screen: str) -> dict:
	"""One Single's form, and what it currently says."""
	space, found = _screen(space_code, screen)
	doctype = found["document_type"]
	_allowed(space, doctype)
	return shape(doctype, found, columns_of(doctype, found))


@frappe.whitelist(methods=["POST"])
def save(space_code: str, screen: str, values) -> dict:
	"""Write a settings page.

	Not a tool: a tool's document is never stored, so a doctype with a verb is
	refused here rather than quietly saved on the way to running.
	"""
	space, found = _screen(space_code, screen)
	doctype = found["document_type"]
	if doctype in VERBS:
		frappe.throw(_("{0} is a tool and does not keep what you typed.")
		             .format(found.get("label") or screen))
	_allowed(space, doctype, write=True)

	doc = frappe.get_single(doctype)
	apply_values(doc, columns_of(doctype, found), values)
	doc.save()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def run(space_code: str, screen: str, values) -> dict:
	"""Do what this page's button says, through the doctype's own method.

	The document is built in memory from what the page sent and dropped
	afterwards — see the module docstring. The method is `VERBS`', never the
	request's.
	"""
	space, found = _screen(space_code, screen)
	doctype = found["document_type"]
	verb = VERBS.get(doctype)
	if not verb:
		frappe.throw(_("{0} has nothing to run.")
		             .format(found.get("label") or screen),
		             frappe.PermissionError)
	_allowed(space, doctype, write=True)

	doc = frappe.get_single(doctype)
	apply_values(doc, columns_of(doctype, found), values)

	# The path names a class as well as a method, and the document has to be
	# one — a controller this app overrode is a subclass and still is one. An
	# upgrade that moves or renames the class stops here, with the path in the
	# message, rather than calling whatever else answers to the method name.
	where, _sep, method = verb["call"].rpartition(".")
	try:
		wanted = frappe.get_attr(where)
	except (AttributeError, ImportError, ModuleNotFoundError):
		wanted = None
	if not wanted or not isinstance(doc, wanted):
		frappe.throw(_("{0} is not what this page was written against.")
		             .format(verb["call"]))
	answer = getattr(doc, method)()
	# What came back, where it is a list of names — ERPNext's importer answers
	# with the documents it made under fifty rows and with nothing at all above
	# that, where it has enqueued the work instead.
	made = answer if isinstance(answer, list) else []
	return {"ok": True, "count": len(made), "enqueued": answer is None}
