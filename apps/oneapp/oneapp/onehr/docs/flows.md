# Flows

    own          whose records the reader may see, and the `@me` resolution
    presence     where somebody is, now
    history      how they have been
    me           the reader's own page
    checkin      the one thing here that writes a punch
    place        where a check-in has to happen, and on whose network
    roster       taking the register
    hiring, payroll, money, growth, timekeeping, boarding   the verbs
    tools        the three bulk tools that had no door of any kind
    settings     the groups behind the configuration page
    assistant    the two tools the engine's eight could not answer

## The reader's own page — `me.home`

One read: their job, whether they are in, what is left of each leave type, what
they have asked for, what is coming up, and the row of faces beside them.

**The rule that made it possible without widening a grant** is `own.py`:
`employee_of` resolves the reader to their `Employee`, and `may_read` is what
every one of these endpoints goes through. A person reads their own record and
their manager's, peers' and reports' *presence* — not their records.

`@me` in a screen's filters is the same resolution, through `onespace/mine.py`,
so **My leave** as a screen and "my leave" in the assistant cannot come apart.

## Presence — `presence.of`

The last punch read against the shift. Not a field on anything: `Employee
Checkin` rows say in and out, a shift says what the day is meant to be, and
whether somebody is *in* is those two compared.

## History — `history.of`

An allocation minus what was taken against it, per leave type. Also not a
field, and also not expressible as a filter — which is why the assistant needed
a tool of its own.

## Checking in — `checkin.py`

`next_direction` answers whether the next punch is IN or OUT, so the control is
one button rather than two.

`file` writes an `Employee Checkin`, and it is the one thing in this module
that writes on a reader's own behalf.

## Where a check-in has to be — `place.py`

`detect` is the setting-up half: a place is a coordinate and a radius, or a
network, and **it is detected rather than typed**. Somebody standing in the
office presses a button and the place is where they are.

Asked for before it is asked for: the check-in control resolves the place
*before* offering the button, so a person out of range is told why rather than
refused after pressing.

## Taking the register — `roster.py`

`day(date)` is the matrix — people down, the day across. `mark` writes
attendance for a whole day at once, which is the bulk tool HRMS's own screens
could not reach.

A **component screen that names a doctype** to say who it is for: "Mark the
day" has no grant to be hidden by otherwise, and it is the officer's page.

## The verbs

Six modules of them — `hiring`, `payroll`, `money`, `growth`, `timekeeping`,
`boarding` — each registering through `onespace_actions`. About forty buttons,
each a line of declaration rather than a control.

Three are **deliberately not verbs**, and the README says which and why.

## The bulk tools nobody could open — `tools.py`

`page`, `people`, `run`. The Leave Control Panel, the Shift Assignment Tool and
the Bulk Salary Structure Assignment are Singles with no list to put them in, so
a person of authority had no door to them at all.

**A tool's own document is never saved** — the Control Panel is a form you run,
not a record you keep.

HR Settings and Payroll Settings were here too and are now the engine's
`onespace/singles.py`, which draws any space's Single as a screen. The two
OnePeople screens still name them; what changed is who answers.

## Onboarding and exits — `boarding.py`

`Employee Onboarding` and `Employee Separation` subclassed. Every step is a
`Task` HRMS assigns as it creates it.
