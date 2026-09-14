# Horilla, read against OneHR

An audit of **`horilla/horilla-hr`** — a Django HR suite, LGPL-2.1, ~8,600 files,
read at `e2d2889` (v2.1.6, 2026-09-11) — against the OneHR space this repository
ships. It is the closest thing to a direct competitor that is open enough to
read, and unlike ERPNext it was designed as an HR product rather than as an ERP
module that happens to contain HR.

Everything below is from the source. Nothing here is from the marketing site.

---

## 1. The licence, first, because it decides how this document may be used

Horilla is **LGPL-2.1**, stated as version 2.1 with no "or later" — the README
badge, the LICENSE file and the repository metadata all agree.

This repository is AGPL-3.0. LGPL-2.1 §3 permits converting a copy to **GPL-2.0**,
and GPL-2.0 is not upward-compatible with GPL-3.0 or AGPL-3.0. So the licences do
*not* match in the way `frappe/drive`'s and `frappe/sheets`' do, and the rule in
`CLAUDE.md` about taking code from those repositories does not extend here.

**Take ideas, not code.** No file, no function, no template, no stylesheet. What
follows is an argument about product shape, which is not copyrightable and is the
only thing worth taking anyway: their implementation is Django class-based views
with one template per screen, which is precisely the thing our manifest exists to
avoid.

---

## 2. The short version

Horilla's feature surface is roughly twice ours and its *engine* is roughly a
tenth as good. It has 34 named HR reports, an assets module, a helpdesk, mail
automations, biometric and geofenced check-in, and an exit process — and to add a
screen it needs a view class, a filter class, a template, a URL and a sidebar
entry. Ours needs a dict in a manifest.

So the audit divides cleanly, and the division is the useful part:

* **Four decisions about where things live** that they got right and we did not.
  These are cheap, they are the ones a person feels on the first day, and three
  of the four are things we had already written down as "next" without knowing
  somebody had shipped them (§3).
* **A list of things they have and we do not**, most of which we should not build
  and some of which we should (§4).
* **A list of things we have and they do not**, which is longer than expected and
  is the reason none of this is a rewrite (§5).

---

## 3. Four things about where things live

### 3.1 "My leave" sits above "Leave", in the same rail

Every Horilla module whose records are *about* a person puts the employee's own
view at the top of that module's menu, beside the administrator's: **My
Dashboard** above Employees, **My Attendances** above Attendances, **My Leave
Requests** above Leave Requests. One rail, two audiences, and the difference
between them is one word at the front of a label.

We arrived at the same problem from the other end. `docs/ERP-SPACES.md` §8.3
records that the `if_owner` grants make self-service *correct* without making it
*short*, and proposes a component screen. Horilla's answer is better than the one
we wrote down, because it is not one screen — it is the admission that half the
entries in an HR rail have two readers and each should be able to see the other's
existence.

And their **My Dashboard** is the screen §8.3 was reaching for: leave balance by
type, work hours this week, an attendance strip, recent payslips, my goals, my
recent leave requests, announcements, and what is coming up. Eight blocks, one
page, no navigation. That is a person's whole relationship with HR.

### 3.2 Configuration is one page with tabs, not nine entries in the rail

Every Horilla module ends its menu with a single **Configuration** entry that
opens a tabbed page: Employee's has Shift, Rotating shift, Shift schedule,
Rotating work type, Employee type, Tags and Work type; Payroll's has Auto
payslip, Salary structure, Allowance and Deduction; Performance's has Bonus
point, Objective template, Period and Question template.

OneHR's Setup group is seven rail entries — Departments, Designations, Leave
types, Shift types, Salary components, Salary structures — and
`docs/ERP-SPACES.md` §6 lists a further twelve doctypes we granted for their
pickers and gave no screen at all. Both halves of that are the same mistake read
two ways: the first put maintenance in the list of destinations, and the second
left twelve tables with nowhere to be edited from inside the product.

One Configuration screen per space, a tab per table, last in the rail, answers
both. It removes six entries from OneHR's rail and gives Leave Policy, Leave
Period, Payroll Period, Employee Grade, Employment Type, Interview Type,
Grievance Type, Expense Claim Type, Applicant Source, Appraisal Template, KRA and
Training Program the home they do not currently have.

### 3.3 A module opens on an answer, not on a list

