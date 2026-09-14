# OneHR

The space is a manifest — `oneapp_control/spaces/onehr.py`, thirty screens over
ERPNext and HRMS, argued in `docs/ERP-SPACES.md` §5. This module is the part of
OneHR that is *not* a declaration: the questions an HR product is opened for
that no field on a doctype answers.

There is exactly one rule about what belongs here. **A screen that a manifest
can declare does not.** Adding Payslips was a dict; this is for the reasoning
that has to happen somewhere and has no doctype to live on.

---

## 1. `presence` — where somebody is, now

The question every HR product is opened for and none of them answers on the page
you are already on: *is Omar in today?*

HRMS holds the answer across four doctypes and shows it in none of them. Employee
Checkin is a log, Attendance is a day's verdict written after the fact by a
scheduled job, Leave Application is an approval, and the Holiday List is a
calendar. A person asking that question has to open three of those and do the
reasoning themselves — which is the same shape as the whole OneSpace argument,
one question down.

So the reasoning happens once, **ranked** rather than merged:

    on leave    an approved Leave Application covering today
    holiday     today is in the shift's or the company's Holiday List
    in          the last check-in today was an IN
    out         the last check-in today was an OUT
    absent      Attendance marked them so, and nothing above said otherwise
    unknown     none of the four has anything to say

The ranking is the product decision and it is worth defending. The four disagree
all the time, and the disagreement is *not an error*: somebody on approved leave
who badged in to collect a laptop is on leave, and a page that says "in" because
a turnstile said so is a page that will get somebody's pay wrong. Leave outranks
a log. A holiday outranks a log and is outranked by leave, because the list is
about the company and the application is about the person.

**`late` is a fact about an `in`, not a sixth state.** Somebody who arrived at
09:41 against a 09:00 shift is here; they are simply here late. Making it its
own state means a strip of faces cannot count how many people are in, and the
count is most of what a strip of faces is for. `GRACE` is ten minutes, because a
page that calls somebody late for arriving at 09:03 starts an argument every
morning.

**This reads and never writes.** Auto-attendance is HRMS's and runs on a
schedule. A page that marked somebody present because it happened to be open
would be a second writer on the same rows with no lock between them.

## 2. `history` — how they have been

The other half. "Is Omar in" is a state; "how has Omar been" is a shape, and the
shape is what somebody opening a record is usually actually after — a run of red
in the third week of a month says more than any single day's verdict.

Eight weeks of days, each one of `present`, `half`, `leave`, `holiday`, `absent`
or `none`, plus what leave is left per type. Built from the *calendar* rather
than from the rows: a list of only the days Attendance knows about is a strip
with holes that line up with nothing, and the whole point of a strip is that the
seventh cell is always the same weekday.

`none` is a day with no record — before somebody joined, or a day the attendance
job has not reached. It is drawn as a gap rather than as an absence, because
those are not the same thing and colouring them alike is how a strip lies.

## 3. Where analytics go, which this module is the answer to half of

The line that everybody gets wrong, written down once:

    a screen's dashboard view   how is the workforce
    a person's record           how is this person

A dashboard over one row is a number with nothing to compare it to, so the
population is answered by the widgets the manifest declares — headcount by
department, how many are on leave this week, the attendance rate — measured over
the rows that screen already narrows to, as the person asking. And the individual
is answered on their own record, by this module, because none of those widgets
can narrow to one person without becoming a worse version of this.

A widget that would say "eight people are on leave" belongs on the first. One
that says "Omar has twelve days left" belongs on the second. Both, and never the
same one twice.

## 4. `me` and `checkin` — the reader's own page

Everything above is written for the person who *administers* people. The
directory, the attendance screen, the leave board, the payroll run: all of them
are an officer's view of a workforce, and the person each of those rows is about
had nowhere to stand. `docs/HORILLA.md` §3.1 is the same finding read off a
competitor — half the entries in an HR rail have two readers and only one of them
was ever served.

One page, no navigation, every block in one call. Somebody asking how much leave
they have left should not have to know the answer lives in a doctype called Leave
Allocation. Eight calls would be eight spinners and a page that assembles itself
in front of the reader, so `me.home` returns the lot: who you are, where you are
now, your last eight weeks and what leave is left, what you have asked for, your
payslips, your goals, your people, and what is coming up.

`home` **takes no arguments**, and that is the security property rather than an
economy: there is no employee to pass, so there is no employee to pass somebody
else's.

### The rule that made it possible without widening a grant

`own.py`, and it is the counterpart to an idiom this space already had.

