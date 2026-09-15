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
the roles a space defines are the space's, not the workspace's — OnePeople's
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
OnePeople and Books — which is what makes the board's first group read as a board
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
page and its route go. *Done.*

`onespace/one.py` is the whole of it, through the `onespace_space_providers`
seam the console already used — so nothing downstream learned a new concept.
`sync.state()` now *orders* the synced spaces and the provided ones together
rather than concatenating them, because a rail whose order depends on where a
space came from is a rail with a seam in it.

Its Home is three blocks and one call: what needs you, what is next, what you
had open. Not "which spaces does this workspace have" — the corner answers that
better than a page can, and nobody opens a tab in the morning to find it out. A
block with nothing in it is absent rather than empty, and the column count
follows the number of blocks, so two cards never leave a card-shaped hole.

The root redirects into One, `WORKSPACE` in `useCrumbs` resolves there, and a
space code nobody holds lands there too — excepting itself, or that is a
browser that navigates for ever.

**5. The dialog, dismantled.** Twenty-two tabs become tabs on a *page*: the
per-space ones onto each space's Configuration, the workspace's and your own
onto One's. *Done.*

The mechanism is four lines: a Configuration page's `screens` list may hold
`{"panel": "ai"}` as well as a screen name, `configuration._panel` turns that
into a tab if `tabs.may_open` admits this reader, and the page renders the
component `settings/panels.js` already mapped. No panel was rewritten. The map
moved out of the shell into its own module, which is what made it a second
caller rather than a copy.

Three of them are the *space's* rather than the workspace's — alerts, naming,
print formats — because all three are keyed on a doctype, so "this space's" is
exactly "the ones its screens show". `sync.granted_doctypes` takes a space code
now and the three endpoints pass one through. They are appended by the engine
rather than declared by a manifest, and `sync.configured` gives a Configuration
page to any space that did not declare one — so there is nowhere for them to be
missing from.

AI is the one that did not move, and it is worth saying why rather than
quietly leaving it: an AI feature belongs to an *app*, and nothing in a feature
says which space it is for. Until one does there is nothing to narrow it by.

What the move bought, beyond tidiness: every panel has a route. Twenty-two
panels and no way to link to one made every support answer "open settings, then
find Backups"; §C4 had bolted a `?panel=` onto whatever page happened to be
underneath, which was the right idea in the wrong place. `?screen=configuration
&tab=backups` is ordinary screen state.

**6. A home per space.** Each space's landing screen, drawn for the role
reading it. *Done.*

A space without one lands on whatever its first rail entry happens to be — a
list of somebody's records, usually not the reader's, sorted by when they were
made, and never the thing the person came to do.

The obvious build is a component per space and it is wrong twice over: a page
of bespoke queries that knows none of the columns, states or permissions the
space already declared, and no answer at all to "role-specific" short of a
role → layout table somebody maintains beside the roles themselves.

So a home is **blocks, and a block is a screen of this space** — the same trick
the Configuration page uses and a record's tabs use, for the same three
reasons. **Role-specific falls out of that**, which is the whole argument: a
block is dropped when the reader cannot open its screen, `navigable` already
narrows a space's screens to the seat, and where the difference is whose rows
rather than which screens the manifest names a `@me`-narrowed twin. Nothing in
`homepage.py` or `SpaceHome.vue` knows what a role is.

OnePeople keeps its own — it is genuinely more than blocks, and it is what showed
that a space needs a front page at all.

One thing a block needed that `RelatedRows` did not have: to be short. Five
rows and three columns, and the three *share* the width rather than keeping the
pixel widths the screen chose for a page — three of those in a quarter of one
add up past the block and clip the last column against its own panel.

**7. The quick dial and the foot.** The assistant's button and window, and the
footer's row of surfaces. *Done.*

The dial was the assistant's mark drawn small inside a washed disc, which is
what a flat glyph needs and what the new mark is not: a spectrum aperture with
its own edge and its own shadow, so a disc behind it was a second ring around a
drawing that already had one — and the whole thing read as a generic corner
button. The mark fills the face now, `AiFace` everywhere it appears, and
`--oneapp-ai-wash` is gone with the ring it painted.

The foot's real defect was not decoration: four identical glyphs and no mark of
where you were. Every other navigation in this product says so. It does now,
with the same raised chip the rail's own active item uses — a grey fill was the
first try and very nearly invisible, because the rail is grey too.

## What did not move, and why

Two of the settings the restructure was asked to make per-space stayed on One,
and both are here rather than left quiet.

**AI.** A feature belongs to an *app* — `@ai_feature("invoice.summary", …)` —
and nothing in a feature says which space it is for. The other three moved
because all three are keyed on a **doctype**, and a space has already declared
which doctypes it shows; there is no equivalent fact about a feature to narrow
by. The honest change is a space on the feature declaration, and then this
moves in an afternoon.

**Roles.** Granting is on One, which is the half that was asked for and the
half that is genuinely central: a person holds one set of roles across every
space they open. *Defining* is already per-space in the only sense a customer
meets — a space's roles come with the space and cannot be edited — and the
custom role builder stays on One because a role built out of OneCRM's screens
*and* OnePeople's is an ordinary thing to want and a space-scoped builder cannot
express it.
