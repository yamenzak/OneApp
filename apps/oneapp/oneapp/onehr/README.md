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

## 4. Two links worth knowing about

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

## 5. What is not here, and why

**No writes at all.** Checking somebody in from their record page is a good idea
and is not this: it needs a device policy, a geofence decision and a duplicate
rule, all of which HRMS already has opinions about. See `docs/HORILLA.md` §4.

**No caching.** Two queries per record open is cheaper than a cache that can be
wrong about whether somebody is at work.

**Nothing OneHR-shaped in the engine.** `lib/screen/recordViews.js` knows there
is a `person` page; it does not know what an Employee Checkin is. The record
view asks this module by name, and a workspace without HRMS gets `unknown` and
draws nothing — OneHR is one space on a workspace that may carry others, and a
record page that 500s because an app is missing is worse than one that says it
does not know.
