# One system

Every app in this product was built in its own arc, and each arc made the
locally right call. The result is a product where the same job is done four
ways: a list is a list except in Files where it is a `FileRow`, a date is
whatever the surface that printed it thought a date was, and an upload dialog
depends on which screen you started from. None of those were mistakes at the
time. All of them are now.

This document is the audit and the plan for collapsing them. It has three
parts and they are done in order:

1. **The areas** — the whole surface, divided so that nothing falls between
   two sections. Listed below with nothing in them.
2. **The audit** — each section studied against the real code, with evidence,
   and a verdict: what the one version is. Sections are filled in one at a
   time and each is committed as it lands, because this document is the
   memory of the work and a finding that lives only in a conversation is a
   finding that is lost.
3. **The synthesis** — cross-module consistencies the section audits could not
   see on their own, the staged plan that follows, and the guards that stop
   the next arc from re-diverging.

## How a section is audited

Each one answers the same five questions, in this order, and an audit that
skips one is not done:

- **What exists.** The components, composables and server reads that serve
  this job today, named with paths.
- **Where it diverges.** Every place doing the same job differently, with a
  file reference. Counted, not gestured at.
- **What the one version is.** The verdict. A single source of truth, named.
- **What it costs.** What has to move, what breaks, and what a caller has to
  change. There are no live tenants, so "the data model is wrong" is a
  *reason to change it*, not a constraint.
- **The guard.** The test that makes the divergence impossible to reintroduce.
  A rule with no test is a rule that lasts one arc.

## Two standing rules for the whole effort

**Centralisation beats convenience.** More routing, more indirection and more
declarations are an acceptable price for one place to fix a thing. The
question at every fork is not "is this easier here" but "where does the fix
land when this is wrong in six places".

**A rail is a guard plus a default.** Making the right thing possible is not
enough — it has to be the path of least resistance *and* the only one that
passes CI. Every verdict below ends in a guard for that reason.

---

# Part 1 — The areas

## A. Foundations

- **A1. The design language.** Tokens, radius, spacing, the type scale,
  colour, elevation, dark mode. What is guarded and what escapes.
- **A2. The component vocabulary.** The `@/ui` barrel, our own shared
  components, and every place that hand-rolled one of them.
- **A3. Copy and voice.** The register of UI text, the developer-facing
  sentences that leaked into the product, and the i18n surface.

## B. The data surfaces

- **B1. The list engine.** One grid, and every surface that re-implements it.
- **B2. Narrowing.** Filters, quick filters, search, sort, saved views —
  standard versus the per-app variants.
- **B3. Actions.** Row actions, document actions, bulk actions, screen
  actions: what exists, what is missing, what contradicts.
- **B4. Row and cell states.** Hover, focus, selection, the open row, drag.
- **B5. Fields.** Read-only, disabled, permlevel and dependency behaviour
  across the form, the dialog, the child table and the inline cell.

## C. Chrome and navigation

- **C1. Breadcrumbs.** One system, everywhere, including editors and settings.
- **C2. Placement doctrine.** Pane versus sidebar versus dialog versus inline,
  audited across every app.
- **C3. The shell.** Space switching, the launcher, the app switcher, the
  mobile shell, the rail.
- **C4. What lives in the URL.** Deep links, return-to, restored state.

## D. Cross-cutting behaviour

- **D1. Time, number and money.** One clock, one formatter, one doctrine about
  whose timezone a moment is shown in.
- **D2. Feedback.** Toasts, errors, confirmations, empty states, loading,
  optimistic writes.
- **D3. Uploads and attachment.** One picker, one queue, one preview.
- **D4. Mobile.** Breakpoints and what every surface does under them.

## E. The apps

- **E1. OneStorage.** The file surface, automated foldering per doctype and
  per document, mounting a doctype or a record over WebDAV, and the Files tab
  inside a record.
- **E2. OneDoc.** Its own space and a document experience that stands beside
  the ones people already use. Mobile.
