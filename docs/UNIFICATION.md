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

## A3. Copy and voice

### What exists

`tests/test_ui_copy.py` reads every string the browser can show in both SPAs
and every message the server throws, and refuses twelve words of plumbing
vocabulary — `doctype`, `fieldname`, `permlevel`, `payload`, `hmac`,
`whitelisted` and the rest — each mapped to what to say instead. It also
refuses naming our suppliers on a customer screen and telling a customer to
wait for a sync. The operator console is exempt from the vendor nouns and
nothing else. The guard is explicit that it is a spelling test and not a style
test.

It works. Sampling the prose, the register is right: plain, second person, no
jargon. *"Files are not in these copies. They are kept as they are, and a
restore matches them back up with the records that own them."* is a good
sentence.

### Where it diverges

**The problem is volume, not register.** 2,608 visible strings; 68% are three
words or fewer and only 21 run past 25 words. So there is no epidemic of long
sentences. What there is, is *stacking*:

    BackupSettings.vue     209 words in 12 explanatory strings
    BooksSettings.vue      160 in  8
    Marketplace.vue        159 in  8
    account/Overview.vue   156 in  7
    StorageSettings.vue    150 in  6
    AiSettings.vue         148 in 11
    Outlook.vue            131 in  8

Every individual sentence on those screens passes review. Twelve of them
stacked down a settings panel is a manual, and a reader who wanted to change
how often a backup is taken has to read an essay to find the control. No rule
anywhere says how much prose a screen may carry, so each sentence was added by
somebody who was right that *that* sentence was worth having.

**Protocols is the extreme case and it is worse than it looks.** The screen
renders `vdv.coverage()` — 22 part titles, 13 notes and a per-door
explanation, about 400 words of server-written text laid out as cards. It is
also, as the user put it, not clear what it is *for*: it is a capability
statement ("do you read 457-3") wearing the clothes of a feature list, on a
rail beside Sources and Deliveries, where a reader reasonably expects to
configure something.

**206 English sentences are shipped from the server outside the translation
system**, across 60 Python files, and they divide in two:

- ~21 are AI prompts and tool descriptions — `chat/toolbox.py`,
  `ai/proposing.py`, `ai/text.py`. These are *correctly* English: they are
  addressed to a model, not a person. But nothing marks them as such, so they
  are indistinguishable from the rest by any tool.
- The other ~185 are genuine UI text. `onespace/workspace.py` alone carries 16
  — they are the help lines under the branding and sign-in settings, shown to
  an Arabic reader in English. `notifications.py` has the 7 notification-type
  descriptions. `onemobility/sniff.py` has 8 refusals a user sees when a feed
  will not load. `vdv.py` has 6.

**The control plane is extracted and never translated.** `oneapp_control` has
a `main.pot` and no `ar.po` or `de.po`, against 212 `_()` calls. The operator
console is English-only by accident rather than by decision.

### What the one version is

**A prose budget, enforced.** One line of orientation per *screen*, one line
of help per *control*, and a hard ceiling — twenty words for a help line,
forty for a screen's orientation. Anything longer is not deleted, it *moves*:
behind an info affordance on the control it explains, or into the docs. The
sentence that explains what a restore does to files is a good sentence in a
popover and a bad one as the fifth paragraph of a panel.

**Protocols becomes an answer, not a page.** It is a capability statement, so
it belongs where the question is asked — a "what can this read?" panel on the
Sources screen and in the new-source flow, showing the parts relevant to the
folder in front of you, with the full shelf a click away. Not a rail entry.

**Server text is classified at the call site.** Two markers, not one: `_()`
for anything a person will read, and a distinct `prompt()` (an identity
function that exists to be greppable) for text addressed to a model. Then
"English sentence in server code that is neither" is a mechanical failure.

**The control plane gets ar and de**, on the same pipeline as the tenant app.

### What it costs

The budget is the expensive one, because it is a rewrite of seven screens and
a judgement call on each sentence — and it is the one the user asked for
first, so it is worth the time. Reclassifying server text is mechanical:
~185 `_()` wraps, ~21 `prompt()` wraps, then the POT and two locales.
Translating the control plane is one pass of the existing `i18n.py gap`
workflow. Protocols moving is small and is really an E5 job; it is named here
because the *reason* it is wrong is a copy problem.

### The guard

1. A visible string longer than 20 words fails unless the file is a docs page
   or the string is inside a popover component. (The current 21 offenders get
   fixed first; the guard then holds the line.)
