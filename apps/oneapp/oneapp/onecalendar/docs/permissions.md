# Permissions

**OneCalendar has no roles**, and it makes no permission decision of its own.
That is the design rather than an omission, and it is worth stating plainly
because a calendar is exactly the surface where a second permission model grows
by accident.

## Both sources are already permissioned

**Screens.** A source is a screen the reader can open, resolved through
`spaceview` and queried through the screen's own filtered path. A record
absent from that screen is absent here, for the same reason and by the same
code. There is no calendar-shaped shortcut around a grant.

**Events.** The reader's own `Event` rows: owned by them, or naming them in
`Event Participants`. An events *screen* shows the workspace's events; the
diary shows yours.

## The failure mode that is handled

A source that raises is **skipped, not fatal**. One screen whose doctype was
revoked between the manifest being read and the query running is not a reason
to take somebody's whole week away. The grid is drawn from what could be read.

## The one that is a safety property

**A source that cannot say whose a row is, is left out of Mine rather than
guessed at.** `about` is how a source says; a screen without it contributes to
Everyone and to nothing else.

The failure mode of guessing is concrete and was real: before the lens existed
there was only Everyone, which for a manager is the company's month and for
everybody else was accidentally their own — every interview in the company on
one person's Tuesday.

## What a reader may write

`diary.save_event`, four fields, into their own `Event`. Nothing else. Every
other row on the grid is written where it belongs, by the space that owns it,
under that space's seats.

## A record's calendar

Reached through `diary.about(space_code, screen, name)`, which resolves the
space and the screen before it reads anything — so a record in a space the
reader cannot open has no calendar to them. There is no lens here, because
"mine" over one record would be the reader's own rows about a thing they opened
*because* it is not only theirs.
