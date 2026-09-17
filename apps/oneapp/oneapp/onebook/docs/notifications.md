# Notifications

**This space sends nothing.** `ALERTS` is absent from
`oneapp_control/spaces/onebook.py`, so the tenant seeder writes an empty list
and no rule is created.

That is a decision rather than an omission, and it has one reason: every event
worth an alert here is somebody else's already. A payroll run that needs paying
is announced by OnePeople to the person who ran it. An expense claim that has
been approved is announced by OnePeople to the claimant. An invoice raised
against a project is announced by nothing, because the person who raised it is
the person who would be told.

The one that would be genuinely new is **an invoice that is overdue**, and it is
not a document event — it is a date arriving, which is a scheduled pass and not
an alert rule.

`docs/ONEBOOK.md` §4 got most of the way there without one. **Owed to us** is an
ageing sorted by what is late rather than by what is large, so the thing worth a
Monday morning is the first row on the page. That is a screen somebody opens
rather than a message that finds them, and the difference is the last mile: a
pass that mails the ageing on a Monday is the honest remaining version of this,
and it does not exist yet.

What a workspace gets anyway, from the engine and not from here: following a
document (`onespace/notifications.py`), an @mention in a comment, and an
assignment. Those are on every doctype in the product and need no declaration.
