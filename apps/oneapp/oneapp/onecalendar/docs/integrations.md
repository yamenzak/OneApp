# Integrations

## Frappe

**`Event` and `Event Participants`.** The store under the merge. Used as the
framework ships them: no override, no custom field, no subclass. The two ways
an event is yours — `owner`, and a row in `Event Participants` — are Frappe's
own, which is why an event somebody else put in your diary arrives without this
module knowing how it got there.

**`_assign`** is read, not written. `diary._about_filters` turns it into the
`like` that Frappe's own "assigned to me" is, which is how a screen with no
owner field of its own still answers *mine*.

Frappe's `Event` also carries repeat fields. Nothing here reads or writes them
— see the README's item 3.

## ERPNext and HRMS

**Through their screens, never directly.** OneCalendar imports neither. What
arrives on the grid from them is what their spaces' manifests declare: a
Quotation's `valid_till`, a Leave Application's dates, an Interview's slot, a
Timesheet's day. The merge reads screens; a screen reads a doctype.

That indirection is the reason a new ERPNext doctype on a calendar is a
manifest edit and not a change here. `Interview Detail.interviewer` is the one
place a doctype's shape shows through, because "whose is this row" lives in a
child table for that one.

## The engine (`onespace`)

Nearly all of it, and this is the module that leans on the engine hardest:

* **`spaceview`** resolves every source. A screen absent from the reader's rail
  is absent from their diary for the same reason and by the same code.
* **`mine.py`** resolves `about`. The `@me` sentinel means the same thing here
  as in a screen's own filters, so "my leave" cannot come apart from **My
  leave**.
* **The record shell** supplies a record's own calendar. There is no manifest
  key for it: the showcase's tabs and the connections beside them already say
  which screens are about this record and which field points back.

## OneTask and OneProject

A task with a date is on the grid because OneProject's manifest declares a
calendar over ERPNext's `Task` — not because this module knows what a task is.
`docs/WORK.md` §6 is the argument that these are one question rather than
three.

## The desk (`onespace`, DESKTOP §6)

The diary is a desk window, because checking Tuesday against the quotation you
are writing is the whole use of it. It keeps nothing — no folder, no open item
— so `lib/window.js` is an id and nothing else, and its single verb teleports
into the window's title bar rather than drawing a second band under it.

## OneLegal

`legal.py` adds the privacy clause, and its content is a *negative*: nothing
here connects to Google or Exchange, no ICS leaves, no RSVP arrives. Saying so
is the point — a calendar is the module people assume syncs.

## OneAI

See `ai.md`.

## Not connected, deliberately

An outside calendar. Two-way sync with Google or Exchange is a module of its
own, not a flag on this one, and the privacy clause says as much today.
