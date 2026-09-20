# Collections

**OneHR owns no doctypes at all.** Not one — there is no `onehr/doctype/`
directory and `OneHR` is not in `modules.txt`.

That is the strongest statement of the rule `docs/ERP-SPACES.md` argues for:
**OneHR is Frappe HR with better views and the four things HRMS lacks**,
and it owns no employee table. HRMS ships around two hundred doctypes; nearly
all of them are real and almost none is *a place a person goes to work*. The
space is a choice among them, and the choice is the product.

## Borrowed — the ones a screen is built on

| Doctype | From | What it is here |
| --- | --- | --- |
| `Employee` | HRMS | A person. The record page is a face, a reporting line and their own tabs. |
| `Attendance`, `Attendance Request`, `Employee Checkin` | HRMS | The register, and the punches behind it. |
| `Leave Application`, `Leave Allocation`, `Leave Policy`, `Leave Period`, `Leave Policy Assignment`, `Compensatory Leave Request` | HRMS | Leave, in six nouns. |
| `Shift Assignment`, `Shift Request`, `Shift Schedule`, `Shift Schedule Assignment`, `Overtime Slip` | HRMS | Time. |
| `Salary Structure`, `Salary Slip`, `Payroll Entry`, `Payroll Period`, `Payroll Settings`, `Payroll Correction` | HRMS | Pay — the Admin seat's. |
| `Job Opening`, `Job Applicant`, `Job Offer`, `Job Requisition`, `Interview`, `Interview Feedback`, `Appointment Letter`, `Staffing Plan`, `Employee Referral` | HRMS | Hiring. |
| `Goal`, `Appraisal`, `Appraisal Cycle`, `KRA`, `Training Program`, `Training Event`, `Employee Performance Feedback` | HRMS | Growth. |
| `Employee Onboarding`, `Employee Separation`, `Exit Interview`, `Employee Grievance` | HRMS | Arriving and leaving. Subclassed — `boarding.Onboarding`, `boarding.Exit`. |
| `Department`, `Designation`, `Branch`, `Employee Grade`, `Employment Type`, `Holiday List`, `Skill` | HRMS / ERPNext | The tables the work is measured by. |
| `Leave Control Panel`, `Shift Assignment Tool`, `Bulk Salary Structure Assignment` | HRMS | Singles used as bulk tools, given a door by `tools.py`. |
| `HR Settings`, `Payroll Settings` | HRMS | Singles, given a door by the engine's `onespace/singles.py`. |
| `Task`, `ToDo` | ERPNext / Frappe | Every step of an onboarding or an exit. |

## The custom fields, which are the four things HRMS lacks

Declared in `oneapp_control/spaces/onehr.py`. The one that earned its place:

**`custom_person`** — a Link to `User` with `fetch_from: employee.user_id`, on
the four doctypes that need it.

Its whole reason is notifications. The subject of "you were marked absent" is
its `employee`, which holds `HR-EMP-00003` — not an address.
`alerts.addressable` refuses that and says so in its own docstring; what it
offers instead is `owner`, which is who *filed* the row: the same person for a
leave application somebody wrote themselves and the wrong person for every row
the company writes about somebody.

`Employee.user_id` was already the bridge. What was missing was a way to reach
it from the row, and `addressable` already accepts a Link to User — so the
whole class of "tell the person this is about" opened with no engine change and
no second recipient model.

## The field levels

`FIELD_LEVELS` in the same manifest, and this is where the confidential lane
is. Two levels rather than one, because Frappe's permission levels are a ladder
and not a set — reaching level two does not grant level one:

* **level 1** — the personnel file: date of birth, passport, health details,
  emergency contact, the resignation and relieving dates. `HR-Manager` and
  `HR-Admin`.
* **level 2** — `ctc`, the salary mode and currency, the bank account, the
  IBAN. **`HR-Admin` alone.**

ERPNext puts every Employee field at level zero, so the same grant that makes
the directory openable by a colleague handed everybody everybody else's pay.
