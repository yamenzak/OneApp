# Night UI works — an audit against Frappe CRM

Read `frappe/crm` at `fa9f3a1` (317 Vue components) beside our own engine (31
screen components) and asked one question throughout: **what do they have that
our manifest could generate, rather than that we would hand-write per space?**

That framing matters, because it is the one place we are already ahead and the
one place it would be easy to lose.

---

## 0. The headline: we are more general, they are more furnished

CRM declares its record tabs **by hand, per page**. `pages/Deal.vue:575` is a
literal list of nine tabs with imported icon components; `pages/Lead.vue`,
`pages/Contact.vue` and their three mobile twins each have their own copy. Their
list views are one component per doctype — `DealsListView.vue`,
`LeadsListView.vue`, `ContactsListView.vue`, `TasksListView.vue`. Nothing in
their frontend reads a server-side manifest; there is no equivalent of
`spaceview.spec`.

Ours generates all of that from the doctype and the manifest. A new Space needs
no Vue at all.

So this audit is **not** "become CRM". It is: take the components they have
built that we have not, and wire each one into the generator/manifest so it
arrives for free on every Space. Where CRM hard-codes, we declare.

Everything below is sorted by that test.

---

## 1. Child tables — we have one, it is thinner than theirs

We do have `ChildTable.vue` (211 lines). CRM's `Controls/Grid.vue` is 843, plus
three modals. What theirs has that ours does not:

| | CRM | Ours |
|---|---|---|
| Inline edit | ✓ | ✓ |
| Expand a row into a form | ✓ `GridRowModal` | ✓ |
| Add / delete a row | ✓ | ✓ |
| **Select rows, delete in bulk** | ✓ | ✗ |
| **Drag to reorder (`idx`)** | ✓ | ✗ |
| **Choose which columns show** | ✓ `GridFieldsEditorModal` | ✗ |
| **Per-column width** | ✓ | ✗ |
| **Right-align numerics** | ✓ | ✗ |
| **Required marker in the header** | ✓ | ✗ |

**Proposal.** Add the four cheap ones — bulk select/delete, drag reorder,
right-aligned numeric columns, the required asterisk. The column picker I would
*not* copy: theirs is per-user UI state stored client-side; ours should read
`in_list_view` off the child doctype, which is the same answer the doctype
already gives and needs no picker at all. That is the manifest-first version of
the same feature.

---

## 2. Kanban — worth building, and it is the same card as the link preview

CRM's `KanbanView.vue` is 277 lines over `vuedraggable`. Columns come from a
Select field's options, each column carries a colour, cards drag between columns
and the drop writes the field. Card content is a slot: title field, then a
declared list of fields beneath.

Two things fall out of this that you spotted and I agree with:

**The kanban column *is* our Document States work.** We just declared a colour
for every option of every status Select. A kanban over `Tenant.status` gets its
seven columns and their colours with nothing further declared. Kanban is
therefore much cheaper for us than it was for them.

**The kanban card and the link hover card are the same component.** Ours
(`RecordPreview.vue`, 120 lines) is a label/value grid driven by `in_preview`,
which is the doctype's own flag. A kanban card is: title, a few fields, an
avatar. Those are the same inputs. One `RecordCard` used by both means the hover
card gets better for free when the kanban does, and a doctype that marks
`in_preview` fields gets a decent kanban card without a manifest entry.

**Proposal.** Build `board` (we already reserve the name in `viewTypes.js`) as:
- columns from the screen's `status_field` options, coloured by Document States
- cards are `RecordCard`, shared with the link preview
- drop writes the status field through the existing `save`
- `view_settings.board.column_field` overrides the status field where a screen
  wants to group by something else — the schema for that already exists

---

## 3. The record surface — tabs, and what is on them

Ours has four tabs: Details, Comments, History, Files. Theirs has up to ten, but
six of those are CRM-domain (Emails, Calls, Tasks, Notes, Events, WhatsApp) and
should not be copied.

What is genuinely better in theirs:

- **`Activities.vue` renders one timeline with typed entries** — each activity
  carries an icon chosen by type (`timelineIcon()`), a timestamp component, and
  a per-type body. Ours splits comments and history into two tabs and neither
  has an icon.
- **`CollapsibleSection`** — their side panel folds sections and remembers it.
  Ours renders sections flat (we do have `sectionCollapsed` in `rules.js` for
  `collapsible`, so the metadata is there and the affordance is not).
- **`FadedScrollableDiv`** — a scroll container that fades its top and bottom
  edge. Small, and it is the honest version of the glow we just removed from the
  list, because here it genuinely marks a scroll boundary rather than dimming
  data.

**Proposal.**
- Merge Comments and History into one **Activity** tab with typed, icon-carrying
  entries, keeping the separate tabs as filters within it. This is closer to the
  desk and to CRM, and it stops "who changed this" and "what did they say about
  it" being two places.
- Honour `collapsible` / `collapsible_depends_on` in `FormSections` — we already
  carry both properties and render neither.
- A **Meta** tab, or keep `RecordMeta` where it is at the foot of Details. I lean
  to leaving it: it is two lines, and a tab for it would be the least-visited tab
  in the product. Worth your call.

---

## 4. Tab icons — and enforcing them

