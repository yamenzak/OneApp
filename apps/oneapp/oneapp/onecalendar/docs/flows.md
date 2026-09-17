# Flows

## Drawing somebody's week — `diary.agenda(since, until, lens)`

1. **The range is the query.** `since` and `until` are the days the grid is
   drawing, the same pair a screen-level calendar sends. A month assembled from
   whichever rows sorted first has holes in it, and a diary with holes is worse
   than no diary.
2. **`_sources`** lists every screen the reader can open that declares a
   calendar and is `in_diary`. Resolved through `spaceview`, so a space the
   reader cannot open contributes nothing and the permission argument is one
   argument rather than two.
3. **`_from_screens`** queries each one through the screen's own filtered path.
   A source that raises is skipped: one screen whose doctype was revoked
   between the manifest and the query is not a reason to take somebody's whole
   week away.
4. **`_own_events`** adds the reader's `Event` rows — owned by them, or naming
   them as a participant.
5. **`_once`** de-duplicates. The same record can arrive from two screens.
6. Each entry carries its **source** — `record` or `event` — which is what
   pressing it uses to decide where to go.

## The two lenses

**Mine** is the default, because a calendar opened on a Tuesday morning is a
question about your Tuesday. It keeps the reader's own events and every source
that can say which person its rows are about.

**Everyone** is the whole merge: who is off, which interviews are booked, what
lands this month.

**A source that cannot say is left out of Mine rather than guessed at.** That
is the safety property, and the failure mode of the alternative is concrete:
before the lens existed there was only Everyone, which for a manager is the
company's month and for everybody else was accidentally their own. A screen
that is already a twin — `@me` in its own filters — is personal without saying
anything, because it is nothing *but* personal.

## A record's own calendar — `diary.about(space_code, screen, name)`

Two things differ from the merge, and both follow from the question being about
one record rather than about somebody's week:

* It does **not** ask for `diary`. A timesheet does not belong in everybody's
  calendar and absolutely belongs in this project's.
* There is **no lens**. "Mine" over one record would be the reader's own rows
  about a thing they opened *because* it is not only theirs.

## Pressing an entry

A record goes to the screen it belongs to, on its own space. An event of the
reader's own opens for editing where it is, because there is no screen behind
it to go to. In the desk window, pressing an entry moves the page underneath —
which is not an oversight: a window over a quotation, and the entry that opens
the *next* quotation, is what a diary beside your work is for.

## Writing — `diary.save_event`

The only write this module makes. Four fields, into `Event`. Everything else on
the grid is written wherever it belongs.
