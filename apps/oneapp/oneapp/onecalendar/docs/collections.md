# Collections

**OneCalendar owns no doctypes.** It is a merge first and a store second, and
the store is Frappe's `Event` — the row a workspace already has for "a thing in
somebody's diary". A doctype of our own would have been a second place a
meeting could live and a migration for every workspace that had already put one
in `Event`.

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `Event` | Frappe core | The reader's own entries: the ones with nowhere else to live. Theirs means owned by them **or** naming them in `Event Participants`. |
| `Event Participants` | Frappe core | Read, to answer the second half of "theirs". Nothing in the product writes it yet — see the README's item 2. |
| *Everything a screen declares* | Every space | Not a doctype this module names. A screen with a calendar view contributes its rows, resolved through the screen's own path. |

That last row is the design. The merge does not hold a list of doctypes; it
holds a list of **screens the reader can open that declare a calendar**, and
what is on the grid follows from what is in the manifests.

## What a source declares

On a screen's calendar view settings:

    about     a filter fragment saying whose a row is, in the same shape a
              screen's own `filters` take — `{"employee": "@me:employee"}`
    diary     whether this source belongs in somebody's *week* as opposed to
              in a record's own calendar

`about` is resolved by `onespace/mine.py`, the same resolver that narrows a
twin screen, so "my leave" asked here cannot come apart from **My leave** asked
as a screen. Two spellings earn their own handling: `_assign` becomes the
`like` Frappe's own "assigned to me" is, and `Interview Detail.interviewer`
asks about a person named in a child table rather than on the document.

## A record's calendar is declared nowhere

A project's month, an employee's, a client's — there is no manifest key for it
and there will not be one. The record shell already says which screens are
about one of these and which field points back, as the showcase's tabs and the
connections the engine derives beside them. A record's calendar is that list
read as a calendar, so a manifest that gains a tab gains a calendar with it.
