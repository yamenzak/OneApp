# One shell

Nine arcs built nine products and one of them — the shell they all sit in —
was never built at all. It accreted. The corner is a switcher over whatever
`session.spaces` happened to hold; the apps that are not spaces are a list in
`nav.js` that grew an entry at a time; the front door is a page of cards
called Spaces that nobody has ever wanted to arrive at; and everything a
workspace configures lives in a dialog with twenty-two tabs that opens over
whatever you were looking at and has no address.

Every one of those was the right call when it was made and none of them is
now, for the same reason `docs/UNIFICATION.md` F1 gives: the abstraction was
built at the second caller and abandoned at the third. There were three
non-space surfaces and a list was fine. There are nine, and twenty-seven marks
in the design, and the ones this workspace does not have are simply absent —
so the product's own answer to "what else is there" is nothing at all.

This is the plan for the shell as one thing. Seven stages, a commit each, and
a checkpoint per stage that is a screenshot rather than a test count.

## The four decisions under all of it

**One is a space.** Not a special case beside the spaces, not a page above
them — a space, in the same list, with the same rail, the same screens and the
same Configuration. What makes it the standard one is only that every
workspace has it and it is where the things that belong to no other space
live: your profile, the workspace's own settings, who is in it and what they
may do. A shell whose front door is a *space* has one kind of destination
instead of two, which is what kills the Spaces page: you no longer arrive
somewhere in order to choose where to go.

**A space configures itself.** AI, alerts, print formats, naming series and
the roles a space defines are the space's, not the workspace's — OneHR's
alerts have nothing to say to OneCRM and a single Alerts tab listing both is a
tab you scroll. They move onto each space's own Configuration screen, which
already exists and already does exactly this job for its tables
(`onespace/configuration.py`). What stays central is the part that genuinely
is: *which people hold which roles*, which is One's.

**Configuration is not an admin surface.** The dialog was only ever offered to
admins because a member opening it would have been refused by every tab, and
`onespace/tabs.py` fixed that half by declaring an audience per tab. The other
half is this: a Configuration screen is a screen, so it is narrowed by the
same permissions as every other screen, and a person who may edit a leave type
should reach it the way they reach a leave application. The audience decides
what is *in* the page, never whether the page exists.

**Every app is in the switcher, including the ones we have not built.** The
design names twenty-seven and the product ships nine. Hiding the other
eighteen is not modesty, it is the same mistake as hiding a facet that cannot
be used: F1's third finding says the honest answer is to show it, disabled,
with the reason. So the board shows the set, the ones this workspace holds are
live, the ones we have not built say so, and the ones an admin could add link
to where they are added.

## The stages

**1. The mark set.** Twenty-seven marks out of the new design page, replacing
sixteen. The page draws them in code now rather than holding them as literals,
so the generator runs the page instead of parsing it. Checkpoint: the contact
sheet, 64px and 20px, on both grounds. *Done.*

Four spaces gained the mark they had always been missing — OneProject, OneCRM,
OneHR and Books — which is what makes the board's first group read as a board
rather than as a row of initials.

**2. The app catalogue, and 3. the switcher.** Done together, because they are
one thing seen twice: the catalogue is what there is, the board is the drawing
of it, and building either without the other would have meant building the
board twice. `modules/onespace/lib/shell/apps.js` is the whole declaration —
mark, name, how it is reached, and a `live` predicate per built app — and
`useApps()` turns it into four states. `nav.js` keeps `useNav()` and reads its
`surfaces` from there, so the rail, the phone's More sheet and the board are
three renderings of one list. *Done.*

Four states, and the third is the one that did not exist before:

    here   this workspace has it and you may open it
    off    built, and not switched on here — no address, no assistant
    add    a space this workspace could have, and you may add one
    soon   drawn, not built

`to` being null is the whole of "you cannot press this", so a dim tile is a
plain element rather than a link that refuses, and it carries the reason as its
title. Two marks are off the board and `tests/test_marks.py` makes adding a
third cost an argument: **One** is the shell you are standing in, and
**OneAdmin** is ours.

**4. One, the space.** One arrives as a real space with a rail; the Spaces
page and its route go. Checkpoint: signing in lands somewhere that is work.

**5. The dialog, dismantled.** Twenty-two tabs become screens: the per-space
ones onto each space's Configuration, the workspace's and your own onto One's.
Checkpoint: every tab reachable by address, and the dialog gone.

**6. A home per space.** Each space's landing screen, drawn for the role
reading it — OneHR already has one and it is the shape the rest copy.
Checkpoint: the same space, opened by two people, showing two pages.

**7. The quick dial and the foot.** The assistant's button and window, and the
footer's row of surfaces. Checkpoint: both, on a phone.
