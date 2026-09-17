# Notifications

**OneTask ships no `ALERTS` rows of its own**, and two mechanisms it does not
own carry what a person hears.

## The assignment, which is Frappe's

Assigning a task goes through `assign_to.add`, so the person gets Frappe's own
assignment notification and the task appears in their work list beside
everything else they have been asked to look at. This module writes no second
notice about the same event.

## The automation, which is a face on `Assignment Rule`

"When a task reaches In review, hand it to the reviewers" —
`onespace/routing.py`, beside the alerts panel it shares a gate and a
vocabulary with. Handing work over *is* the notification: the person finds it
in their list.

**Unassigning is deliberately not offered.** Work vanishing from somebody's
list weeks later, with nothing on the record to say why, is a footgun with a
delay on it — and it is a footgun whose *notification* is the absence of one.

## What OneProject's manifest sends

Anything about a task that is worth a rule belongs in the space's `ALERTS`,
because the space owns the screens somebody would act on. A due date passing, a
project closing with work open: those are the space's to declare and not this
module's.

## What is not built, and would be worth having

**Nothing tells you your clock is still running.** A `Timesheet Detail` with no
`to_time` survives a closed browser and an expired session on purpose, which is
the right storage decision and leaves a person who forgot at five o'clock with
fourteen hours on a task. The rule is "a running entry older than N hours,
to its owner", and it needs a scheduled job rather than a `doc_events` hook,
which is why it is not one line in a manifest.