2. A file may carry at most 60 words of prose across strings of 9 words or
   more. This is the stacking rule, and it is the one that would have stopped
   BackupSettings at four paragraphs instead of twelve.
3. An English sentence of five words or more in a Python string literal must
   be inside `_()` or `prompt()`. The 206 become zero.
4. Every app with a `main.pot` has a `.po` for every shipped locale, fully
   translated — `test_i18n.py` extended to `oneapp_control`.

## B1. The list engine

### What exists

Two components and seven composables, and they are well made. `RecordTable`
(569 lines) is the mechanics — tracks, a sticky header, pinned columns, one
scroller for both axes, edges that say there is more, windowing past a few
hundred rows — and it knows nothing about what a cell contains or what a row
click means. `ListBody` adds the semantics. `ChildTable` is the second caller,
so the grid inside a record and the grid on a screen are the same grid. That
split is right and should not change.

Around them, `ScreenHost` composes the rest: `ListSearch`, `QuickFilters`,
`FilterPanel`, `ColumnPicker`, `TallyMenu`, `ScreenActions`, `SelectionBar`,
`ListFooter`, `ViewSwitcher`, and eight view bodies. Between them these deliver
about fourteen capabilities.

### Where it diverges

**The engine is not an engine. It is one screen, decomposed.** Every list
composable has exactly one consumer:

    useRows        1     useBulkActions  1     useRowWrites  1
    useSorting     1     useListFollow   1     usePeek       1
    useSavedViews  2

and their signatures say why:

    useRows({ spaceCode, spec, payload, range, onChange })
    useSorting({ order, spec, onChange })
    useBulkActions({ spaceCode, spec, selection, payload, reloadRows })
    usePeek({ spaceCode, spec, route, router, reloadList })

Every one takes `spec` — a declared screen — and most take `spaceCode`. They
were extracted out of a 2,000-line `ScreenHost` during the "split the giants"
cleanup, which is a good thing to have done and is not the same thing as
building an engine. Nothing whose rows come from anywhere but
`frappe.client.get_list` against a declared screen can use any of it.

**So everything else built its own, and here is what each one has.** Fourteen
capabilities across seventeen surfaces:

| surface | row | sort | search | filter | cols | saved | virt | group | bulk | empty | load | page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| engine (ScreenHost) | table | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| child table | table | · | · | · | ✓ | · | ✓ | · | · | · | · | ✓ |
| Drive | own | ✓ | ✓ | · | · | · | · | · | ✓ | ✓ | ✓ | · |
| Mail threads | own | · | ✓ | · | · | · | · | ✓ | ✓ | ✓ | ✓ | ✓ |
| record Files tab | own | · | · | · | · | · | · | · | · | ✓ | ✓ | · |
| attachment gallery | own | · | · | ✓ | · | · | · | · | · | · | ✓ | · |
| Drive: linked | own | · | · | · | · | · | · | · | · | · | ✓ | · |
| notifications | own | · | · | · | · | · | · | · | · | ✓ | ✓ | · |
| versions | own | · | · | · | · | · | · | · | · | ✓ | ✓ | · |
| ops Attention | own | · | · | · | · | · | · | · | · | ✓ | ✓ | · |
| marketplace | own | · | · | · | · | · | · | · | · | ✓ | ✓ | · |
| role builder | own | · | · | · | · | · | · | · | · | ✓ | ✓ | · |
| launcher | own | · | · | · | · | · | · | · | · | ✓ | · | · |
| people | own | · | · | · | · | · | · | · | · | · | ✓ | · |
| calendar diary | own | · | · | · | · | · | · | · | · | · | · | · |
| upload tray | own | · | · | · | · | · | · | · | · | · | · | · |
| mobility calls | own | · | · | · | · | · | · | · | · | · | · | · |

Sixteen surfaces, sixteen implementations, and the column of ticks falls off a
cliff after the first row. Nothing outside the engine can sort by clicking a
header. Nothing outside the engine can save a view. Two surfaces can search and
they search differently. Drive is 1,080 lines plus a 300-line `FileRow`; Mail
is 1,094; both re-derive selection, the empty state, the loading state and the
bulk bar from scratch.

**Two of these gaps are user-visible bugs rather than missing polish.** A
person who has 400 files in a folder cannot sort them by size, because Drive's
header is a hand-built row with two sort links rather than table headers. A
person looking at a record's Files tab cannot select two attachments and
delete both.

### What the one version is

