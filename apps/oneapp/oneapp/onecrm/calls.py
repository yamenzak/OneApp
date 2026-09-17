"""A call, logged by hand — the commonest thing on a sales desk.

`docs/ONECRM.md` stage 5. Frappe CRM ships a `CRM Call Log` with Twilio and
Exotel behind it, and the part worth taking is the part that needs neither:
that log carries a `telephony_medium` of **Manual**, because most of the value
of a call log is having one at all. Somebody rings a number, writes three
lines, and it is on the record for ever — which works with a desk phone, a
mobile and a switchboard nobody has heard of.

Three decisions.

**Two presses, from the record you are already reading.** The verb does not
write anything: it answers `{"create": …}` and the engine opens the Calls
screen's own New dialog with the record, the time, the person and whatever
number that doctype was carrying already filled in. So the fields, the
required-ness and the permission are the Calls screen's, and nobody has a call
logged on their behalf by a button.

**Who was on the other end is read generically.** `NUMBERS` and `WHOM` are
candidate fieldnames tried in order against whatever doctype the verb was
pressed on, rather than a map from doctype to field. An Opportunity keeps a
number in `contact_mobile` and a Lead in `mobile_no` and a Contact in
`mobile_no` too, and the next app to want this verb keeps it somewhere else
again — a list of names that misses is a blank box, and a map that has not
heard of your doctype is no verb at all.

**And it is about anything.** `about_doctype`/`about_name` is a dynamic pair,
so a call about a job, a tenant, a patient or a supplier is the same row. This
lives in `onecrm` because selling is where somebody asked for it first; nothing
in it is about selling.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

#: Ours.
CALL = "One Call"

#: The screen the New dialog opens on, and the space it is in.
SPACE = "onecrm"
SCREEN = "calls"

#: Where a phone number hides, in the order worth trying.
#:
#: Read off the doctype's own meta rather than assumed: a field in this list
#: that the doctype has not got is skipped, and a record that has none of them
#: opens the dialog with the number blank, which is what a person is about to
#: type anyway.
NUMBERS = ("contact_mobile", "mobile_no", "phone", "contact_phone",
           "phone_number", "customer_phone_number", "whatsapp_no")

#: And who the other end is, by the same rule. Ordered person-first: a call is
#: to somebody, and falling back to the organisation's name is better than
#: falling back to `CRM-OPP-2026-00031`.
WHOM = ("contact_display", "contact_person", "lead_name", "person_name",
        "customer_name", "company_name", "organization", "party_name")

#: The address-book row, where the doctype is holding one.
CONTACTS = ("contact_person", "contact")


def entries(doctype: str, name: str, resolved: dict) -> list[dict]:
	"""The calls logged about one record, for its merged timeline.

	A registered source — `spaceview/surround.py` explains why that is a list.
	`get_list` rather than `get_all`, like every other source there: a call is
	as private as the record it is on, and a timeline that reads past somebody's
	permissions is a timeline that leaks.
	"""
	from oneapp.onespace.spaceview.surround import TIMELINE_PAGE

	if not frappe.db.table_exists(CALL):
		return []

	rows = frappe.get_list(
		CALL,
		filters={"about_doctype": doctype, "about_name": name},
		fields=["name", "with_whom", "way", "number", "at", "minutes",
		        "outcome", "person", "note"],
		order_by="at desc",
		limit_page_length=TIMELINE_PAGE,
	)
	if not rows:
		return []

	named = _named({one.get("person") for one in rows})
	return [{
		"kind": "call",
		"key": f"call:{one['name']}",
		# `at` and not `creation`: the merged column is ordered by when things
		# happened, and a call logged on Friday about Tuesday belongs on
		# Tuesday. It is the one source here whose time is typed by a person.
		"on": one.get("at"),
		"by": named.get(one.get("person")) or one.get("person"),
		"by_id": one.get("person"),
		"with_whom": one.get("with_whom") or "",
		"way": one.get("way") or "",
		"number": one.get("number") or "",
		"minutes": int(one.get("minutes") or 0),
		"outcome": one.get("outcome") or "",
		"note": one.get("note") or "",
		"call": one["name"],
	} for one in rows]


def _named(users: set) -> dict:
	"""Full names for the people who made these calls."""
	users = {one for one in users if one}
	if not users:
		return {}
	rows = frappe.get_all("User", filters={"name": ["in", list(users)]},
	                      fields=["name", "full_name"])
	return {one["name"]: one.get("full_name") or one["name"] for one in rows}


# --------------------------------------------------------------------------- #
# The verb
#
# `run_action` hands a method the record's name and nothing else — deliberately,
# see its docstring — so the doctype has to come from somewhere, and the honest
# somewhere is the declaration. Hence four one-line functions rather than one
# that takes a doctype as an argument: a whitelisted method that will log a call
# about any doctype you name is a wider door than any of these screens needs.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def about_a_deal(name: str) -> dict:
	"""Log a call about an opportunity."""
	return _logging("Opportunity", name)


@frappe.whitelist(methods=["POST"])
def about_a_lead(name: str) -> dict:
	"""Log a call about a lead."""
	return _logging("Lead", name)


@frappe.whitelist(methods=["POST"])
def about_a_contact(name: str) -> dict:
	"""Log a call about a person in the address book."""
	return _logging("Contact", name)


@frappe.whitelist(methods=["POST"])
def about_an_organisation(name: str) -> dict:
	"""Log a call about an organisation — ERPNext's Prospect."""
	return _logging("Prospect", name)


