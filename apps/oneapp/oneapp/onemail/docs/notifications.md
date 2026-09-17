# Notifications

Mail is the notification, mostly — but this module does own three mechanisms
that decide what reaches a person, and one of them is the workspace's own.

## `Mail Rule` — the workspace's own filing

One condition, one destination: `field`, `operator`, `matches` → `into`, plus
`mark_read` and `star`. `priority` orders them.

It is a rule a **person** writes about their own mail rather than an alert a
manifest ships, which is why it is a doctype here and not an `ALERTS` row
anywhere. `rules.py` applies them on arrival.

Marking a rule `mark_read` is the one way a message can arrive without
anybody's unread count moving, and it is the workspace's decision to make.

## Out of office

Also `rules.py`. An auto-reply is the one thing this product sends without a
person pressing send, which is why it is in the same file as the rules and
under the same gate.

## Unread, which is per person

`seen` is a custom field and **not** a doctype, because a table with a row per
person per message would exist to answer a question only that person ever asks.
`mailbox/flags.py` is the whole of it. Two people on `sales@` each have their
own count, which is the thing Frappe's per-document `Communication.seen` could
not do.

## What this module does not send

**No `ALERTS` rows.** A message arriving is not a notification about mail — it
*is* mail. A second notice saying "you have mail" beside the mail would be the
product telling somebody something the screen in front of them already says.

**Nothing about a bounce.** `suppression.py` stops sending to an address that
bounced, and the sender finds out by the message being in their sent folder
with a suppression against the recipient. That is thin, and it is the honest
gap: the rule worth writing is "a message you sent could not be delivered", to
the sender, on suppression — one `doc_events` hook, and it is not written.
