# Notifications

**OneCalendar sends nothing, and the gap is named rather than hidden.**

No rule in any manifest's `ALERTS`, no `doc_events` hook. What a person hears
about something on their calendar comes from the space that owns the row: a
leave application's approver hears from OneHR, a quotation's owner from
OneCRM. The diary is a lens over rows other modules already talk about, and a
second notification from here would be two notifications about one thing.

## What is missing, and why it is not a flag

**Reminders.** The obvious one, and it is item 2 in the README's closing list
for a reason: a reminder needs somebody to remind, and nothing in the product
can yet put you in somebody else's event. The dialog has four fields and none
of them names a person. So the order is a people picker first, then reminders —
and reminders are an alerts *table* on an event rather than a field, because
"fifteen minutes before, by email, and again at the hour, by push" is three
answers.

The merge already reads `Event Participants`, so the reading half exists. It is
the writing half that does not.
