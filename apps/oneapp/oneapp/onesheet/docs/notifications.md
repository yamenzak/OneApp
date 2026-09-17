# Notifications

**OneWorkbook ships no `ALERTS` rows and sends nothing itself.** A sheet is a
`File`, so sharing and notes reach people through OneCloud and Frappe's own
notification, and a second notice here would be two about one event.

## What is deliberately silent

**A plan being applied.** The grid applies a model's plan through the same
calls the toolbar uses, so a colleague in the workbook **watches it arrive**
over the collaboration relay. That is the notification, and it is the right
one: it is information about now, to the people for whom it is now.

## The one that would be worth having

**A locked feed being unlocked.**

`feed.lock` is the moment a document stops following a sheet, and it exists
because a rate edited at six o'clock must not move a number somebody agreed to
at three. `unlock` undoes exactly that protection.

It is already a decision somebody makes, with `locked_by` and `locked_on` on
the row — but nothing tells the person who *locked* it that somebody else has
unlocked it, and that is precisely the person who has a reason to care. The
rule is "a feed you locked was unlocked by somebody else", to the locker, on
unlock, which is a `doc_events` hook on `Sheet Feed` and a line in the space
manifest that owns the record being fed.

It is not written because the feed's record belongs to whichever space declared
it — a Quotation is OneCRM's — and the rule therefore belongs to that manifest
rather than to this module. Naming it here is the honest way to leave it.
