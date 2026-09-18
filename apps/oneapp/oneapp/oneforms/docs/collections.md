# Collections

**This module owns no doctype.** Everything it touches is Frappe's, which is
the point: a form is a view over a table somebody else already has.

## Borrowed

| Doctype | What it is here |
|---|---|
| `Web Form` | the form. One row per door. |
| `Web Form Field` | its fields, a child table of the above. |
| `Web Form Request` | one recipient's key: an expiry, the values to pre-fill, and the documents that key may touch. |

## The field we add

`install.py` puts `custom_onespace` on `Web Form` — a read-only Check marking a
form this workspace made. Frappe ships two on every site and an app may install
more, and those are part of what that app *is*. Same field and the same
argument as the mark on `Notification`, `Assignment Rule` and `Email Template`.

## What a key holder's list reads

`Web Form.list_columns` — a child table this module fills rather than leaves
empty, because empty is not a default: Frappe falls back to the doctype's
list-view fields and resolves every Link in them against Guest, which throws.
Four columns, from the form's own plain fields.

## And the doctype a form is over

Any one `finding.placed` says this reader can already open. That is not a list
kept here — it is every screen of every space they hold, which is the only
answer that cannot drift from what the rest of the product shows them.

**`File`**, borrowed. What somebody attached to a form, written by
`attaching.py` rather than by `accept` — see `flows.md` for why — private, and
attached to the document the submission made.

**`Custom Field`**, written. One per doctype a form is made over —
`custom_web_form`, hidden and indexed — so a form can count what it collected.
And two on `Web Form` itself from `install.py`: the mark that says a form was
made here, and the six settings the Look panel reopens on.