The Employee seat is granted `if_owner` on everything a person *files*: you raise
your own leave application and cannot read the one at the next desk. That is
right, and it covers exactly half of what a self-service page is about, because
the other half is not filed by its subject at all.

    if_owner    what you filed             leave applications, claims, goals
    own.py      what was filed about you   attendance, allocations, payslips

An Attendance row is written by a scheduled job. A Leave Allocation is written by
the people officer. A payslip is written by payroll. Their owner is never their
subject, so `if_owner` returns nothing for precisely the rows a person most wants
to see about themselves — and the alternative, granting those doctypes outright,
is how an Employee seat comes to read the whole company's attendance.

So: **your own row needs no grant; anybody else's needs the doctype.** One
sentence, one function, and it is a *narrowing* rather than a second permission
path — the same shape as the favourites filter in `spaceview/filters.py`, which
can only ever mean the session's own user because the value is not the caller's
to supply. `may_read` cannot be pointed at a colleague and answer yes.

It also closed something that was open. `history.of` used to ask only whether the
reader could read the *Employee record*, and the Employee seat can read every one
of them — a directory nobody can open is not a directory. So any colleague's
eight-week attendance strip and leave balance were readable by anybody in the
space. Reading somebody's record and reading their numbers are not the same
question, and now they are not the same check.

Pay is on the useful side of this for the first time. A payslip is about somebody
and is not owned by them, so the same rule lets a person see their own without
the Salary Slip grant, and anybody else's still needs the payroll seat — which is
exactly the line this space already draws. The employee simply stops being the
one person in the company who cannot see their own pay.

### Checking in, which is the one thing here that writes

§5 below used to say *no writes at all*, and the refusal was about checking
**somebody else** in from **their** record: that needs a device policy, a
geofence decision and a duplicate rule, and it is still not built. Filing your
own is a different act with none of those questions in it, and
`docs/HORILLA.md` §3.4 calls it the single cheapest thing in that document — the
one HR act that happens twice a day for every employee, made a destination four
clicks deep.

Two properties carry it:

**It takes no employee.** There is no argument to point at a colleague. The row
is written for `own.employee_of()` and nobody else.

**The direction is read, not asked.** The browser does not send IN or OUT,
because a page open since this morning would send whichever the button said when
it loaded. `presence.of` already ranks the four doctypes that answer where
somebody is, so the direction is the opposite of wherever they are — and somebody
the reasoning says is on leave or on a holiday is offered no direction at all,
because a badge-in on approved leave is exactly the disagreement `presence`
exists to rank and writing one would manufacture it.

Everything else is HRMS's. The row goes in as an ordinary document so its own
validation runs — shift resolution, the duplicate window, whatever a workspace
has added — and there is no `ignore_permissions` anywhere near it. The Employee
seat is granted `Employee Checkin` at `Write` rather than `Manage`, deliberately:
a check-in is a log, and somebody who can delete their own arrival time has a log
that cannot be used for anything.

## 5. Two links worth knowing about

Both are ordinary fields on Employee and both work from the person page's
Details tab. Neither is obvious, so both are written down.

**`reports_to` is the org chart.** It is what the People screen's tree nests by,
what the person page draws as the line under somebody's name, and what the
`children` declaration hangs their direct reports off — one field read three
ways. Setting it goes through the real document, so HRMS's own rules still run:
*Employee cannot report to himself* is its message, not ours, and a circular
chain is refused the same way. That is the property worth protecting — a save
path that wrote the column directly would be faster and would let a workspace
build a reporting loop nobody could see.