Attendance, Leave, Payroll, Recruitment, Performance, Onboarding, Offboarding,
Assets, Helpdesk and Project each open on a **Dashboard** as the first menu
entry. Not a view of a list — a page about the module.

We made the dashboard a *view type* on a screen, which is the better primitive:
it is measured over the rows that screen already narrows to, as the person
asking, so the chart and the list cannot disagree. What we do not have is the
thing a rail needs at the top: a space's own landing page, before you have
chosen which of thirty screens you meant. Opening OneHR today lands you on
People, which is a list of everybody — an answer to a question nobody asked
first.

### 3.4 Check in and check out is in the top bar, always

Horilla's navbar carries a Check-In control on every page of the product. It is
the one HR act that happens twice a day for every employee, and making it a
destination — rail, Time, Check-ins, New — is four decisions in front of a thing
that should be one.

We have a Check-ins screen and no control. This is the single cheapest thing in
this document and probably the one a customer notices first.

---

## 4. What they have that we do not

Sorted by whether it is worth having, which is most of the value of reading a
competitor.

### Worth building

**Named reports as destinations.** Their `report` module registers 34 HR reports
by slug — Headcount Bridge, Turnover, Absenteeism Rate, Time to Hire, Offer &
Acceptance, Quality of Hire, Span of Control, Tenure & Longevity, Payroll
Readiness, Overtime Analysis, Open Leave Balance, Document Expiry Aging, and
more — each with its own filters, a pivot explorer, drilldown, saved layouts
(private/company/system), filter presets, favourites, scheduled delivery by
email, and async export.

`docs/ERP-SPACES.md` §6 refused ERPNext's query reports, and that refusal was
right: a second engine beside the dashboard view is two answers to one question.
This is not that. A report here is a *question with a name*, and the honest shape
for it in our vocabulary is a screen whose default view is a dashboard, sitting
in a group called Reports — no new engine, no new permission path, and the
fifteen or so of those 34 that matter are each a manifest entry.

Three of them are not expressible over one doctype's rows today — Headcount
Bridge and Turnover need a period-over-period comparison, Time to Hire needs a
duration between two records. Those are the argument for the one widget kind we
do not have.

**Attendance as three screens, not one.** Daily Work Status, Late Arrival & Early
Departure, and Monthly Summary are separate rail entries over the same
attendance data. That is the same insight as our view types, applied a level up:
"who is late" and "what did this month total" are different questions and a
filter chip is not a place.

**Import.** They have quick import with related-model column mapping on every
list; we have export and no import. A customer arriving from another system with
four hundred employees in a spreadsheet currently cannot start.

**Announcements, with read tracking and comments.** A first-class model, shown on
the employee dashboard. Every workspace has this need and currently answers it
with email.

**Document requests with expiry.** `DocumentRequest` asks an employee for a
document, tracks whether it arrived, and carries an expiry date — which is what
makes their Contracts & Document Expiry report possible. We have the Drive and no
notion of a document somebody owes us.

**Nested group-by with accordions.** We group by one field. They group by
several, and the group header carries its own actions.

**Approval chains by condition.** `MultipleApprovalCondition` routes an approval
to different managers depending on the record — an amount over a threshold goes
higher. `docs/ERP-SPACES.md` §8.1 already names Frappe Workflows as the mechanism
for approvals; this is the shape of the thing worth expressing in a manifest.

### Worth knowing about, not worth building now

**Assets** (register, batches, allocation requests, history), **Helpdesk**
(tickets, FAQs), **Meetings**, **360 Feedback**, **Bonus Points**, **Talent
Pool**, **Recruitment Survey**, **Onboarding task lists**, **Exit process**,
**Rotating shift and work-type assignment**, **Roster with a publish log**.

Each is a real product decision and several are better than nothing, but every
one of them is a module, not a screen — and OneHR is already thirty screens.
Assets and Helpdesk in particular are their own spaces if they are anything.

**Mail automations.** Trigger on a model change, pick a template, pick a channel.
We have `onemail` and the framework's own notifications; the gap is a person
being able to say it without code.

**Biometric, geofenced and face-recognition check-in.** Genuinely differentiating
in the markets this product sells into, and genuinely a project.

### Not worth having

