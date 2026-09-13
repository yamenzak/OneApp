# OneProject, OneCRM, OneHR — ERPNext, cut into three

ERPNext's Projects, CRM and HR modules ship about two hundred and forty
doctypes between them, and its desk shows nearly all of them across three
workspaces of links. Almost none of those links is *a place a person goes to
work*: Leave Ledger Entry is an accounting artefact, Activity Type is a rate
card, Employee Property History is an audit trail, Salary Detail is a row
inside a slip. The desk cannot tell the difference — a doctype is a doctype —
so the first thing everybody who uses ERPNext does is learn which nine of the
forty links in front of them they actually need.

That learning is the product we are selling instead.

This document is the argument for the three spaces, the rules all three follow,
what each one is made of, and what was deliberately left out. The manifests are
`apps/oneapp_control/oneapp_control/spaces/{oneproject,onecrm,onehr}.py`; each
is the machine-readable half of a section below. Read `docs/APPS-AND-SPACES.md`
first if you have not — it is where `requires_apps` and `custom_fields` come
from, and both are load-bearing here.

---

## 1. Why three, and not one

The obvious alternative is one space called OneERP with everything in it. It is
worse for three reasons, in ascending order of how much they cost.

**A rail is a list of places to go and work.** Sixty entries is not a list, it
is a directory — and a directory is a thing you search rather than a thing you
read. Three rails of nine, fourteen and thirty are each readable top to
bottom, which is the difference between knowing where you are and looking for
where you are.

**A person is one of these things at a time.** Nobody is simultaneously running
a fit-out, chasing a quotation and approving leave. They may do all three in a
week, and the launcher is where you say which one you are doing now. A space is
a *mode*, and a mode you never leave is not one.

**Entitlement is per space.** This is the one that is not about taste. A
workspace that buys project management and not payroll should carry neither the
payroll screens nor the payroll *permissions* — and with one space it carries
both or neither. Three spaces means three grants, three role sets and three
`requires_apps` lines, and the site a customer gets is the union of what they
asked for. `apps.wanted_for` already computes exactly that.

The cost of three is that a customer who wants all three pays three grants and
sees three entries in the launcher, which is the correct thing for them to see.

---

## 2. The rules all three follow

Every one of these was written because the alternative is what ERPNext does.

### A screen is somewhere a person has a job to do

Not every doctype gets one. The test is whether somebody *goes* there: you go
to Tasks, you go to Leave, you go to Applicants. You do not go to Employment
Type — you meet it as the far end of a dropdown on a Job Opening, and a Link
control reads a doctype's own metadata and needs no screen to offer its values.

So OneHR grants Employee Grade, Employment Type, Interview Type, Grievance Type
and Expense Claim Type and gives none of them a rail entry. The grant is what
makes the picker work; the screen would only be a table you edit twice a year,
sitting between two places you go every day.

### What is maintained rather than worked in goes under one heading, last

`screen_group` draws a heading in the rail when the group changes. Every space
here ends with **Setup**: project and task types, sales stages and lost reasons,
leave types and salary components. ERPNext's own workspaces interleave these
with the transactions, which is how a salesperson's list of destinations comes
to contain Market Segment.

The rule the generator enforces: screens sharing a group must be declared
adjacently, because the rail draws a heading on *change* rather than building a
tree. That keeps the model a flat ordered list, which is what the record pane
can page through.

### A screen opens as the thing it is

This is most of the difference, and it is why the view types were worth
building. A list is the right shape for exactly one question — *which rows* —
and ERPNext answers every question with it.

* **A board**, where the question is *where does each of these stand*: tasks,
  deals, leave applications, job applicants, expense claims. A leave board of
  three columns is an approver's whole job on one screen.
* **A calendar**, where the record *is* a date: attendance, leave, shifts,
  interviews, appointments, timesheets. HRMS knows attendance is a grid of days
  — it ships a bespoke "Monthly Attendance Sheet" report to draw one — and the
  doctype's own list view is twenty thousand rows in date order.
* **A Gantt**, where the record is a span with progress: projects, tasks,
  shifts, goals.