**`<DataList>`: the engine, with the screen declaration replaced by a source
contract.** The whole of what `ScreenHost` composes, behind one component, and
`spec` demoted from a hard dependency to one implementation of a
`ListSource` interface:

    ListSource = {
      load({ start, pageLength, orderBy, filters, search }) -> { rows, total, hasMore }
      columns()                 -> column set, or null to let the caller declare them
      identify(row)             -> a stable key
      capabilities              -> which of the fourteen this source honours
      actions(rows)             -> what can be done to a selection
    }

Four implementations ship with it: `DoctypeSource` (what `useRows` is today,
`spec` and all, so no existing screen changes behaviour), `FileSource` (Drive
and every attach surface, including a remote mount), `ThreadSource` (Mail), and
`StaticSource` (an array in hand — notifications, versions, Attention,
marketplace, people, roles, the launcher).

`capabilities` is the honest part. A remote WebDAV mount genuinely cannot count
its rows or sort them server-side, and a list that offers a sort it cannot
perform is worse than one that does not offer it. So the source declares what
it can do and `<DataList>` renders exactly that much — which is also what
turns "Drive has no sorting" from an omission into a decision with a reason
attached.

**Every one of the sixteen becomes a caller.** Drive keeps its grid/list toggle
(that is a view type, and it should become one of the engine's view types so
any list can offer it). Mail keeps its thread grouping. Everything else keeps
its slot for how a row renders and loses everything around it.

### What it costs

This is the largest single item in the plan and the one everything in B
depends on. Realistically: the `ListSource` contract and `DoctypeSource` are a
refactor of `ScreenHost` that must come out behaviour-identical — the existing
browser specs are the check, and they are good ones. `FileSource` is the
biggest win and the biggest risk, because Drive's tree, its drag and drop, its
remote mounts and its upload tray all hang off the current implementation.
`StaticSource` converts seven surfaces almost mechanically and should go first
as the proof that the contract is right.

Roughly 2,000 lines deleted, and every capability arriving everywhere at once
thereafter — which is the whole argument. Sorting Drive by size stops being a
feature and becomes a consequence.

### The guard

1. A `v-for` that renders something with a `hover:bg-` class is refused outside
   `Row.vue` (A2's guard, and this is the section that makes it satisfiable).
2. Every `ListSource` implementation is checked against the interface — the
   same shape as the existing manifest-property guard: a capability declared
   and not implemented, or implemented and not declared, fails.
3. A surface that renders more than five rows from an array and is not a
   `<DataList>` fails. Blunt, and the escape hatch is a declared exemption
   with a reason, which is the point: the next one has to be argued for.
4. The existing browser specs for list behaviour run against every source, not
   only the doctype one — one spec file, parameterised over the four.

## B2. Narrowing — filters, search, sort, saved views

### What exists

Four controls, all in `components/screen/views/`: `QuickFilters` (226 lines),
`FilterPanel` (140), `ListSearch` (75) and the saved-view menu inside
`ScreenHeader`. Behind them, `OneSpace Saved View` stores `space_code`,
`screen`, `filters`, `order_by`, `columns`, `page_length`, `group_by`,
`favourites`, `view_type` and `view_settings`. That doctype is well made and —
this is the important part — it is **already general**. It is keyed on a space
code and a screen slug, not on a doctype, so Drive could store a view as
`('', 'files')` tomorrow. The storage was designed for more than the one
caller it has.

### Where it diverges

**Two filter bars, and the newer one is better.** `QuickFilters` reads the
doctype's own `in_standard_filter` fields and draws a `Select` or a text box
per field in a bordered box. `onemobility/FacetBar` (100 lines) draws a
`Combobox` per facet as a subtle button that turns outline when set, with an
X beside each set one, a "Clear all", and a single sentence at the end naming
the facets this view cannot answer.

The FacetBar wins on three counts that matter: its options are **searchable**
(a `Combobox`, not a `Select` — the difference between usable and unusable at
forty lines), each facet clears **individually**, and a facet the underlying
table has no column for is shown **disabled with the reason stated once**
rather than silently missing. QuickFilters wins on one that matters more:
its source is the doctype's own metadata, so nothing is declared twice, while
the facet vocabulary is a second table in `onemobility/facets.py`.

So this is not "OneMobility went off-piste". It is two halves of the right
answer in two files.

**Three search boxes.** `ListSearch` is `w-32 sm:w-44`, carries a search icon,
debounces, and clears on Escape. Drive's is `w-28 sm:w-48`, has **no icon**,
fires on `@input` and does not clear on Escape. Mail's is its own again, with
a `/` shortcut to focus it — the only one of the three that has one, and the
best idea of the three. Two of 215 files handle Escape on a search box.

**Sorting exists twice and looks nothing like itself.** The engine sorts by
clicking a column header. Drive sorts through a dropdown of four named orders
(`ORDERS` → a Dropdown of `onClick`s). A person who learns one learns nothing
about the other, and no other surface sorts at all.

**Saved views have one consumer**, `ScreenHost`, despite storage that would
serve six. The things a person would most want to save — a Drive folder
filtered to images, sorted biggest first; a mail search — cannot be saved.

**Filters are expressed in four shapes.** The engine's `filters` JSON (Frappe
operator tuples); the facet bar's `{facetKey: value}` resolved server-side by
`facets.resolve`; Drive's ad-hoc query arguments; and Mail's own. Each is
reasonable alone. Together they mean a saved view cannot be moved between
surfaces and a filter cannot be expressed in a URL the same way twice.