**A tab per relationship on the employee record.** Their employee profile carries
about fourteen: about, work, attendance, leave, payroll, allowance/deduction,
contract, asset, asset request, documents, performance, bonus points, penalty
account, notes, history, mail log, permissions. Ours carries four and a Reports
tree, and four is closer to right — a tab strip that scrolls is a rail that
escaped.

**Their list engine's option surface.** `HorillaListView` has forty-odd class
attributes, eleven of which are about import column mapping. This is what a
manifest exists not to be.

---

## 5. What we have that they do not

Written down because an audit that only lists gaps produces a worse product.

* **A screen is a declaration.** Adding one is a dict in a Python module and a
  `bench migrate`. Theirs is five files.
* **Nine view types, chosen per screen** — list, board, calendar, dashboard,
  gantt, grid, map, report, tree — each dropped silently if the screen has not
  declared what it needs. Horilla hard-codes one layout per page and has a
  bespoke kanban for recruitment.
* **One record surface** with a showcase, facts, children and tabs derived from
  the same list endpoint, with the same permissions. Theirs is a template per
  tab per module.
* **Permissions as reconciled grants.** A space declares doctypes and seats; the
  sync writes Custom DocPerms at every permlevel and removes what is no longer
  declared. Theirs is Django permissions plus per-view checks, which is where
  their own `alt_permissions` comment says they got it wrong once already.
* **Seat-aware navigation**, as of this branch: the rail is narrowed to what your
  roles actually reach.
* **The rest of the product.** The Drive, the merged diary, mail, documents,
  spreadsheets, collaboration, printing, the assistant, the legal gate,
  multi-tenancy and a control plane. Horilla is an HR app; OneSpace is the place
  HR happens to be one of the things you do.

---

## 6. What to do, in order

1. **A Configuration screen per space.** §3.2. Removes six rail entries from
   OneHR and gives twelve orphaned doctypes a home. This is a component screen
   plus a manifest key naming which doctypes are tabs on it; nothing about the
   permission model changes, because every one of those doctypes is already
   granted. **Built** — `onespace/configuration.py` and
   `screens/Configuration.vue`, twelve tabs on OneHR and four and six on the
   other two.
2. **An employee home.** §3.1 and §3.4 together: the eight-block page, plus the
   check-in control in the shell. The blocks are all screens we already have,
   read through the endpoints they already use. **Built** —
   `oneapp/onehr/me.py` and `screens/onehr/Home.vue`, under a **You** heading
   at the top of OneHR's rail. The control is on that page rather than in the
   shell: a check-in affordance every space pays for is the abstraction-at-the-
   second-caller trap `docs/UNIFICATION.md` F1 is about, and there is one space
   that wants it. What made the page possible without widening a grant is
   `onehr/own.py` — your own row needs no grant, anybody else's needs the
   doctype — which is the counterpart to `if_owner` that this repo did not have
   a name for.
3. **"My" as a first-class narrowing.** A screen may declare that it has a
   self-service twin, and the rail draws both. This is a manifest key and a
   filter, not a screen. **Built**, and it turned out to be *neither* a
   manifest key nor a screen-shaped mechanism: a twin is an ordinary screen
   declaration — `{**parent, "screen": "my-leave", …}`, because a manifest is a
   Python file and that is the whole of the reuse — and the only thing the
   engine learned is a filter value meaning the reader. `oneapp/onespace/
   mine.py`: `@me` is the session's user and `@me:<kind>` is somebody that user
   *is* in another app's terms, registered through an `onespace_subjects` hook
   so the engine stays ignorant of HRMS. My leave, My claims and My goals in
   OneHR; My deals in OneCRM, off the user with no app to ask.

   Not My attendance or My payslips: a screen is a doctype grant and the
   Employee seat holds neither. Those stay as blocks on Home, where `own.py`
   crosses that line for a row and deliberately not for a screen.
4. **A space landing screen.** §3.3.
5. **Named reports as screens.** §4, and the one new widget kind the three
   period-over-period reports need.
6. **Import.** §4.
7. **Announcements and document requests.** §4, and both are probably OneSpace
   features rather than OneHR ones.

Stages 1 to 4 are a week and change nothing underneath. Stage 5 is where the
argument in §6 of `docs/ERP-SPACES.md` gets revisited on purpose rather than by
drift, and it should not start before somebody has said out loud that a report is
a screen and not an engine.