* **A tree**, where the records nest: the org chart is `reports_to` and one
  line of manifest; departments, territories, goals and sub-tasks are the same
  line again. HRMS stores every one of these hierarchies and draws one of them.
* **A grid**, where a record is recognised rather than scanned: people,
  contacts, organisations, openings. Employee carries a photograph, and a page
  of faces is how a person is actually found.
* **A dashboard**, where the question is *how many, how much, and which way is
  it going* — and this is the one that replaces something rather than adding
  to it. ERPNext's answer to that question is a query report, in the desk, that
  this product does not render. Here it is a fourth way of looking at the screen
  you are already on, measured over the rows that screen already narrows to, as
  the person asking — so the chart and the list beside it cannot disagree, and
  neither can count a row its reader may not read.

Every screen keeps its list. The declaration says which view it *opens* with,
which is the decision ERPNext never had anywhere to record.

### A record that is a thing gets a showcase

A project is a budget, a spend, a percentage and everything filed against it. A
person is a face, a manager, their reports, their leave and their claims. A job
opening is an advert and the people who answered it. Rendering any of those as
a column of labelled inputs is technically a record page and practically a
filing cabinet.

So the four records that are *things* declare a showcase — `onespace/showcase.py`
— with an eyebrow, a badge, four facts and the screens that point back at them.
The tabs are not a second permission model: each names a screen in the same
space and the field on it pointing here, and the browser then asks the ordinary
list endpoint, which checks the space, the permissions and the filters exactly
as it does for any other list.

### Schema is added only where a distinction has nowhere to live

Two of the three spaces add fields. The third adds none, and that is written
down rather than left as an absence — see §5.

A Custom Field is applied to a workspace's database once and never taken away,
so every one of them is a column that every future migration carries. The bar
is therefore: a distinction every customer of this space makes, that ERPNext has
no column for, and that a screen here reads. Four fields cleared it.

---

## 3. OneProject

Nine screens over ERPNext's Projects module, which ships sixteen doctypes.

| Screen | Doctype | Opens as | Also |
| --- | --- | --- | --- |
| Projects | Project | Board, by health | List, Gantt, Calendar, Dashboard |
| Tasks | Task | Board, by status | List, Gantt, Calendar, Tree, Dashboard |
| Milestones | Task | Calendar | List, Board |
| Time | Timesheet | Calendar | List, Dashboard |
| Invoices | Sales Invoice | List | Dashboard |
| *Setup* | Project Type, Task Type, Activity Type, Project Template | List | |

### The two fields

**`custom_health`** — At risk / Off track / On track. ERPNext's `status` is
Open / On hold / Completed / Cancelled, which says whether a project is
*running*. The question anybody opens a portfolio to ask is whether the running
ones are all right, and those are different questions: a project can be Open and
in trouble. The board that matters cannot be drawn off `status`, so it is drawn
off this.

The three values are ordered worst-first on purpose. SQL sorts a Select
alphabetically, and "At risk" before "Off track" before "On track" is
alphabetical *and* urgent — so a list ordered by health leads with the rows
somebody has to do something about, and a board's first column is the one to
read first.

**`custom_manager`** — a Link to User. ERPNext's Project has a `users` child
table and no single owner, so a portfolio list had no column for the first thing
anybody asks about a row, and the answer lived in a grid you had to open the
record to read.

### Two things about the screens

**Templates are filtered out of the task screens.** ERPNext keeps project
templates as Tasks with a status of `Template`, so an unfiltered board of that
doctype has a seventh column holding things nobody can do, sitting between
Pending Review and Completed. `filters: {"is_template": 0}`.

**Milestones are a screen and not a filter somebody remembers.** ERPNext has the
`is_milestone` flag and nothing in the desk reads it back. It is the handful of
dates a client asks about, it is a calendar rather than a list, and it is one
line of manifest.

### The limit worth stating

The Time dashboard measures *timesheets*, not hours. A timesheet's hours live in
a child table, and no chart in this engine can reach one — `dashboard.compute`
aggregates over the screen's own doctype, deliberately, because that is what
makes it impossible for a widget to count a row its reader may not read. So
"hours by person" and "hours by project" are answerable (the sheet carries both
totals and a project) and "hours by activity type this month" is not.

