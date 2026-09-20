# The desk — what we rebuilt, and what we should not have

The question, asked plainly: *we have been reinventing the wheel. Frappe's desk
already ships sockets, follows, likes, view types, dashboards, reports, actions,
workflows, permissions, notifications, child tables, web forms — and it is
customisable by nature, database-driven, and updated every week. Why did we
write all of it ourselves?*

The answer is that the question is right about a fifth of the SPA and wrong
about the rest, and that the fifth it is right about is worth taking seriously
because it is the fifth we have spent the most time on.

## 0. The stages

| | | |
|--:|---|---|
| 1 | This document — measure both sides before moving anything | done |
| 2 | The desk becomes reachable at all, for us, behind a flag | |
| 3 | The operator console is tried as workspaces | |
| 4 | The verdict on the operator console, written here | |
| 5 | `frappe.watch` — what changed upstream since we last looked | |
| 6 | The borrowing guards: never rebuild what the framework ships | |
| 7 | Whatever stages 3 and 4 decide | |

Stage 1 is this document. Nothing else starts until it is read and argued with,
because the last three arcs each cost four to six weeks and this one would cost
more than all of them together if it were started from the wrong half.

## 1. What is actually in v17's desk, measured

Opened and counted rather than remembered, on the `develop` checkout in
`bench1` (`frappe 17.0.0-dev`):

* **`Dock`, `Dock Item`, `Desktop Icon`, `Desktop Layout`, `Desktop Settings`,
  `Custom Sidebar`, `Sidebar`, `Sidebar Item`, `Custom Workspace`.** These are
  new and they are, name for name, the shell that `docs/DESKTOP.md` stages 1 to
  6 built: a dock of apps, an icon per app, a layout the reader arranges, a
  sidebar per module. `Desktop Icon` even carries `logo_url` and `icon_type`,
  which is the custom-SVG registry the plan asks about.
* **`Workspace`** carries `charts`, `shortcuts`, `links`, `number_cards`,
  `quick_lists`, `custom_blocks`, `roles`, `restrict_to_domain`, `for_user`,
  `is_hidden`, `parent_page`. That is a manifest, stored in the database, with
  per-role visibility — which is what `spaces/*.py` is.
* **`User.block_modules`, `Module Profile`, `Block Module`.** Per-user module
  hiding, already there. The "tenants should not see infrastructure doctypes"
  half of the plan is a `Module Profile` per role, not a feature.
* **`Custom HTML Block`** is `html` + `script` + `style` + `roles`. The script
  runs with a `root_element`, so it can mount anything — Vue included, because
  the desk bundle already ships Vue. It is an escape hatch and a good one; it is
  not a place a product lives.
* **The form, list and report engines** are `frappe.ui.form.*` and
  `frappe.views.*` — 380 JS files under `frappe/public/js`, of which the form
  and list directories are 77 files of jQuery against `class.js`. 92 files
  across the whole desk mention Vue, and almost all of them are leaf widgets in
  `ui/`. The desk's spine is not Vue and is not going to be.

So the plan's premise is **better than it sounds** on the shell and **worse
than it sounds** on the spine.

## 2. Three things the plan assumes that are not there

**The theme picker is not a registry.** `ui/theme_switcher.js`'s `fetch_themes`
returns a literal array of `automatic`, `light`, `dark` and resolves it. There
is no hook, no doctype, no `frappe.ui.themes.register`. "Registering a new theme
in the picker" means replacing that file in our app — which is possible, and is
also the first file we would own a fork of, in the one place upstream changes
most often.

**`Website Theme` is the portal's, not the desk's.** The desk's colours are
`frappe/public/scss` variables compiled at build time. A tenant-chosen accent is
a CSS-variable layer we would write and maintain, which is `theming.py` again.

**Replacing a page we do not like is not free support.** Overriding the login
page or an error screen is `website_route_rules` and a template, which is
genuinely cheap. Overriding a *desk* page is shadowing a file in
`frappe/public/js`, and from then on every upgrade is a three-way merge on
somebody else's UI. That is the opposite of updates arriving for free.

## 3. The fact that decides most of it

**Frappe does not build products on the desk any more.** Every product they
have shipped since roughly 2022 — CRM, Helpdesk, Drive, Insights, Gameplan,
Builder, LMS, Writer, Sheets — is a standalone Vue SPA on frappe-ui, served at
its own route, using the desk's *backend* and none of its UI. We know this from
our own reading: `docs/DRIVE.md` §"what we take" is an inventory of Drive's Vue
components, `docs/WRITER.md` is about frappe-ui's editor, `docs/SHEETS.md` §"the
frappe-ui gap" is about their editor's frappe-ui version, and `docs/ONECRM.md`
is a study of a Vue record page.

The organisation that wrote the desk, that knows it better than anyone, and that
carries its maintenance cost, chose an SPA every time it had a product to build.
That is not a reason to copy them blindly. It is a reason to be suspicious of
the claim that the desk is the cheaper host for a product — because the people
best placed to know did not find it so.

The distinction they are drawing, and it is the right one: **the desk is a
generic UI over a schema, and a product is not a schema.**

## 4. What the desk would actually replace, in lines

The SPA is 109,114 lines of `.vue` and `.js`, excluding tests.