### What the one version is

**One `<Narrow>` bar, which is the FacetBar's interaction over
QuickFilters' source.** A `Combobox` per field, subtle until set and outline
after, an X per set field, a Clear all, and one sentence naming what this
source cannot answer — with the fields coming from whatever the `ListSource`
offers: `in_standard_filter` for a doctype, `facets.offered()` for a fact
table, a declared list for Drive. The "unavailable, and why" mechanism
generalises exactly: it is `capabilities` from B1, rendered.

**One search box.** `ListSearch`, with Mail's `/` shortcut promoted into it
and Escape-to-clear kept. It goes wherever `<DataList>` goes, which is
everywhere.

**One sort.** Clicking a column header, everywhere — and where a surface has
no columns to head (a grid of file cards, a thread list), the same order menu,
drawn from the source's declared sortable fields rather than hand-listed.
Drive's `ORDERS` becomes `FileSource.sortable`.

**One filter shape, and it is the engine's.** Frappe's operator tuples are the
richest of the four and the only one with a server-side resolver already
written for arbitrary doctypes. The facet vocabulary becomes a *source of
field definitions* feeding that shape, not a parallel encoding: `facets.resolve`
keeps doing the fact-table translation, but what the browser holds and what a
saved view stores is one JSON shape.

**Saved views everywhere `<DataList>` is**, which the doctype already allows.

### What it costs

`<Narrow>` is a rewrite of `QuickFilters` with the FacetBar's markup, and
then the FacetBar is deleted — call it two days including the five mobility
screens. The single filter shape is the risky one: it changes what the mobility
screens send, so `facets.resolve` gains a translation layer and its tests have
to prove the same rows come back. Search and sort are small. Saved views
everywhere is free once B1 lands, which is the pattern for most of section B.

### The guard

1. `Select` is refused inside a filter bar — a filter control is a `Combobox`,
   because a list of forty options with no search is not a control.
2. Every search input in the SPA is `<ListSearch>`; a `FormControl` with a
   placeholder matching `/search/i` outside it fails.
3. Every `ListSource` that declares `sortable` renders the same sort affordance
   — asserted in the browser specs, parameterised over the four sources.
4. A filter value reaching the server is the engine's tuple shape. One schema
   check at the boundary, the same way manifests are checked.

## B3. Actions — row, selection, document, screen

### What exists

Two components with genuinely good doctrines written into them.
`RecordActions` renders whatever moves the document forward as one solid
button and everything else behind three dots, deciding which is which off the
next state's `doc_status` rather than off the word on it, and showing nothing
at all while the form is dirty. `ScreenActions` renders a space's declared
verbs, and its rule is that **every action appears in both places** — `scope`
says how many records a verb takes, not where its button lives, and a
single-record verb still appears in the selection bar, disabled until exactly
one row is ticked. Both of those are the right answers and neither should
change.

What is missing is a doctrine for the *other* actions — the ones nobody
declared, that every object has.

### Where it diverges

**A record's row has two affordances: open it, and heart it.** There is no row
menu anywhere in the engine list. Compare a file row, which right-clicks to
Rename, Move to a folder, Move to the bin, Share, and — in the bin — Put it
back and Delete for good. A record is the central object of this product and
a file is a supporting one, and the file has six row actions to the record's
one.

