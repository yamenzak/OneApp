# Notifications

**OneMobility ships no `ALERTS` rows**, and for this space that is a genuine
gap rather than a design — which makes it the one module whose notifications
page is mostly a list of what should exist.

## What the product does instead

**Status on the record.** `Transit Source` carries `status`, `last_run` and
`watermark`; `Transit Feed` carries `status`, `received_on` and `notes`. A feed
that failed says so where somebody maintaining feeds is already looking.

**Contested claims are a screen.** `conflicts.disagreements()` is a list of
what two sources disagree about, and resolving one is a person pressing accept.
A notification would only tell somebody that the list is not empty.

**The map is the alert.** `forecast.risk`, `bunching_risk`, `unusual` and
`faults` are read by a live screen. For an operator watching a network in real
time, a row appearing on the screen in front of them *is* the notice, and an
in-app notification beside it would be the product saying twice what it
already said once.

## What should exist, in order

1. **A source stopped delivering.** `every_minutes` and `last_run` are both on
   the row, so "this source has not answered for three intervals" is
   computable, and it is the one failure that silently degrades everything
   above it: the map keeps drawing, with older and older data, and nothing says
   so. To the Admin seat, which is the seat that can fix it.
2. **A feed arrived and parsed badly.** `lines_seen`, `stops_seen` and
   `trips_seen` are on the feed, so a delivery that dropped ninety per cent of
   its stops is visible in the numbers and nothing compares them to last time.
3. **A day is about to freeze.** `hot_days` passing means detail leaves the
   database, and a workspace that wanted to look at last month finds it in the
   bucket instead. `live.at` already says `frozen` and the screen already offers
   to bring it back, so this is a courtesy rather than a hole.

None is written. The first is the one worth writing.

## Why none of them is a manifest line

All three are **scheduled comparisons** rather than document events: nothing
happens when a source stops delivering, which is precisely the problem.
`ALERTS` rows hang off `doc_events`, so these need a job, and a job is code
rather than a declaration.
