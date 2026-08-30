# Overnight plan 01 — field properties, and the types we never mapped

A plan, not a change. Nothing here is built yet.

Two gaps came out of the last review, and they are the same gap seen from two
sides. A doctype describes its fields in sixty-six properties and thirty-seven
types; a screen currently reads twenty-four of the properties and renders
twenty-eight of the types honestly. Everything in between either silently does
nothing (`precision` travels to the browser and is never used) or silently does
the wrong thing (a Text Editor field is a plain textarea, so somebody types a
paragraph and it saves as text into a column the rest of Frappe renders as
HTML).

The aim is that a screen over any doctype looks like the doctype meant it,
without a manifest repeating anything the doctype already said.

---

## Where the truth lives

Five files decide all of this, and four of them are generated. Editing a
generated file is how the browser and the server come to disagree about whether
a field is editable, which is the one disagreement that produces a control the
server then refuses.

| File | What it is |
| --- | --- |
| `scripts/field_types.py` | **Canonical.** fieldtype → (control, cell, icon, editable), the operator tables, the layout list. |
| `apps/oneapp/oneapp/oneapp_core/fieldtypes.py` | Generated from it. What the server believes. |
| `apps/{oneapp,oneapp_control}/frontend/src/lib/fields.js` | Generated from it. What the browser believes. |
| `apps/oneapp/oneapp/oneapp_core/spaceview.py` | The resolver: `_columns` decides which properties travel, `_offerable` decides which fields a person may ever see, `_form` lays them out. |
| `apps/oneapp/frontend/src/components/screen/FieldControl.vue` / `FieldCell.vue` | The two renderers — a field being written, and a field being read. |

`scripts/gen_frontend.py` owns `src/ui.js` (the sanctioned frappe-ui surface)
and the ESLint import rules. Any new frappe-ui entry point has to be added
there, in both apps, or it cannot be imported at all.

---

## Part 1 — Field properties

### 1.1 `hidden` is a bug, not a gap

`_offerable` (`spaceview.py:176`) filters Frappe's bookkeeping, layout fields,
child tables and anything above this user's permlevel. It does not filter
`df.hidden`. `_quick_entry` does — so a field the doctype hides is correctly
absent from the quick-create form, and then present in the column picker, in
the list, and on the record form.

That is not a permission hole: `hidden` is presentation, and Frappe hides these
because they hold plumbing nobody should be asked about, not because they hold
secrets. It is still wrong, and it is wrong in the direction that makes every
screen over a busy ERPNext doctype look like a database dump.

**Plan.** Add `and not getattr(df, "hidden", 0)` to `_offerable`. Two knock-on
effects, both already handled by existing code and worth asserting in tests
rather than assuming:

* A saved layout that already picked a now-hidden column keeps the column in
  its stored list, and `_placed` intersects that list with what is offered — so
  it stops rendering rather than erroring. That is the right behaviour; the test
  should say so.
* A field hidden by a Property Setter rather than by the doctype behaves the
  same way, because `frappe.get_meta` has already applied it.

One deliberate exception: a field the *manifest* names explicitly. A space that
declares `hidden_but_we_want_it` in its columns is making a considered choice
about its own doctype, and the manifest is code we wrote. Honour it, and only
it — `_offerable` widens the picker, the manifest states an intent.

### 1.2 The two properties we already send and never use

`precision` and `non_negative` travel from `_columns` to the browser and no
component reads them.

*(Corrected while building: `columns` **is** read — by `_default_width` on the
server, which the browser never sees. The original audit grepped the frontend
only.)*

* **`precision`** — Frappe's per-field override of the site's float precision.
  A Float with `precision: 4` currently renders with whatever `toLocaleString`
  defaults to, so `0.0625` becomes `0.063` in the list and full in the record.
  Plan: `FieldCell` formats numeric cells to `precision` where the field sets
  one, falling back to the site's default (Currency has its own answer, from
  the currency, which is a separate question — see 1.6).
* **`non_negative`** — Frappe's own "this cannot go below zero". Plan: pass
  `min="0"` to the numeric `FormControl`. Client-side hinting only; the server
  enforces it on save regardless, which is the correct division.

