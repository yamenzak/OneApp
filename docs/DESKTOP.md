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
two that look alike.

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

**1. The window shell.** Extract what `AssistantWidget` does into a component
and a store: one window, with a title bar, drag, a resize grip, maximise,
close, and size and position remembered per tenant. The assistant becomes its
first tenant and loses its own copy of all of it. Nothing else changes.
*Checkpoint: the assistant behaves exactly as it did, and its widget file is
half the size.*

**2. The dock.** The row along the bottom: the apps this workspace holds, the
ones it does not (disabled, with the reason — `apps.js` already knows), and
what is open. Clicking opens a window; clicking an open one raises or
minimises it. The quick actions move off the sidebar's foot and onto it.
*Checkpoint: OneAI opens from the dock and the foot has stopped being a menu.*

**3. Picture in picture.** The breadcrumb becomes `🏠 / Employees ▾ / Ahmad`
and the crumb opens the list it names in a window, restored exactly — the view,
the filters, the scroll. Picking a row navigates the page under it.
*Checkpoint: open a person, press the crumb, pick the next person, and the
window is still there with the same filters.*

**4. The pane goes.** `surfaces.js` collapses: a record is a page. The drawer
goes with it and a Link field opens the same picture-in-picture window. Every
spec that asserted a pane, a drawer or a resize is rewritten to assert the
window.
*Checkpoint: the record is the width of the window everywhere, and no spec
mentions a pane.*

**5. The apps become tenants.** Mail, Drive, the diary, the sheet and the
document editor open as windows and fold at window width. Their routes stay as
the maximised case, so a deep link still works.
*Checkpoint: Mail open in a window over OnePeople's payroll runs, both usable.*

**6. The phone answer.** A window is a sheet, the dock is the foot's row, PiP is
the sheet. One pass over the mobile project of the browser suite.
*Checkpoint: the mobile suite is green and nothing on a phone is draggable.*
