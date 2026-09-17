# Notifications

**OneCloud ships no `ALERTS` rows.** What reaches a person about a file comes
from two mechanisms it does not own, and one gap it should close.

## Frappe's, unchanged

**Sharing** goes through `DocShare`, so a person shared with gets the
framework's own notification, in the same feed as everything else shared with
them. Writing a second notice here would be two notices about one event.

**A note on a file** is a `Comment` (`chatting.py`), so a mention in one
reaches the person mentioned the way a mention anywhere else does.

## The quota, which is the control plane's

Running out of storage is a fact about a tenant's plan, so the warning belongs
to the control plane rather than to an alert on a tenant site. `quota.py` and
`limits.py` are what a tenant reads; `docs/ONEADMIN.md` is the other side.

## The one that should exist and does not

**The bin sweep gives no warning.** `custom_trashed_on` plus thirty days, and
on the thirtieth day the file and its object are gone. Nothing tells the person
who binned it, or the owner if those differ, that a deletion is coming.

Thirty days is long enough that this is not urgent and exactly long enough that
nobody remembers. The rule is "files you binned go for good next week", weekly,
to whoever set `custom_trashed_on` — a scheduled job rather than a `doc_events`
hook, which is why it is not one line in a manifest.

## What deliberately sends nothing

**A remote folder going unreachable.** `Remote Folder` records `status`,
`last_checked` and `last_message`, and the rail shows it. Mailing about it would
be mailing about somebody else's server being down, which is usually a thing
they already know and always a thing we cannot fix.