Confirmed: **none of our tabs carry an icon.** Not the record tabs
(`fields`, `comments`, `history`, `files`), not the doctype's own Tab Breaks
rendered by `RecordForm`, not the settings dialog's panels (those do have icons
— `SettingsShell` passes one per group).

CRM gives every tab an icon, hand-imported per page.

**Proposal, manifest-first:**
- Record tabs: a fixed four, so their icons live in one constant beside the tab
  list. No declaration needed.
- **Doctype Tab Breaks**: Frappe has no icon property on a Tab Break. Two honest
  options — (a) derive one from the tab's label against a small keyword map, or
  (b) let the manifest declare `tab_icons` per screen. I prefer **(a) with (b)
  as the override**, because a doctype we do not own (ERPNext's) will never have
  a manifest entry and should still get something.
- **Enforce it** the way we now enforce status colours: a test that every tab
  our UI renders resolves to an icon, so adding a fifth record tab without one
  fails.

---

## 5. Select icons — the natural extension of the colour work

We just gave every status option a colour. An icon per option is the same
declaration, one field wider, and renders in more places than the colour does:

- the list badge
- the record's status badge
- the Select control's own options when open
- a kanban column header
- a quick-filter chip

**Proposal.** Extend the generator's `states=` from `(title, color)` to
`(title, color, icon)`, icon optional and drawn from the same closed lucide set
`SPACE_ICONS` uses. Frappe's own `DocType State` has no icon column, so this is
ours: it rides in the payload beside `states` rather than in the doctype JSON's
`states` array — or, cleaner, we add it to the array and Frappe simply ignores a
key it does not know. I would test which before committing to it.

Enforcement mirrors the colour rule: **if any option of a Select declares an
icon, all of them must** — a half-iconed dropdown is worse than none.

---

## 6. Views we do not have

`viewTypes.js` reserves `board`, `calendar`, `grid`, `map` and builds none.
CRM has list, kanban, group-by, calendar and a dashboard.

Ranked by what our manifest can generate cheaply:

1. **Board (kanban)** — cheapest, because Document States already give the
   columns and their colours. §2.
2. **Group-by** — CRM's `GroupBy.vue` is 74 lines. We already group rows inside
   the list (`group_by` on a saved view), so this is arguably done.
3. **Calendar** — needs a start/end field pair. `view_settings.calendar.
   start_field` is already in the schema. Medium.
4. **Grid (gallery)** — cards in a wrap. Trivial once `RecordCard` exists (§2).
5. **Map** — needs a Geolocation field. We render Geolocation as read-only
   today. Lowest value; I would drop it from `viewTypes` rather than leave a
   name we do not intend to build.

---

## 7. Components of theirs worth having, that our manifest can drive

- **`Resizer.vue`** — a drag handle. We resize the record pane already; theirs
  is reusable.
- **`FadedScrollableDiv`** — §3.
- **`MultipleAvatar`** — a stack of overlapping avatars with an overflow count.
  We show `_assign` as plain text. This is the desk's own treatment.
- **`AssignTo`** — assignment as a first-class control over `_assign`. We carry
  the field and render it as text.
- **`QuickEntryModal` / `CreateDocumentModal`** — we have this (`CreateDialog`).
- **`ConditionsFilter`** — nested AND/OR filter groups. Ours is a flat AND list.
  This is a real capability gap, but a large one; I would not do it tonight.
- **`IconPicker`** — we have one.
- **`KeyboardShortcut` / `ShortcutTooltip`** — no shortcuts in ours at all.

---

## 8. What I would do tonight, in order

Each is independently shippable and independently revertable.

| # | Work | Why it is first |
|---|------|-----------------|
| 1 | `RecordCard`, shared by link preview and kanban | Unblocks 2 and 5; makes the hover card better on its own |
| 2 | Board view over the status field | Biggest visible win; Document States already did the hard part |
| 3 | Select icons, declared beside colours, enforced | Small, and it improves every surface that shows a status |
| 4 | Tab icons + the guard that every tab has one | Small, and you asked for it explicitly |
| 5 | Child table: bulk select/delete, reorder, numeric alignment, required marker | Contained; no new concepts |
| 6 | Collapsible sections (we carry the metadata already) | Two properties currently read and ignored |
| 7 | Merge Comments + History into one Activity timeline with typed icons | Largest of the seven; do last |

Not tonight, and I would want to talk about them first: nested AND/OR filters,
calendar view, assignment as a control, keyboard shortcuts.

---

## 9. Two things I would push back on

**Do not copy their per-page tab declarations.** It is the one structural thing
we do better, and every component below could be wired the same wrong way if we
are not deliberate.

**Do not copy their per-doctype list views.** `DealsListView.vue` exists because
their list cannot be generated. Ours can. Any component we lift should end up
reading the manifest or the doctype, never a literal.

---

## 10. Licence

`frappe/crm` is **AGPL-3.0**; our repo is MIT. Same constraint as `frappe/central`
last time: read it for patterns, do not paste code. Everything above is written
as "build this, informed by how they did it", and I will implement from our own
components — `frappe-ui` itself is the shared dependency and is MIT, so anything
that is really a frappe-ui component we should take from frappe-ui directly
rather than from CRM's copy of the idea.