Fixing it properly means a widget that can name a child table and a permission
story for one. It is not urgent: the question people actually ask of a timesheet
screen is who logged how much and how much of it was billable.

---

## 4. OneCRM

Eight places to work and six tables under Setup, over ERPNext's CRM module,
which ships twenty-six doctypes.

| Screen | Doctype | Opens as | Also |
| --- | --- | --- | --- |
| Deals | Opportunity | Board, by sales stage | List, Dashboard, Calendar |
| Follow-ups | Opportunity | Calendar | List, Board |
| Leads | Lead | Board, by qualification | List, Grid, Dashboard |
| Organisations | Prospect | Grid | List, Dashboard |
| Contacts | Contact | Grid | List |
| Quotations | Quotation | List | Board, Dashboard |
| Appointments | Appointment | Calendar | List |
| Contracts | Contract | List | Board, Calendar, Dashboard |
| *Setup* | Sales Stage, Opportunity Type, UTM Source, Campaign, Territory, Opportunity Lost Reason | | |

### The next step

ERPNext records what a deal is worth, which stage it is at, how likely it is and
when it is expected to close. It has nowhere at all to say that you promised to
send a revised price on Thursday.

That is the field a salesperson works out of. A week is a list of next steps
sorted by date, not a list of deals sorted by value — which is why every CRM
people actually use has one and why the absence is the single biggest thing
wrong with ERPNext's. So `custom_next_step` (Data) and `custom_next_step_on`
(Date), on Lead and on Opportunity both: a lead you are nurturing has next steps
for months before it becomes a deal, and losing them at the moment of conversion
is how a qualified lead goes quiet.

The whole **Follow-ups** screen falls out of those two fields, and it is
deliberately plain: the deals still alive, sorted by the date something was
promised, ascending. No clever filter and no invented "overdue" vocabulary —
ascending *is* overdue-first, and a sort somebody can read is worth more than an
operator they cannot.

### Two state fields, and which one the board is drawn by

Both of the CRM's main doctypes carry two, and in both cases the interesting one
is not the one called `status`.

**Opportunity.** `status` is what has *happened* — Open, Quotation, Converted,
Lost — and `sales_stage` is how far along it is. The board is drawn by the
stage, because that is the pipeline; the badge beside each name is the status,
because a Lost deal sitting in Negotiation is exactly the row somebody needs to
see.

**Lead.** `status` is nine values long and half of them describe the *deal* the
lead turned into — Opportunity, Quotation, Lost Quotation, Converted — so a
board of it has four columns that are really about a different record.
`qualification_status` is three values and is the actual question a lead sits
inside: unqualified, being worked, qualified. Board by that, badge by `status`.

### A pipeline in pipeline order

`Sales Stage` has a name and nothing else — no sequence — so a board drawn from
it comes out in whatever order the values arrived in, which read Negotiation,
Prospecting, Proposal. A Select carries its own order and a Link has none.

The order is a decision, so the manifest declares it: `STAGES` in `onecrm.py`,
carried to the browser as `view_settings.board.arrangement.order`. A guard now
fails any board over a Link that declares none, because the failure is silent
and looks like a rendering bug rather than a missing declaration.

### Who may change what a pipeline is measured by

Two roles: **rep** and **sales manager**. The split matters more here than
anywhere else in the repository, because the things a sales manager maintains
are the things a pipeline is *measured by*. A rep who can edit the sales stages
can move a deal into a stage they invented, and the forecast quietly stops
meaning anything. So every measurement table — stages, sources, territories,
lost reasons — is Read for a rep and Write for the manager, and nothing in
between.

---

## 5. OneHR

Thirty screens under seven headings, over HRMS, which ships around two hundred
doctypes. This is the space the choosing is most of the product for.

**People** — People, Onboarding, Exits, Grievances
**Time** — Attendance, Check-ins, Shifts, Attendance requests, Shift requests
**Leave** — Leave, Allocations, Holidays
**Pay** — Payslips, Payroll runs, Claims, Advances
**Hiring** — Openings, Applicants, Interviews, Offers
**Growth** — Goals, Appraisals, Appraisal cycles, Training
**Setup** — Departments, Designations, Leave types, Shift types, Salary
components, Salary structures

