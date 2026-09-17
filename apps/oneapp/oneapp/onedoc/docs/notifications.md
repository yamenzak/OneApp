# Notifications

**OneWriter ships no `ALERTS` rows and sends nothing itself.** Everything a
person hears about a document comes from OneCloud, because a document is a
`File` and the events worth hearing about happen to the file:

* **Shared with you** — `DocShare`, Frappe's own notification.
* **A note on it** — a `Comment`, so a mention reaches the person mentioned the
  way a mention anywhere else does.
* **Somebody else has it open** — the presence row in the header, which is the
  socket rather than a notification, and is right: it is information about
  *now*.

A second notice from this module about the same file would be two notices about
one thing.

## What is genuinely missing

**Nothing says a sent document has drifted.** A document with record fields in
it that has *not* been settled goes on asking, so a quotation that changed
means a letter that now reads differently from the one the customer holds. The
product's answer is `settle`, one press, and nothing reminds anybody to press
it.

The rule is "this document reads a record that has changed since you sent it",
and it needs a notion of *sent* that does not exist: mailing a document is
mailing a file, and nothing marks the file. Settling is the closest thing to a
send and is exactly the step somebody forgets.

That is the honest gap and the reason it is not one line in a manifest.