### 1.3 Properties worth adding

| Property | What it means | Plan |
| --- | --- | --- |
| `length` | Max characters on a Data field. | Carry it; `maxlength` on the control. Frappe truncates on save, so without it a person types past the limit and watches the end vanish. |
| `min_value` / `max_value` | Numeric bounds. | Carry them; `min`/`max` on the numeric control. Same division as `non_negative`: a hint here, enforcement on the server. |
| `unique` | This value may not repeat. | Carry it. Shown as the field's note ("Must be unique"), and used to turn the server's `DuplicateEntryError` into a message on *that field* rather than a red toast about a database constraint. |
| `not_nullable` | Empty is not allowed, distinct from `reqd`. | Carry it; treat as required for the purpose of blocking a save, with its own message. A `reqd` field asks; a `not_nullable` field refuses. |
| `collapsible` / `collapsible_depends_on` | A section starts folded. | Carry through `_form` onto the section, not the field. `FormSections` grows a disclosure. `collapsible_depends_on` is an expression — `lib/rules.js` already parses this dialect, so it is the same call as `depends_on`. |
| `allow_on_submit` | Editable after submit. | Carry it. Only matters once we render a submittable doctype, but the rule is cheap: when `docstatus == 1`, a field is editable only if `allow_on_submit`. Without it a submitted record looks fully editable and every save is refused. |
| `fetch_if_empty` | `fetch_from` fills in only a blank. | Carry it, and say so in the note. Today every `fetch_from` field reads as "From Customer" whether or not it will overwrite what you typed. |
| `sort_options` | Sort a Select's options alphabetically. | Carry it; sort in `FieldControl`. One line, and the desk does it. |
| `remember_last_selected_value` | A Link that reopens on your last choice. | Carry it; the picker seeds from `localStorage`, keyed by doctype and fieldname. |
| `documentation_url` | A link to the docs for this field. | Carry it; an info icon beside the label. |
| `show_description_on_click` | The description is behind an icon, not inline. | Carry it; changes where the note renders, nothing else. |
| `mask` | An input mask (`ignore_xss_filter`'s neighbour on Data). | Carry it. Applied as a display format, not as a validator — a mask that fights the typist is worse than none. |
| `max_height` | A ceiling on a text control's height. | Carry it onto the textarea and the editors. |
| `hide_border` | A section draws no rule above it. | Carry through `_form` onto the section. |
| `translatable` | The value is user text to be translated. | Carry it; no UI, but it belongs in the payload before something needs it and we have to re-run this audit. |

### 1.4 `ignore_user_permissions` — read it, and refuse to honour it

Frappe lets a docfield say "User Permissions do not apply to this Link". That
is a legitimate escape hatch inside the desk, where the person configuring it
is an administrator reasoning about their own site.

Here it is a way for a doctype we did not write to widen what a customer's
screen can reach, and `tests/test_permission_paths.py` exists precisely to stop
that class of thing. **Plan: carry the flag so the payload is honest, and do not
act on it.** Our link picker keeps asking Frappe with permissions on. Write the
reasoning into the code, because the next person to read the property will
assume it was missed.

### 1.5 Properties that stay unread, deliberately

`print_hide`, `print_hide_if_no_value`, `print_width`, `report_hide`,
`in_import_template`, `in_global_search`, `show_dashboard`, `show_on_timeline`,
`oldfieldname`, `oldfieldtype`, `search_index`, `ignore_xss_filter`,
`make_attachment_public`, `allow_bulk_edit`, `in_filter`, `is_virtual`,
`no_copy`, `alignment`, `button_color`, `sticky`, `width`.

Each is either about a surface we do not have (print formats, the report
builder, global search, the form dashboard), a database concern
(`search_index`), or a desk-only affordance. Two are worth a note rather than
silence:

* **`no_copy`** matters the moment we add "duplicate this record". Nothing to
  do now; the task should say so when it is written.
* **`is_virtual`** is a doctype-level concern more than a field one, and it
  changes how a value is fetched. Out of scope, but it is the one item on this
  list that would need real work rather than a line.

### 1.6 Currency, which is none of the above

A Currency field's precision does not come from `precision` — it comes from the
currency, which comes from another field on the record (`options` naming a Link
to Currency, or a literal code), falling back to the site's default currency and
its `Currency Format`. We render the number and no symbol.

Not part of this plan, but it is the thing somebody will report as "precision is
still wrong" the day after 1.2 ships, so it should be its own task.

---

## Part 2 — The types

Thirty-seven fieldtypes. Five of them are a textarea pretending to be something
else, one is a picker with nothing to pick, two are unreachable, and six have no
control at all.

### 2.1 Text Editor and HTML Editor → `frappe-ui/editor`

frappe-ui ships a TipTap editor on its own entry point, `frappe-ui/editor`,
exporting `Editor` with `format: 'html' | 'json' | 'markdown'`, an
`uploadFunction`, and the kits (`RichTextKit`, `CommentKit`, `InlineKit`) that
decide which extensions load. The comment in `scripts/field_types.py` that says
we chose a textarea because the editor "is heavy and not SSR-safe" is now the
wrong trade: there is no SSR here, and the weight is one async chunk on a route
that has a rich-text field.

**Plan.** `Text Editor` → `Editor` with `format="html"` and `RichTextKit`.
`HTML Editor` is Frappe's *source* editor — it is markup a person edits as
markup — so it goes to the code editor in 2.3 with `language="html"`, not to
the rich one. Getting these two the same way round is the whole point of
separating them.

The upload function wires to the same File endpoints the record already uses
(`attachments` / `remove_attachment` in `spaceview.py`), so an image pasted into
a description is an attachment on the record like any other.

### 2.2 Markdown Editor → the same component, `format="markdown"`

`Editor` takes `format="markdown"` and round-trips through the same document
model. Frappe stores markdown text; the editor reads and writes it.

One decision to make when this is built, not now: whether the markdown field
edits *as* rich text (WYSIWYG, stored as markdown) or as markdown source with a
preview. Frappe's desk does the second. The first is nicer and is what
`format="markdown"` gives for free. Recommendation: start with the frappe-ui
default, because a person editing a Markdown Editor field in our SPA is a
customer, not a developer — and revisit if someone complains that their
front-matter got eaten.

### 2.3 Code and JSON → `CodeEditor`

frappe-ui has a CodeMirror-backed `CodeEditor` with lazy per-language chunks
(`loadLanguage`), `variant`, `size`, and a `CodePreview` for read-only. It
lives on `frappe-ui/experimental`, which is an unstable entry point with no
backward-compatibility promise.

**Plan.** Use it, and be explicit about the bet:

* `Code` → `CodeEditor`, language from `df.options` (Frappe puts the language
  there) mapped onto frappe-ui's `CodeLanguage` keys, defaulting to plain.
* `JSON` → `CodeEditor` with `language="json"`.
* `HTML Editor` → `CodeEditor` with `language="html"` (from 2.1).
* Read-only or above-permlevel → `CodePreview`.

The experimental risk is real and bounded: it is one import path and one
component, wrapped by `FieldControl`, so a breaking change touches one file. The
alternative — a textarea over a JSON column — is a customer editing braces in a
box with no bracket matching, which is not a smaller risk.

**The guard does not cover it.** `tests/frappe_ui_api.py` reads props and slots
out of `node_modules/frappe-ui/src`, and `experimental/` is a sibling of `src`.
Anything imported from there is unchecked, which is exactly the surface where an
unchecked prop is most likely. Part of this task is extending `UI_SRC` to a list
of roots that includes `experimental/`, so the experimental components are held
to the same standard as the stable ones.

### 2.4 Attachment Gallery — Frappe's own model, not a new one

Currently in `LAYOUT_TYPES`, so it is skipped entirely.

It is worth reading what Frappe actually does before designing this, because it
is not what the name suggests. `Attachment Gallery` is in `no_value_fields` and
in `display_fieldtypes`: **the field holds nothing.** The desk control
(`frappe/public/js/frappe/form/controls/attachment_gallery.js`) renders the
*record's own File rows*, optionally narrowed by `link_filters` on the docfield
— a filter over `File`, resolved server-side by
`frappe.desk.form.load.get_filtered_attachments`, which refuses any filter row
not targeting `File`. Upload attaches to the record. Delete removes the File.

So "multiple attachments under one field" is already how Frappe models it, and
we already have the two halves: `attachments()` and `remove_attachment()` in
`spaceview.py`, and `RecordFiles.vue` listing them.

**Plan.**

* Move `Attachment Gallery` out of `LAYOUT_TYPES` into `FIELD_TYPES` as
  `("AttachmentGallery", "hidden", "lucide-images", False)` — not editable in
  the sense of holding a value, because it holds none, and the control writes
  through the File endpoints rather than through the record's payload.
* Extend `attachments()` to take an optional `fieldname`, apply that docfield's
  `link_filters` server-side with the same "must target File" refusal Frappe
  makes, and return the same shape. Not the desk endpoint: ours is bounded by
  the screen, and reusing theirs would step around that.
* New `AttachmentGallery.vue` beside `RecordFiles.vue`. Images as a carousel —
  frappe-ui has no carousel, so it is a horizontal scroller with snap points and
  two chevron buttons, which is what a carousel is when you do not need
  autoplay. Non-images fall back to the file rows `RecordFiles` already draws.
  Upload via `FileUploader` with `doctype`/`docname`/`fieldname`, which attaches
  in the same request.
* On an unsaved record, the desk says "Save the document to attach files." Do
  the same: there is nothing to attach to, and inventing a staging area for it
  is a lot of machinery for the create dialog.

### 2.5 Table (child table) — the list component, cut down

A child table is a list inside a record: rows of one doctype, ordered by `idx`,
belonging to a parent. `ListBody.vue` already takes `spec`, `rows` and
`columns` as props and does not fetch anything itself — the shell fetches — so
it is closer to reusable than it looks.

What it also has, and a child grid must not: virtualization, grouping, saved
views, favourites, selection-driven bulk actions, and a row click that
navigates to a record route.

**Plan.** Not "reuse `ListBody`", and not a second table either. Extract the
part that is genuinely shared — the grid tracks, the sticky header, the cell
dispatch through `FieldCell`, the width and pin model — into something both
call, and let `ChildTable.vue` be the small one:

* Rows come from the parent's payload, not from a fetch. `_form` gains the
  child table as a placed field, and `record()` returns its rows.
* Columns are the child doctype's `in_list_view` fields, resolved through
  `_columns` so every property in Part 1 applies inside the grid too. This is
  where the work actually is, and it is why this item is bigger than it reads:
  a cell in a child table is a `FieldControl`, not a `FieldCell`, because the
  grid is editable in place.
* Add, remove, reorder. Frappe's grid does all three; `idx` is the order.
* **Row expansion, in the first pass.** A row opens into the child doctype's
  own form, and that form is `RecordForm` / `FormSections` — the same renderer
  the record pane and the create dialog use, so a child row gets tabs, section
  and column breaks, `depends_on` and every property in Part 1 for free, and
  there is one layout engine rather than two.

  Three things it does not inherit, and each is a prop rather than a fork:
  `RecordForm` takes `spec` (for `form` and `all_columns`) plus `spaceCode` and
  `screen`, and a child doctype has no screen of its own. So `_form` runs
  against the child's meta and the result travels *inside* the parent's column
  payload as the child field's own `form` — one resolve, on the server, where
  the permlevel filter already lives. `spaceCode`/`screen` stay the parent's,
  because that is what bounds the Link pickers inside the row, and a child row's
  links must be bounded by the same screen as everything else.

  Where it opens is a layout question with an obvious answer on each size: a
  drawer over the pane on desktop, a full page on a phone — the split
  `RecordPane` already makes.
* `Table MultiSelect` becomes reachable at the same time. It is mapped to
  `MultiSelect` today and unreachable: `_offerable` excludes it outright and
  `_placed` intersects the manifest with what is offered, so a manifest naming
  one gets nothing. It is a child table whose rows are one Link each — cheaper
  than the general case, and it should ship with this, not after it.

The permission question is the same one as everywhere else and has the same
answer: a child doctype's rows are readable exactly when the parent is, and
`_offerable`'s permlevel filter applies to the child's meta.

### 2.6 Dynamic Link

`_link_target` (`spaceview.py:1223`) returns `None` for anything that is not a
plain `Link`, so `link_options` returns `[]` — a picker with nothing in it —
and `_with_links` only resolves `fieldtype == "Link"`, so the cell shows the raw
id. The comment says it is "refused rather than guessed at" because the picker
has no record. That is true of the *screen*; it is not true of the *form*, which
is holding the record being edited and therefore knows what the other field
says.

**Plan.**

* `link_options` gains an optional `target` argument. The browser sends the
  current value of `depends_on_field` — which `_columns` already carries — and
  the server validates it: it must be a real doctype, it must be one this space
  granted, and this user must be able to read it. A Dynamic Link is a pointer to
  an arbitrary doctype, so a client naming its own target is exactly the kind of
  widening the screen allowlist exists to stop. The check is the whole feature.
* `_with_links` resolves Dynamic Link columns by grouping rows by their target
  doctype — one query per distinct target per page, which for a real list is one
  or two.
* `FieldControl` passes the target through to `LinkPicker`, and clears the value
  when the target field changes. Frappe does the same, and a link left pointing
  at a record in the doctype you just stopped pointing at is a silent data bug.

### 2.7 Icon → the picker we already built

`IconPicker.vue` exists (built for a view's own icon: lucide names from
`lib/icons.js`, plus emoji, validated server-side by `_view_icon` against
frappe-ui's own emoji rule). A doctype's `Icon` field wants the same picker
without the emoji half — Frappe stores a lucide/Frappe icon name there and other
code renders it as one.

**Plan.** Split `IconPicker` into the picker and its two modes, `Icon` →
`IconPicker` with emoji off, editable `True`. The cell already renders `icon`.

### 2.8 Postponed: Color, Signature, Barcode, Geolocation

Editing stays out. All four need a real component — a colour picker, a
signature pad, a barcode renderer, a map — and frappe-ui has none of them. The
current fallback shows the value as text with a note saying it is edited
elsewhere, which is honest but reads as a dead end.

**Plan: render the value properly, keep the control out.**

* **Color** — the cell already draws a swatch (`FieldCell.vue:32`). The
  *control* draws a text row with a dot. Make them the same swatch, and drop the
  "edited elsewhere" note in favour of nothing: a read-only value does not need
  an apology.
* **Signature** — Frappe stores a data-URI PNG. Render it as an image, at a
  sensible height, on a plain background. One line, and it turns a wall of
  base64 into a signature.
* **Barcode** — Frappe stores the *value*, and the desk renders the barcode from
  it. Render the value as text now; a barcode is a small SVG generator and can
  wait for a customer who needs to scan one off a screen.
* **Geolocation** — a GeoJSON blob. No honest small rendering. Leave it as the
  fallback, and say "Map" rather than showing the JSON.

None of these get `editable: True`, so the server keeps refusing to write them
and the two tables stay in agreement.

---

## Part 3 — What this costs in guards and tests

Every item above trips at least one existing guard. That is the guards working;
it is also most of the work, so it should be planned rather than discovered.

* **`tests/test_field_types.py`** reads Frappe's own fieldtype list and our
  table back. Moving `Attachment Gallery` out of `LAYOUT_TYPES` and adding
  controls changes both sides; the test has to keep failing for the right
  reason.
* **`tests/test_frontend_guards.py`** asserts every non-deprecated frappe-ui
  component is in the barrel, and that no local `.vue` shadows a barrel name.
  `AttachmentGallery.vue` and `ChildTable.vue` are safe; `Editor.vue` would not
  be, so ours must not be called that.
* **`tests/frappe_ui_api.py`** reads props out of `frappe-ui/src` only.
  Extending it to `experimental/` is a prerequisite for 2.3, not a follow-up.
* **`tests/test_frappe_ui_usage.py`** checks props, slots, required props and
  literal-union values against those declarations. `Editor`, `CodeEditor` and
  `CodePreview` all have closed unions (`format`, `variant`, `size`,
  `language`), so this will catch a typo — once the reader can see them.
* **`tests/test_screens.py`** stubs `_layouts` and `_columns`; new keys in the
  column payload mean new keys in the fixtures.
* **`tests/test_field_rules.py`** drives `lib/rules.js` through node.
  `collapsible_depends_on` is the same dialect, so it is a case, not a change.
* **`tests/test_permission_paths.py`** is the one to watch on 2.6. A new
  `target` argument that reaches `frappe.get_list` is exactly the shape it
  audits, and it should fail until the validation is there.
* **ESLint** (`gen_frontend.py`) restricts imports to `@/ui`. `frappe-ui/editor`
  and `frappe-ui/experimental` need barrel entries and matching restricted-path
  rules in both apps, or the components are unimportable — and adding them only
  to the barrel while leaving the rule off is how the one reviewable list stops
  being the one reviewable list.

---

## Part 4 — Order

Roughly ascending by risk, and each batch is independently shippable.

**Batch 1 — the bug and the free wins.** `hidden` in `_offerable`; `precision`
and `non_negative` actually used; `sort_options`; `length`, `min_value`,
`max_value`. All server-side or one-line client-side, no new imports, no new
components. **Done.**

**Batch 2 — the properties that need somewhere to render.** `unique` and
`not_nullable` (including turning a duplicate-entry error into a field-level
message), `fetch_if_empty`, `documentation_url`, `show_description_on_click`,
`max_height`, `mask`, `remember_last_selected_value`, `translatable`,
`ignore_user_permissions` (carried, not honoured), `allow_on_submit`, and
`collapsible` / `collapsible_depends_on` / `hide_border` through `_form`.

**Batch 3 — the editors.** Barrel and ESLint for `frappe-ui/editor`; extend the
API reader to `experimental/`; barrel and ESLint for `frappe-ui/experimental`;
then Text Editor, Markdown Editor, Code, JSON, HTML Editor, and the four
read-only renderings from 2.8, which are small and sit in the same two files.

**Batch 4 — Dynamic Link.** Server-validated target, `_with_links` grouping,
the picker clearing on target change. Small, but it is the one that touches the
permission boundary, so it gets its own batch and its own tests.

**Batch 5 — Attachment Gallery.** Endpoint filter, carousel, upload, the
unsaved-record case.

**Batch 6 — child tables.** Extract the shared grid, `ChildTable.vue`, in-place
editing, add/remove/reorder, row expansion through `RecordForm`, and
`Table MultiSelect` alongside it. The biggest item by a distance, and the one
most likely to want splitting once it starts — if it does, the seam is the grid
(rows, cells, add/remove/reorder) against the expansion (`_form` on the child
meta, the drawer, the page).

---

## Part 5 — Decisions, taken

1. **Markdown edits as WYSIWYG** (2.2) — `Editor` with `format="markdown"`,
   the component's own default. The reader is a customer, not a developer. The
   cost is that markdown the editor does not model — front-matter, raw HTML,
   footnotes — can be normalised on save; if that turns out to bite, a source
   toggle is the fix, not a rewrite.
2. **Take the experimental `CodeEditor`** (2.3), wrapped by `FieldControl` so a
   breaking change touches one file, and with `tests/frappe_ui_api.py` extended
   to read `experimental/` so its props are checked like every other
   component's. That extension is a prerequisite, not a follow-up.
3. **Child rows expand, in the first pass** (2.5), through `RecordForm` and
   `FormSections` rather than a second layout engine. `_form` runs against the
   child's meta on the server and travels inside the parent's column payload.
4. **Currency precision is its own task** (1.6), after Batch 1. Batch 1 fixes
   `precision` for Float, Int and Percent; resolving a record's currency, its
   format and its symbol is a different question and should not turn the
   free-wins batch into a medium one.