- **E3. OneSheet.** The same, for a grid. Collapsed and hidden controls.
- **E4. OneMail.** Panes, the sidebar, and the walls of text.
- **E5. OneMobility.** The facet bar against the standard one, Protocols, and
  how its screens are framed.
- **E6. OneCalendar.**
- **E7. The workspace surfaces.** Account, settings, the operator console.
- **E8. AI.** The experience, the tenant's own assistant name and face, and
  where the product should feel like magic rather than like a form.
- **E9. OneCode.** Groundwork and rails only: a buildless SPA a tenant writes,
  hosts on their own R2 and wires into Frappe's webpage system, with the AI
  knowledge to write it.

## F. Synthesis

- **F1.** Cross-module findings.
- **F2.** The staged plan.
- **F3.** The guards and rails.

---

# Part 2 — The audit

*Sections are appended here as they are done.*

## A1. The design language

### What exists

Colour, radius and iconography are already single-sourced and already guarded,
and the guards work. There are **zero** raw Tailwind greys in the SPA — not one
`text-gray-500`, not one `bg-gray-100` — against 829 uses of `text-ink-*`, 158
of `bg-surface-*` and 190 of `border-outline-*`. Radius is a four-word
vocabulary (`rounded-4/6/7/full`, plus the `-none` side variants) enforced by
`tests/test_design_tokens.py`, which also refuses a class that emits no CSS and
an icon name built by string interpolation. Theming runs entirely through
tokens: there are **two** `dark:` utilities in the whole SPA, both in vendored
or sandboxed content.

So this section is not about a missing system. It is about four places the
system has a rule nobody wrote down, and one place it has no rule at all.

### Where it diverges

**Two type scales, and the difference between them is real.** Both are in
heavy use — 473 uses of `text-p-{xs,sm,base}` against 178 of
`text-{2xs,xs,sm,base,lg,xl,2xl,3xl}` — and thirty files use both. It looks
like duplication and is not. Read off the built CSS:

    .text-p-xs    12px / 1.6    .text-2xs   11px / 1.15
    .text-p-sm    13px / 1.5    .text-xs    12px / 1.15
    .text-p-base  14px / 1.5    .text-sm    13px / 1.15
                                .text-base  14px / 1.15

Same sizes, **different leading**: `text-p-*` is prose leading, `text-*` is
label leading. That is a good system. The problem is that the rule was never
stated, so the choice is made by whoever typed the class — and the result is
visible in the one number that matters most here:

**109 elements carry `truncate` and a `text-p-*` class at the same time.** A
paragraph leading on text that is declared single-line. 85 of them are in
`onespace`, 11 in `onestorage`, 6 in `onemail`. Every one of those rows is
about 4px taller than it should be and reads slightly loose. This is a large
part of why dense surfaces feel unresolved, and it is countable, mechanical
and guardable.

**Seven greys doing three jobs.** `text-ink-gray-3` through `-9` are all in
use, with 314 at `-5`, 201 at `-8`, 122 at `-6` and 79 at `-7`. Three roles are
actually being expressed — the thing you read, the thing beside it, and the
thing you only notice when you look for it — and `-6` versus `-7` versus `-5`
for the second role is a coin flip at the call site.

**Five elevations, no doctrine, and a guard that misses the commonest one.**
29 bare `shadow`, 6 `shadow-sm`, 5 `shadow-2xl`, 3 `shadow-lg`, 1 `shadow-xl`.
`test_shadows_pair_with_an_elevation_surface` checks that a shadowed element
sits on `surface-elevation-*` — a real rule, for a real dark-mode failure —
but its pattern is `shadow-(sm|base|md|lg|xl|2xl)`, so the 29 bare `shadow`
utilities, more than all the named ones together, are not examined at all.
And nothing anywhere says which surface belongs at which height, so a popover
and a floating bar can sit at different elevations for no reason but the order
they were written.

