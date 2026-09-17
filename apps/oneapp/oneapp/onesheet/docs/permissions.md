# Permissions

**OneWorkbook has no roles**, and one refusal is the whole of its permission
design.

## The permission is the `File`'s

Every read checks the `File` row: its own permissions, `is_private`, and
`DocShare` for what has been shared. A person who may read the sheet may open
it; a person who may write it may save it.

## `Sheet Book` has none of its own

It is granted to **System Manager only**, and every path into a workbook's
contents is one of this module's functions — `book.get_sheet`,
`reading.read_range`, `export.download`, `printing.printable` — each of which
checks the `File` first.

That is what stops *"a sheet is a `File`"* from being true of the identity and
false of the contents. Without it, a workbook's blob would be readable by
anybody who could name its row, and the row's name is not a secret.

## The named range is a permission boundary

**Everything outside it is private.** A document reads what a named range
offers, and the lookup tables, the scratch columns and the note the estimator
wrote to themselves are not in it. That is not a convention — `feed.py` reads
the rectangle and nothing else, so what a document can see is what somebody
chose to name.

It is also what makes a spreadsheet usable *as a spreadsheet* rather than as a
form with gridlines: a person can keep their working in the file without
publishing it.

## Locking is the one that protects a number somebody agreed to

`feed.lock` ends a feed, and **after it the document is the record**. A rate
edited at six o'clock must not move a number a customer accepted at three.

`unlock` exists, and it is a decision somebody makes rather than something that
happens. `locked_by` and `locked_on` are on the row so the decision has a name
against it.

## What a model may do

Nothing directly. `sheet.plan` answers with a plan; the **browser** applies it,
through the same `setCell`, `applyToRange`, `setColWidth`, `setFreeze` and
`pushEditOp` the toolbar uses. So the history records it as ordinary edits, a
colleague in the workbook watches it arrive, and the write happens under the
permissions of the person who asked.

The plan is validated here against the workbook that actually exists: a tab
that is not there is dropped, a style key nothing declares is dropped from its
step, and **a plan bigger than the store holds is refused whole**, because half
a plan applied is a workbook nobody asked for.
