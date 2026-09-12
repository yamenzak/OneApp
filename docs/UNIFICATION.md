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