| | lines | would the desk host it |
|---|--:|---|
| `onespace/components/screen` + `lib/screen` — the list, record, field and view engine | 22,050 | **yes, and better** |
| `onesheet` — the spreadsheet | 35,130 | no |
| `onestorage`, `onedoc`, `onemail`, `oneforms`, `oneai`, `onemobility` | 22,800 | no |
| `onespace` shell, desk, windows, brand, narrowing | ~22,000 | partly — the dock and sidebar, not the windows |
| `shared/` | 14,534 | some |

So: **about 22,000 lines are a reimplementation of something the desk does, and
does more of.** Filters, sorting, saved views, bulk edit, the report view,
Kanban, the calendar, group-by, the column picker, `depends_on`,
`read_only_depends_on`, child grids, attachments, comments, assignments, tags,
likes, follows, the timeline. We have most of those and the desk has all of
them, plus print formats, the query report, and `Customize Form`.

And **about 58,000 lines are things the desk cannot host at any price** — a
canvas spreadsheet with its own selection and history, a rich-text editor with
collaboration, a file manager, a mail reader, an assistant, a public page a
stranger opens. `onesheet` alone is a third of the SPA.

That ratio is the answer. The rewrite would delete a fifth of the code and
rehost the other four fifths inside a chrome that was not designed for them.

## 5. What the "no desk" rule was actually about

`docs/ONEADMIN.md` §"No desk" and `tests/test_no_desk.py` are worth re-reading
before overturning, because the argument is narrower than the rule:

> the desk exposes the whole schema — every tenant's billing, every credential —
> behind a UI that was never designed to be a boundary, and "it is only for
> admins" stops being true the first time it isn't.

That is an argument about **the control plane**, and it does not weaken. An
operator with desk access to `control.localhost` can read every customer's
Stripe ids and every site's credentials, and no `Module Profile` makes a
role-based UI into a boundary — Frappe's own permission model is the boundary,
and the desk is simply a window onto whatever it allows.

It was then applied to the tenant product too, which is where it is arguable.
A tenant's desk exposes a tenant's own schema, which is their data. That is a
different claim and a much weaker one.

**So the rule should be split rather than kept or dropped.** No desk on the
control plane, ever, for the reason above. On a tenant site it is a product
question, not a security one.

## 6. What is worth taking, whatever else is decided

Four things, and none of them requires moving to the desk:

**`frappe.watch` — the upstream diff.** The plan's third bullet, and it is the
best idea in it regardless of the rest. A script that reads `frappe`'s git log
since a recorded sha, lists new doctypes, new hooks, new whitelisted methods and
new `frappe.*` client utilities, and fails a test when the record is stale. We
have been on `develop` for months and have never once asked what landed. `Dock`
and `Desktop Icon` are proof: we built both, upstream shipped both, and nobody
noticed either way.

**The borrowing guard.** A test that fails when we write something the framework
already ships. It cannot be general, so it is a list — and the list is worth
having even at twenty entries, because every one of them is a week. `docs/
FRAPPE.md` is already two thirds of this: it is 296 doctypes with a verdict
each, and what it is missing is the *client* side.

**The shell doctypes as our storage.** `Workspace`, `Dock`, `Desktop Icon`,
`Custom Sidebar` are a schema for exactly what `spaces/*.py` declares. Reading
our manifests out of those doctypes instead of our own — while still drawing
them ourselves — would mean a tenant can rearrange their own dock in a UI
Frappe maintains, and would delete the manifest storage without touching the
SPA. This is the cheapest real win on the list.

**`Module Profile` for the clutter.** The whitelabel half of the plan is a
configuration, not an arc.

## 7. The recommendation

**Do not move the product to the desk. Do move the operator console's
*question* there — as an experiment with a verdict written down.**

The operator console is the one surface where every argument in the plan is at
its strongest and every argument against it is at its weakest: it is generic
CRUD over our own doctypes, it has one user who is technical, it has no brand
to protect, it is where `docs/ONEADMIN-SIMPLIFICATION.md` already found twenty
of twenty-nine rail entries to be "a place to go looking for a problem", and it
is the smallest thing we could move. If the desk is as good as the plan says, a
week on that will show it plainly, and we will have learned it for the price of
a week rather than a quarter.

Except that the one reason the console is *not* on the desk is the security
argument in §5, which is real. So stage 3 is the experiment and stage 4 is the
verdict, and the verdict has to answer that argument or it fails.

Everything else in the plan — the upstream diff, the borrowing guards, the
shell doctypes, `Module Profile` — is worth doing now and does not depend on
the outcome.

## What this does not do

**It does not defend every line of the 22,000.** A good deal of the screen
engine is worse than the desk's and some of it is worse than it had to be. The
answer to that is to borrow harder from the framework's *client* library —
`frappe.model`, `frappe.perm`, the `depends_on` evaluator, `frappe.datetime` —
not to move house.

**It does not claim the SPA was obviously right at the time.** It was decided
before `Dock` and `Custom Sidebar` existed, and by someone who had not read the
desk carefully. Both of those are true and both are in the plan, correctly.

**It does not price the move.** Nobody should price a rewrite of 109,000 lines
from a document. Stage 3 exists so that the number comes from a week of work
instead of an argument.
