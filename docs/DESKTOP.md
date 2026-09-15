# The desk

`docs/SHELL.md` built one shell out of nine arcs. This is the second thing that
happened to it, and it is not a tidying: the product stopped being one app with
a rail down the side and became a **desk** you keep several things open on.

Three pressures, and they arrived together.

**The apps stopped being places.** OneMail, OneCloud, OneAI and the six after
them are not screens of a space — they are things you need *while* doing
something else. Answering a mail should not cost you the payroll run you were
halfway through, and today it costs you the whole content area. The assistant
already solved this for itself, in one component, with its own drag and its own
resize and its own remembered corner: `AssistantWidget`. Nine apps each solving
it again is the shape F1 refuses.

**The pane stopped paying for itself.** A record beside its list was the right
answer when a record was a form. It is the wrong answer now that a record is a
*page* — a person with a face and a photograph, a day of attendance drawn as a
day, an opening drawn as a funnel. Every one of those has to survive being
480 pixels wide, and the honest choices are pixel-perfect responsiveness for
every bespoke page forever, or one width. One width.

**But the pane was doing a real job**, and dropping it without replacing that
job is how this goes wrong. The job is: mark this one done, glance at the next,
come back. That is not "two things side by side", it is **getting back to the
list without losing it** — and the list is already named in the breadcrumb.

## The four decisions under all of it

**A window is the unit.** One shell — drag, resize, maximise, close, remembered
size and position — and everything that is not the page you are on is a tenant
of it. The dock's apps are windows. A picture-in-picture list is a window. The
assistant is a window, and it is the one that already exists: this arc extracts
what it does rather than inventing it. Two overlay mechanisms would be two sets
of behaviour to learn and two to keep honest.

**The breadcrumb is how you get back.** Today a record replaces the trail:
`🏠 / Employees / List` becomes `🏠 / Ahmad`, and the list you came from is
gone from the page and from the address. It becomes `🏠 / Employees ▾ / Ahmad`,
where the crumb is a *control*: press it and the list you came from opens in a
window, exactly as it was — its view, its filters, its scroll — and picking
another row navigates the page underneath. The pane's job, done by the thing
that was already naming the place.

**A link is the same gesture.** A Link field on a record opened a drawer over
the page. It opens the same window, over the same list, with the same picker —
so "open the thing this points at" is one behaviour in the product instead of
two that look alike. What the window holds is a *preview*: read-only, one
control, and that control is the way out to the record's own screen. A window
is something you consult or pick from, never something you work in — stage 5
has the argument.

**The dock is a place, not a menu.** A row along the bottom, the same standing
as the bar along the top: what is installed, what is open, what is asking for
attention. An app opens windowed and can be maximised, which is the answer to
"is Mail a page or a window" — it is a window, and maximised it is the width of
a page. There is no second layout.

## What this costs, said plainly

**Every bespoke page stops having to be responsive to a pane.** That is the
saving, and it is most of the argument.

**Every app that is currently a route becomes a window tenant.** Mail, Drive,
the diary, the sheet and the document editor each draw their own chrome
assuming they own the content area. Maximised they still do; at window size
they have to fold. That is the work.

**Windows are session state, not URL state.** Position and size are remembered
per app, per person; *which* windows are open is not in the address. A pasted
link opens the page, not somebody else's desk. The assistant already behaves
this way and nobody has wanted otherwise.

**Mobile is deferred, not ignored.** A phone has no desk: there is no room to
put two things side by side and no pointer to drag with. So on a phone a window
is a full-height sheet, the dock is the row of surfaces the foot already draws,
and picture-in-picture is the same sheet. Nothing regresses, nothing is
pretended. The real phone pass is its own arc, after this one.

## The stages

Each is a commit, each leaves the product working, and each has a checkpoint
that is a screenshot rather than a test count.

**1. The window shell.** *Done.* Extract what `AssistantWidget` does into a
component and a store: one window, with a title bar, drag, a resize grip, maximise,
close, and size and position remembered per tenant. The assistant becomes its
first tenant and loses its own copy of all of it. Nothing else changes.
*Checkpoint: the assistant behaves exactly as it did, and its widget file is
half the size.*

**2. The dock.** *Done.* The row along the bottom: the apps this workspace
holds, the ones it does not (dim, with the reason — `apps.js` already knew),
and what is open, with a shelf at the other end for what is true right now —
the clock, and the weather after it. One press opens; one more on the window in
front folds it away; one on a window behind raises it. It sits under the page
rather than across the whole window: the column keeps its own foot, because the
quota meter, you and the bell are not places you go, and a dock spanning the
sidebar put two stacks of chrome in one corner. The apps moved off that foot. The assistant's own
64px mark in the opposite corner went with them — two permanent marks in two
corners meaning nearly the same thing — and with it the sixty pixels every list
footer and the notes rail had been reserving to keep clear of it. The desk
became the viewport *less* the dock, so a window filling it never covers the
tile that folds it away.