### Pay is a seat of its own

Every HR department in the world keeps salary away from the people who
administer leave. ERPNext's answer is a bag of roles somebody assembles by hand
and gets subtly wrong, and the failure is silent: a payslip is readable by
whoever holds Employee read, and nobody finds out until they do.

So OneHR declares three roles — **employee**, **people officer**, **payroll** —
and the Pay screens belong to the third alone. A workspace that wants one person
doing both hands out both roles, which is a decision somebody made rather than
one they inherited.

The employee seat is the other half of that: `if_owner` on every self-service
door — leave applications, attendance requests, shift requests, expense claims,
travel requests, grievances, goals — so you file your own and cannot read the
person next to you's. One manifest, two lists, decided by the grant rather than
by a filter somebody has to remember to apply.

**Where the split stops.** A grant is per doctype, so the seats divide the
*screens* and not the fields. HRMS keeps `ctc` and `salary_currency` on
Employee at permission level zero, and OneHR's people officer manages Employee —
so they can read what somebody is on, from the person's own record, without
holding the payroll seat. That is a real hole in an otherwise clean line and it
is not one a manifest can close today: hiding a field from one seat and not
another needs field-level grants, which this space vocabulary does not have.

The workaround a workspace has is the one ERPNext gives everybody — a Property
Setter raising those two fields above level zero — and the thing worth building
is a space being able to say it. Until then: a people officer sees what a
person earns, and a workspace that cannot live with that gives the HR job to
somebody who also holds payroll.

**And `if_owner` means *created by*, not *about*.** It is the only narrowing a
grant has, and it is the wrong axis for half of what the employee seat is for: a
leave application filed on somebody's behalf by HR, a goal set for them in an
appraisal cycle, a claim entered by finance — every one of those is *theirs* and
none of them is owned by them, so the employee seat cannot see it. In practice
these documents are nearly always filed by the person they are about, which is
why the seat works at all; the day it does not, the answer is Frappe's own User
Permission on Employee, applied per member, and a space cannot ask for one yet.

### No custom fields, and why that is worth saying

The other two spaces each add a field because each was missing a distinction
every customer makes. HRMS has no such hole. It has been written and rewritten
by people running payroll in a dozen jurisdictions, and every field a screen
here wants already exists under a name somebody argued about.

Adding one anyway would be the expensive kind of mistake, for the reason in §2:
a Custom Field is forever and a screen that merely *looks* thin is not a reason
to make one.

### Three screens that are a judgement rather than a translation

**Check-ins.** The raw punch log, which is what attendance is made of. It earns
a rail entry for exactly one reason: when a day is marked Absent and somebody
swears they were there, this is the only place that can settle it — and HRMS
buries it behind a Shift Type setting.

**Payslips, with New hidden.** A payslip is *produced* by a payroll run; one
made by hand is one that no run will ever reconcile. The doctype allows it and
ERPNext offers the button anyway. `hide_new` is the manifest saying no, and it
is the clearest example in the repository of what that flag is for.

**Holidays under Leave rather than Setup.** A holiday list is a table somebody
maintains, which by §2 belongs under Setup — and it is also the thing anybody
planning leave looks at next. It is filed where the question is asked.

---

## 6. What is deliberately not here

Listing this matters as much as listing what is, because the temptation with a
space over somebody else's app is to keep going until it is the app again.

**Everything reachable as the far end of a link.** Employee Grade, Employment
Type, Interview Type, Grievance Type, Expense Claim Type, Job Applicant Source,
Leave Policy, Leave Period, Payroll Period, Appraisal Template, KRA, Training
Program. Granted so the pickers work; no rail entry, because a table you edit
twice a year is not a destination.

**The ledgers.** Leave Ledger Entry, Employee Property History, Salary Detail,
Leave Encashment, Gratuity, the tax exemption family. These are what the
transactions *produce*. A screen over one is a screen where the only honest
action is reading, and the thing you would be reading it for — "why is this
balance what it is" — is a question the record it belongs to should answer.

**Payroll's deep end.** Income Tax Slab, Employee Benefit Application, Employee
Other Income, Retention Bonus, Salary Withholding. Real, jurisdictional, and
used by the people who would rather be in the desk for them anyway. The line
drawn is: OneHR runs a payroll cycle and shows what came out of it; configuring
a tax regime is not in it.

