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

All twenty-two sections are below, in the order of Part 1. Each answers the
same five questions: what exists, where it diverges, what the one version is,
what it costs, and the guard.

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

**Four elevations and no doctrine.** 6 `shadow-sm`, 4 `shadow-2xl`, 3
`shadow-lg`, 1 `shadow-xl`. Nothing anywhere says which height belongs to
what, so a popover and a floating bar sit at different elevations for no
reason but the order they were written — and they do: three bars that all
float over the page, the undo bar at `xl`, the drop bar at `lg`, the selection
bar at `2xl`.

> **~~29 bare `shadow`, and a guard that misses the commonest case.~~**
> *Withdrawn on execution.* There are none. The 29 came from a text grep that
> counted `drop-shadow`, `box-shadow:` declarations inside the vendored sheet
> CSS, and the word in a dozen comments. Reading real class lists — the
> extractor `tests/token_audit.py` already provides, which is what the guards
> use — there are 14 shadow utilities in the two SPAs and every one of them is
> a named step. `test_shadows_pair_with_an_elevation_surface`'s pattern was
> therefore complete after all, and the finding against it does not stand.
> Kept because the lesson is the one F1 names: a grep over source text and a
> scan over class lists are different instruments, and only one of them was
> ever going to be right here.

**Two of the greys are one colour in dark.** Not in the audit's first pass
and found while executing it: read off frappe-ui's own token data,
`ink-gray-4` and `ink-gray-5` both resolve to `darkMode/gray/400`. In light
they are 0.683 and 0.586 and clearly apart. So any design that separates two
things by putting one at `-4` and the other at `-5` separates them in light
and not at all in dark, and there are 48 uses of `-4` against 316 of `-5` to
check. It is also why the role naming below stops at `-5`: `-4` is a
placeholder or a disabled control, not a quieter muted.

**Forty arbitrary values, and they cluster.** `h-[62vh]` three times,
`max-h-[70vh]` four, `max-w-[940px]` three, `w-[min(17rem,90vw)]` twice.
Those are not one-offs — they are an unnamed dialog-body height, an unnamed
reading measure and an unnamed popover width, each re-derived at the call site.

> **~~A display face used once, against two font files shipped to every
> visitor.~~** *Withdrawn on execution.* `font-display` is indeed on exactly
> one element — a record's name over its own photograph, which is precisely
> what the token's own comment says it is for. The cost half of the finding is
> simply wrong: both `@font-face` rules carry a `unicode-range` and
> `font-display: swap`, and nothing preloads them, so 18KB of Anton and 9KB of
> Reem Kufi are fetched only when a glyph in that range is actually rendered —
> that is, only on a showcase. A visitor who never opens one downloads
> neither. One use of a display face is restraint, not waste.

### What the one version is

**The type rule is a role rule, and it is written down.** `text-*` for a line
that cannot wrap — a label, a number, a chip, a button, a table cell, a crumb.
`text-p-*` for anything that may run to a second line — a description, a help
line, an empty-state body, a message. The scale has no hole to step outside
of: frappe-ui carries the same ten steps in both families, `2xs` included, so
the choice between them is always a choice of role and never of availability
(`test_the_two_type_scales_have_the_same_steps` pins that).

**Three named ink roles, mapped onto the tokens once.** `text-ink-primary`
(gray-8), `text-ink-secondary` (gray-6), `text-ink-muted` (gray-5). Callers
ask for the role, and the four numbers the roles replace are refused outright,
so there is one spelling per role rather than two vocabularies for one colour.

gray-7 does **not** survive as a fourth role. The audit left it open, on the
reading that it might be a level with a case of its own; 79 uses scattered one
or two to a file across forty-five files, with no pattern to read off, is that
case failing to be made. It folds into `secondary`. gray-1/2/3/4 and gray-9
keep their numbers: a hairline, a disabled control, a placeholder, black over
a photograph — edge levels with jobs, not quieter versions of a role.

**Four elevations with a name each**: flat (no class at all), `shadow-raised`
(a card in the flow of the page), `shadow-floating` (a panel anchored inside a
surface — a popover, a menu, a cluster of controls over a map) and
`shadow-over` (fixed above the whole page — a drawer, a toast, the selection
bar, the upload tray). The raw steps are refused, so the question "how high is
this?" has to be answered before the class is typed.

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

1. `truncate`, `whitespace-nowrap` or `line-clamp-1` may not appear in a class
   list that also carries `text-p-*`
   (`test_single_line_text_does_not_wear_paragraph_leading`). Exact, and it
   catches the whole family of leading mistakes.
2. The two scales carry the same steps
   (`test_the_two_type_scales_have_the_same_steps`), read off frappe-ui's own
   token data rather than asserted.
3. A grey with a role may not be asked for by number
   (`test_ink_is_asked_for_by_role`), and
   `test_the_two_quietest_greys_are_one_colour_in_dark` pins the upstream fact
   that decides where the roles stop.
4. A raw elevation step is refused; only the three named heights pass
   (`test_shadows_are_named_by_height`), and the existing
   `test_shadows_pair_with_an_elevation_surface` now reads those names.
5. An arbitrary value (`[...]`) that appears in more than one file is refused
   (`test_an_arbitrary_value_is_used_in_one_file_only`) — the second use is the
   moment it should have been a token.

Each has a witness beside it, per F1's meta-guard.

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

**The panel incantation, in 25 files.** `rounded-6 border
border-outline-gray-2 bg-surface-…` appears in 33 class lists across
twenty-five files, in thirteen spellings that differ only in which surface and
which padding:

    bg-surface-elevation-2        6      bg-surface-base p-4      4
    bg-surface-elevation-2 p-4    6      bg-surface-gray-1 p-3    3
    bg-surface-base               5      … and eight more, once or twice

(The audit first said forty-one files, from a text grep; reading real class
lists gives 33 uses in 25, plus three more the static scan cannot see because
their ground is a conditional expression. The verdict does not change.)

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
component, props for ground (`base` | `raised` | `sunken`), pad (`none` |
`tight` | `normal` | `loose` | `bar`), `elevation` and `tone`; the radius and
the border built in and not passable. Twenty-six files lose a class list.

`bar` is the fifth pad value and it earns its place: a row of controls is
wider than it is tall and wants asymmetric padding, and seven call sites had
each derived their own — `px-2.5 py-2`, `px-3 py-2.5`, `px-4 py-2`, `px-3
py-2`. `tone` takes the ground over rather than sitting beside it, because an
amber panel is amber all the way through and a red panel with a grey border
is not a thing anybody wants.

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

**~~The control plane is extracted and never translated.~~** *Withdrawn on
execution.* `oneapp_control` has a `main.pot` and no locales, and I read that
as an oversight. It is not: `scripts/i18n.py` says so in a comment, and the
argument is right —

> *`oneapp_control` is deliberately not here: it is the operator console,
> every reader of it works for us, and translating our own fleet vocabulary
> into Arabic would be work nobody would ever see. It still gets a POT — that
> is free, and the day we hire an operator who does not read English the
> catalogue is one `sync` away.*

The same reasoning already extends one level down, to `screens/ops/` inside
the tenant SPA. Recorded rather than deleted because the near-miss is the
point: a decision that lives only in a comment reads as an omission to anyone
auditing from the outside, which is F1's root cause arriving in the audit
itself.

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
4. Every app with a `main.pot` either has a complete `.po` per shipped locale
   **or** names itself in `i18n.py`'s exemption list with a reason. The
   exemption is what the guard is for: `oneapp_control` has one and it is
   right, and a second app skipping translation by accident should not look
   the same as the first skipping it on purpose.

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

## B5. Fields — read-only, disabled, permlevel, dependencies

### What exists

The server decides most of it, and decides it well.
`spaceview/meta.py` computes one `editable` flag per field —
`fieldtypes.editable(fieldtype) and not read_only and permlevel in writable`
— and `records.py::_writable` uses the same flag to narrow what a save is
allowed to touch, with a separate allowlist per child table. So static
`read_only` and permlevel are enforced on both sides, which is the hard part
and is right.

`lib/screen/rules.js` implements Frappe's three dynamic rules —
`depends_on`, `mandatory_depends_on`, `read_only_depends_on` — as an
expression evaluator over the current document.

### Where it diverges

**Four surfaces ask "may I edit this?" and get four different answers.**

| clause | form / create dialog | child table | inline cell |
|---|---|---|---|
| screen `can_write` | ✓ (via `disabled`) | ✓ (via `disabled`) | ✓ |
| server `editable` (read_only + permlevel) | ✓ | ✓ | ✓ |
| submitted / cancelled | ✓ (`frozen`) | ✓ (`locked`) | ✓ (`docstatus`) |
| workflow lock | ✓ (`locked`) | partial | · |
| **`read_only_depends_on`** | ✓ | **·** | **·** |
| `depends_on` (hide the field) | ✓ | · | · |
| `mandatory_depends_on` | ✓ | · | · |

The form gets all seven. The child table and the inline cell get three and a
half. The create dialog is fine — it composes `RecordForm` → `FormSections`,
so it inherits the whole rule, which is the pattern the other two should have
followed.

**That bottom row is a bug, not an inconsistency.** A field declared
`read_only_depends_on: eval:doc.status=="Closed"` is locked in the form and
editable in the child table and in the inline cell — and the server does not
enforce it either, because `_writable` is built from the *static* `editable`
flag and `read_only_depends_on` is dynamic. So the rule is advisory in one
place and absent in three, and a write that the form forbids goes through.

**There is no read-only *rendering* anywhere. Everything is `:disabled`.**
`FieldControl` takes one `disabled` prop and passes it to fifteen controls.
Frappe distinguishes the two states for a reason: *disabled* means this
control is temporarily unavailable, *read-only* means this value is
information rather than input. A record with twelve read-only fields shows
twelve greyed-out inputs — it looks broken rather than informational, which
is precisely the "weird performance" the user described.

The workaround already in the tree is the tell. `LinkPicker.vue:275`:

> *A disabled Combobox still draws its placeholder, so a `read_only` Link sat
> saying "Search…" over a control that would not open.*

That is a correct local fix for a wrong global model, and there will be one of
those per control type as each is noticed.

**`disabled` also means three different things at the call site.** A form
passes it for "the whole record is locked", `ChildTable` for "the grid is not
editable", `ScreenActions` for "this verb needs exactly one row". One prop
name, three meanings, and the visual result is the same grey in all three.

### What the one version is

**One function, on the server, returning one verdict per field.**
`meta.py` already computes `editable`; it gains a sibling that returns a
*state* rather than a boolean — `writable` | `readonly` | `hidden` — and the
dynamic rules are evaluated where the static ones already are, against the
document being rendered. The browser keeps `rules.js` for live re-evaluation
as the user types, but it and the server run **the same three expressions**,
and `_writable` consults the dynamic verdict on save. The bug closes on both
sides at once.

**Three renderings, not two.**

- *writable* — the control.
- *readonly* — the **value as text**, in the field's own layout, with no box,
  no grey and no placeholder. This is the missing one and it is most of the
  perceived improvement.
- *hidden* — absent, as now.

`disabled` survives only for its true meaning: a control that is momentarily
unavailable because something is in flight.

**Every surface renders a field through the same component.** `FieldControl`
takes `state` instead of `disabled`, and the child table and the inline cell
ask the same resolver the form asks. An inline cell whose field resolves to
`readonly` is simply not editable — which it already should be.

### What it costs

The server change is contained: one function in `meta.py`, one consultation
in `records.py`, and the expression evaluator ported from `rules.js` to
Python — or, better, the existing Python-side `frappe.utils.safe_eval` path
Frappe already uses for these, which means porting nothing. The read-only
rendering is a new branch in `FieldControl` plus a per-fieldtype "how does
this value read as text" mapping — fifteen small decisions, and `format.js`
already holds most of them for the list's cells.

Worth doing early: it is a data-integrity fix as well as a visual one, and
B5 is the only section in B that is not blocked by the `<DataList>` refactor.

### The guard

1. Every surface that renders a field imports `FieldControl` — no surface
   builds a control from a fieldtype itself.
2. A test that renders the same field, on the same document, through the form,
   the child table and the inline cell, and asserts one verdict. This is the
   exact test that was missing, and it is cheap.
3. `read_only_depends_on` is asserted on the server: a save that sets a field
   whose dynamic rule is true is refused, with a test per rule type.
4. `:disabled` on a `FieldControl` fails — the prop is `state`.

## C1. Breadcrumbs

### What exists

frappe-ui's `<Breadcrumbs>`, used in ten files, each inside a
`<nav data-slot="breadcrumb" aria-label="Breadcrumb">` — so the *markup*
convention already holds everywhere it is used. `useCrumbs` derives the
engine's trail from the space and the screen, and it is the most complete
implementation: a home crumb rendered as a house icon with the space's name
as its accessible label, the screen, and then the open record drawn as its own
element rather than as a crumb, with its face, its id and two status badges
beside it.

### Where it diverges