**Forty arbitrary values, and they cluster.** `h-[62vh]` three times,
`max-h-[70vh]` four, `max-w-[940px]` three, `w-[min(17rem,90vw)]` twice.
Those are not one-offs — they are an unnamed dialog-body height, an unnamed
reading measure and an unnamed popover width, each re-derived at the call site.

**A display face used once.** `font-display` appears on exactly one element,
against two self-hosted font files shipped to every visitor. Either it is a
part of the identity and is used where a name is meant to be looked at, or it
is dead weight on the critical path.

### What the one version is

**The type rule is a role rule, and it is written down.** `text-*` for a line
that cannot wrap — a label, a number, a chip, a button, a table cell, a crumb.
`text-p-*` for anything that may run to a second line — a description, a help
line, an empty-state body, a message. `text-2xs` gains a `text-p-2xs` sibling
or loses its callers; a scale with a hole in it is a scale people step outside.

**Three named ink roles, mapped onto the tokens once.** `--ink-primary`
(gray-8), `--ink-secondary` (gray-6), `--ink-muted` (gray-5), with gray-3/4/7/9
reserved for the specific cases that can argue for themselves. Callers ask for
the role.

**Four elevations with a name each**: flat, raised (a card), floating (a
popover, a menu), and over (a dialog, a toast, the selection bar). Bare
`shadow` retires.

**The clustered arbitrary values become tokens**: a dialog body height, a
reading measure, a popover width.

### What it costs

The type fix is 109 mechanical edits plus a rule in the design doc; nothing
moves. The ink roles are a token file plus a codemod over 736 call sites — the
risk is that a wrong role choice is invisible in review, so it is done per
module with a screenshot each. Elevation is ~44 edits. The arbitrary values are
a dozen. None of it touches behaviour, and none of it is blocked by anything
else in this plan, which makes A1 the right first stage: every later section
adds markup, and adding it against an unstated rule is how the 109 became 109.

### The guard

Four tests in `tests/test_design_tokens.py`, all of the same shape as the radius
guard that already works:

1. `truncate` or `whitespace-nowrap` may not appear in a class list that also
   carries `text-p-*`. This one is exact and catches the whole family of
   leading mistakes.
2. Every `text-*` size class is in the named scale, and every size class used
   has a sibling in the other family — no holes.
3. `shadow` unqualified is refused; only the four named elevations pass.
4. An arbitrary value (`[...]`) that appears in more than one file is refused —
   the second use is the moment it should have been a token.

## A2. The component vocabulary

### What exists

A generated barrel at `src/ui.js` re-exports 129 frappe-ui components, ESLint
refuses a direct `frappe-ui` import, and `tests/test_frappe_ui_usage.py` reads
the library's own declarations so an unknown prop or slot fails CI rather than
silently rendering nothing. There are about eighty frontend guards in total.
The discipline shows in the raw numbers: three `<table>` elements in 215 Vue
files, one `<a href>`, zero `<dialog>`, zero `role="dialog"`, four hand-written
spinners' worth of `<Spinner>` (all sanctioned). This is not a codebase that
hand-rolls buttons.

It hand-rolls *compositions*.

### Where it diverges

**The panel incantation, in 41 files.** `rounded-6 border
border-outline-gray-2 bg-surface-…` appears in forty-one files in nine
spellings that differ only in which surface and which padding:

    bg-surface-elevation-2        5      bg-surface-base p-4      4
    bg-surface-base               5      bg-surface-gray-1 p-3    3
    bg-surface-elevation-2 p-4    2      … and four more, once each

This is the single most duplicated markup in the product, it is the thing a
reader sees more than any other, and there is no component for it. Every new
panel is a fresh decision about padding and ground.