**`user_id` is the login, and it does something on the way past.** Linking an
employee to a User makes HRMS write a **User Permission** for that person on
that Employee row — which silently narrows what they can see across the whole
workspace, not just in OneHR. That is the behaviour a customer wants (an
employee reads their own record and not their colleague's) and it is worth
saying out loud, because nothing on the form says it is about to happen.

`User` is on `registry.NEVER_GRANTED`, so no space may ever grant it — and the
picker still works, because the two are different questions. A space's grants
decide which doctypes its *screens* may show; a Link picker asks Frappe whether
this reader may read the target. Frappe lets a Desk User read User, so the field
is fillable without OneHR being handed the permission system. `erp-spaces.spec.js`
holds that, because it is exactly the kind of thing a tightening of the grant
model would break silently.

Who may do either: the **people officer** seat, which the manifest gives
`Manage` on Employee. The employee seat has `Read` — a colleague's name is not a
secret from a colleague, but their record is not theirs to edit.

## 6. `hiring` — the three verbs the desk kept

HRMS has all three and puts them in the desk's **Create >** menu: schedule an
interview from an applicant, make them an offer, and turn an accepted offer into
an employee. That menu is `frm.add_custom_button` in an app's JavaScript — a
door this product does not have and should not, since a tenant-shipped script is
what `docs/UNIFICATION.md` rail 34 refuses — so all three were reachable only
from `/app`, which is the one place OneSpace does not go.

They are declared actions, through the hook OneMobility and the operator console
already use, and each answers with **what should happen next** rather than doing
it. The engine then opens the target screen's own New dialog with those fields
filled in — see `docs/ONESPACE.md`, under the record's controls.

**None of them inserts**, and that is the rule rather than an omission. An
Interview needs a type and a time; an Employee needs a date of birth and a date
of joining. A verb that inserted would either fail validation or skip it, and
skipping it is how a workspace ends up with an Employee payroll cannot run.
Frappe's own `get_mapped_doc` agrees: it *returns* a document and leaves it
unsaved.

**Each sends only what the target cannot derive.** Interview fetches the
opening, the designation and the résumé link off the applicant, so scheduling
sends the applicant and nothing else; a verb that filled those in too would be
having an opinion about values HRMS derives, and the first one HRMS changes is
the one that then disagrees. An offer sends the company and the date, which are
required and are on no applicant.

**The Job Offer → Employee mapping is HRMS's**, through `make_employee`. It is
the one of the three with real field mapping in it — the name, the personal
email, the confirmation date, and the back-link on `job_offer` that makes a hire
traceable to the offer — and that back-link is exactly the field somebody
re-deriving it would forget.

The refusals are where the decisions live. Only an accepted offer becomes an
employee, and somebody already rejected is not offered a job. The buttons are on
every row regardless: one that vanishes at some statuses is one nobody learns is
there.

## 7. `place` — where a check-in has to happen, and on whose network

Two rules, and only one of them is ours. That is the useful part of this
section: the first thing to do with a feature request like this is find out
whether the app underneath already has it.

**Where. HRMS's.** A **Shift Location** carries a position and a
`checkin_radius`; a Shift Assignment points an employee's shift at one;
`Employee Checkin` refuses a log more than that far from it once
`HR Settings.allow_geolocation_tracking` is on. All of it worked and none of it
was reachable, for one reason: the browser never sent a position. So the work
was not a geofence — it was four fields, a permission prompt, and a screen to
set the thing up on.

**Whose network. Ours**, because HRMS has no notion of one, and "you have to be
on the office wifi" is the other half of the same question in every workspace
that asks the first half. It is a Custom Field on the same Shift Location: the
place and the network it has are one fact about an office, and splitting them
across two doctypes would mean assigning both to a shift separately.

**A browser cannot read an SSID.** There is no web API for it and there will not
be one. What is checkable is the address the request arrives from, which for an
office is its public egress — so "the office wifi" is implemented, honestly, as
"the network we see you coming from", and the page says that where somebody
setting it up will read it. Read off `request_ip`, never off a header: a header
is a value the caller sets, which is the whole of the attack on this kind of
rule.

**The failure direction is chosen.** A line in that list that is neither an
address nor a range is dropped rather than fatal — a typo in a settings box that
stopped a whole office checking in would be a worse failure than a rule one line
shorter than intended. But a request whose address could not be resolved at all
satisfies nothing, because the alternative is a rule that opens up when the
proxy configuration changes.

### Asked for before it is asked for

`next_direction` answers what a check-in has to carry, and the button is drawn
from that. A workspace that records nothing never prompts anybody; one that does
says which office under the button rather than refusing them at the turnstile. A
location prompt somebody did not expect is a location prompt somebody refuses
once and then cannot use.

The coordinates are the only arguments `file` takes and they are **not a
permission**. They say where the browser thinks it is; what is done with them is
HRMS's. Somebody who sends a flattering pair has lied to a geofence, which is
what a geofence over a web browser is worth — and is why the network rule is
beside it, since that one is read off the connection and cannot be sent.

### Setting one up without typing it

A geofence is a position, a distance and a network, and typing any of the three
is both tedious and the step where it gets set up wrong: a latitude with the
sign flipped is a circle in the wrong hemisphere and nothing says so until
somebody cannot check in. So the `place` record view offers both instead — the
position from the browser, which is standing in the office when a manager sets
this up, and the network from the server, which sees where the request arrived
from.

Neither is forced. Both fill fields the form below still owns, so what was
detected is editable in the same place everything else is, and the page says
what the place currently demands as a sentence rather than as three numbers.

The switch that makes any of it read — HRMS's `allow_geolocation_tracking` — is
a workspace setting rather than a per-place one, because theirs is. `settings.py`
puts it under Workspace → Check-ins, and the place page says so when a place has
a distance and the switch is off.

## 8. Two pages a form could not be

Neither of these is code in this module — both are record views in the engine's
library, drawn from this space's manifest — but both are about HRMS's data and
this is where that is written down.

**An opening is how the role is going.** `OpeningRecord.vue`, named by
`view_settings.record.as` on the openings screen. The page is the posting's life
(posted when, closing when, and a warning where the closing date has been and
gone with it still open), what it pays, how many there are to fill, and the
funnel: this one role's applicants across the six hiring stages, in the order
`APPLICANT_STAGES` puts them.

The funnel is counted through `spaceview.tally` on the *applicants* screen under
a `job_title` filter — the endpoint the list's own narrowing menu uses, so the
space, the permissions and the filter are checked where every list checks them,
and six numbers cost one query rather than two hundred rows. Every declared
stage is drawn, zeroes included: fourteen replied and nobody shortlisted is a
recruiter who has stopped looking, and a funnel that hides its empty stages
cannot show that. The bars are measured against the fullest stage rather than
against the total, for the same reason — three shortlisted out of forty-three
is invisible as a share and is the number somebody came to read.

**A day is why the verdict is the verdict.** `DayRecord.vue`, on the attendance
screen, which is what a cell of the grid opens. Who, the date and the shift; the
hours worked against the shift's standard; the two flags HRMS sets on a day it
otherwise counts as worked; and the punches the day was computed from.

The punches are the argument for the page. `Employee Checkin.attendance` is the
link auto attendance writes when it marks a day from the log, so "I was here and
it says I was not" is one filter away — and it was a filter nobody could reach
without leaving the record for the Check-ins screen and typing it. The empty
case is drawn rather than hidden, because on most days it is the finding: a day
marked Present with nothing punched behind it was written by hand or by an
Attendance Request. The exception is a day of leave, where nobody expected a
punch — there the page draws the Leave Application that granted it instead, and
says nothing at all about the clock.

## 9. What it tells people about

Eight rules, shipped in the manifest and seeded once — `ALERTS` in
`spaces/onehr.py`, `sync._seed_alerts` on the way in. Two sentences per request
type: the person who has to approve one hears that it exists, and the person who
asked hears what was decided.

HRMS already knows both, and writes them into **PWA Notification** — its mobile
app's own store, which no seat here grants and no screen reads. There were
twenty-three of them on the dev site, written and never delivered. These are the
same two sentences said through the notification spine this product has: an
in-app row typed `Alert`, so it has a switch in everybody's own Notifications
panel, and somewhere for the click to go.

Three things about the shape are worth writing down.

**They arrive as the workspace's own.** Seeded through `alerts.save`, so they
are marked exactly as a rule typed into Settings is marked and are listed,
editable, pausable and deletable there. Once each, keyed on the subject —
nothing reapplies, so a rule somebody reworded stays reworded and one they
deleted stays deleted.

**`created`, not `submitted`.** HRMS refuses to submit a Leave Application until
its status is already Approved or Rejected, so a rule on Submit would tell the
approver about a decision they had already made. The draft *is* the request,
which is why HRMS's own notice goes out from `after_insert`.

**In-app, not email.** Frappe sends both from inside one `try`, so on a
workspace with no outgoing email account the failed send takes the in-app row
down with it — logged as "Failed to send Notification" where nobody looks.
In-app cannot fail that way, and turning email on is one control in Settings
belonging to the workspace that has configured mail.

The two that go to a *role* rather than a person — Attendance Request and Travel
Request, which have no approver field — name the role by its **label**. A
manifest cannot write the Frappe name down: it is derived from the space's
`role_name`, which the control plane owns, so `sync._alert_role` composes the
same thing `registry.frappe_role_for` does.

## 10. What is not here, and why

**One write, and it is your own.** `checkin.py` files a check-in for the person
asking and refuses everything else — §4. Checking *somebody else* in from *their*
record is still not here and still needs a device policy, a geofence decision and
a duplicate rule, all of which HRMS already has opinions about.

**No announcements, no document requests, no org chart page.** All three are
Horilla blocks this page does without, and the first two are probably OneSpace
features rather than OneHR ones — see `docs/HORILLA.md` §6.

**No caching.** Two queries per record open is cheaper than a cache that can be
wrong about whether somebody is at work.

**Nothing OneHR-shaped in the engine.** `lib/screen/recordViews.js` knows there
is a `person` page; it does not know what an Employee Checkin is. The record
view asks this module by name, and a workspace without HRMS gets `unknown` and
draws nothing — OneHR is one space on a workspace that may carry others, and a
record page that 500s because an app is missing is worse than one that says it
does not know.
