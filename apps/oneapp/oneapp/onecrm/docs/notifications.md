# Notifications

OneCRM ships no `ALERTS` rows, and it has the one mechanism in the product that
does the job an alert would do badly.

## Answering is a state on the record, not a mail

`custom_answering` and `custom_settling` are the two states — waiting,
answered, late; open, settled, overdue — written by `answering.py` and read by
the list as a row state and by the screen as a tag.

That is deliberately not a notification. A promise about responding is a thing
a desk looks at all day, so it belongs **on the rows**, where a person scanning
their queue sees which three are about to go late. A mail saying "this one went
late" arrives after the fact, which is exactly too late to act on.

`answering.late_now` runs per clock and sweeps what has passed its deadline, so
the state is true without anybody opening anything.

## What would be worth sending, and is not

**The warning before, rather than the mark after.** "Three deals fall due in
the next hour, to whoever owns them" is the rule that would change what
somebody does, and it needs a scheduled job that knows how far ahead to look —
which is a setting on the target (`respond_within` minus a warning window) that
does not exist.

That is the honest gap. Naming it here rather than shipping the easy version —
a mail when a deal *is* late — is the decision: the easy version is a record of
failure sent to the person who already failed.

## What the space's manifest could carry and does not

A lost deal, a won deal, a quotation expiring. All three are one line in
`ALERTS` and none is written, because none of them is a thing somebody needs to
be *told*: the pipeline screen says so, and a desk that mails about every
transition is a desk whose mail gets filtered.