**3. Picture in picture.** *Done.* The breadcrumb becomes
`🏠 / Employees ▾ / Ahmad`, where the middle is a control rather than a crumb:
pressing it opens the list it names in a window, and picking a row there
navigates the page under it.

Restored exactly, and by not restoring anything. The obvious build is a second
screen host inside the window, re-resolving the screen and re-fetching with the
same filters — and it is wrong the way a copy is always wrong: the filters would
be the ones last *saved* rather than the half-typed search and unsaved narrowing
somebody actually has, and the scroll would start at the top. `ScreenHost`
already keeps its list mounted behind an open record (`v-show`, not `v-if`), so
the window does not draw a list: it is where that list is drawn, and a
`<Teleport>` moves it. Same component, same rows, same selection, no second
request. `lib/desk/pip.js` has the argument at length.

It also found a frozen `computed`: `Trail` decided whether to collapse the trail
by reading `useSlots()` inside one, which registers no reactive dependency — so
the answer was whatever was true on the first render and never changed. Opening
a record changes the query rather than the path, nothing re-keys the host, and
the screen's crumb went on being drawn under an open record for months. It only
looked wrong once the waypoint arrived beside it and the name appeared twice.

**4. The pane goes.** *Done.* `surfaces.js` collapses to two names and a
target: a record is a page. The resizable column, the manifest's default, the
remembered preference and the control that changed it are all gone, and so is
the second trail the bar drew exactly as wide as the pane. The drawer goes with
it — a record reached from another record opens in the same window the
breadcrumb does, which makes "open the thing this points at" one behaviour in
the product rather than two that look alike, and loses the scrim, which is a
gain: a drawer dimmed the record you opened it *from*.

**The Drive's pane stays**, and this is the one place the stage is narrower than
its title. The argument against the pane is that a record is a *place* with a
bespoke page behind it and every one of those had to survive 480 pixels. A file
preview is not that: it is an image, a PDF, a sheet — content that reflows at
any width by being what it is, which is the one case the argument never applied
to. `ObjectPane` therefore keeps its third branch and the Drive is its only
caller.

It also forced the window layering question the drawer had already answered
once. A dialog portals itself to `body` at `z-50`, and a window drawn inside the
page loses to it however high its own z-index goes — so a Link peeked from
inside a create dialog opened behind the dialog that asked for it. The desk now
has a layer of its own, one element at the dialogs' depth, re-appended to `body`
whenever a window opens: the desk against everything else is settled by document
order, and the windows against each other by z-index inside it. A dialog opened
over a sitting desk covers it; a window opened from that dialog covers the
dialog.

**5. The record shell.** *Done.* A record is a page now, which is the moment
to ask what a page of it should be. Two things, and the second was built twice.

**The doctype's own tabs flatten into the rail.** They were a second strip
inside the first — Details, and then Address & Contact / Accounting / Tax
*inside* Details — which at page width was a row under a rail and in a window
was two rows stacked. The rail is upright precisely because a column does not
run out of room, so they go in it.

Grouped, though, and not as one flat list. A field group on this record and a
screen pointing at *other* records are different kinds of thing, and fifteen
undifferentiated entries is where "Address & Contact" sits beside "Invoices"
and you have to read both to tell which is which. So: "This record", then
"Related". A window and a phone keep the nested strip, because a row that is
already scrolling sideways cannot take seven more.

**Everything else is height, not width.** The first build of this was a 288px
sidebar holding the pipeline, the verbs and the meta — and a rail on the left
plus a sidebar on the right is five hundred pixels of chrome on a 1280-wide
window, which left the form four hundred and ninety. That is the pane's
arithmetic wearing a different coat, and the pane is the thing this arc spent
stage 4 removing. Built, looked at, deleted.

What replaced it puts each thing where its subject already is:

* **The pipeline is a band** under the trail — every state the document can be
  in, in order, the one it is at lit, and the steps available from it at the
  end of the row where the states are pointing. Forty-four pixels of height,
  no width, and nothing at all for a doctype that neither submits nor flows.
  Horizontal is also how anybody draws a pipeline. `docflow.state` gained the
  states before and after the current one, which is what makes it a pipeline
  rather than a status.
* **Unsaved changes are a bar**: how many, which fields, and Save and Discard —
  opening to what each one was and is about to be. Only while there is
  something to save, and it is now the only place Save is drawn.
* **Meta is a popover** off the line that names the record. It was a *tab*,
  which is the strangest of the three: not a place you go, but a paragraph
  about the thing you are looking at.