**Project Update.** ERPNext's "collect progress" emails, which almost nobody
turns on and which nothing else reads.

**ERPNext's own dashboards and query reports.** Not ported, and not planned to
be. The dashboard view type answers the same questions against the screen's own
rows, with the screen's own permissions; a report engine beside it would be a
second answer to one question.

---

## 7. What looking at them found

The manifests went in without a single record behind them, which is the same as
not having looked. `scripts/seed_erp_spaces.py` puts four projects, seventeen
tasks, a fortnight of timesheets, ten deals under ten leads, eight people, a
hundred and one days of attendance, eight payslips and a hiring pipeline on the
dev tenant. Then every screen was opened, and four things were wrong — none of
them in a manifest.

**A screen granted to a seat was granted to nobody.** `_granted_doctypes` read
the Custom DocPerms of the space's *base* role only. That was right while a
space had exactly one; since a `DOCTYPES` row could name a role it has been
false, and totally so — OneHR's Attendance belongs to the people officer, so
opening Attendance answered "Attendance is not part of OneHR" for every seat
including the one that holds it. It now reads every role the space's manifest
became, narrowed to the ones you hold; and the two refusals are different
sentences, because a doctype the space does not grant at all is a manifest that
does not add up, and one granted to another seat is the permission model
working.

**A calendar drew a five-day leave as one chip.** frappe-ui's Calendar places an
event by its start alone — `Calendar.vue` sets `date = fromDate` and the month
grid groups by that, so `toDate` reaches the event modal and no layout code at
all. A span is now a chip a day, clipped to the days on screen
(`lib/screen/spans.js`). On a leave screen that is not cosmetic: the month was
wrong about who was in.

**A pipeline board was alphabetical.** §4 above.

**`cards` is not a view type.** The resolved spec calls a card-shaped view's
settings `cards`, so that is what a manifest writes — three spaces did,
OneMobility included — and `_view_settings` dropped every one of those blocks
in silence, because the key has to be a view type. The key is `grid`.

**A four-star candidate drew one star, and clicking four stars stored four
hundred per cent.** Frappe keeps a Rating as a fraction of one — four out of
five is `0.8` — and frappe-ui's `Rating` counts whole stars. Neither the cell
nor the control converted, so reading rounded 0.8 down to one star and writing
sent `4` straight into a column nothing clamps. `lib/screen/rating.js` is the
pair of conversions and the round trip is tested.

**A Gantt's bars were two greys a step apart from the row behind them**, and it
opened scrolled to today — so a screen of seventeen tasks whose work is behind
them showed ten empty rows and three bars hugging the left edge. The fill is now
the space's own accent (`surface-gray-10`, which is where `theming.py` puts it)
and the chart opens framed on its first bar; the library draws a Today button in
its own header, so the other direction costs one click and this one costs none.

**Every field above permission level zero was invisible to everybody.** This is
the largest of them and it is not about these spaces at all. Frappe reads a
doctype's standard permissions *only while it has no Custom DocPerm*; the moment
one exists, the custom rows are the whole answer. `sync_permissions` wrote ours
at level zero and nothing else, so a doctype a space granted lost every level-1
grant its own app shipped — and a field above level zero became unreadable and
unwritable by everyone on that site, in this product and in the desk.

Silent, naturally. `_offerable` drops a field the reader may not read, so the
column, the badge and the board column simply are not there. OneHR's leave board
is columns of `Leave Application.status`, which HRMS keeps at level 1: the board
did not exist, and nothing anywhere said why. Twelve of the hundred and eight
doctypes these spaces grant have a levelled field, and they are the ones that
matter — a leave application's status, an expense claim's approval status, a
check-in's time.

A grant is now mirrored at every level the doctype's own fields use. That is the
honest rule rather than a conservative one: a permlevel separates roles *inside
an app's own role set*, and a tenant holds none of those roles — so declining to
grant the level protects nothing and hides a field from the person whose record
it is. A space that needs a field kept from one of its seats should not grant
that doctype to that seat.

