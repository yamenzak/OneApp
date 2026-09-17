"""Frappe HR, and what this product does to it.

OnePeople is thirty screens over HRMS and owns **no doctypes at all** — there
is no `onehr/doctype/` and `OnePeople` is not in `modules.txt`.
`docs/ERP-SPACES.md` §5 is the argument: HRMS ships around two hundred
doctypes, nearly all of them real, and almost none of them is *a place a
person goes to work*. The space is a choice among them, and the choice is the
product.

So this is the shortest of the three adapters in controllers and the longest
in functions called, which is exactly the shape that follows: we change almost
nothing about HRMS and we press a great many of its buttons.

`docs/ERP-SPACES.md`, "And then the other thirty", is the pass that found
them: HRMS declares about ninety `frm.add_custom_button` calls across
thirty-eight files, and almost every one ends by returning an unsaved document
the desk syncs into a form. This product has no unsaved form, so `onehr/verbs.py`
has exactly two honest answers — `filled` for a document whose interesting
fields are scalars, `drafted` for one whose point is its child rows — and every
function below is called through one of them.
"""

APP = "hrms"
NAME = "Frappe HR"

#: Their doctype, our controller. Two, and they are the same document with a
#: different sign on the date: HRMS builds an onboarding and an exit out of a
#: Project and a Task per step, and `onehr/boarding.py` types them so somebody's
#: first week does not sit in OneProject's portfolio beside a client's building.
SUBCLASSED = {
	"Employee Onboarding": "`onehr/boarding.py`. Stamps the Project it "
	                       "creates with a type, so the induction checklists "
	                       "can be kept out of the projects list.",
	"Employee Separation": "The same, on the way out.",
}

#: Nothing. HRMS's own controllers already do what a `doc_events` handler here
#: would, and the two documents we needed behaviour on are subclassed above.
#:
#: An empty declaration rather than an absent one, for the reason
#: `docs/CLEANUP.md` §8 gives about the module docs: "this module hooks
#: nothing" is information and a missing key is not.
HOOKED = {}

#: Their tables carrying a column of ours. Nine, and eight of them are
#: OnePeople's `custom_person` — a Link to `User` fetched from
#: `employee.user_id`, which exists entirely because a notification's subject
#: has to be an address and `employee` holds `HR-EMP-00003`.
EXTENDED = {
	"Appraisal": "OnePeople.",
	"Attendance": "OnePeople, and RUA.",
	"Employee Advance": "OnePeople.",
	"Expense Claim": "OnePeople.",
	"Goal": "OnePeople.",
	"Leave Application": "OnePeople.",
	"Salary Slip": "OnePeople.",
	"Shift Assignment": "OnePeople.",
	"Shift Location": "OnePeople — where a check-in has to be, and on whose "
	                  "network.",
}

#: Their functions we call. Every one is a verb on a screen, reached through
#: `onehr/verbs.py`.
CALLED = {
	"hrms.hr.doctype.attendance.attendance.mark_attendance":
		"Marking a whole day at once. `onehr/roster.py`, which is the one "
		"screen in OnePeople that writes a row per person per day.",
	"hrms.hr.doctype.employee_advance.employee_advance"
	".create_return_through_additional_salary":
		"Taking an unspent advance back out of the next payslip. "
		"`onehr/money.py`.",
	"hrms.hr.doctype.employee_advance.employee_advance.make_return_entry":
		"The other way to return one: a payment back. `onehr/money.py`.",
	"hrms.hr.doctype.employee_onboarding.employee_onboarding"
	".EmployeeOnboarding":
		"The base class the onboarding subclasses.",
	"hrms.hr.doctype.employee_onboarding.employee_onboarding.make_employee":
		"Turning a finished onboarding into a person. `onehr/boarding.py`.",
	"hrms.hr.doctype.employee_referral.employee_referral"
	".create_additional_salary":
		"Paying a referral bonus. `onehr/hiring.py`.",
	"hrms.hr.doctype.employee_referral.employee_referral.create_job_applicant":
		"A referral becomes an applicant. `onehr/hiring.py`.",
	"hrms.hr.doctype.employee_separation.employee_separation"
	".EmployeeSeparation":
		"The base class the exit subclasses.",
	"hrms.hr.doctype.exit_interview.exit_interview.send_exit_questionnaire":
		"Sending a leaver the questionnaire, which is a Web Form link and a "
		"mail HRMS already composes. `onehr/boarding.py`.",
	"hrms.hr.doctype.job_offer.job_offer.make_employee":
		"An accepted offer becomes a person. `onehr/hiring.py`.",
	"hrms.hr.doctype.job_requisition.job_requisition.make_job_opening":
		"An approved requisition becomes an opening. `onehr/hiring.py`.",
	"hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry.expire_allocation":
		"Ending an allocation early. `onehr/timekeeping.py`.",
	"hrms.overrides.employee_payment_entry.get_payment_entry_for_employee":
		"Paying an approved expense claim or an advance. The one place "
		"OnePeople touches money, and it *drafts* rather than posts — "
		"`docs/ERP-SPACES.md`, \"The line that moved\". `onehr/money.py`.",
}