**You cannot delete a record you have open.** The open record's menu is Print,
Follow, Like, Duplicate, Copy link, Reload — that is the whole of `extras` —
and `RecordActions` only carries workflow and docstatus transitions. Delete
lives in the selection bar. So deleting one record is: close it, find its row,
tick the checkbox, use the bulk bar, confirm. This is not a missing nicety; it
is the single most common destructive verb being reachable only through the
multi-record path.

**Here is the whole parity table.** Rows are verbs; columns are the three
places a verb can live for a record.

| verb | row | selection | open record |
|---|---|---|---|
| open | ✓ | · | — |
| like | ✓ | · | ✓ |
| edit fields | · | ✓ (bulk) | ✓ |
| assign | · | ✓ | ✓ (control) |
| submit / cancel | · | ✓ | ✓ |
| print | · | ✓ | ✓ |
| export | · | ✓ | · |
| **delete** | · | ✓ | **·** |
| duplicate | · | · | ✓ |
| copy link | · | · | ✓ |
| follow | · | · | ✓ |
| share | · | · | ✓ (field) |
| rename | · | · | ✓ (Meta tab) |
| declared actions | · | ✓ | ✓ |

Three verbs are selection-only, five are record-only, and the row column is
almost empty. Nothing about the split is principled — it is which arc added
which verb.

**Files have the mirror-image problem, and their two menus disagree.** The row
menu says "Move to the bin", "Put it back", "Delete for good", "Rename",
"Move to a folder", "Share". The selection bar says "Bin", "Put back",
"Delete", "Delete for good", "Move". Same verbs, different words — *Delete*
in the selection bar and *Delete for good* on the row are the same action —
and Rename and Share are row-only, which is right for rename and wrong for
share.

**Mail has a third arrangement.** Archive, Delete, Unread and Star sit as four
icon buttons in a toolbar over the thread list, again on the open thread, and
Star also sits on each row. "Move to" exists only on the open thread. Reply,
Reply to all and Forward are in the reader. Nothing here is wrong, but a
person moving from Mail to a record list finds none of the geography
transfers.

**And the words differ for one action.** "Move to the bin" / "Bin" / "Move to
Trash" / "Delete" / "Delete for good" / "Delete {0}" are four distinct
destructive verbs for what a reader experiences as two ideas: put it where I
can get it back, and destroy it.

### What the one version is

**Three places, one rule, stated as: a verb that acts on one object appears
wherever that object is.** `ScreenActions`' own rule, generalised off declared
actions and onto the built-in ones. Concretely:

- **The row** gets a menu — three dots on hover, right-click anywhere on the
  row — carrying every single-object verb the source declares: open, duplicate,
  copy link, rename, share, follow, print, delete. Files, records, threads,
  files in a record's Files tab, all the same menu in the same place.
- **The selection bar** carries the same verbs where they make sense over many,
  plus the ones that only make sense over many (bulk edit, export). A verb that
  takes one object appears disabled with the reason, exactly as declared
  actions already do.
- **The open object** carries the same menu again, because closing something
  to act on it is the defect above.

**The verb list is the source's, not the surface's.** `ListSource.actions(rows)`
from B1 returns them; `DoctypeSource` returns the record set, `FileSource` the
file set, `ThreadSource` the mail set. One renderer, three vocabularies, and
the renderer is the same `Dropdown` in all three places.

**Two destructive words, product-wide.** *Move to the bin* for the reversible
one and *Delete for ever* for the irreversible one, on records, files, threads
and everything after. A confirmation only on the irreversible one — the
reversible one gets an undo toast instead, which is D2's business.

### What it costs

The row menu is the new component and is small once `<Row>` from A2 exists.
Wiring `actions()` into the three sources is a day each. The real work is
deciding the verb set per source and writing the missing endpoints — a record
has no rename endpoint outside the Meta tab, and share is a field control
rather than an action. Renaming the destructive verbs is a copy pass and
touches the toasts with it.

Record delete from the open record should not wait for any of this. It is four
lines and it is a bug.

### The guard

1. Every verb a source declares is rendered in all three places or explicitly
   marked `where: 'selection-only'` / `'row-only'` with a reason. The default
   is everywhere; the exception has to be typed.
2. No surface renders a destructive verb whose label is not one of the two
   sanctioned strings.
3. An irreversible verb has a confirmation; a reversible one has an undo. Both
   checkable from the action declaration, and this is the same guard D2 wants.
4. A browser spec per source: open the row menu, assert the declared verbs are
   there, in one parameterised file.