**A board of a Select came out in the doctype's option order**, which is a
sequence for some doctypes and a pile for others: `Expense Claim.status` offers
Paid before Unpaid and Submitted after both, and `Job Applicant.status` puts
Rejected between Shortlisted and Hold — a hiring board with the bin in the
middle of the pipeline. Three boards now declare their order, and a guard
checks every declared value is one the Select can actually hold, because a
misspelt one does not fail: it quietly leaves the column where it was.

**And the settings gear on every list in the product could not be clicked.**
The footer ends with it and the assistant's launcher is `fixed` in the
bottom-end corner from `md` up; they were in the same place, so every click on
the gear landed on the orb. It had been true since the widget shipped and
nothing caught it, because CI has no bench and therefore runs no browser at all
— the suite has been green in the only place nobody was looking. The footer
reserves the corner now, whether or not the workspace has an assistant: the
widget is movable, so "is it in the corner right now" is not a question that row
can answer.

Two more, found by the guard rather than by the screenshots: four RUA screens
offered a dashboard with no widgets behind it, so the tab was never there; and
OneMobility's Deliveries dashboard declared four widgets as `count` and `sum`,
which are aggregates rather than kinds, so every one was dropped and the screen
drew an empty page.

And the pass itself is a script now: `scripts/check_screens.py` resolves every
screen of every shipped space, asks for its rows under each view type it offers,
computes its dashboard, and reports anything refused, dropped or drawn short. It
is three seconds against forty-seven screenshots and an afternoon, and it is not
a replacement for looking — a screen can resolve perfectly and read badly, and
it has no opinion about a dark card or a bar chart nobody can see.

All five of the visible ones are pinned in `e2e/erp-spaces.spec.js`, which
skips itself on a bench without ERPNext the way the fixture does — a site that
answers "skipped, no ERPNext" is a normal thing to run the suite against, and a
spec that failed there is a spec everybody learns to ignore.

Which is the argument for `tests/test_space_screens.py`. **Every way of getting
a manifest wrong is silent**: a bad fieldname is one column fewer, a view type
missing its field opens as a list, a widget in a vocabulary the server does not
know is dropped and a dashboard with none left is dropped whole. The guard
checks every fieldname, fieldtype, view type, widget, showcase tab and custom
field against the real doctype — off a bench where there is one, off
`tests/fixtures/upstream_fields.json` where there is not, and the snapshot
against the bench where both exist, so a field ERPNext renames fails one test
with the field named rather than quietly emptying a column.

---

## 8. What comes next

In the order the work is worth doing.

1. **Approvals where they belong.** Leave, expense claims and shift requests are
   all "somebody has to say yes". The board already makes the queue visible and
   the record already submits — `spaceview/docstate.py` has submit, cancel,
   amend *and* workflow transitions — so saying yes is three clicks rather than
   a trip to the desk. What is missing is the verb on the card.

   The mechanism for it is not `actions.py`, which wants a Python provider
   behind a hook: it is a **Frappe Workflow**, which this product already
   renders as buttons, and which a space could ship the way a screen already
   ships a naming series and a print format — applied once, and the workspace's
   own afterwards. That is the shape to build, and it is worth checking against
   a real customer first: an approval chain is the thing every company thinks
   is theirs.
2. **A widget that can reach a child table.** §3's limit. The question is a
   permission story, not a query.
3. **The employee's own screens.** The `if_owner` grants make self-service
   correct; what they do not do is make it *short*. Somebody filing leave wants
   their balance, their holidays and one form, and today that is three screens
   in a rail of thirty. A component screen — the escape hatch in §2 — is
   the honest answer.
4. **Seat-aware navigation.** The rail lists every screen in a space whatever
   you hold, so an employee sees Payslips and is refused it. The refusal is now
   a sentence that says why, which is the floor; hiding the entry is the
   ceiling, and it needs the space payload to carry which roles reach which
   screens.
5. **A OneProject portfolio screen that is not a doctype.** Everything here is
   over rows. The one thing a delivery director asks that no row answers is
   "which of these forty projects should I be worried about this week", which
   is health, slip and burn read together. That is a component screen and a
   small amount of arithmetic — the same shape as OneMobility's Insights.