**Six independent `crumbs` computeds, and they disagree about the root.**

    engine     [ 🏠 space home ] / [ screen ]   + record element
    Drive      [ Files ] / [ folder ] / [ folder ]
    Mail       [ Mail ] / [ folder ]
    Chat       [ assistant's name ] / [ conversation ]
    OneDoc     [ where you came from, or Files ] / [ title ]
    Calendar   [ Calendar ]
    Account    [ Account ]
    Launcher   [ Spaces ]
    Marketplace[ Add a space ]

Nine roots. The engine's root is the *space*; every other surface's root is
*itself*. So there is no shared first crumb, no way to get from Mail back to
the workspace in one click, and no answer to "where am I" that is consistent
across two screens. OneDoc's root is the cleverest and the most inconsistent:
it is wherever you came from, remembered in a `back` param, which means the
same document has a different trail depending on how you reached it.

**Five surfaces have no breadcrumb at all**, and two of them are the
product's most immersive:

    onesheet/pages/Sheet.vue        none
    onedoc/pages/Doc.vue            none (its editor draws its own)
    onespace/pages/ScreenHost.vue   none (ScreenHeader draws it)
    onestorage/pages/Linked.vue     none
    settings/SettingsShell.vue      none

Sheet is the one that matters: a person deep in a workbook has no trail and no
route home but the browser's back button.

**The trail and the page title are separate ideas that nobody separated.**
The engine puts the record in the header *beside* the crumbs as its own
element — which is right, and is a decision nothing else knows about. Mail
puts the thread subject nowhere. OneDoc puts the title *in* the trail as the
last crumb. So the same question ("what am I looking at?") is answered in
three structural positions.

### What the one version is

**One composable, `useCrumbs`, with one root, and every surface calls it.**

The root is the **workspace**, always, and the second crumb is where you are
in it — a space, or one of the workspace-level places (Mail, Files, Calendar,
Chat, Account). The engine's current root becomes the second crumb rather than
the first. That costs one crumb of width and buys a product where the top-left
is always the same thing and always goes to the same place.

    [ workspace ] / [ space or place ] / [ screen or folder ] / …  ⟨ subject ⟩

**The subject is not a crumb.** It is the element after the trail, drawn once,
by one component — the record's face and badges today, a document's title, a
workbook's name, a thread's subject. OneDoc's title moves out of the trail
into it; Mail's subject appears for the first time.

**A trail segment is a link or it is not there.** OneDoc's remembered `back`
becomes a real *context* crumb — "from Projects / Acme" — only when the
document was opened from a record, and the root stays constant either way.

**Sheet, Doc, Linked and Settings get one.** The editors get the compact
variant: workspace mark, one place crumb, the subject, and nothing else; the
chrome is already narrow there, which is the reason they have none and is
solved by making the trail small rather than absent.

### What it costs

Small and broad. One composable gains a `place` argument and loses its
assumption that the caller is a space screen; nine call sites shrink to nine
one-liners; two editors gain a header row they do not currently have, which is
the only layout risk in the section (both are full-bleed by design — see C2).

### The guard

1. Every routed page renders exactly one `data-slot="breadcrumb"`. Zero fails;
   two fails.
2. The items come from `useCrumbs` — a `<Breadcrumbs :items>` bound to a
   literal array fails, which is five of the nine today.
3. The first crumb of every trail resolves to the same route.
4. A browser spec that walks every top-level surface and asserts the first
   crumb is present, is a link, and goes home.

## C2. Placement — pane, sidebar, dialog, inline

### What exists

Four app-level sidebars — Mail, Drive, Calendar, Chat — and they are
structurally identical: `Sidebar` + `SidebarItem` + `SidebarResizer` inside a
`nav`, 75 to 229 lines. That much is consistent and should stay.

The record has the most thought-through placement rule in the product, and
`RecordDrawer`'s own comment states it: a pane beside the list on a wide
screen, a drawer with a scrim on a narrow one, and a dialog for creating. The
pane is resizable and shares the window; the drawer covers it and is not.
That is a real doctrine, written down, with a reason.

`Rail` and `RailItem` are exported from the barrel and used **nowhere**,
despite "the rail" being the word used throughout the comments and the docs
for the app-level navigation. The thing everyone calls a rail is a `Sidebar`.

### Where it diverges

**The record's doctrine is not applied to anything else that opens.** Six
objects open in six ways:

| object | wide screen | narrow screen |
|---|---|---|
| record | pane beside the list, resizable | drawer with a scrim |
| file (Drive) | pane beside the list, resizable | pane, narrower |
| file (record's Files tab) | dialog | dialog |
| file (mail attachment) | dialog | dialog |
| mail thread | fixed reading pane | replaces the list |
| document (OneDoc) | its own route | its own route |
| workbook (OneSheet) | its own route | its own route |
| conversation (Chat) | fixed pane | fixed pane |

The same file opens in a resizable pane in Drive and in a dialog from a
record — and `FileSurface`'s own docstring says the body is deliberately
chrome-free so that *"whatever holds it owns the title and the actions"*,
which is the right architecture serving three different holders for no
reason anybody chose.

**Dialog counts tell the story of where configuration went.**

    onespace   26 files with a Dialog
    onesheet   10
    onestorage  9
    onedoc      3      onemail  3      onecode 2      onecalendar 1
    onemobility 0

OneSheet and OneStorage each grew a dialog layer of their own — ten and nine
— while OneMobility has none and puts everything inline on the screen. Those
are the two extremes of the same missing decision.

**Configuration lives in three places depending on which app you are in.**
The workspace has a settings dialog with 24 panels. Drive has its own
`settingsOpen` dialog for a mount, plus `ConnectFolder` for making one. Mail
reaches *into* the workspace dialog (`openSettings` imported from the shell)
and then watches it close to know when to reload. So "configure this thing"
is a workspace dialog, an app dialog, or a cross-app call, and the reader
cannot predict which.

**Nothing says when a thing deserves a route.** A document and a workbook get
one; a record does not; a conversation gets a query parameter; a file gets a
query parameter in Drive and nothing at all in a dialog. Sheet and Doc having
routes is right — they are places you live in — but the rule that makes them
right has never been written, so the next editor-shaped thing will be decided
by whoever builds it.

### What the one version is

**One rule, stated as a question about the object, not about the app.**

- **Does it have a life of its own?** — you can link to it, come back to it,
  and work in it for an hour. Then it is a **route**: a document, a workbook,
  a code file. Full window, compact crumbs (C1), its own header.
- **Is it the subject of the list you are in?** Then it is a **pane** beside
  that list on a wide screen and a **drawer** on a narrow one — the record's
  existing rule, applied to files, threads and conversations without
  exception. The Files tab of a record stops using a dialog; the mail
  attachment stops using a dialog; both get the pane the Drive already has.
- **Is it a decision you are making about something else?** Then it is a
  **dialog**: create, confirm, connect, pick. Bounded, focused, dismissible,
  and never a place you read.
- **Is it a property of the thing in front of you?** Then it is **inline**,
  on the thing.

**Configuration is one place.** The workspace settings dialog is the only
settings surface; an app contributes panels to it rather than growing its own.
Drive's mount settings become a panel; `ConnectFolder` stays a dialog because
connecting is a decision, not a configuration.

**`Rail` is adopted or deleted.** The vocabulary should match what the screen
does: if the app-level navigation is a rail, it is `<Rail>`; if it is a
sidebar, the word "rail" comes out of the comments and the docs. One or the
other, not both.

### What it costs

Moving file preview from dialogs into the pane is the real work and it is
worth it on its own — it is the same finding E1 reaches from the Drive side.
The settings consolidation is mostly moving files. The route rule changes
nothing today; it is a rail for tomorrow, which is what C2 exists to
establish before OneCode adds a tenth surface.

### The guard

1. A `<Dialog>` whose body renders a `ListSource` or a `FileSurface` fails —
   those are reading surfaces and reading surfaces are panes.
2. Every pane is `<ObjectPane>`, one component, so the drawer/pane breakpoint
   switch is decided once.
3. A settings panel outside `components/settings/` fails.
4. The word "rail" in a comment must be within a file that imports `Rail`.
   Petty, and it is the kind of pettiness that keeps a vocabulary honest.

## C3. The shell — space switching, the rail, the launcher, mobile

### What exists

Better than expected, and the guards are why. `lib/shell/nav.js` holds **two**
declarations and both are single-sourced: `nav` (a space's own screens, from
its manifest, with view types and saved layouts hanging off each) and
`surfaces` (the workspace-level places — Files, Settings, the assistant,
Calendar, Marketplace, Mail). `test_navigation_is_declared_in_one_place` and
`test_both_renderings_read_that_one_list` keep the desktop rail and the
phone's bottom bar reading the same list, which is the bug they were written
for: *"the rail had Mail and the More sheet did not"*.

There is a complete brand system —
`shared/lib/brand/marks.js` carries inline SVG marks for onestorage, onesheet,
onedoc, onecode, oneai, onemarket, onemail and onecalendar, drawn in their own
colours deliberately so an app is recognisable at 20px. A mark for **OneCode
already exists**, which E9 should note.

The space switcher is a grid of faces rather than a menu of words, with a
stated reason. The collapsed rail drops headings and expanders and keeps
icons.

### Where it diverges

**One destination, two identities, decided by screen width.** Each surface
declares both `brand` (the mark) and `icon` (a lucide glyph), and the comment
explains the intent — *"a 100×100 gradient at 16px in a row of outlines is a
smudge among glyphs"*. The intent is right and the consequence is not
examined: Files is a blue-gradient storage mark on a laptop and a grey
`lucide-folder` outline on a phone. Someone who learns the product on one
device recognises nothing on the other. The marks are the stronger identity
and the phone is where recognition matters most.

**Space screens have no brand and no consistency of icon source.** A space's
screens draw `spaceIcon(screen.icon)` from a curated lucide set of ~60. A
workspace place draws a mark. So inside a space you are in a world of grey
outlines and outside it you are in a world of colour, with no transition
between them.

**`surfaces` has no ordering principle.** Files, Settings, assistant,
Calendar, Marketplace, Mail — that is the literal order in the array.
Settings is second; Mail, the most-used of them for anybody who has an
address, is last and conditional. Three of the six are conditional
(`assistant.available`, `session.isAdmin`, `mail.held`), so the rail's shape
changes per person with nothing holding the stable items still.

**Two lists, one rail, no stated relationship.** A reader sees space screens
and workspace places in one vertical column. Nothing says which is which
beyond position, and when a space declares no `screen_group` headings — most
do not — the column is undifferentiated.

**The collapsed rail loses the headings and the expanders**, which is right,
and keeps no way to reach a view type or a saved layout, which is not: those
are only in the expander. A person who collapses the rail to get width loses
the ability to switch a screen's view from the rail entirely.

### What the one version is

**The mark is the identity, at every width.** The phone draws marks too, at
the size the bottom bar allows, with the glyph kept only as the fallback for
a surface that has no mark. If a mark is a smudge at 16px, the answer is to
draw a simplified mark at 16px — the marks are ours and are generated — not
to substitute a different symbol.

**A space gets a mark of its own**, generated the way the app marks are, from
its icon and its colour. Then the rail is one visual language from top to
bottom, and the launcher's tiles, the switcher's grid and the rail's items
are the same face at three sizes.

**`surfaces` is ordered by a rule and grouped**: the places you live in
(Mail, Files, Calendar), then the assistant, then the doors out (Marketplace,
Settings) pinned to the bottom of the rail where the account already is.
Conditional items leave their slot rather than collapsing the list.

**The two lists are visibly two.** A divider and a label — the space's name
over its screens — which the sidebar family already supports and which
`SidebarSection` and `SidebarHeader` exist for. Both are exported from the
barrel and unused.

**The collapsed rail keeps the expanders** as a hover flyout, which is what
the same component does on a phone already.

### What it costs

Marks on the phone is a generator change plus a size variant — half a day.
Space marks is the bigger one: `gen_brand.py` gains a per-space path and the
space doctype gains a colour, and the launcher, switcher, rail and marketplace
all pick it up for free. Reordering is a line. The collapsed flyout is small.

### The guard

1. Every `surfaces` entry has a `brand`; a surface with only an `icon` fails.
2. The desktop rail and the phone bar render the same *mark* for the same key
   — asserted in the browser at both viewports, which is the existing
   both-renderings guard extended from labels to identity.
3. `SidebarSection` / `SidebarHeader` are used, or removed from the barrel
   (A2's unused-export rule, applied).
4. The rail's item order comes from a declared group, not from array position.

## C4. What lives in the URL

### What exists

Thirteen query parameters across the SPA:

    screen 16   folder 13   place 12   chat 6    record 4   layout 4
    type 3      peek 2      checkout 2  thread 1  overlay 1  workspace 1
    peekScreen 1

and `returnTo.js`, which carries `back` and `backLabel` so an editor reached
from a record closes back to that record — with the path validated against
`//evil.example`, which is the kind of care this area generally shows.

Alongside it, seven things live in `localStorage` instead: the rail's
collapsed state, a Link field's last choice, a screen's chosen surface, a
child table's columns, Drive's grid/list toggle, Drive's sort order, and every
`Resizer` width.

### Where it diverges

**Three naming conventions for one idea.** `screen` and `record` are the
engine's; `place` and `folder` are Drive's; `thread` is Mail's; `chat` is the
assistant's. Each names "which one of these am I looking at" and each does it
differently — `record` is an id, `thread` is a key, `chat` is a session name,
`folder` is a `File` name and `place` is an enum. A reader cannot look at a
URL and tell what kind of thing it points at, and neither can a link handler.

**`peek` and `peekScreen` are a second record-opening mechanism** beside
`record`. Two parameters for "show me this record beside what I am doing"
versus "show me this record", where the difference is which screen's rules
apply. That is a real distinction and it is encoded as two extra parameters
rather than as one qualified value.

**Drive's sort and view are in `localStorage`; the engine's are in the URL
and the database.** So a Drive link sent to a colleague arrives in whatever
order *their* browser last used, while a screen link arrives exactly as sent.
Same product, opposite answers, and the Drive one is the wrong answer for the
same reason saved views exist.

**Nothing that is not a route has a URL.** The settings dialog, the assistant
panel, the column picker, the filter panel, the create dialog, every
`FormDialog` — none is addressable. Settings especially: there are 24 panels
and no way to link to one, which makes every support answer "open settings,
then find Backups".

**Reload loses more than it should.** A record's open tab, a list's scroll
position, a filter panel left open, a child table's page — all reset. The
engine keeps filters and columns because a saved view holds them, which is
the right mechanism for the durable ones; the ephemeral ones have no
mechanism at all.

### What the one version is

**One parameter shape for "what am I looking at", and it is typed.** A single
`at` parameter carrying a qualified reference — `record:Task/TASK-0001`,
`file:abc123`, `thread:xyz`, `chat:s1` — resolved by one function that knows
which surface each kind opens in (which is C2's placement rule, executed).
`screen`, `type` and `layout` stay as they are: they say *where* you are, not
*what* you have open, and that distinction is worth keeping in the URL's
shape.

**`peek` becomes a modifier on `at`, not a second parameter.**

**Anything durable and shareable goes in the URL or in a saved view; anything
per-browser goes in `localStorage`, and the test is "would I want to send
this to a colleague".** Drive's sort and view fail that test and move — to a
saved view, since B2 establishes Drive gets those. Rail collapse, resizer
widths and a Link field's last choice pass it and stay.

**Every panel is addressable.** Settings becomes `?panel=backups`, the
assistant `?ask=`, the filter panel `?filters=open`. These are dialogs and
panels rather than routes — C2 keeps them dialogs — but a dialog with an
address is a dialog somebody can be sent to, and it costs one watcher each.

**Ephemeral state is restored from the URL or deliberately not.** Scroll
position and an open tab are worth restoring and are cheap; a half-typed
filter is not. The point is that it is decided rather than defaulted.

### What it costs

The `at` parameter is a breaking URL change, which is free — there are no
tenants — and is the sort of thing that becomes impossible to do later. It
also *simplifies* the five surfaces that currently each parse their own
parameter. Making panels addressable is a day. Moving Drive's preferences is
small and waits on B2.

### The guard

1. A `route.query` key outside the declared set fails. The set is a list in
   one file, which is also the documentation.
2. `localStorage` is written only through one `remember()` helper that takes a
   declared key, and the declared keys are asserted to be per-browser
   conveniences — the same shape as the icon-set guard.
3. Every dialog that can be opened from a menu has an address: a browser spec
   that opens each from a cold URL.
4. A test that round-trips every `at` kind through the resolver.

## D1. Time, number and money

### What exists

One good rule, guarded: Frappe stores datetimes in the *site's* timezone, so
`dayjs(value)` reads them as if they were the reader's and puts an invoice on
the wrong day. `dayjsLocal` converts, the boot payload carries
`system_timezone`, `main.js` configures it, and
`test_stored_datetimes_are_converted_from_the_site_timezone` asserts all three
plus refuses a bare `dayjs(` in any `.vue` file. 57 call sites use
`dayjsLocal`.

`lib/screen/format.js` handles numbers well: the field's own `precision`, then
the site's `float_precision` / `currency_precision`, then a plain rendering,
with the currency *symbol* deliberately separated from the decimal count.

### Where it diverges

**There are three clocks, not one.**

    dayjsLocal            57 uses   site tz → reader's local.  Guarded.
    toLocale*String       28 uses   the browser's idea of the string.  Unguarded.
    server-side           12+ uses  format_datetime / strftime, sent as text.

The guard only reads `.vue` files, and the 28 `toLocaleDateString` /
`toLocaleTimeString` / `toLocaleString` calls are mostly in `.js` — ten of
them in OneSheet (`VersionHistory`, `CellHistoryPopover`,
`VersionPreviewBanner`, `lib/utils/format-number.js`, the formula engine).
Handing a stored Frappe datetime string to `toLocaleDateString` is *precisely*
the bug the guard exists to prevent, done in the one file extension the guard
does not read. So a sheet's version history is in the wrong timezone for
anyone not sitting on the server, and nothing catches it.

The server-formatted ones are worse in a different way: `versions.py` sends
`"d MMM, HH:mm"` already rendered, so the browser cannot convert it at all
even if it wanted to.

**Five date formats for two ideas.**

    'D MMM YYYY, HH:mm'   5      'D MMMM YYYY, HH:mm'  2
    'D MMM YYYY'          3      'D MMMM YYYY'         1
    'd MMM, HH:mm'        (server)

Two month spellings, chosen per call site.

**The workspace's own date and number preferences are never read.**
`workspace.py` exposes `date_format`, `time_format` and `number_format` as
settings that write through to System Settings — a person can set them, and
the SPA reads none of them. Dates are hardcoded `D MMM YYYY`; numbers go
through `toLocaleString(undefined, …)`, which follows *the browser's* locale.

So a German workspace that sets `dd-mm-yyyy` and `#.###,##` sees `12 Sep 2026`
and — depending only on the reader's browser language, which nobody
configured — either `1,234.50` or `1.234,50`. The dates ignore the setting;
the numbers ignore it and vary per reader. That is the "datetime handling is
random" complaint, and the number half of it is worse because it is
invisible: two colleagues reading the same invoice see different separators.

**`fromNow` in ten files with no rule.** "3 days ago" appears on row meta,
file rows, versions, sessions, record meta, mail. Nothing says when a relative
time is right and when an absolute one is, so the same column is relative in
one surface and absolute in another, and a relative time older than a week is
less useful than a date.

**The boot payload carries the timezone and not the formats.** It carries
`system_timezone`, `brand`, `lang` and `assistant` — the things wanted before
first paint — and the argument for each applies exactly to `date_format` and
`number_format`, which are also wanted before the first number is drawn.

### What the one version is

**One module, `lib/format`, and nothing formats a date or a number outside
it.** It reads the workspace's `date_format`, `time_format`, `number_format`,
`float_precision`, `currency_precision` and `system_timezone` off the boot
payload, and exposes six functions:

    date(value)        a day, in the workspace's format
    time(value)        a time of day
    moment(value)      both
    ago(value)         relative, and only under the threshold — see below
    number(value, col) what format.js does today, plus the workspace's separators
    money(value, ccy)  number, with the symbol and the currency's own precision

**One rule for relative time**: under seven days it is relative, over seven it
is a date, and a tooltip always carries the absolute value. That is one line
in `ago()` and it retires the per-surface decision.

**The three clocks become one.** `toLocale*` is banned outright and the guard
extends to `.js`. Server-side formatting of anything a browser will render is
banned too: the server sends an ISO string and the browser formats it, which
is the only arrangement in which the reader's timezone can be honoured at all.

**Money is its own function.** Today the symbol is deliberately separated from
the precision, with a good reason — and the consequence is that every caller
re-joins them, so a currency's own precision (JPY has none, KWD has three) is
nobody's job.

### What it costs

Small for the size of the improvement. 57 `dayjsLocal` calls become `date()`
or `moment()`; 28 `toLocale*` calls become the same; 12 server-side formats
become ISO strings and their callers gain a format call. The boot payload
gains three keys. The risk is in OneSheet, where `format-number.js` is
vendored-adjacent and the formula engine's `TEXT()` has its own date
formatting that must stay spec-compliant rather than workspace-configured —
that one is a genuine exception and should be named as one.

### The guard

1. `dayjs(`, `toLocaleDateString`, `toLocaleTimeString`, `toLocaleString` and
   `Intl.DateTimeFormat` are refused in `.vue` **and** `.js` — the existing
   guard, extended to the extension where all the offenders are.
2. A date format string (`'D MMM…'`) outside `lib/format` fails.
3. `format_datetime` / `strftime` in any Python file whose output reaches a
   browser payload fails. The boundary is the whitelisted endpoints, which
   `test_endpoints.py` already enumerates.
4. A test that sets the workspace to `dd-mm-yyyy` and `#.###,##` and asserts a
   rendered list changes — the check that would have caught the settings being
   unread on the day they were added.

## D2. Feedback — toasts, errors, confirmations, loading

### What exists

A good wrapper with a stated rule. `shared/lib/runtime/notify.js`:

> *Every mutation reports its outcome and every failure is rendered from a
> normalised Frappe error… **Pages should not call `toast` directly** — these
> wrappers are what guarantee the sound and the error parsing happen.*

`notifyError` normalises, sends the traceback to the console rather than the
toast, plays a tone and gives the toast eight seconds. Sixteen files use it.

The silent-catch situation is *better* than it looks from a grep: 19 empty
catches across 14 files, and all but one carry a comment explaining why
silence is right — a dropped five-second poll, `localStorage` in a private
window, a count that failed while the rows are already on screen. Those are
correct. Only `onesheet/editor/index.vue` has a genuinely bare one.

### Where it diverges

**The rule has no guard, and seven files break it.** `DocEditor`, `Network`,
`BoardBody`, `BackupSettings`, `ShareLink` and two shared libraries call
`toast.*` directly — eleven calls — so those outcomes have no sound and their
errors are whatever the caller happened to pass rather than a normalised
Frappe error.

**Three feedback channels, no rule about which.**

    notify* toast       16 files    transient, with sound, normalised
    raw toast           7 files     transient, silent, unnormalised
    <ErrorMessage>      83 uses     inline, permanent until fixed

`ErrorMessage` at 83 uses is by far the most common and is the right choice
for a form field's refusal. It is also used for things that are not form
refusals, and nothing says where the line is.

**Success is reported for bulk writes and not for single ones.**
`useBulkActions` calls `notifySuccess`; `useRowWrites` — which is every
inline cell edit and every heart — imports only `notifyError`. So changing
one cell says nothing when it works and complains when it fails, while
changing forty says "Updated 40". That asymmetry is backwards: the bulk case
is the one where the user can see the rows change.

**Two user-visible toasts are untranslated, and the i18n guard cannot see
them.** In `useBulkActions.js`:

    notifySuccess(`${said} ${result.done.length}`)
    notifySuccess(`Deleted ${result?.deleted?.length || 0}`)

They are template literals, and the copy reader extracts quoted strings. So
an Arabic workspace deleting three records is told "Deleted 3" in English,
and `test_nothing_a_customer_reads_is_still_in_english` passes. There are
fourteen more English template literals in the SPA, mostly in OneSheet
(`"${tabName}" is a template now.`, `Copied into ${n} cell${n === 1 ? '' :
's'}`) — and that last one is also the plural bug `__()` exists to prevent.

**There is no undo in the product.** The word appears eight times, always in
prose explaining that something *cannot* be undone. Every destructive action
is therefore a confirmation dialog — fifteen files have one — which is the
heavier instrument used because the lighter one does not exist. B3's
"reversible verbs get an undo" has nothing to build on.

**Loading has no rule either.** `test_something_waits_visibly_while_a_screen_loads`
guards screens; below that it is per surface — a `Spinner`, a `loading` prop
on a chart, a disabled button, or nothing.

### What the one version is

**Four channels, and the rule is about how long the news is true for.**

| the news | channel |
|---|---|
| this worked, and you can see the result | nothing |
| this worked, and you cannot see the result | toast, 3s |
| this worked and can be undone | toast with an Undo, 8s |
| this failed, and it is about a field | `ErrorMessage` under the field |
| this failed, and it is about the action | toast, 8s, normalised |
| this is broken until you fix it | `<Alert>` in place |

The first row is the one that is missing and it matters: a toast for something
visibly done is noise, which is probably why `useRowWrites` has none — but
the fix for an inline cell edit is not silence, it is the cell showing it
saved.

**`notify.js` becomes the only door.** `toast` stops being re-exported from
it; the barrel's `toast` is refused outside `notify.js`.

**Undo exists.** A `notifyUndoable(message, undo)` that holds the action for
its toast's lifetime — and the reversible deletes from B3 are its first
callers. This is what lets the destructive-verb confirmations drop from
fifteen dialogs to only the irreversible ones.

**Every toast string goes through `__()`,** and the copy reader learns to
read template literals.

### What it costs

Small. Eleven direct `toast` calls move to `notify`; two strings get wrapped;
`useRowWrites` gains a saved indicator rather than a toast. `notifyUndoable`
is a day, and the confirmation cull it enables is the visible win. Teaching
the copy reader about template literals is worth doing on its own — it is a
blind spot in a guard we rely on, and D2 found it by accident.

### The guard

1. `toast` imported anywhere but `notify.js` fails.
2. Every `notify*` argument is a `__()` call or a variable — a bare string or
   template literal fails.
3. The copy reader extracts template literals; the existing English-check then
   catches the sixteen offenders.
4. A mutation composable that calls `notifyError` and never reports success
   fails, unless it declares `silentSuccess` with a reason.

## D3. Uploads and attachment

### What exists

The best-consolidated area in the audit, and worth saying so. `attach.js`'s
own docstring records the arc:

> *There were four ways a file could reach a `File` row and they behaved
> differently… only one of them could send a large file — the Drive's — so a
> 200 MB video went into the Drive fine and failed the moment somebody tried
> to attach one to a record. So one function.*

`putFile` tries the presigned direct-to-R2 path and falls back to frappe-ui's
`upload`, and callers do not choose. `FilePicker` is the sanctioned dialog —
library, this device, camera — with a stated rule that **upload writes into
the Drive and then picks the result**, so there is no "attached but not in
the Drive". Eight surfaces use it.

### Where it diverges

**The bytes are unified; the experience around them is not.** `putFile`
solved *how* a file gets there. What a person sees while it happens still
depends entirely on where they started.

    surface                  picker      drag-drop   queue   progress
    Drive                    own + tray      ✓          ✓        ✓
    FilePicker (8 callers)   dialog          ✓          ·        ✓
    ScreenActions            raw input       ·          ·        ·
    OneSheet import          raw input       ✓*         ·        ·
    Mail composer            FilePicker      ✓          ·        ·
    record Files tab         FilePicker      ·          ·        ✓

`<UploadTray />` is rendered in **exactly one place**: `Drive.vue:474`. So the
queue that survives a navigation, that shows five files uploading and lets you
watch them, exists only if you started in the Drive. Attach a 200 MB video to
a record and it now *works* — that was the arc's win — and you watch it inside
a dialog you cannot close, with no queue and nothing to return to.

**Two surfaces still use a raw `<input type="file">`.** `ScreenActions` (with
a reason: a declared action's `upload` modifier needs one file and no dialog)
and the OneSheet editor. Drive's own and `CameraCapture`'s are legitimate —
Drive is the destination and CameraCapture is inside the picker.

**Drag-and-drop lands on nine surfaces and four of them are not about files**
(`BoardBody`, `ColumnPicker`, `BuilderZone`, `FormatBuilder` — reordering, not
uploading). Of the five that are, each implements its own `dragover` /
`dragleave` / `drop`, its own hover treatment (B4's finding again) and its own
rejection behaviour.

**Nothing tells anybody a size limit before they try.** The only size
messaging in the SPA is `FileSurface`'s *"This one is too big to show here"*
— about *reading* a file. There is no "up to 25 MB" anywhere near an upload
control, and the WebDAV work established that the ceiling is real and comes
from `conf.max_file_size`. A person discovers it by failing.

### What the one version is

**One `<Attach>` affordance, and it is the same thing everywhere.**
`FilePicker` is already most of it; what it needs is to stop being only a
dialog. The same component in three shapes — a dialog (as now), a drop zone
(for a Files tab or a composer), and a bare button (for `ScreenActions`) —
all three going through `putFile`, all three feeding the *same* queue.

**The tray is global.** `<UploadTray />` moves to `AppShell`, once, so an
upload started anywhere survives navigating away from where it started. This
is one line and it is most of the perceived improvement — it turns attaching
a large file from a modal you must babysit into a background task.

**Drag-and-drop is one directive.** `v-drop-files`, carrying B4's drop-target
treatment and the same rejection behaviour, replacing five hand-rolled
implementations. The four reorder-drag surfaces are a separate concern and
keep theirs.

**The ceiling is stated before it is hit.** The limit comes from the server
(`conf.max_file_size`) and belongs in the boot payload beside the other
formats D1 wants there, printed under every attach control and checked in the
browser before a byte is sent.

### What it costs

Moving the tray is a line. Making `FilePicker` render in three shapes is a
day. The directive is half a day and deletes five implementations. The size
limit is a boot key and a sentence. This section has the best
work-to-improvement ratio after B4, and none of it is blocked by anything.

### The guard

1. `<input type="file">` outside `FilePicker` and `CameraCapture` fails.
2. `@drop` on an element that is not using `v-drop-files` fails, unless the
   file declares it is reordering.
3. `<UploadTray />` appears exactly once, in the shell.
4. A browser spec that starts an upload in a record's Files tab, navigates to
   another screen, and asserts the tray is still there and still counting.

## D4. Mobile

### What exists

One breakpoint, shared and well argued. `lib/shell/breakpoint.js` is generated
into both apps, reference-counts a single `MediaQueryList`, and says why:

> *The shell is not responsive CSS — DesktopShell and MobileShell are different
> components with different slots, so something has to choose. Two apps
> choosing at two widths is how the same account looks like two products on
> the same tablet. 768px is Tailwind's `md`, so anything that also branches in
> CSS agrees with this without a second number to keep in step.*

Playwright runs every spec at two viewports, desktop and a Pixel 7.

### Where it diverges

**The argument for 768 is right and the code does not follow it.** The
stated reason for choosing `md` is that CSS branching would then agree. In
practice:

    sm:   77 uses      md:  12      lg:  22      xl:  6

`sm:` is 640px. So between 640 and 767 the shell has switched to
`MobileShell` — bottom bar, no sidebar, records as pages — while every `sm:`
rule in the content has already turned *desktop* on. That 128px band is a
small tablet in portrait and a large phone in landscape, and in it the
product is a mobile shell wrapped around a desktop layout. Six times more
code branches at the wrong number than at the right one.

**Only five files ask `isMobile` at all**: `AppShell`, `Mail`, `Drive`,
`lib/screen/list.js`, and the breakpoint itself. Everything else either
branches in CSS or does not branch.

**OneSheet and OneDoc do not branch.** This is the user's complaint and the
numbers are stark:

    module          responsive prefixes   files   isMobile
    onesheet                 2              20       0
    onedoc                   4               5       0
    onecalendar              0               3       0
    onemobility             18              10       0
    onespace                58             128       -
    onemail                 10              10       ✓
    onestorage               7              16       ✓

The sheet editor is 6,012 lines with **zero** responsive prefixes and zero
`isMobile`. The diary — a week grid — has zero across three files. These are
not surfaces that degrade on a phone; they are surfaces that were never
considered on one.

**168 mobile skips across the browser suite**, and the distribution says
where the thinking stopped: Mail has 31 (Mail is the most mobile-considered
surface, so most of those are honest "the phone opens a record as a page"),
settings 10, live 9, child tables 8. `docs.spec.js` has **no** skips and
eight tests — so OneDoc *is* exercised on a phone and passes, which means
either the tests do not assert layout or the phone experience passes tests
while failing people. Given four responsive prefixes, it is the former.

Many skips are legitimate ("a touch screen cannot drag"). Many are not: *"the
settings gear is desktop chrome"* and *"the board is a desktop surface"* are
decisions made by a skip rather than by a design.

### What the one version is

**One number, and it is 768.** Every `sm:` in a layout context becomes `md:`,
or the shell's breakpoint moves to 640 — but not both left as they are. 768
is the better choice (the shell's argument stands, and a 640 shell switch
would put a bottom bar on a small tablet), so the work is ~77 audited
substitutions. `sm:` stays legitimate for type and spacing that genuinely
steps twice.

**The four unconsidered surfaces get a phone design, not a phone fallback.**
Concretely, and these are E2/E3/E6's to build:

- *OneSheet*: the grid is a canvas and already scrolls; what it lacks is a
  touch-sized toolbar, a formula bar that does not lose half the window to
  the keyboard, and a way to select a range with a finger.
- *OneDoc*: the editor is closest to working; it needs the toolbar collapsed
  to a sheet and the outline behind a control.
- *OneCalendar*: a week grid on a phone is a day list; that is a different
  view type, not a narrower grid.
- *OneMobility*: the map works; the facet bar and the charts do not.

**A skip must name a design decision, not a viewport.** *"The board is a
desktop surface"* becomes either a phone board or a documented redirect to
the list — and the test asserts the redirect.

### What it costs

The breakpoint substitution is a day and is a prerequisite for trusting
anything else in this section. The four phone designs are real work and
belong to their own sections. Auditing the 168 skips is half a day and will
convert perhaps thirty of them into either a test or a known gap.

### The guard

1. A `sm:` prefix on a layout utility (`flex`, `grid`, `hidden`, `w-`, `col-`)
   fails; `md:` or above only. `sm:` stays legal for type and padding.
2. Every module has at least one `isMobile` or `md:` — a module with none has
   not been considered, and the number that proves it is zero.
3. A `test.skip` on the mobile project must carry a reason matching a declared
   vocabulary (`touch-only`, `desktop-chrome-by-design`, `covered-elsewhere`),
   and `desktop-chrome-by-design` must point at the phone equivalent.
4. A screenshot spec at 390px for every routed surface, compared against a
   stored baseline — the cheapest way to notice that a 6,000-line editor has
   never been looked at on a phone.

## E1. OneStorage — foldering, mounting, and the Files tab

### What exists

The data model is the best thing in the product and it is already what this
section needs. `query.py`'s docstring:

> *Home, Recents, Favourites, Shared, Templates, Trash. Every one of them is
> the same query with a different `where` and a different order — there is no
> second store behind any of them.*

and, about the `RECORD` place:

> *Also not in the rail, and the one that proves the whole design: what a
> record has filed against it is this same query with `attached_to_doctype`
> set. The Drive and a record's Files tab are two `where` clauses over one
> table.*

`RecordFiles.vue` honours that — it draws the Drive's own rows, not a copy.
`attach.js` puts every file through one path. `dav.py` serves any Drive folder
over WebDAV with a generated credential.

### Where it diverges

**A share is scoped to a folder; a record's files are a filter. So a record
cannot be mounted.** `Drive Access.folder` is a `Link` to a `File`, and
`dav.py` resolves a share by walking down from it. Everything the rail can
show — Recents, Favourites, Shared, Templates, and crucially *a record's
attachments* and *a doctype's attachments* — is a `where` clause and therefore
unmountable. The one thing the user wants to mount is the one thing the share
model cannot name.

**Attachments land in Frappe's `Home/Attachments` and stay there.**
`query.py:124` notes it. So the Drive's folder tree has a single flat bucket
holding every file attached to every record in the workspace, and the folder
structure a person made is beside it rather than containing it. A workspace
with 4,000 quotations has 4,000 attachments in one folder that nobody browses,
and the only useful view of them is the per-record filter.

**The Files tab is the Drive's rows without the Drive's capabilities** — B1's
matrix: no sort, no search, no selection, no bulk delete. Two attachments
cannot be deleted together from a record.

**A file opens in a pane in Drive and a dialog in the Files tab** — C2's
finding, reached from the other side.

### The question the user asked, and the answer

*Does each doctype get a directory and each document a directory inside it?*

**No — and the reason is the one the architecture already committed to.**
Creating a real folder per record means a `File` row per record: 4,000
quotations is 4,000 folder rows, created on first attach or, worse, eagerly.
It makes `Home/Records/Quotation/` a folder with 4,000 children that no file
manager renders usefully, it puts renaming a record in the business of moving
a folder, and it makes deleting a record a cascade. It also breaks the one
sentence the module rests on: there would now be a second store, and the
Files tab would be a folder listing rather than a filter, which is the
arrangement `query.py` explicitly rejected.

**The right move is the opposite: make the *share* as expressive as the
rail.** `Drive Access.folder` becomes a `scope`, and the scope can be any
place the Drive already knows:

    folder:Home/Drawings          what exists today
    doctype:Quotation             every file attached to any quotation
    document:Quotation/QTN-0001   one record's files
    place:favourites              a rail place
    query:<saved view>            eventually, B2's saved views

`dav.py` resolves a scope through `query.py` instead of walking a folder, and
a mounted `doctype:Quotation` share presents a **virtual directory per
record** — `QTN-0001/`, `QTN-0002/` — assembled from the attachment rows at
`PROPFIND` time, with nothing created and nothing to keep in step. The name of
each virtual directory is the record's title, and a record with no
attachments simply is not there.

**The same virtual tree appears in the Drive itself**, as a rail place called
*Records*: `Records / Quotation / QTN-0001 /`. It is a breadcrumb over three
`where` clauses, which is what the rail already is.

**And `Home/Attachments` stops being where things land.** A file attached to a
record has `attached_to_doctype` and needs no `folder` at all; the flat bucket
is Frappe's default rather than a decision, and the virtual tree replaces
what it was pretending to be.

This is strictly less code than real folders, creates no rows, needs no
migration, and gives the user exactly what was asked for: mount a doctype,
mount a document, and get a directory that is correct the moment a file is
attached.

### What it costs

`Drive Access` gains a `scope` string and keeps `folder` as the first kind.
`dav.py` gains a resolver — the `PROPFIND` for a virtual directory is a
`get_list` with a `where`, which `query.py` already builds. The Drive gains a
*Records* place, which is three lines of rail and one more `where`. The Files
tab's capabilities come free from B1.

The genuinely new work is **write** into a virtual directory: a `PUT` into
`doctype:Quotation/QTN-0001/scope.pdf` has to become an attachment on that
record, which means resolving a title back to a name and checking write
permission on the *record*, not on a folder. That is the one part worth real
care, and it is also the feature — dropping a file into a mounted folder in
Finder and having it appear on the quotation.

### The guard

1. Every scope kind resolves through `query.py`; a second query builder in
   `dav.py` fails.
2. A `PROPFIND`/`PUT`/`DELETE` test per scope kind, including the permission
   case: a share scoped to a doctype the key's owner cannot read is empty, not
   an error.
3. The Files tab and the Drive render the same component with the same
   capability set — asserted by rendering both and diffing the offered
   actions.
4. No file is written to `Home/Attachments`.

## E2 + E3. OneDoc and OneSheet

### What exists

Both are routes, both are pages, and both pages open with the same paragraph:

> *A page rather than a screen inside a Space, for the same reason Mail and
> Files are: a document belongs to the workspace's file table, not to any one
> Space. It is reached from the Drive, from an attachment on a record, or from
> a link somebody sent.*

That is right and settles C2's route question for them. Both get the record
rail (`RecordPanel`), chat (`FileChat`), versions, templates, print, and
collaboration. The sheet editor is vendored from `frappe/sheets` and brings
its own identity bar, formula bar, toolbar and tab strip — which is why
`Sheet.vue` deliberately has no `PageHeader`.

### Where it diverges

**Neither has a space, and that is the user's ask.** A person who wants to
see *their documents* has no door. There is no `Documents` place in the
Drive's rail and no `Sheets` place, despite `custom_kind` already holding
`Doc` and `Sheet` as first-class kinds and every rail place being one `where`
clause. Google Docs' home screen — recent documents, templates, a New button,
shared-with-me — is four filters this product already computes and does not
offer. That is the single cheapest large improvement in section E.

**The two have drifted apart on every piece of shared chrome.** They share
`RecordPanel`, `FileChat` and versions, and disagree about:

    breadcrumb    Doc: [where you came from] / [title]   Sheet: none
    title         Doc: last crumb                        Sheet: editor's own bar
    header        Doc: its own nav row                   Sheet: none at all
    outline       Doc: a rail, and a phone control       Sheet: n/a
    close         Doc: back via returnTo                 Sheet: @close → returnTo

`Sheet.vue`'s reasoning for no header is sound in isolation — four rows of
chrome, a fifth would crowd — and its consequence is C1's finding: the
product's most immersive surface has no way home.

**Neither has been looked at on a phone.** D4's numbers: the 6,012-line sheet
editor has zero responsive prefixes and zero `isMobile`; OneDoc has four
across five files. `docs.spec.js` runs eight tests at phone size with no
skips and passes, which tells us the tests do not assert layout.

**The sheet's own chrome hides things it should not.** The user named it:
text size is behind a menu, and the vendored toolbar's grouping is Frappe's
rather than ours. More importantly the vendored editor is 6,012 lines in one
file and is the single largest obstacle to any of this — every change to the
sheet's chrome is a change inside a vendored file we have already forked.

**Templates exist for both and are not a door either.** `TEMPLATES` is a rail
place — a flag on a file — so "start from a template" is one filter, and
neither editor's New flow leads with it.

### What the one version is

**Two places in the Drive's rail, `Documents` and `Workbooks`, and they are
`where custom_kind = 'Doc' | 'Sheet'`.** With the Drive's own grid view
(thumbnails), its sort, and — once B1 lands — saved views. That is the
Google-Docs home screen, built from parts that exist, and it needs no new
store, no new route and no new permission.

They are not new *apps*: a document is a file and the Drive is where files
are. Giving OneDoc a separate space would recreate the second store E1 just
argued against.

**One editor chrome, shared.** A component that both editors mount: the
compact crumb trail from C1, the title with its rename, the presence strip,
the actions menu (B3's, with the file's verbs), and slots for the editor's
own toolbar. OneDoc's nav row becomes it; the sheet gains it above the
vendored bar, which costs one 36px row and buys a way home, a title that can
be renamed in place, and the same actions as everywhere else.

**A phone design each**, per D4: the sheet needs a touch toolbar, a formula
bar that survives the keyboard, and finger range-selection; the document
needs its toolbar in a sheet and its outline behind a control.

**The vendored editor gets a seam.** Not a rewrite — the vendoring was the
right call and `VENDORED.md` records it. What it needs is the chrome to be
*ours*: the identity bar and the toolbar move out of the vendored file into
our wrapper, leaving the vendored part as the grid, the engine and the canvas.
That is what makes "show the text size" a change we can make.

### What it costs

The two rail places are a day, including the New menu. The shared editor
chrome is a week across both, most of it in prising the sheet's identity bar
out of the vendored file — and that is the enabling work for the phone
designs, the collapsed controls and every later change to either editor.

### The guard

1. Every `custom_kind` that has an editor has a rail place — mechanical, from
   `kinds.py`.
2. Both editors mount `<EditorChrome>`; an editor page rendering its own nav
   row fails.
3. The 390px screenshot baseline from D4 covers both, and the sheet's has to
   show a usable toolbar rather than an overflowing one.
4. The vendored boundary is asserted: a diff against upstream shows chrome
   removed and nothing else, so the next upstream pull stays mergeable.

## E4 + E5 + E6. OneMail, OneMobility, OneCalendar

### OneMail

**What exists.** Two panels with the ground between them, and a stated reason:
*"the same shape a screen takes when a record opens beside its list, and for
the same reason: they are two things you are looking at."* That is exactly
C2's doctrine, arrived at independently, and it is the only surface outside
the record that gets it right. A sidebar of addresses with each mailbox's own
folders, unread badges, a quiet-folders toggle, and a `/` shortcut to search.

**Where it diverges.**

The pane switch is at `sm:` — `sm:w-96` and `hidden sm:flex` — while the
shell switches at `md:`. This is D4's 128px band, and Mail is the clearest
case of it: on a 700px tablet you get a two-pane mail client inside a
bottom-bar mobile shell.

Its verbs are a fourth arrangement (B3): four icon buttons over the list,
the same four again on the open thread, Star also on each row, "Move to" only
on the open thread.

Its search is the third search box (B2) and is the only one with a keyboard
shortcut, which should have been promoted rather than kept local.

Its rows are hand-rolled `RouterLink`s (B1, A2) and its "open thread" colour
is the hover colour (B4).

31 of the suite's 168 mobile skips are Mail's — the most of any surface, and
mostly honest.

**Verdict.** Mail is the best-designed surface in the product and almost all
of its divergence is the rest of the product not having caught up. Its only
independent fix is the breakpoint. Everything else is Mail becoming a caller
of the components sections A–D create — and its `/` shortcut and its pane
doctrine going the other way, into the shared layer.

### OneMobility

**What exists.** Five custom-component screens — Network, Insights, Outlook,
Timetable, Protocols — declared through the manifest's `component` escape
hatch, plus a set of ordinary list screens for the reference doctypes.

**Where it diverges.**

None of the five renders a `PageHeader` or a breadcrumb. They are mounted
inside `ScreenHost`, which draws the crumb for a *list* screen — so a custom
component screen inherits a trail built for something else, and C1's audit
found no crumb in `ScreenHost` because `ScreenHeader` owns it. The
consequence: the five biggest screens in the product's richest space have
chrome that belongs to the list they are not.

Four of the five carry a `FacetBar` and each mounts it separately with its own
`facets` ref, its own `unavailable` array and its own watcher — B2's finding,
with the detail that the *duplication* is four-fold inside one module.

`Network.vue` is 2,177 lines, the second largest file in the SPA, and
`Insights.vue` is 859. Both are a screen, a data layer and a chart layer in
one file.

**Protocols is the one the user questioned, and the questioning is right.**
Its own docstring is a good argument for the *content* — *"the expensive
moment in a German integration is week six, when it turns out the part the
customer meant is not the part that was built"* — and no argument at all for
the *placement*. It is a rail entry beside Sources and Deliveries, where a
reader expects to configure something, and it configures nothing. It is ~400
words of shipped knowledge (A3) answering a question nobody is asking at that
moment.

**Verdict.** Protocols becomes an answer where the question is asked: a "what
can this read?" panel on the Sources screen and in the new-source flow,
showing the parts relevant to the folder in front of you, with the full shelf
one click away. The four facet bars become one, per B2. The five screens get
the same chrome as every other screen, which is C1's compact header. Network
and Insights get split, which is a `SPA cleanup`-shaped job rather than a
design one.

### OneCalendar

**What exists.** A diary that merges every doctype's dated records through
one server-side permission path — *"a quotation due on Tuesday, a site visit
on Wednesday and a review in their own diary"* — which is the right model and
is not duplicated anywhere.

**Where it diverges.**

Zero responsive prefixes across three files. A week grid on a phone is not a
narrower week grid; it is a day list, and that is a view type rather than a
media query.

Its sidebar is the fourth app sidebar and is the thinnest (91 lines) — one
`SidebarItem` — so it is a sidebar because the others are, not because it
carries anything.

It is one of the two surfaces with a literal-array breadcrumb (C1).

**Verdict.** The model is right and the surface is unfinished. It needs the
day-list view type for phones, and its sidebar should either carry the
calendar filters (which calendars are shown) or stop being a sidebar.

### The guard for all three

1. A `component:` screen renders `<ScreenChrome>` — the same header every
   list screen gets — so a custom screen cannot inherit a list's trail.
2. One `FacetBar` mount per module, asserted by import count.
3. No `.vue` file over 1,200 lines; `Network.vue` and `Insights.vue` are the
   two exceptions to retire.
4. The 390px baseline from D4 covers the diary and the five mobility screens.

## E7. The workspace surfaces — account, settings, the operator console

### What exists

**Settings** is the most disciplined surface in the product. `tabs.py`
declares 22 tabs, each with a key, a label, an icon, a section (`You` /
`Workspace`), a kind (`PANEL` for a written component, `FIELDS` for a
declarative spec out of `workspace.GROUPS`) and an audience. The server
decides what a reader may open; the dialog draws what comes back. Two kinds
rather than one is a good split: a settings page that is only fields is
declared, and one that is a real interaction is written.

**Account** is a page with usage bars, plan, billing and apps.

**The operator console** is a Space like any other — its screens are declared
and its custom components are registered in `screens/index.js` under
`onespace-ops/*`, which is the same escape hatch OneMobility uses. That is
the right architecture and is worth protecting.

### Where it diverges

**Account and Settings answer overlapping questions in two places.**
`Account.vue` draws Usage (files, database, people, AI credits), the address,
the custom domain, and the plan. Settings has a Storage tab (usage again), a
Domain tab (the custom domain again) and a People tab (people again). A
reader looking for "how much space am I using" has two correct answers in two
surfaces with two different renderings, and "change my domain" is in Settings
while "see my domain" is on Account.

The split that would make sense — *Account is money and identity, Settings is
configuration* — is not the split that exists.

**`Account.vue` embeds settings components directly** (`<ThemeSetting />`,
`<NotificationSettings />`), so two of Settings' panels also render inside
Account. That is one component in two places, which is fine, wrapped in two
different chromes, which is C2's problem again.

**Nothing in Settings is addressable** — C4's finding, and it bites hardest
here because there are 22 destinations behind one door.

**The ops console has thirty screens and nine custom components**, and
`docs/ONEADMIN-SIMPLIFICATION.md` already audited them against the test *what
does a person do here that a machine could not*. That document's verdict —
twenty of twenty-nine rail entries are places to go looking for a problem —
is a finding this audit does not need to repeat, and the `Attention` screen
(#302) was the first stage of it. It should be folded into the synthesis as
an already-planned arc rather than re-derived.

**The ops screens are the only heavy users of `<ListRow>`** (nine files, all
ops or account). They got the frappe-ui list treatment because they were
built after it existed; the product surfaces were built before. That is
B1's history in one sentence, and it means the ops console is the closest
thing in the repo to a reference implementation.

### What the one version is

**One rule for the Account/Settings split, and it is about who is being
asked.** Account is the *commercial relationship*: the plan, the invoices,
the credits, the apps you have bought, the quota you are against. Settings is
*how this workspace behaves*: branding, sign-in, printing, naming, mail,
roles. Usage appears on Account because it is what you are billed on; the
Storage *tab* keeps the file-level breakdown, which is a different question,
and says so.

**Settings panels are reachable directly** (`?panel=backups`) — C4.

**Account stops embedding settings panels** and links to them instead, which
is what an address makes possible.

**The ops console is the reference implementation and is named as one.** When
B1's `<DataList>` lands, ops migrates first, because it already uses the
components and the migration is therefore a proof that the contract is right
before Drive and Mail depend on it.

### What it costs

Small. Moving three overlaps is a day, the addressing is C4's work, and the
ops console mostly needs nothing from this plan beyond inheriting it — its
own arc is `docs/ONEADMIN-SIMPLIFICATION.md` and stays there.

### The guard

1. A question is answered on one surface: a test that no two tabs/pages
   render the same `workspace.GROUPS` key or the same usage endpoint.
2. Every `tabs.py` key resolves to a component or a group — this exists; it
   extends to "and is reachable by URL".
3. `screens/index.js` is the only registry of custom screen components, for
   ops and for spaces alike.

## E8. AI

### What exists

More than the user's impression suggests, which is itself the finding — the
good parts are not visible often enough to register.

`AiGlow` is a real piece of design and its docstring is the argument:

> *A spinner says "the application is busy"; a sheen over the actual words
> says "this text, here, is being written", which is the only fact worth
> drawing… "AI is happening" needs to be recognisable at a glance across
> mail, a document and a sheet, and a different palette in each would defeat
> that before it started.*

Three modes (block, inline, overlay), a skeleton at the width the answer will
be so the page does not jump, and `prefers-reduced-motion` leaving a static
tint. `AiMark` says one value was model-written, once, everywhere. The verbs
are declared in `shared/lib/ai/verbs.js`. The assistant has a **name and an
avatar a tenant sets** (`AiSettings`), both in the boot payload so the rail
can draw them before anything is fetched.

### Where it diverges

**The avatar is settable and rendered nowhere.** `assistant.avatar` is in the
settings form, in the boot payload and in the reactive — and the only
component that renders it is the settings form that sets it. Not the rail
entry, not the chat panel, not a chat turn, not the mark. A tenant uploads a
face for their assistant and never sees it again.

**The name reaches five files; sixteen strings hardcode the words.**
`assistantName` is used by `AiMark`, `AssistantPanel`, `nav.js`, `Chat.vue`
and the composable. Meanwhile: *"Ask AI"*, *"Ask AI…"*, *"Write with AI"* ×2,
*"Assistant"* ×2, *"Close the assistant"*, *"The assistant"*, *"Use AI in
this workspace"*, *"Written by AI. Check it."*, *"Written by AI. Read it
before you send it."* A workspace that named its assistant *Rua* has a rail
entry saying Rua and eleven other places saying AI.

**Three AI palettes.** The `oneai` brand mark is a rose gradient
(`#fda4af → #e11d48`). `AiGlow` is indigo and pink (`--oneapp-glow-one:
rgba(99,102,241)`, `--two: rgba(236,72,153)`). `AiMark` is amber
(`text-ink-amber-4`). Three colours for one idea, and the amber one collides
with the warning colour used by four `Alert`s.

**`AiGlow` renders in four files.** DocEditor, MailComposer, Mail, Sheet. Not
in a field, not in a cell, not in the chat panel itself, not on a record's
generated summary — so the one component built to make AI feel like something
appears on four surfaces out of the dozen that call a model.

**The chat panel is a chat panel.** It is a transcript and a composer. There
is nothing wrong with it and nothing in it that says this product's assistant
knows the workspace — no faces, no record chips in the answers, no sources
strip, no glow while it thinks. `SuggestionCard` exists and is used twice.

### What the one version is

**The assistant is a character with a name and a face, and they appear
together.** Rail entry, chat header, every assistant turn, the mark on a
generated value, the empty state of the panel, the composer's placeholder.
`assistant.avatar` falls back to the `oneai` mark when unset, so there is
always a face.

**One AI palette, and it is the glow's.** Indigo→pink is the strongest of the
three and is already the one that moves. `AiMark` changes from amber to the
glow's accent — which also stops it colliding with warning. The `oneai` brand
mark stays rose because a brand mark is allowed its own colours (C3), but the
*interface* language is one.

**Every string that names the assistant uses its name.** Sixteen strings
become `__('Ask {0}', [assistantName])` and the rest.

**The glow goes everywhere a model writes.** A field, a cell, a chat turn, a
generated summary — the component exists and the modes cover all of them; it
is a matter of wiring `AiGlow` into `FieldControl`, `EditableCell` and
`ChatTurn`.

**And the premium moment is the answer arriving, not the chrome around it.**
The user asked for glows and colour; the honest version of that ask is that
the *moment of generation* should be the most crafted three seconds in the
product. The parts exist: the sheen, the skeleton at the right width, the
face, the sources. What is missing is that they are never all present at
once. One surface — the assistant panel — should have all of them, and it is
the reference the rest copy.

### What it costs

Small, and almost all of it is wiring. The avatar is a component and six call
sites. The palette is three token swaps. The sixteen strings are a copy pass.
`AiGlow` into three more components is a day. The assistant panel as a
reference surface is the only design work, and it is worth doing first
because it defines what the others copy.

### The guard

1. A visible string containing "AI" or "Assistant" fails unless it is the
   product's own noun (*AI credits*, *AI usage* — a billing term, not the
   assistant).
2. Anything that renders an assistant turn renders `assistant.avatar`.
3. `text-ink-amber-*` is refused in an AI context; one accent token.
4. A component that awaits an AI call and renders no `AiGlow` fails.

## E9. OneCode — the groundwork

This section is rails, not the arc. What has to be true *before* OneCode is
built so that it lands inside the system rather than beside it.

### What exists

More than expected. A `onecode` server module with `languages.py` and
`legal.py`; `CodeFile.vue`, `CodeDialog.vue` and `LanguagePicker.vue` in the
SPA; `CODE` as a first-class `custom_kind` in the Drive with extensions
mapped; `test_onecode.py` guarding that the Python and JavaScript language
catalogues agree. A **brand mark for OneCode already exists** in
`shared/lib/brand/marks.js` (amber, an editor tile with a prompt chevron).

So today a tenant can make a `.py` or a `.js` in the Drive and edit it with
syntax colouring. What they cannot do is *run* it or *serve* it.

Frappe's `Web Page` gives: a `route`, `content_type` (HTML among others),
`main_section_html`, a `javascript` field, `custom_css`, `dynamic_route`
(`/project/<name>`), `dynamic_template`, and — the important one —
`context_script`, a Python field that sets the template context before
rendering. That is a server-side hook with the Frappe object in scope.

And there is a working reference for the whole shape: **this SPA**.
`www/one.py` builds a boot context and `one.html` is a shell; the assets are
built files. A tenant-authored app is the same arrangement with different
assets and a narrower context.

### The four questions the groundwork has to answer

**1. Where does a project live?** In the Drive, as a folder of `File` rows —
not a new store. E1's argument applies unchanged, and it buys a great deal
for free: versions, sharing, the bin, WebDAV (so a tenant can mount their
project in VS Code and edit it locally), the AI's existing file verbs, and
templates. A project is a folder with a manifest file in it; nothing else
distinguishes it.

**2. How is it served, and what has the Frappe object?** Split, exactly as
this SPA is split:

- the **shell** is server-rendered by Frappe — a `Web Page` with a
  `dynamic_route` claimed by the project, whose `context_script` calls one of
  our whitelisted context builders. That is where the Frappe object lives,
  and it is where permission is decided.
- the **assets** are `File` rows served from R2, public or presigned
  depending on the project. `r2.public_url` and `cdn.4dl.app` already exist.

This is the only arrangement in which a tenant's page can both be
multi-file-static *and* know who is looking at it.

**3. What engine?** The requirement is zero build, and the honest reading is
that "buildless" is a property of the *module graph*, not of the framework.
An import map plus native ES modules is the mechanism; then:

- **Vue 3** ships `vue.esm-browser.js` and its SFCs need a compiler — so
  buildless Vue means `defineComponent` with template strings, which is
  workable and is what most buildless Vue looks like.
- **Preact + htm** is the smallest honest answer: 4 KB, JSX-like syntax in
  tagged templates, no build, and it is a well-trodden path.
- **Alpine** or **Lit** for anything that is enhancement rather than an app.

The rail to lay now is not the choice — it is that **the shell serves an
import map the workspace controls**, so the engine is a line in a manifest
rather than a decision baked into the loader. Pin versions, serve them from
our own CDN rather than a third party (the CSP argument and the offline
argument are the same argument), and let a project declare which it wants.

**4. What can a tenant's code reach?** This is the security surface and it is
the reason this section exists before the arc. The answer must be: **nothing
it is not handed.** Concretely — the `context_script` escape hatch is *not*
exposed to tenants; a project declares a *manifest* naming the doctypes and
endpoints it needs, the same shape a Space's manifest already takes, and the
shell builds the context from that declaration under the reader's own
permissions. `linked.py`'s doctrine is the precedent: *"Nothing here takes a
doctype, a filter or a fieldname from the caller."*

### What has to be true before the arc starts

These are the rails, and most are things other sections already want:

1. **A project is a Drive folder** — needs E1's virtual-scope work so a
   project can be mounted and served without a second store.
2. **A manifest shape for a tenant app**, reusing the space manifest's
   validation. `test_manifests.py` and the ENF-1/ENF-2 guards extend to it.
3. **An import map the workspace serves**, with pinned versions on our CDN.
4. **A route registry** — which project claims which path, checked for
   collisions with our own routes at save time, not at request time.
5. **The editor is OneDoc's second editor, not a new one.** `Doc.vue` already
   routes to CodeMirror for anything whose content is its own bytes. A
   multi-file project is a file tree beside that editor — which is B1's
   `FileSource` with a different presentation, and E2/E3's `EditorChrome`.
6. **The AI knowledgebase is the existing verbs plus a project-scoped
   index.** `ai/verbs.js` and the retrieval work from AI-4 already do
   per-record scoping; a project is a folder, and a folder is a scope.
7. **A `Code` place in the Drive's rail**, per E2/E3's rule — mechanical from
   `kinds.py`.

### What it costs, and what it does not

The groundwork is mostly *other sections landing*: E1's scopes, E2/E3's
editor chrome, B1's `FileSource`. The genuinely new pieces before the arc are
the manifest shape, the import map and the route registry — a week, and none
of it is OneCode-specific enough to be wasted if the arc changes shape.

What must **not** happen: a second file store, a second editor, a second
permission path, or a `context_script` a tenant can write. Each of those is
an afternoon's convenience and a year of consequences.

### The guard

1. A tenant project's context comes from a declared manifest; a
   `context_script` authored by a tenant fails validation.
2. A project's route cannot collide with `/one`, `/api`, `/app` or another
   project's — checked on save.
3. The import map's entries are pinned and served from our own host; an
   external `src` in a served project fails.
4. The language catalogue guard (`test_onecode.py`) extends to the import map:
   an engine offered by the picker and absent from the map is a project that
   will not load.

---

# Part 3 — The synthesis

## F1. What the sections could not see on their own

Twenty-two sections, and three patterns run under all of them.

### The abstraction is built at the second caller and abandoned at the third

This is the root cause, and once you see it the audit reads as one finding
repeated.

    RecordDrawer's pane/drawer doctrine   1 object, 6 that need it
    notify.js's "never call toast"        16 callers, 7 that bypass it
    useCrumbs                             1 surface, 9 that need it
    useRows / useSorting / usePeek …      1 consumer each
    OneSpace Saved View (the storage)     general; 1 client
    AiGlow                                4 surfaces, 12 that call a model
    FilePicker                            8 callers, 4 that bypass it
    UploadTray                            1 mount, everywhere that uploads
    RecordTable                           2 callers, 16 lists
    shared/ components                    7 with a single caller

In every case somebody did the right thing — extracted a component, wrote a
rule in a docstring, generalised a doctype — at the moment they had two
callers. And in every case the *third* caller did not arrive through the
abstraction, because nothing made it. The doctrine was in a comment and the
comment was in the file the third caller never opened.

**So the rails are not about writing better abstractions.** The abstractions
here are good. The rails are about the third caller: a guard that fails when
a surface re-implements something that exists, which is what most of the
guards below are.

### Every guard that failed, failed at the edge of its own scan

Four times, independently:

    the datetime guard      reads .vue;   the 28 offenders are .js
    the shadow guard        matches shadow-sm|md|lg|xl|2xl;  29 offenders are bare `shadow`
    the copy reader         extracts quoted strings;  the offenders are template literals
    the i18n suite          covers oneapp;  oneapp_control has a POT and no locales

Each *rule* was right. Each *scan* had a hole, and the code drifted into
exactly the hole — not out of malice but because the hole is where nothing
stopped it. The repo already knows this trick in three places
(`test_the_audit_is_actually_reading_things`,
`test_a_retired_token_would_be_caught`,
`test_the_deprecation_reader_still_finds_one`): a test that the guard would
catch a known offender. It is applied to three guards out of eighty.

**Every guard gets a witness.** That is the single highest-value rail in this
document, because it is the one that keeps the other eighty honest.

### Three findings are the same finding

B1's `ListSource.capabilities`, B2's "this facet is unavailable and here is
why", and E1's scoped WebDAV share are one idea seen from three directions:

> **A source declares what it can do, and the surface renders exactly that
> much.**

A remote mount cannot count its rows. `serviceHour` has no vehicle column. A
saved view of a fact table cannot be sorted by a column it does not hold. In
every case the honest answer is not to hide the control and not to offer a
control that fails, but to show it, disabled, with the reason — which the
FacetBar already does and nothing else copies.

Name it once, implement it once, and B1, B2 and E1 become three callers of
one mechanism.

### Two numbers that should be one, twice

The breakpoint is 768 in the shell and 640 in 77 layout utilities. The type
scale is prose leading in 473 places and label leading in 178, with 109
elements wearing the wrong one. Both have a correct, documented intent and
incorrect usage, and both are mechanical to fix and mechanical to guard.

### Maturity tracks build order exactly

    ops + account     built last     9 files use frappe-ui's ListRow
    record engine     built next     RecordTable, the composables
    Mail              before that    hand-rolled rows, right doctrine
    Drive             before that    hand-rolled everything, 1,080 lines
    the editors       vendored       no chrome, no phone
    Calendar          last but thin  no responsive anything

Nothing built before a component existed uses it. This is why the ops console
is the reference implementation, and why it migrates first when `<DataList>`
lands: it is the cheapest proof that the contract is right.

## F2. The plan

Six stages. The ordering rule: **fix defects immediately, then establish what
everything is measured against, then the shared parts, then the engine, then
the surfaces that consume it.** A stage is done when its guard is green and
its checkpoint passes.

### Stage 0 — the defects (days, not weeks)

Found by the audit, not refactors, and none of them waits for anything.

- Delete on the open record (B3). Four lines.
- `read_only_depends_on` enforced on the server, the child table and the
  inline cell (B5). A field the form locks is currently writable from a grid
  and the save is accepted.
- The breakpoint: `sm:` → `md:` on layout utilities (D4). The 640–767 band
  is a mobile shell around a desktop layout.
- Drive's sort and view out of `localStorage` (C4) — a shared Drive link
  currently arrives in the recipient's last-used order.
- The two untranslated toasts and the fourteen English template literals
  (D2).
- `oneapp_control` gets `ar.po` and `de.po` (A3).

**Checkpoint:** each has a test that fails before and passes after.

### Stage 1 — the vocabulary (1–2 weeks)

Nothing here changes behaviour. Everything after is built against it, which
is why it is first.

- A1: the type role rule, the 109 `truncate`+`text-p-*` fixes, three ink
  roles, four elevations, the three clustered tokens.
- A2: `<Panel>`, and 41 files lose a class list.
- B4: five row states, five treatments — open as a leading edge, focus as a
  ring. The highest visible-quality-per-hour item in the document.
- D1: `lib/format`, reading the workspace's own date and number settings.
- A3: the prose budget, and the seven stacked screens rewritten.

**Checkpoint:** a screenshot set of ten surfaces, before and after, at both
themes. Nothing moves except what was meant to.

### Stage 2 — the shared parts (2–3 weeks)

- A2: `<Row>` and `<Picker>` (twelve pickers → one).
- B2: `<Narrow>` (the FacetBar's interaction over QuickFilters' source), one
  search box with Mail's `/`, one sort.
- B3: the row menu, and two destructive words product-wide.
- D2: `notify` as the only door, and `notifyUndoable` — which is what lets
  the confirmation dialogs drop to the irreversible ones only.
- D3: `<UploadTray />` into the shell (one line, large effect),
  `v-drop-files`, the size ceiling stated before it is hit.
- C1: one crumb root, and the subject as an element rather than a crumb.
- E8: the assistant's face wherever its name is, one palette, the glow wired
  into fields, cells and turns.

**Checkpoint:** a person can do the same thing the same way in Mail, Drive
and a record list — hover a row, open its menu, delete it, undo it.

### Stage 3 — the engine (3–4 weeks)

- Name and build the capability contract (F1's third finding) once.
- B1: `ListSource` + `<DataList>`. `StaticSource` first — seven surfaces,
  nearly mechanical. Then **ops migrates as the proof**. Then `FileSource`,
  then `ThreadSource`, then `DoctypeSource` last, because it is the one that
  must not regress and the browser suite is its check.
- B5: one field-state resolver, three renderings, read-only as text.
- C4: the typed `at` parameter, addressable panels.
- The selection itself, which the checkpoint turned out to be about. `DataList`
  holds what is ticked for any source declaring `CAN.BULK`: a `Set` keyed by
  `identify()`, shift-range, select-all, and a prune after every read. It had
  been written three times — `useDrive`, `Mail.vue`, `useRows` — and the three
  disagreed about what a re-read does to it: one pruned, one emptied the
  selection, one cleared on the verb only. Where the bar *floats* stays the surface's, because Mail's
  list is a 384px column and the Drive's is the whole pane; what it looks like
  does not, and the Drive's hand-rolled `Panel` became the shared
  `SelectionBar` with an `anchor`.

**Checkpoint:** Drive sorts by size; a record's Files tab selects two files
and deletes both; a saved view exists in Mail. None of those is built — all
three are consequences.

**What the checkpoint found.** Two of the three are done and the first was
already. The Files tab needed no feature: it declares `bulk` when this person
may write, passes `picked`/`toggle` down to the row it already drew, and puts
the same bar under it — about twenty lines, which is the claim §B1 was making.

What it *did* need was two server bugs, both of which the verb had been hiding.
A record's Files tab listed every `File` row pointing at the record, binned
ones included, so "Move to the bin" appeared to do nothing — it now reads
through the Drive's own `_visible()`. And Frappe counts those same rows against
`max_attachments`, so four thrown-away files filled ERPNext Project's limit of
four for good: the tab showed nothing, and the fifth upload was refused with
nothing visible to remove. `OneSpaceFile.validate_attachment_limit` counts what
is visible and leaves the refusal itself to the framework. Neither is about
lists, and neither would have been found by reading the code.

Item three, a saved view in Mail, is not done: it needs a stored object on the
server rather than a control, which makes it Stage 4 work rather than a
consequence of the frame.

### Stage 4 — the surfaces (3–4 weeks)

- C2: the placement rule applied. Files out of dialogs and into panes.

  **Done so far.** `RecordPane` is `shared/components/ObjectPane.vue` — the
  rule is about the object, not the app, and the Drive had been opening files
  in it for a year before the name caught up. `FilePane` is the chrome around
  it: one header, one Share-a-link, one Download, one way out, and a body slot
  for the editors the Drive puts there. Three holders of one file became one,
  and `FilePreview` — the dialog a record's Files tab and a mail attachment
  used — is gone.

  `Rail`/`RailItem` are deleted from the barrel rather than adopted. They had
  no caller in three years; "the rail" is this product's word for the
  app-level column, which is a `Sidebar`, and frappe-ui's `Rail` is a narrow
  strip of icons that is not what any of ours are. `lib/shell/sidebar.js` says
  so where the width and the collapsed state already live.

  **Configuration in one place, done.** `tabs.py` declares a `Connections`
  tab beside Storage and Backups, and `ConnectionSettings.vue` is the panel:
  every mount, where it points, whether it is being read, and the three things
  that can be done to one. The form itself is unchanged — `ConnectFolder` is
  the dialog that proves a connection before it writes the row, which is the
  whole feature, and moving where it opens from is not a reason to have a
  second one.

  The Drive keeps both ways in, because that is where a person is standing
  when they think of it; what changed is where they land. "Connect a folder"
  in the New menu and "Connection settings" on a mount both call
  `openSettings('connections')` now, which C4's `?panel=` makes a place you can
  link to rather than a dialog you have to find.

  The guard is mechanical and is the rule stated once: `ConnectFolder` has
  exactly one caller, and it is a settings panel. A surface reaching for a
  credential form again fails.
- E1: scoped shares. Mount `doctype:Quotation`; drop a file into
  `QTN-0001/` in Finder and watch it appear on the record. A *Records* place
  in the Drive.

  **Done so far.** `onestorage/scopes.py` is the vocabulary and the resolver:
  `folder:`, `doctype:`, `document:`, `place:`, each resolved through
  `query.py`'s own filters. `Drive Access` carries a `scope`, and a key
  written before it says `folder:<what it said>` — which is the whole of the
  migration, with no patch and nothing to backfill. `dav.py` walks nodes
  rather than `File` rows, so a mounted `doctype:Project` is one directory per
  record that has a file on it, assembled at PROPFIND time with nothing
  created.

  The genuinely new work — a write *into* a virtual directory — is done and
  exercised end to end: a `PUT` to `/dav/PROJ-0001/drawing.pdf` checks the
  **record's** write permission and lands the file with `attached_to_*` set,
  and a `PUT` into the doctype's own directory is a 409 rather than a loose
  file in Home.

  The *Records* place is in the rail and is the same tree from the same
  resolver: a directory per kind of record that has a file on it, then one per
  record, then the record's own files — and the third level is literally the
  `record` place, so the Drive and a record's Files tab remain one query. It is
  the one place that is a tree rather than a `where`, and `query.py` has no
  clause for it on purpose, which a guard now holds. Nothing is made there:
  New and Upload are drawn and refused with the reason (§F1's middle state)
  rather than dropped.

  And `Home/Attachments` is no longer where an attachment lands.
  `OneSpaceFile.set_folder_name` leaves an attachment folderless, and Home's
  root excludes what is attached — the second half is what makes the first
  safe, because Home lists `folder in ["", "Home", None]` and dropping the
  bucket alone would have put every attachment in the workspace at the top of
  the drive. `Home` on an attachment is cleared as well as absent: Frappe's
  `upload_file` defaults the field to `Home` when the caller sends none, so it
  is the default wearing the name of the root rather than a choice.

  E1 is done bar the picker: the one thing not built is a *scope picker* in the
  share dialog, which still asks the folder question by picking a folder. The
  server takes any scope; the dialog offers one kind of it.
- E2/E3: `Documents` and `Workbooks` places; `EditorChrome` on both editors;
  the sheet's identity bar prised out of the vendored file.

  Done, except for the phone designs, which are Stage 5's. The two places are
  `kinds.PLACE_FOR` inverted into a `where custom_kind = ...`, and the guard
  reads both back so a kind with an editor and no door fails mechanically.
  `EditorChrome` is the bar above both editors: the trail, the mark, the title
  renamed in place, and slots for what is true of the file right now and what
  can be done to it. Bar 1 is gone from the vendored `index.vue` and from
  `editor.css` with it — so the sheet, which had no crumb at all, has a way
  home, and a document's rename is no longer a dialog off the menu.

  Two things the swap taught, both caught in the browser rather than by the
  4,254 guards:

  * `PageHeader` is a *teleport*. An editor hosted in the Drive's pane that
    draws one puts its title in the shell's header, above the list it is
    sitting beside — so the component takes `hosted` and draws a bar of its
    own instead. Nothing static could have seen it.
  * The guard that says every page opens with the trail matched component
    *stems*, so a page two hops from the nav — `Sheet.vue` → `SheetEditor` →
    `EditorChrome` — read as headerless. It now resolves each file's mounts
    through its own imports and walks them to a fixpoint, which is also what
    let `HEADERLESS_PAGES` empty out.

  What is left of the vendored seam is Bar 2. The toolbar is still Frappe's
  grouping inside Frappe's file, which is what makes "show the text size"
  a change we cannot yet make; Bar 1 leaving is the precedent for it.
- E4/E5/E6: Mail becomes a caller; the four facet bars become one; Protocols
  moves to where the question is asked; the diary gets a day view.
- E7: Account is money and identity, Settings is configuration.

**Checkpoint:** every routed surface has the same crumb root, the same row
behaviour, the same actions and the same feedback. A screenshot of ten
surfaces should look like one product.

### Stage 5 — mobile (2 weeks)

- The four phone designs (sheet, document, diary, mobility charts).
- The 390px baseline per routed surface.
- The 168 skips audited into `touch-only`, `covered-elsewhere` or a gap.

**Checkpoint:** the baseline set passes, and no surface has zero mobile
consideration.

### Stage 6 — OneCode rails (1 week, then the arc)

- The tenant-app manifest, on the space manifest's validation.
- The workspace-served import map, pinned, on our own host.
- The route registry with collision checking at save time.
- `Code` as a Drive place; the project as a folder; the editor as OneDoc's
  second editor with a file tree.

**Checkpoint:** a folder of files, a claimed route, a shell with a declared
context, and a page that renders — with no build step and no second store.

## F3. The rails

### The one meta-rail

**Every guard has a witness.** A test that the guard catches a known
offender. Three of the eighty have one; the four failures in F1 are all
guards without one. This is written first because it is what makes the rest
of this list mean anything.

### The rails, by what they prevent

**Re-implementing what exists**

1. A `v-for` rendering an element with `hover:bg-` or `divide-y` outside
   `Row.vue`.
2. A class list with `rounded-6` + `border-outline-` + `bg-surface-` outside
   `Panel.vue`.
3. A component named `*Picker` that does not import `Picker.vue`.
4. A surface rendering more than five rows from an array that is not a
   `<DataList>`.
5. `<input type="file">` outside `FilePicker` / `CameraCapture`.
6. `@drop` without `v-drop-files`, unless declared as reordering.
7. `toast` imported anywhere but `notify.js`.
8. A search input that is not `<ListSearch>`.
9. A settings panel outside `components/settings/`.
10. A file in `shared/components/` with fewer than two importers — the guard
    against premature generalisation, which is the other half of this list.

**Drifting from one answer**

11. `truncate` or `whitespace-nowrap` in a class list carrying `text-p-*`.
12. `sm:` on a layout utility; `md:` and above only.
13. `dayjs(`, `toLocale*String`, `Intl.DateTimeFormat` in `.vue` **and**
    `.js`; a date format string outside `lib/format`.
14. `shadow` unqualified; four named elevations only.
15. An arbitrary value (`[…]`) appearing in more than one file.
16. `:disabled` on a `FieldControl` — the prop is `state`.
17. A destructive verb whose label is not one of the two sanctioned strings.
18. A `route.query` key outside the declared set.
19. `localStorage` written outside one `remember()` helper with a declared
    key.

**Saying the wrong thing**

20. A visible string over 20 words; a file over 60 words of prose.
21. An English sentence of five words or more in Python outside `_()` or
    `prompt()`.
22. A `notify*` argument that is a bare string or template literal.
23. A visible string containing "AI" or "Assistant" that is not a billing
    term.
24. Every app with a POT has a complete `.po` per shipped locale, or a named
    exemption — `oneapp_control` has one and it is argued.

**Leaving somebody behind**

25. `focus-visible` on every interactive row.
26. Every routed page has exactly one breadcrumb, from `useCrumbs`, whose
    first crumb resolves to the same route.
27. Every dialog openable from a menu has an address.
28. A `test.skip` on mobile names a declared reason, and
    `desktop-chrome-by-design` points at the phone equivalent.
29. A 390px screenshot baseline per routed surface.

**Keeping the architecture**

30. Every `ListSource` matches the interface; a capability declared and not
    implemented, or implemented and not declared, fails.
31. Every scope kind resolves through `query.py`; no second query builder.
32. No file is written to `Home/Attachments`.
33. `screens/index.js` is the only registry of custom screen components.
34. A tenant project's context comes from a declared manifest; a
    tenant-authored `context_script` fails.
35. No `.vue` file over 1,200 lines.

### What not to do, whatever it costs

These are the afternoon conveniences with year-long consequences, named so
that a future arc has to argue against a sentence rather than invent the
objection:

- **No second file store.** A document, a workbook, a project, a record's
  attachments and a mounted folder are all `File` rows. Every place is a
  `where`.
- **No folder per record.** E1 argues it; the argument does not expire.
- **No second editor.** Prose is OneDoc, bytes are OneCode, a grid is
  OneSheet, and a new file type picks one of the three.
- **No second permission path.** `linked.py` is the only narrow surface and
  it exists because Frappe cannot grant to a guest.
- **No `context_script` a tenant can write.**
- **No component in `shared/` before its second caller, and none left there
  after its first leaves.**
- **No new toast, crumb, row, panel, picker or upload affordance.** There is
  one of each. If it does not fit, change the one.

---

# Part 4 — What has landed

Kept here rather than in a changelog because a plan nobody marks up is a plan
that stops describing the code. One line per item, with the commit.

## Stage 0 — the defects

- **0a. Delete the record you are looking at.** The verb was reachable only
  through the selection bar. `remove` already took one name or a list, so the
  server needed nothing; the record menu now carries a `theme` through and
  sorts on it, and `removed` is its own event because the host has to reload
  the list as well as shut the pane.
- **0b. `read_only_depends_on` is enforced everywhere.** The form honoured it
  and the child table, the inline cell and the save path did not — so a field
  the form locked was writable from a grid and the save was accepted.
  `shared/fieldrules.py` is a port of `rules.js` rather than a call to
  `safe_eval`, because the expression is written in the desk's JavaScript
  dialect; a 31-case corpus runs through both and every answer must match.
- **0c. One breakpoint.** 54 layout utilities moved from `sm:` to `md:`, so
  the 640–767 band stops being a mobile shell around a desktop layout. The
  settings dialog is the one exemption and is declared as one: its geometry is
  frappe-ui's, which switches at 640, and matching the library beats matching
  ourselves inside a dialog.
- **0d. The Drive's order is in the link.** Sort key, direction and grid-or-list
  were localStorage only, so a link to a folder arrived in whatever order the
  recipient last used. They are query parameters now, with localStorage as the
  default when the link is silent — the same shape the list engine already
  used, rather than a second one.
- **0e. The toasts the guard could not see.** `copy_reader.py` read text nodes
  and `__()` calls and not template literals, so seven toasts built with
  backticks were invisible to both the i18n guard and the copy guard. The
  reader takes them now, with `{0}` substituted for each hole, and
  `useBulkActions` takes a function rather than a string so the count can be
  interpolated inside the translated sentence instead of stapled to it.

## Stage 1 — the vocabulary

- **A1. Type, ink, elevation and the measurements nobody named.** Five
  changes, no behaviour. 111 class lists in 58 files had `truncate` beside
  `text-p-*` — paragraph leading on text declared single-line, about 6px of
  extra height per row, and most of why dense surfaces read loose. 768 tokens
  in 162 files became roles: `text-ink-primary`, `-secondary`, `-muted` (with
  gray-7 folding into secondary), `shadow-raised`, `-floating`, `-over`, and
  eight clustered arbitrary values that turned out to be measurements —
  `h-overlay`, `max-w-measure`, `max-w-page`, `min-h-body`, `auto-rows-tile`,
  `bottom-scrubber`. Two of the section's findings did not survive contact and
  are struck through above; one new one (gray-4 and gray-5 are the same colour
  in dark) came out of executing it. One visible move rather than none: the
  print preview in the format builder grows from 62vh to 70vh, because two
  frames doing the same job at two heights is the divergence being removed.
- **A2. The bordered rectangle is a component.** `<Panel>` is generated into
  both bundles, because the signup page draws panels too and a panel that
  looks different on the way in is the first thing a customer sees. 32 call
  sites across 26 files; the thirteen spellings become four props, and the two
  print previews that had drifted to different heights are one value. Three
  sites are not panels and stayed as they were — a chat bubble, a dashed
  dropzone, a file row — and the guard does not flag them because their ground
  is a conditional rather than a static class list, which is the honest line:
  `test_the_panel_shape_is_a_component` refuses the incantation, not every
  rounded thing.
  The shared folder got its rule too. `PresenceStrip` had one caller and the
  workbook had hand-rolled the same row of faces in vendored CSS — so the
  workbook is its second caller now, and the one thing the sheet's version did
  better (a tooltip saying which tab somebody is on) became `note` on the
  shared one. `BrandLockup` had no callers at all and is deleted.
  `test_a_shared_component_is_shared` holds the line: two modules, or one
  other shared file, or it does not belong in `shared/`.
- **B4. Five row states, and two of them are not fills.** `lib/rowstate.js`,
  generated into both bundles. Hover is a *lighter* step than selection, focus
  is a 2px inset ring, and **open is a leading edge** — which is the whole
  trick: a row can now be open and hovered and ticked at once, where three
  fills fighting over one background is why there was only ever one colour for
  all three. The accent for the edge and the ring is the workspace's own
  (`--surface-gray-10` / `--outline-gray-8`, which is where `theme.js` paints
  it), so "you are here" is the same colour as the solid button in every
  workspace. Applied to the engine's list, Drive's files, Mail's threads, the
  version panel, the notification feed and Attention; the editable cell stops
  painting its own fill and hangs its affordance off `group/row`, so the cell
  under the pointer no longer looks like the thing about to be acted on when
  clicking it opens the record.
- **D1. One clock, and it is the workspace's.** `lib/runtime/format.js`:
  `date`, `time`, `moment`, `ago`, `number`, `money`, reading `date_format`,
  `time_format`, `number_format`, the two precisions and the currency off the
  boot payload — settings a person could already change, that wrote through to
  System Settings, and that nothing read back. 28 `dayjsLocal` call sites and
  33 `toLocale*`/`Intl` ones became calls into it; the browser's own
  formatting is refused in `.vue` **and** `.js`, which is the extension where
  every offender lived. `ago()` carries the one rule — relative under seven
  days, a date over it — so the same column is not relative on one surface and
  absolute on another. Two exceptions are named rather than silent: the
  spreadsheet's `TEXT()` and its number formatter answer to the cell's format
  code rather than to the workspace, which is what a formula is for.
  `versions.py` stops rendering a timestamp into a stored title, because that
  is the one thing a browser can never undo.
  `tests/js/hooks.mjs` is new and is what makes this checkable: it resolves
  the `@/` alias and stubs the barrel and the boot payload, so `test_format.py`
  can set a workspace to `dd.mm.yyyy` and `#.###,##` and read back what a
  column says — and `test_number_format.py` now runs through it too.
- **A3. The prose budget, and 44 paragraphs that were help lines.** Not one
  string in either SPA now runs past twenty words; the 44 that did were cut
  without losing the fact each was carrying — the one that tried
  (StorageSettings' "including files on records you cannot open") was caught
  by the test that pins it, which is the right way round.
  The stacking rule landed as a **ratchet rather than a cap**, and the audit's
  own guard #2 is amended for it: a flat sixty-word ceiling would have pushed
  somebody to split a file rather than shorten a screen, and several of the
  worst files hold mutually exclusive branches of one message where no reader
  ever sees more than one. `tests/prose_budget.txt` records what each of the
  twenty-two over-sixty screens carries today and
  `test_a_screen_carries_no_more_prose_than_it_did` only lets it go down;
  `scripts/prose_budget.py` re-measures after a cut.
  Two parts of A3 are not in this: the 206 English sentences shipped from the
  server (a scan written fresh finds 671 by a looser definition than the
  audit's, and reconciling the two is its own pass rather than a guess), and
  Protocols moving to where the question is asked, which E5 owns in Stage 4.

## Stage 2 — the shared parts

- **D2. One door, and an undo to put behind it.** `toast` is gone from the
  barrel and out of `notify.js`'s exports; the eight raw calls in five files
  go through `notifySuccess`/`notifyError`/`notifyWarning` and get the sound,
  the parsed Frappe error and the eight-second duration they were missing.
  `notifyUndoable(message, undo)` is new and is the point of the section: the
  reason fifteen files reach for a confirmation dialog is that undo did not
  exist anywhere in the product — the word appeared eight times, always in
  prose explaining that something *could not* be undone. The rule for which
  channel carries which news is written at the top of `notify.js` and is
  about how long the news is true for.
  One guard is not about D2 at all and is here because the bug is: an import
  statement nested inside another, which this arc produced three times from
  the same "insert after the last `^import`" helper. ESLint catches it
  everywhere except the eslint-ignored sheets editor, where it reached a
  build. `test_no_import_landed_inside_another_one` does not care which file
  it is in.
- **A2. `<Row>` and `<Picker>`, and what the audit's counts got wrong.**
  `shared/components/Row.vue`, generated into both bundles: it *derives* its
  element rather than taking one — a link where there is somewhere to go, a
  button where there is not — which matters because four of the hand-rolled
  rows were clickable `<div>`s that no keyboard could reach. Above that, the
  hit target, the five states from `lib/rowstate.js`, three pads (from the
  seven spellings the call sites had between them) and three edges. Mail's
  threads, the notification feed, the version panel, the attachment gallery,
  the showcase's children, the tally menu, the compliance findings and the
  clause list are callers. `align` is the one prop that earns its place twice
  over: a notification's body is three lines and its face belongs beside the
  first of them.
  The hover fill is the part worth the most. There were **five** — `gray-1`,
  `gray-2`, `gray-3`, `white/15`, `white/10` — so a tile in the space
  switcher lit up harder than the row in the list beside it, and nobody had
  decided that. `HOVER` in `lib/rowstate.js` is now the only `hover:bg-`
  literal in either SPA and `test_one_hover_fill_and_it_is_here` is what
  keeps it that way; the space switcher's tile, the launcher's, the code
  file's title box and the "My workspaces" row all import it. `overlay` is
  the one honest exception and it is a *ground*, not a class at a call site:
  the record showcase sits on a photograph, where a grey fill is mud.
  `shared/components/Picker.vue` is the dialog that asks one question over a
  narrowable set: the search, the 250ms debounce, the skeleton, the empty
  line, the close — and the **arrow keys**, which is the half that existed
  nowhere. `source` is an array (narrowed here) or a function (asked, and its
  own in-flight state draws the skeleton), and how a candidate looks stays the
  caller's through `#option`. The language, the folder, the template and the
  bound record are callers; four files lost their own debounce. Its list is
  a `role="listbox"` of `role="option"` rows, which is the one thing the
  `Combobox` inside `RecordPicker` had been getting for free and the four
  hand-rolled scrollers had not.
  **The audit said twelve pickers and ~2,400 lines, and that was a grep
  talking.** Five of the twelve are not this interaction and are named in
  `NOT_A_DIALOG_PICKER` with what each one is instead: `LinkPicker` is a
  field (a modal in the middle of typing a record is not an improvement),
  `Icon`/`Marker`/`ColorPicker` are popovers over a grid — one question, and
  nothing to narrow, because a grid is scanned rather than read —
  `ColumnPicker` is multi-select *with an order*, and `FilePicker` is three
  tabs of which one is a picker, which §D3 owns. `PivotFieldPicker` is
  vendored. `RolePicker` turned out to be in no import in the whole SPA:
  `MemberRoles.vue` is the live one, and the dead file is deleted.
  Two guards came out of that. `test_the_exemptions_still_exist` refuses a
  name in the list whose file has gone, because a stale exemption is a hole
  nobody can see; and `test_nothing_sits_in_shared_with_one_caller` closes
  §A2's last finding, allowing the one honest case — a shared component whose
  single caller is itself shared, which is still not owned by a module.
  Two surfaces kept `rowState()` without becoming `<Row>` callers, and the
  reason is the same both times: they are a row *and* something else.
  Attention's rows are bordered panels, and Drive's `FileRow` draws a card in
  the grid view from the same component. Both compose the vocabulary; neither
  would gain anything from a layout that is not theirs.
  One generator bug fell out of it: `spec.py::rewrite` moved `@/` imports by
  the table's keys, which carry a file extension — so a moved *directory*
  rewrote and a moved *file* silently did not. Every generated import that
  had ever moved happened to be under a directory key, which is why nothing
  had caught it. It now tries the extension-stripped form too.
- **B2. One bar to narrow with, one box to search in, and the sort left where
  it is.** `shared/components/Narrow.vue` is the facet bar's *interaction*
  over the quick filters' *source*, which is the whole finding: neither was
  wrong and each had the half the other lacked. Every control is searchable
  (a `Combobox`, not a `Select` — forty options with no search is not a
  control), every set one clears on its own X, there is a Clear all, and a
  field this source has no column for is disabled with the reason said once
  at the end rather than in six identical tooltips. `FacetBar` is deleted and
  Network, Insights, Timetable and Outlook compose the shared one.
  The engine's `QuickFilters` is now an *adapter* rather than a bar: 226
  lines become 130, and what is left is the part that is actually about a
  doctype — which fields it offers (`in_standard_filter` plus the ID box),
  where each control's options come from, and how what somebody chose becomes
  Frappe's operator tuples. Two controls changed kind on the way: a **Select**
  was a `Select` and is a searchable list now, and a **Link** was a *text
  box* — which asked a customer to know a record's id — and is a list fed by
  `spaceview.link_options`, the same endpoint the Link field's own picker
  uses, so it is bounded by the screen and runs the reader's permissions.
  A filter cannot offer a record they could not have opened.
  **One search box.** `ListSearch` everywhere: Drive's had no icon, fired on
  every keystroke and did not clear on Escape; the file picker's had its own
  hand-rolled debounce; Mail's had the best idea of the four — `/` to focus —
  and was the only one with it. `/` is the box's own now, so every surface
  with a search box has it, and so is Escape-to-clear, which two of 215 files
  had. There is **no** `submit` prop and there was nearly one: Mail's body
  search looked like it needed Enter rather than a debounce, until the
  watcher under its script turned out to already debounce at exactly the same
  300ms. A prop with one caller that turns out not to need it is the shape
  §F1 warns about; three call sites and three debounces became one.
  **The sort is not in this stage, and that is deliberate.** The plan's
  answer — the order menu drawn from the source's declared sortable fields —
  needs the source to exist. Drive's `ORDERS` becomes `FileSource.sortable`
  in B1, and building a second hand-listed menu now to delete it in three
  weeks is the exact habit §F1 named. The same goes for the single filter
  *shape*: `Narrow` holds `{key: value}` and each caller converts, which is
  one shape in the browser and two on the wire; collapsing the wire is
  `facets.resolve` growing a translation layer, and that belongs beside B1's
  `ListSource` rather than ahead of it.
  Four guards: `test_one_search_box` refuses a `FormControl` whose
  placeholder says Search outside `ListSearch` (two exemptions, each
  narrowing a list already drawn); `test_the_search_box_carries_the_shortcut_
  and_the_escape` pins `/` and Escape and refuses Mail binding `/` a second
  time; `test_a_filter_control_is_never_a_bare_select` keeps the bar on
  `Combobox`; and `test_one_narrowing_bar` names the five callers and refuses
  `FacetBar` coming back.
- **B3. A row menu, and two destructive words.** `shared/components/RowMenu.vue`
  is the three dots, and what it owns is the affordance rather than the verbs:
  it appears on the row's hover off `group/row` from §B4 — so forty rows are
  not forty sets of dots — stays while its own menu is open, is simply there
  on a phone, which has no hover to reveal it with, and sorts the destructive
  entry last and in red rather than leaving that to be remembered at each
  call site.
  A record's row had **one** affordance before this and a file's had six: the
  parity table in the audit is the argument, and the worst line in it was
  delete, which lived only in the *bulk* bar — so removing one record meant
  opening it, closing it, ticking its box and using the multi-record path.
  The row now carries Open, Copy link, Duplicate and Delete for ever, and
  every one of them was already reachable somewhere that was not the row.
  Duplicate asks `duplicateRecord`, the same endpoint the open record's own
  Duplicate uses, so the two cannot drift; Delete selects the row and goes
  through the confirmation that already exists, because a second delete path
  is how two delete paths come to disagree.
  **Two destructive words, and they are now the only two.** There were six —
  `Move to the bin`, `Bin`, `Move to Trash`, `Delete`, `Delete for good`,
  `Delete it all` — for what a reader experiences as two ideas, and *Delete*
  in one bar meant what *Delete for good* meant on the row beside it. It is
  `Move to the bin` for the one that comes back and `Delete for ever` for the
  one that does not, each allowed to name its object in the middle
  (`Delete 3 records for ever?`) and neither allowed to be shortened —
  including on a phone, where Drive's bar goes icon-only instead of saying
  `Bin`. A record's delete is `for ever` because this product offers no way
  back from one, and saying `Delete` while a file says `Delete for ever` for
  the same finality is the drift being deleted.
  **And the bin got its undo**, which is D2's `notifyUndoable` finding its
  first caller and the reason that function exists: the bin is *the*
  reversible destructive verb, and the only way back was to change place,
  find the file among everything anybody had thrown away, and put it back.
  Two guards: `test_two_destructive_words_and_no_others` reads every
  `label`/`tooltip` in both bundles and refuses a third, with a witness test
  that checks the six it would have caught; the scan is deliberately narrow,
  because "Move to a folder" is a move and "Deleted after" is a date and a
  guard people add exceptions to is a guard nobody reads.
  **What is not here is the third place.** The plan's rule is that a verb
  acting on one object appears on the row, in the selection bar *and* on the
  open object, drawn from `ListSource.actions(rows)` — and the source arrives
  with B1. Until then the row's four are written where the screen knows them,
  in the shape a `Dropdown` already takes, so B1 replaces the list rather
  than adding to it.
  One typo fell out of the copy pass: `PrintingSettings` had been saying "A
  letter head is the band above and below a printed page.'s." since it was
  written.
  The catalogues are caught up with it. `i18n_pot.py` had not been run since
  §A3 rewrote 44 paragraphs, so the POT was a stage behind and ar/de with it;
  regenerating, syncing and translating the 57 that were owed brings both
  back to zero.
  **Two bugs the browser pass found, both of them B2's.** `QuickFilters`
  became a `Narrow` adapter with two `v-model`s and one watcher, and the
  watcher only watched `chosen` — so switching a box from *contains* to
  *equals* changed the operator and asked nothing, because the value had not
  moved. It watches both now. The second was worse and was hiding behind the
  first: the same watcher fired when the *screen* seeded the bar from what
  was saved, so saving a screen made it dirty again the moment it resolved
  and Save never turned into Undo. The seeding records the state it wrote and
  the watcher skips it — compared rather than flagged, because the write is
  synchronous and the watcher is not, so there is no window where a real
  change is swallowed.
  And one piece of litter: `record-extras` named the record it destroys
  `zzDelete me`, which the fixture's `ZZ %` sweep does not match, so two
  failed runs left two rows behind and the third counted them. The record is
  prefixed now and the sweep reaches `Compliance Document`.
- **D3. One upload, wherever it was started.** `<UploadTray />` was rendered in
  exactly one place — `Drive.vue:474` — so the queue that survives a
  navigation existed only if you happened to have started in the Drive.
  Attaching a 200 MB video to a record *worked*, which was the earlier arc's
  win, and you watched it inside a dialog you could not close with nothing to
  come back to. The tray is in the shell root now, beside `SettingsShell` and
  for the same reason: outside `AppShell` because that file is generated into
  both SPAs and the control plane has no files, and outside the layout so an
  upload outlives the layout swapping under it. `FilePicker` stops awaiting
  `putFile` and pushes onto the same queue, which is where `attachTo` and a
  per-item `then` come from — the dialog shuts, the tray counts, and the field
  fills when the bytes land.
  **`v-drop-files` is the one drop target.** Each of the surfaces that took a
  file from the desktop had written its own `dragenter`/`dragover`/
  `dragleave`, its own counter for the fact that both fire for every child the
  pointer crosses, its own hover treatment — so a drop target in the Drive and
  one in the picker did not look alike — and its own answer to a folder, which
  arrives as a zero-byte `File` with no type and uploads as an empty file
  named after the folder. The directive carries §B4's `DROP`, ignores a drag
  that is not carrying files (a row dragged over a folder is not an upload,
  and a target that lights for it is a target that lies) and refuses what is
  over the ceiling before a byte is sent. The four reorder drags keep their
  own and are named, with what each one moves.
  **The ceiling is stated before it is hit.** There was no size messaging
  anywhere near an upload control; the only sentence in the SPA about a size
  was `FileSurface`'s "too big to show here", which is about reading. It is
  not one number, which is why `onestorage/limits.py` answers rather than a
  constant: below `direct.THRESHOLD` a file is POSTed to Frappe and
  `max_file_size` bounds it, and above it the bytes go straight to R2 in parts
  and nothing between here and Cloudflare reads the body — so on a site with a
  bucket there is no per-file ceiling worth printing and the control says
  nothing, because the thing that refuses a large file there is the quota,
  which has its own words and its own number. It rides the boot payload
  because the sentence belongs *under* the control. `dav.py` now quotes the
  same function rather than its own copy of Frappe's expression.
  **And one byte formatter, not six.** The guard found four more after the two
  the audit knew about, and they disagreed about zero, about whether TB
  exists, and about whose decimal separator to use — so a quota bar reading
  `1.2 GB` sat above a file list reading `1,2 GB`. `lib/files/size.js` is
  generated into both bundles; `blank` is the one real difference between the
  callers, because a file list wants an empty cell and a quota bar wants
  `0 B`.
  Five guards: the tray is drawn exactly once and in `App.vue`; a `<input
  type="file">` outside the five that own one fails; an `@drop` handler that
  is not `v-drop-files` and not named in `NOT_AN_UPLOAD` fails; nothing spells
  out its own byte units; and the picker states and checks the ceiling. Plus
  the browser spec the plan asked for: start an upload on a record, leave the
  record, find the tray still counting.
- **C1. One crumb root, and the subject out of the trail.** There were nine
  `crumbs` computeds and they disagreed about the first thing on the page.
  The engine's root was the *space*; every other surface's root was itself —
  Files, Mail, Calendar, Account, Spaces, Add a space, the assistant's own
  name. So there was no shared first crumb, no way from Mail back to the
  workspace in one click, and no answer to "where am I" that held across two
  screens. OneDoc's was the cleverest and the least consistent: its root was
  wherever you came from, remembered in a query parameter, so the same
  document had a different trail depending on how you reached it.
  `shared/composables/useCrumbs.js` now prepends the workspace to everything
  and takes a *place* and a *trail*; `shared/components/Trail.vue` is the nav,
  the house and the subject slot. The engine's space becomes the second crumb,
  the Drive's phone case that dropped its own "Files" crumb to save width is
  gone — frappe-ui collapses a trail to its last two with an ellipsis menu,
  which is a better answer than a surface deciding which of its crumbs is
  expendable — and OneDoc's `back` becomes a crumb *after* Files rather than
  instead of it.
  **The subject is not a crumb.** The engine already knew this and nothing
  else did: a record was drawn as its own element after the trail, with its
  face, its id and two badges, while OneDoc put its title *in* the trail as
  the last crumb and Mail put its subject nowhere. It is one slot on `Trail`
  now, and `useCrumbs` lost the half of it that was about records —
  `useSubject.js` is that half, because the thing that builds crumbs should
  not also know what a docstatus badge is.
  **One correction to the audit.** It asked for four surfaces to gain a trail
  on the reading that a person deep in a workbook had "no route home but the
  browser's back button". That is not true of the code: both full-bleed
  editors put the way out on their own brand mark — at rest it says what this
  is, under the pointer it becomes an arrow — which is §C2's full-bleed
  pattern and *is* a route home. A fifth row of chrome above four would have
  bought a second exit and a layout risk, so they keep the mark and
  `NO_TRAIL` says so, beside the two that are genuinely not places: a link a
  stranger holds has no workspace to be the root of, and the settings dialog
  is a dialog.
  Four guards: nothing but `Trail.vue` draws a `Breadcrumbs`; a `Trail` whose
  items are not from `useCrumbs` fails; the root is prepended in one place and
  nothing else builds a home crumb; and the surfaces without one are named
  with reasons and checked to still exist and still lack one. Plus the browser
  spec the plan asked for — walk the workspace-level places and find the same
  house at the front of each, going to the same address.
- **E8. The assistant is a character, and one colour.** The audit's own
  finding was that the good parts were not visible often enough to register,
  and the sharpest example was the face: `assistant.avatar` was settable, in
  the boot payload, in the reactive — and rendered by exactly one component,
  the settings form that sets it. A workspace uploaded a picture for their
  assistant and never saw it again. `shared/components/AiFace.vue` is that
  face, and it appears where the assistant *speaks*: the panel header, every
  turn it takes, the empty state, and the moment an answer is on its way. The
  `oneai` mark when nothing is set, rather than `Avatar`'s letter — a letter
  is what a person falls back to, and this is not one.
  **One palette.** There were three for one idea and the amber one was also
  what four `Alert`s use for a warning, so "a model wrote this" and
  "something is wrong here" were the same colour. `--oneapp-ai-ink` is the
  glow's own indigo at full strength, and `AiMark` takes it. The `oneai`
  brand mark keeps its rose because a brand mark is allowed its own colours
  (§C3); the interface language is one.
  **The name, not the category.** Seven visible strings said *AI* or *the
  assistant* where they meant the thing this workspace named — `Ask AI`,
  `Write with AI` twice, `Written by AI` twice, `Close the assistant`, `The
  assistant is not switched on here`. They take `assistantName` now. What
  still says AI is the *feature*: the settings tab, the switch, the credits.
  A workspace buys AI and names its assistant, and the two nouns are
  different.
  **And the wait is the moment.** The component built to make generation feel
  like something rendered on four surfaces and the assistant's own was not
  one of them: a spinner beside the word "Looking", which says the
  application is busy — the one fact nobody needed. It is the face that is
  about to speak, breathing in the glow's two hues, beside a skeleton at the
  width of the paragraph that is coming, with the sheen travelling across it.
  That is the three seconds the user's "boring as it could be" was about, and
  it is now the reference the rest copy.
  Four guards: a visible string may say AI only where AI is the feature;
  everything that renders the assistant speaking renders its face; the three
  components that *are* the AI language may not use the warning colour; and
  the assistant's wait is the glow, with no spinner beside it.

## Stage 3

- **F1. The capability contract, named once.** Three findings were one
  finding: B1's `ListSource.capabilities`, B2's "this facet is unavailable and
  here is why", and E1's scoped share. `shared/lib/capability.js` is the name
  they share — a vocabulary of fourteen things a list surface can offer, and
  three states rather than two.
  `true` means draw the control; a *string* means draw it, disabled, and say
  that sentence; absent means draw nothing. The middle state is the whole
  point: "Drive has no sorting" was an omission, and "this host answers in its
  own order" is a decision with its reason attached, which a person reads once
  and stops looking for the control.
  **It ships with a caller, on purpose.** §F1's own root cause is the
  abstraction built at the second caller and abandoned at the third, so a
  contract with no caller would be this document making its own mistake. The
  Drive's remote mounts are the live case: four scattered `inRemote` checks,
  each an omission with its reason in a code comment rather than on screen.
  They are one declaration now, the sort control is drawn and disabled with
  the reason on it, and where the select-all used to simply vanish the row
  says why instead.
  `offers()` throws on a capability nobody declared — §F1's *second* pattern
  is a rule that is right and a scan with a hole in it, and `sorting` where
  the vocabulary says `sort` would otherwise be a control that is silently
  never offered. Four unit tests and two guards, one of which refuses a
  surface that declares a refusal and never renders its reason.
- **B1, part one. `ListSource`, `StaticSource` and `<DataList>`.** The engine
  is not an engine — it is one screen, decomposed, and every list composable
  has exactly one consumer because every signature takes `spec`. So
  seventeen other surfaces built their own frame, and the audit's table of
  fourteen capabilities against those seventeen is almost entirely blank:
  nothing had a way to *ask* for a skeleton, an empty state or a count.
  `lib/list/source.js` is the seam. A source answers four questions —
  `load`, `identify`, `empty` — and declares `can`, which is §F1's contract.
  `components/DataList.vue` renders exactly that much: the row is a slot,
  and everything around it is the frame. A control the source cannot honour
  is not drawn; one it *refuses* says the reason where the control would
  have been.
  `StaticSource` is the first of four and the cheapest proof, because seven
  of the seventeen already hold their rows in memory. Two of them migrate
  here as the evidence the shape is right: **Attention**, which is the
  console's reference implementation and the plan's nominated proof, and the
  **notification feed**. Both lose a skeleton, an empty state and a `v-for`,
  and keep the only part that was theirs — the row. Both declare *nothing*,
  which is the point: a feed is read from the top and closed, and a list of
  thirteen checks is already worst-first, so a sort control over either
  would be a control that makes the screen worse. Declaring nothing is a
  decision; the blank column in the audit's table was an omission.
  `FileSource`, `ThreadSource` and `DoctypeSource` follow, and `DoctypeSource`
  is last on purpose: it is the one that must not regress, and the browser
  suite is its check.
  Three guards: a source answers all four questions and the frame asks all
  four; a `<DataList>` with no `:source` fails; and a caller that keeps its
  own `EmptyState` beside the frame fails, because handing the frame over and
  then redrawing half of it is how the second caller becomes the third.
- **C4. The URL vocabulary, one typed `at`, and panels with addresses.**
  Three pieces, and the first two are rails rather than features.
  `lib/url/params.js` declares every query parameter this product puts in a
  URL, grouped by the question it answers, and a guard refuses one that is not
  in it — a URL is the only part of this interface a person can send to a
  colleague and it was the part nobody owned. `lib/url/remember.js` is the one
  door to `localStorage`, with every key declared beside the answer to the
  question that decides whether something belongs there at all: *would I want
  to send this to a colleague?* Seven call sites were each re-deciding what to
  do when storage is off, full or blocked; the answer is to forget, and it is
  in one place now.
  Then `at`. Five parameters answered "which one of these am I looking at" in
  five shapes, and `?at=record:TASK-0001` is the one. The part worth recording
  is that a browser spec found the flaw before it shipped: `link-open.spec.js`
  asserts that a link from an invoice opens the client in a drawer *over* the
  invoice, and with `at` as a single slot the drawer erased the record
  underneath — the one thing a drawer exists not to do. So `at` is a stack,
  outermost first — `?at=record:INV-0007|peek:clients/CL-0003` — which is what
  "peek becomes a modifier" means once it meets the thing it describes.
  Opening a record sets the stack, a peek pushes, closing pops, and the
  browser's own back button therefore does the same thing.
  Settings, the assistant and the filter panel have addresses now, through one
  composable rather than three pairs of watchers: the loop between "the URL
  says something" and "the panel changed" is the part that is easy to get
  wrong, and three handwritten copies would be three chances to get it wrong
  differently. They stay dialogs and panels — C2 is right that a thing you
  toggle is not a route — and `replace` rather than `push`, because a history
  full of panel toggles is a back button that does nothing visible four times.
  What changes is that "open settings, then find Backups" becomes a link.
  A browser spec opens each from a *cold* URL, which is what a link somebody
  sends actually does; opening one by clicking and reading the URL back would
  prove only half of it.
- **B5. One resolver, and the third rendering.** Stage 0 closed the *bug* —
  `read_only_depends_on` was advisory in one place and absent in three, and
  the server did not enforce it either. This closes what caused it, which is
  that four surfaces asked "may I edit this?" and there was no one place to
  ask. `shared/lib/fields/state.js` folds all seven clauses — the doctype's
  three dynamic rules, the server's static `editable`, `set_only_once`, the
  docstatus, and the screen's own permission — into one verdict, and the form,
  the child table and the inline cell all call it. The create dialog composes
  the form, so it inherited the whole rule already; that was the pattern the
  other two should have followed.
  The verdict is a *state* and not a boolean, which is the other half.
  `disabled` was doing the work of two ideas and painting both the same grey:
  a control that is momentarily unavailable, and a value you may not write.
  The second is not a control at all, and `ReadValue` draws it as the value in
  the field's own place — no box, no grey, no placeholder — using `FieldCell`,
  because "how does a Currency read" is one question and the list answered it
  for every fieldtype years ago. Four fieldtypes keep their own read-only
  form, and the reason is that they are still things you *look at*: a
  document, a code file, a gallery, an upload. `CodePreview` rather than a
  greyed editor was the oldest of these decisions and it is the one the rest
  now follow.
  Two browser specs failed, and both were the old model written down: one
  asserted `toBeDisabled()` on a field the doctype locks, the other read a
  fetched value out of an input. Both now assert the new behaviour, which
  makes them the cheapest place the third rendering is proved.
  Four guards: every field surface calls the resolver; no surface spells out
  a clause the resolver owns (keyed on the source with its comments stripped,
  because saying *why* a clause moved is not keeping it); `FieldControl` takes
  `state` and has a read-only rendering; and the states are three.
- **B1, the rest. The other three sources, and what they taught the
  contract.** The order mattered more than the count: each implementation had
  to make the contract earn a shape rather than the contract predicting one.
  `StaticSource` finished at seven surfaces and produced `busy()` — a source
  built out of an array literal has its rows, and one built out of a fetch has
  an *empty* array for as long as the read takes, which the frame was reading
  as "there is nothing here" and saying so where the skeleton belonged.
  **`FileSource`** is the one file query — `onestorage.listing` — that the
  Drive, a record's Files tab and the attach picker were already three
  readings of on the server and three frames of in the browser. It has a
  second door rather than one, and the door is the interesting part: a
  record's tab goes through `spaceview.attachments`, because which doctype a
  screen is and which files belong to *this* Attachment Gallery are both
  decided on the server and neither is a thing the browser may be trusted to
  send. It also produced `keep`, the post-filter the picker's "no folders, and
  only these extensions" really is.
  **`ThreadSource`** is a mailbox, and it produced the two shapes nothing else
  needed: `append`, because a mailbox pages by a cursor and `start` means
  nothing to it, and `fold`, because a conversation can straddle a page with
  half its messages in each and the counts have to be *added* rather than one
  copy dropped. Every other source keeps the frame's default, which is to drop
  the repeat.
  **`DoctypeSource`** was last because it is the one that must not regress,
  and it is the one that is not filling a gap: the engine already offers all
  fourteen capabilities — it is the surface the audit's table was measured
  *against*. What it closes is the vocabulary. The engine's fetch now answers
  the same questions as a file list and a mailbox and declares what it can do
  in the same words, and a surface that wants records *without* the view
  switcher, the filter panel, saved views and grouping can have the frame
  without taking the engine with it. What deliberately did not happen is the
  engine moving into `DataList`: the board, the cards, the calendar and the
  columns a page was actually fetched with reach the caller through
  `onAnswer`, because a frame that knew about any of them would be the engine
  again.
  The frame learned two things from having real callers. `v-model:searched`
  lets a caller own the search box — the Drive's belongs beside Upload and
  New, Mail's beside Write, and that is a layout decision the frame has no
  business overruling — while a source that cannot be searched still gets no
  box. And a read that fails is the frame's state rather than an unhandled
  rejection: caught, kept, and said where the rows would have been, with a
  `#failed` slot for a caller that wants to say it differently. Half the
  surfaces that had one said it in a toast that is gone by the time anybody
  looks — §D2.
  **What a browser found that 4,226 guards and a clean build did not.** One
  run of `drive.spec.js` failed six ways, and the cause was one line: 
  `ListSearch` emits `update:modelValue` and `changed` back to back in the
  same handler, so a caller that owns the box had a current ref and a prop one
  render behind. The first keystroke searched for the previous value, which is
  no search at all. `read` waits a tick, which is the only place that
  knowledge belongs. The same run found the Drive asking for its first page
  twice on mount and twice on every walk into a folder, because the frame
  reads when it gets a source and the page was still asking beside it. This is
  what "the browser suite is its check" was for, and it is worth saying that
  the unit suite and the build were both green throughout.