What that gives up is the multipurpose column — for charts, or whatever else
wants one later. It is worth giving up until something actually needs it: a
column that exists for the day something might want it is the drawer every
unplaced control ends up in.

It also forced the form's columns to be honest. The grid drew two or three by
`md:`, a question about the *viewport*, which was right for exactly as long as
a form had the page to itself. It is a container query now, and the widths are
measured rather than picked: a Sales Invoice declares "Is Rate Adjustment Entry
(Debit Note)", whose label lays out at 268px and does not wrap inside
frappe-ui's Checkbox, so the floor is 280 a column — 37rem for two, 57rem for
three.

*Checkpoint: open a submitted invoice and where it stands, what can be done to
it, and what is about to change are all readable without opening a menu or a
tab — and the form is wider than it was before any of this.*

**And then the window had to answer for itself.** A record shell this complete,
drawn inside a window over another record, asks a question the drawer never
had to: is the thing in the window a *record* or a *look at* one. Left as a
record it is three problems. Its own Link fields offer to peek their targets,
so a window opens over a window and the third thing on screen is two removes
from what the page is about. Its band submits and cancels a document somebody
opened to glance at. And a form you can type into, inside a frame that closes
when you click past it, loses what was typed.

So: **a window holds something you consult or pick from, never something you
work in.** The record in one is read-only — fields disabled, no band, no verbs,
nothing that can become unsaved — and it draws exactly one control, which is
the door out to its own screen, where all of it works. One computed does it
(`canWrite`, which the form, the showcase, the meta and rename all already
read) and one injected symbol tells the Link fields four levels down to offer
the door and not the second window: `lib/screen/previewing.js`.

Two things followed from looking at it. **The door came off the chrome.** It
was an arrow-up-right on the title bar, one seat along from "Fill the desk",
which is a pair of arrows pointing up-right and down-left — two glyphs that
look alike, one changing the size of the box and the other changing what page
you are on, and nothing about either saying which. It is a labelled button at
the foot of the preview now, beside the sentence "A preview — read only",
which is also the answer to the reader who tries to type in here and wants to
know why they cannot.

**And the window draws the record the way the page does.** It was the one
place left drawing the nested strip stage 5 removed — Details / Payments /
Address & Contact under Details / Quotations / Payments, two rows of tabs
where the page has one grouped rail — because `upright` read "a desktop page,
and not a window". That was a guess about width dressed as a question about
surface. It measures now: a rail wherever there is room for the rail and a
column of form beside it (`RAIL + COLUMN + GUTTERS`, a `ResizeObserver` on the
record's own element, for the same reason the form's columns became a
container query). A page clears it at every width it ever had; the record
window, widened to 900 to make room, clears it; a window dragged to its 520px
minimum does not and falls back to the strip, which is the honest answer at
that width.

**And then it could have several.** The alternative considered first was a
window that *tabs* — press a link and it gains a tab rather than a layer — and
it was set aside as a browser's problem: hibernating what is not in front, and
deciding what the assistant thinks it is looking at when four unrelated records
sit behind one another.

Read-only took both away. `at` was always a stack and had only ever held one
peek; it holds as many as you open now. They share one corner, so every one but
the front is covered to the pixel, and only the front is *drawn* — which is the
whole of the hibernation, because a preview has no unsaved state to suspend.
What is kept is the fetched record, which is JSON and costs nothing beside a
mounted form, so raising one is instant rather than a reload with a blank frame
in the middle of it. And the view context is the page, because a preview is a
glance: one line of policy, no machinery.

The dock is the tab bar, which is the other half of why this is cheap — there
was nothing to build. A tile per preview, carrying the record's own face where
it has one and its initials where it does not, because five previews are five
records and one glyph drawn five times is a row you have to press to read. The
tiles are ordered by when they arrived rather than by the stack, or pressing
one would rearrange the row under the pointer that pressed it.

Two things had to become deterministic on the way. **Which window is in front
is the URL's answer**, not the network's: three peeks in a pasted address are
three fetches, and the first build let whichever *returned* last take the
front, so the same link drew a different window each time it was opened.
And **a window remembers its corner by family**, not by id — a corner per
record is a window that opens somewhere new every time you glance at a
different client.

**6. The apps become tenants.** Mail, Drive, the diary, the sheet and the
document editor open as windows and fold at window width. Their routes stay as
the maximised case, so a deep link still works.
*Checkpoint: Mail open in a window over OnePeople's payroll runs, both usable.*

**7. The phone answer.** A window is a sheet — already true, brought forward in
stage 4 because a peeked record was otherwise invisible there — the dock is the
foot's row, and the record's rail and sidebar fold to whatever a 390-pixel
column can hold. One pass over the mobile project of the browser suite.
*Checkpoint: the mobile suite is green and nothing on a phone is draggable.*