**Nine surfaces hand-roll a row list.** `<ListRow>` is used in nine files and
all nine are operator or account screens. Every product surface that shows
rows — Mail's thread list (`onemail/pages/Mail.vue`, a `RouterLink` v-for),
Drive's file list (`onestorage/components/FileRow.vue`), the notification feed,
the version panel, the role builder, the upload tray, the launcher, Attention,
the mobility kinds list — builds its own row out of a `v-for` and a
`hover:bg-` class. Seventeen files, counted. They disagree about padding,
about where the hover lands, about whether the whole row is the hit target,
and about what "selected" looks like. (What each one does differently is B4;
that they are seventeen separate implementations is this section's finding.)

**Twelve pickers.** `ColumnPicker`, `LinkPicker`, `IconPicker`, `RolePicker`,
`LanguagePicker`, `MarkerPicker`, `PivotFieldPicker`, `ColorPicker`,
`FilePicker`, `FolderPicker`, `TemplatePicker`, `RecordPicker` — 78 to 505
lines each, ~2,400 lines in total. They are all the same interaction: a
search box, a scrolling list of candidates, keyboard navigation, a choice, a
close. Four of them support keyboard navigation; the rest do not.

**Shared components with one caller.** `RecordPanel` is used in 3 files,
`SharePanel` in 2, `FileChat` in 2, `AiMenu` in 2, `SuggestionCard` in 2,
`RecordPicker` and `PresenceStrip` in 1 each. These were extracted into
`shared/` because they *look* general, and then the next surface that needed
the same thing built its own instead. A shared component with one caller is
not a shared component; it is a file in the wrong folder.

**Seventeen barrel exports are never referenced**, and four of them matter:
`PageHeaderTitle`, `PageHeaderBackButton`, `PageHeaderMobile` and
`PageHeaderMobileTitle`. The page-header family was adopted as a container and
its parts were re-implemented inside it — which is exactly the finding C1 will
land on from the other direction. `TimePicker` is unused too, which is one
reason D1 will find hand-built time entry.

### What the one version is

**`<Panel>`, and everything that is a bordered rectangle uses it.** One
component, props for ground (`base` | `raised` | `sunken`) and pad (`none` |
`tight` | `normal` | `loose`), the radius and the border built in and not
passable. Forty-one files lose a class list.

**One row.** frappe-ui's `List`/`ListRow` is the base, and above it one
`<Row>` of ours that fixes what every caller re-invents: the hit target is the
whole row, the hover is one class, the selected and open states are the same
two classes everywhere, the leading slot is an avatar-or-icon-or-nothing and
the trailing slot is meta-or-actions. Mail, Drive, notifications, versions and
the rest become callers. This is the component B1 and B4 both depend on.

**One `<Picker>`.** Search, list, keyboard, choose, close — with a `source`
that is either an array or an async loader, and a slot for how a candidate
renders. The twelve become twelve slot definitions and ~2,400 lines become
~400. `LinkPicker` keeps a thin wrapper because a Link field's source is a
doctype and that lookup is worth a name.

**Nothing lives in `shared/` until it has two callers.** The ones that do not
move back beside their caller; the ones that should have had two get their
second.

### What it costs

`<Panel>` is a day and touches 41 files with no behaviour change — the same
shape as A1, and it should ship with A1 for the same reason. `<Row>` is the
expensive one and is not really an A-section job at all: it cannot be designed
without B1's verdict on the list engine and B4's on states, so it is specified
here and built there. `<Picker>` is self-contained and can run in parallel
with anything.

### The guard

1. A class list containing `rounded-6` and `border-outline-` and `bg-surface-`
   is refused outside `Panel.vue`. Mechanical, exact, and it is the same
   pattern as the radius guard.
2. A `v-for` on an element whose class list carries `hover:bg-` or `divide-y`
   is refused outside `Row.vue` — that is the hand-rolled-list signature, and
   it caught all seventeen when written as a scan.
3. A component whose name ends in `Picker` must import `Picker.vue`.
4. A file in `shared/components/` with fewer than two importers fails. This one
   is unusual — a guard against premature generalisation rather than against
   duplication — and it is the one that stops `shared/` becoming an attic.
