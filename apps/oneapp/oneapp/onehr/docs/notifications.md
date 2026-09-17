# Notifications

**Sixteen rules, shipped in the manifest** — `ALERTS` in `spaces/onehr.py`,
seeded by `sync._seed_alerts` on the way in. This is the module with the most
of them in the product, and the shape is worth the detail.

## Two sentences per request type

The person who has to approve one hears that it exists, and the person who
asked hears what was decided.

A **grievance** is one of them, and it was the door in the space that opened
onto nothing: somebody files a complaint about their workload and it sits in a
list until whoever happens to open that list opens it. Raised goes to the
Manager's role; decided goes back to the person who filed it.

## Six are about *you* rather than about something you asked for

You have been put on a shift, you were marked absent, your payslip is ready,
your advance was decided, a goal was set for you, your appraisal is finished.

The payslip is the one people actually wait for, and **HRMS sends it to its
mobile app and nowhere else** — there were twenty-three `PWA Notification` rows
on the dev site, written and never delivered, into a store no seat grants and
no screen reads.

None of these could be written before `custom_person` existed. See
`collections.md`: the subject of such a row is its `employee`, which holds
`HR-EMP-00003` and not an address.

## Three things about the shape

**They arrive as the workspace's own.** Seeded through `alerts.save`, so they
are marked exactly as a rule typed into Settings is marked and are listed,
editable, pausable and deletable there. **Once each, keyed on the subject** —
nothing reapplies, so a rule somebody reworded stays reworded and one they
deleted stays deleted.

**`created`, not `submitted`.** HRMS refuses to submit a Leave Application
until its status is already Approved or Rejected, so a rule on Submit would
tell the approver about a decision they had already made. The draft *is* the
request, which is why HRMS's own notice goes out from `after_insert` too.

**In-app, not email.** Frappe sends both from inside one `try`, so on a
workspace with no outgoing email account the failed send takes the in-app row
down with it — logged as "Failed to send Notification" where nobody looks.
In-app cannot fail that way, and turning email on is one control in Settings
belonging to the workspace that has configured mail.

## The two that go to a role

Attendance Request and Travel Request have no approver field, so they name the
**Manager** — by its *label*, because a manifest cannot write a Frappe role
name down. `sync._alert_role` composes `<prefix>-<Seat>` the same way
`registry.frappe_role_for` does.

## Two things are deliberately absent

**Hiring.** Everything worth saying there is said to a *candidate*, and a
candidate is not a login. That makes it mail rather than an alert —
`integrations.md` has the argument.

**Onboarding and exits.** Every step of one is a `Task` HRMS assigns to a
person or a role as it creates it, and an assignment already notifies. A second
alert saying the same thing is how a product teaches people to ignore both.
