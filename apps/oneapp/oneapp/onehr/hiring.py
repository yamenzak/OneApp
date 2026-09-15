"""The three things you do to somebody applying for a job.

HRMS has all three and puts them in the desk's **Create >** menu, which is
`frm.add_custom_button` in an app's JavaScript — a door this product does not
have, and should not: a tenant-shipped script is the thing `docs/UNIFICATION.md`
rail 34 refuses. So without this, scheduling an interview, making an offer and
hiring the person who accepted one were all reachable only from `/app`, which is
the one place OneSpace does not go.

They are declared actions — `spaceview/actions.py`, the same hook OneMobility
and the operator console already use — and each answers with **what should
happen next** rather than doing it:

    {"create": {"screen": "interviews", "values": {…}}}

The engine then opens that screen's own New dialog with those fields filled in.
Not a form written here: the same dialog every list opens, so the fields, the
validation, the required-ness and the permission are the target screen's. That
is the whole reason none of these inserts anything.

**Why not insert.** All three targets have required fields nobody can derive —
an Interview needs a type and a time, an Employee needs a date of birth — so a
verb that inserted would either fail validation or skip it, and skipping it is
how a workspace ends up with an Employee nobody can run payroll for. Frappe's
own `get_mapped_doc` agrees: it *returns* a document and lets the desk render it
unsaved.

**What is taken from HRMS and what is not.** The Job Offer → Employee mapping is
theirs, through `make_employee`, because it is a solved problem we would only be
re-solving and it is the one of the three with real field mapping in it. The
other two are four fields each and are written here, because HRMS's own
`create_interview` requires an interview type this verb has no way to choose and
`schedule_interview` inserts.
"""

import frappe
from frappe import _

#: The screens these verbs send a reader to. Names in OnePeople's manifest, and
#: checked there rather than here: `run_action` resolves the screen against the
#: space before it hands the answer back, so a rename that missed this file
#: fails at the verb rather than opening something that is not there.
INTERVIEWS = "interviews"
OFFERS = "offers"
PEOPLE = "people"

#: Where an applicant has to have got to before the verb is worth offering.
#: Read rather than enforced — the screen shows the button on every row and the
#: refusal below is what decides — because a button that vanishes at some
#: statuses is a button nobody learns is there.
OFFERABLE = ("Open", "Replied", "Shortlisted", "Hold", "Accepted")


def installed() -> bool:
	return all(frappe.db.exists("DocType", one)
	           for one in ("Job Applicant", "Interview", "Job Offer"))


def actions() -> dict:
	"""Every verb these screens declare, keyed `space_code/screen`.

	Declared for `onehr` only. A second HR space would name the same methods in
	its own provider, which is the whole reason this is a dict of screens rather
	than something the manifest carries: an action names a *method*, and a list
	of methods a workspace could extend by editing a row is not a thing to have.
	"""
	return {
		"onehr/applicants": [
			{
				"key": "schedule-interview",
				"label": _("Schedule an interview"),
				"icon": "lucide-message-square",
				"scope": "one",
				"method": "oneapp.onehr.hiring.interview",
			},
			{
				"key": "make-offer",
				"label": _("Make an offer"),
				"icon": "lucide-file-text",
				"scope": "one",
				"method": "oneapp.onehr.hiring.offer",
			},
		],
		"onehr/offers": [
			{
				"key": "hire",
				"label": _("Hire"),
				"icon": "lucide-user-round",
				"scope": "one",
				"method": "oneapp.onehr.hiring.hire",
			},
		],
	}


def interview(applicant: str) -> dict:
	"""An Interview about this applicant, for the reader to schedule.

	Four fields and no type, deliberately. HRMS's own `create_interview` takes
	an interview type and refuses one whose designation does not match the
	applicant's — that is a choice with a rule behind it, and a verb that picked
	for the reader would pick wrong on the first workspace that runs two rounds.
	The dialog asks, and HRMS's validation still answers.
	"""
	found = _applicant(applicant)
	# One field, because Interview fetches the rest off it — the opening, the
	# designation and the résumé link are all `fetch_from` on the applicant, and
	# sending them too would be this verb having an opinion about values HRMS
	# derives. The form says so under each of them.
	return {"create": {"screen": INTERVIEWS, "values": {"job_applicant": found.name}}}


def offer(applicant: str) -> dict:
	"""A Job Offer to this applicant, for the reader to price and date.

	Everything an offer *is* — the terms, the salary, the date it stands until —
	is the thing being decided, so this fills in only who it is to.
	"""
	found = _applicant(applicant)
	if found.status not in OFFERABLE:
		frappe.throw(
			_("{0} is {1}, so there is no offer to make.").format(
				found.applicant_name or found.name, _(found.status or "")),
		)

	# Who it is to, when, and where from. The name, the email and the
	# designation are `fetch_from` the applicant, so sending them would be this
	# verb having an opinion about values HRMS derives — and `company` is the
	# one required field no applicant carries.
	return {"create": {
		"screen": OFFERS,
		"values": {
			"job_applicant": found.name,
			"company": found.company or frappe.defaults.get_user_default("Company"),
			"offer_date": frappe.utils.today(),
			"status": "Awaiting Response",
		},
	}}


def hire(offer_name: str) -> dict:
	"""The Employee this offer becomes, once somebody has said yes.

	HRMS's own mapping, through `make_employee`, which is the right call rather
	than a shortcut: it is the one of these three with real field mapping in it
	— the name, the personal email, the confirmation date, and the back-link on
	`job_offer` that makes the hire traceable to the offer. Re-deriving that
	here would be a second answer to a question HRMS has already answered, and
	the back-link is exactly the field somebody would forget.

	Returned unsaved and handed to the People screen's New dialog, because an
	Employee needs a date of birth and a date of joining that no offer carries.
	"""
	if not installed():
		frappe.throw(_("This workspace does not do hiring."))

	status = frappe.db.get_value("Job Offer", offer_name, "status")
	if status != "Accepted":
		frappe.throw(
			_("This offer is {0}. Only an accepted one becomes an employee.")
			.format(_(status or "")),
		)

	# After the refusals, not before them. A workspace without HRMS has no
	# module to import, and an `ImportError` is a worse answer to "this offer
	# has not been accepted" than the sentence above.
	from hrms.hr.doctype.job_offer.job_offer import make_employee

	made = make_employee(offer_name)
	return {"create": {
		"screen": PEOPLE,
		# `as_dict` rather than the document: what crosses to the browser is a
		# set of field values for a dialog, and a Document carries a great deal
		# that is not that — its child tables, its flags, its meta.
		"values": {
			field: value
			for field, value in made.as_dict().items()
			if _wanted(field, value)
		},
	}}


#: What does not travel. Frappe's own bookkeeping, which a New dialog has no
#: use for and which would arrive as fields nobody declared.
NOT_WANTED = {
	"doctype", "name", "owner", "creation", "modified", "modified_by",
	"docstatus", "idx", "parent", "parentfield", "parenttype", "__islocal",
	"__unsaved",
}


def _wanted(field: str, value) -> bool:
	return (
		field not in NOT_WANTED
		and not field.startswith("_")
		and value not in (None, "", [])
		and not isinstance(value, (list, dict))
	)


def _applicant(name: str):
	"""The applicant, read as the caller.

	`run_action` has already asked whether this reader may write the record —
	that is its third check — so this is the read that turns a name into fields
	rather than a second permission. `get_doc` rather than `get_all` because a
	verb reading five fields off one row is not a query.
	"""
	if not installed():
		frappe.throw(_("This workspace does not do hiring."))
	return frappe.get_doc("Job Applicant", name)