## B4. Row and cell states — hover, focus, selection, open

### What exists

Not much, and the gaps are larger than the divergences. This is the section
where the user's word — *horrible* — is the accurate one.

### Where it diverges

**The engine's list rows have no hover state at all.** There is not one
`hover:` utility in `RecordTable.vue` or `ListBody.vue`. Moving the pointer
down the product's central surface changes nothing. What *does* respond is
`EditableCell`, which greys the single cell under the pointer — so on a list
of records, the cell highlights and the row does not, which reads as the cell
being the thing you are about to act on when clicking it opens the record.

**`bg-surface-gray-2` means four different things.** It is:

    the open record            ListBody.vue:180  (with aria-current)
    the selected file          FileRow.vue
    the open mail thread       Mail.vue:96
    the current version        VersionPanel.vue
    …and the hover colour      in all of the above, and EditableCell

So in Drive, a hovered file and a selected file are the same colour. In Mail,
a hovered thread and the open thread are the same colour. In the record list,
a hovered cell is the same colour as the open row. One token is carrying
hover, selection and "you are here", which are three different statements, and
the only surface that distinguishes them does it with `aria-current` — which
is correct, invisible, and read by nobody using a mouse.

**Selection is a checkbox and nothing else.** A ticked row in the engine list
is identical to an unticked one apart from the box itself. `ListBody`'s own
comment says *"a person acting on four ticked rows while a fifth is open must
be able to tell the two apart at a glance"* — the comment is right and the
code only solves half of it: the open row is marked, the ticked rows are not.

**`focus-visible` appears once in the entire built stylesheet.** Tabbing
through a list, a board or a file grid shows nothing. The row is a
`RouterLink` or a `button` in most of the hand-rolled surfaces, so it *takes*
focus — and then says nothing about having it. Every hand-rolled row in A2's
list of seventeen has this, and so does the engine.

**Three hover colours and one of them is not a token.**
`hover:bg-surface-gray-2` (13 uses), `hover:bg-surface-gray-1` (3), and
`hover:bg-white` (1) — the last being raw Tailwind that slipped past the
colour guard, which checks greys and not `white`.

**Drag states are a fourth vocabulary.** `FileRow` uses `ring-2
ring-outline-gray-3` for a drop target and `opacity-50` for the dragged thing;
`BoardBody` uses `ring-2 ring-outline-gray-3` for a column under a drag and
nothing for the card. Two surfaces, two-thirds of an agreement.

### What the one version is

**Five states, five distinct treatments, one set of tokens, everywhere.**

| state | treatment | why not the others |
|---|---|---|
| rest | the surface | |
| hover | `--row-hover` — a *lighter* step than selection | it is a pointer, not a decision |
| focus-visible | a 2px inset ring in the accent, no background change | it must survive on top of hover, selection and open |
| selected (ticked) | `--row-selected` plus the tick | it is a set, and the set must be countable at a glance |
| open / current | a 2px leading edge bar in the accent, `aria-current` kept | it is one row, it is *where you are*, and it must be legible on top of hover and selection |

The key decisions are that **open is an edge, not a fill** — which is what
finally lets an open row also be hovered and also be ticked without three
fills fighting — and that **focus is a ring**, for the same reason.

**Cells do not hover in a row that hovers.** An editable cell gets its
affordance on the row's hover (a hairline border appearing on editable cells
of the hovered row) rather than a competing fill of its own.

**One drag vocabulary**: the lifted thing at 50%, the drop target with the
focus ring's token, and an insertion line where position matters.

### What it costs

Small, and disproportionately visible. It is a token file, five class sets,
`<Row>` from A2 applying them, and deleting the ad-hoc ones from seventeen
files. The one design decision worth taking care over is the accent for focus
and current: it must clear contrast on both themes and must not read as the
selection colour.

This is the highest ratio of perceived quality to work in the entire plan,
and it is why B4 should ship in the first wave rather than waiting for the
`<DataList>` refactor that will eventually own it.

### The guard

1. `focus-visible` is required on every interactive row — mechanically: an
   element with `v-for` and `@click` or `:to` must carry the focus class or
   compose `<Row>`.
2. A `hover:bg-*` utility outside `Row.vue` fails.
3. The three state tokens are distinct values in both themes, asserted against
   the built CSS the way the radius guard reads real class lists.
4. A browser spec that hovers, ticks and opens the same row and asserts three
   different computed backgrounds — the one check that would have caught all
   of this the day it was written.