def _logging(doctype: str, name: str) -> dict:
	"""The Calls screen's New dialog, already about this record.

	Nothing is written. `{"create": …}` is `spaceview/run.py`'s own answer for
	"this record is the start of another one", and the dialog it opens is the
	one the Calls list opens — which is where the permission to create a call
	is decided, rather than here.
	"""
	if not frappe.has_permission(doctype, "read", doc=name):
		raise frappe.PermissionError(_("You cannot read {0}.").format(name))

	held = _held(doctype, name)
	values = {
		"about_doctype": doctype,
		"about_name": name,
		# Now, because a call is logged straight after it: a person who was on
		# the phone a minute ago should press Save, not fill in a clock.
		"at": now_datetime(),
		"person": frappe.session.user,
		"way": "Outgoing",
		"outcome": "Answered",
		"with_whom": _first(held, WHOM) or _title(doctype, name),
		"number": _first(held, NUMBERS),
		"contact": _first(held, CONTACTS),
	}
	return {"create": {"screen": SCREEN,
	                   "values": {k: v for k, v in values.items() if v}}}


def _held(doctype: str, name: str) -> dict:
	"""Whatever of `NUMBERS`, `WHOM` and `CONTACTS` this doctype actually has.

	One read, of the fields that exist. Asking for a fieldname a doctype has
	not got is an error in Frappe rather than a blank, so the meta decides the
	list before the query is made.
	"""
	meta = frappe.get_meta(doctype)
	wanted = [one for one in (*WHOM, *NUMBERS, *CONTACTS)
	          if meta.has_field(one)]
	if not wanted:
		return {}
	return frappe.db.get_value(doctype, name, sorted(set(wanted)),
	                           as_dict=True) or {}


def _first(held: dict, names) -> str:
	"""The first of these fields that the record had something in."""
	for one in names:
		value = held.get(one)
		if value:
			return str(value)
	return ""


def _title(doctype: str, name: str) -> str:
	"""What to call the other end when no field said."""
	meta = frappe.get_meta(doctype)
	title = getattr(meta, "title_field", "") or ""
	if title and title != "name":
		said = frappe.db.get_value(doctype, name, title)
		if said:
			return str(said)
	return str(name)


def actions() -> dict:
	"""The one verb, on the four screens somebody is looking at a person from.

	Offered on every row rather than on some of them — `onehr/verbs.py` states
	the rule and the reason. There is no state a call cannot be logged in: you
	can ring somebody about a lost deal, and a log of the call where they told
	you so is exactly the row worth having.
	"""
	from frappe import _ as translate

	def verb(method: str) -> list[dict]:
		return [{
			"key": "log-a-call",
			"label": translate("Log a call"),
			"icon": "lucide-phone",
			"scope": "one",
			"method": f"oneapp.onecrm.calls.{method}",
		}]

	return {
		f"{SPACE}/deals": verb("about_a_deal"),
		f"{SPACE}/my-deals": verb("about_a_deal"),
		f"{SPACE}/leads": verb("about_a_lead"),
		f"{SPACE}/contacts": verb("about_a_contact"),
		f"{SPACE}/organisations": verb("about_an_organisation"),
	}
