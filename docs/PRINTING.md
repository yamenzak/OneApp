# Printing and naming

Two things a workspace decides once and lives with for years: what a printed
document looks like, and what a record's id looks like before anybody types
one. Both are Frappe's, whole, and both are reached from OneSpace's settings
rather than from the desk — which nobody here uses.

The short version: **we built the surfaces, not the mechanics.** Every write
goes through Frappe's own `Print Format`, `Letter Head`, `Print Settings` and
`Document Naming Settings`, and every render goes through
`PrintFormatGenerator` and `frappe.get_print`. There is no HTML in
`printing.py` and no SQL in `naming.py`.

> A reference, not an explanation. The argument for all of this — why the
> framework renders and we do not — is in `docs/ONESPACE.md`; this is the
> schema and the rules a test reads back.

---

## Why not a renderer of our own

A print format is not a template we render. It is a document *the framework*
renders: `frappe.get_print` walks the format, resolves the letter head, applies
the print style, honours the page size and margins, runs the per-fieldtype
renderers and hands the result to whichever PDF engine the site runs. Every one
of those is a decision somebody already made carefully.

A second renderer would be a second set of the same decisions, drifting — and
"drifting" for a printed invoice means a customer's letter head in the wrong
place on the copy that went to their auditor. So the builder writes Frappe's
own `format_data` and stops.

That has one consequence worth stating plainly: **a format drawn here opens and
prints identically anywhere else it is reached from** — a scheduled email, a
portal download, the desk if anybody ever turned it on.

---

## The layout contract

`format_data` on a Frappe *beta* print format (`print_format_builder_beta = 1`):

```json
{
  "sections": [
    {"columns": [{"fields": [ ... ], "width": 1}],
     "justify": "space-between", "gap": 20}
  ],
  "header": {"columns": [{"fields": [ ... ]}]},
  "footer": {"columns": [{"fields": [ ... ]}]}
}
```

A **field** is a docfield-shaped dict — `fieldname`, `fieldtype`, `label`, and
`show_label: "hide"` for value-only. A child table carries `table_columns`,
each naming a field of the *child* doctype (plus `idx`, the row number).

An **element** is one of exactly five, because the generator's own template
branches on each by name and falls through to "render the docfield" for
anything else:

| Element | Carries |
|---|---|
| `HTML` | `html` — rendered as a Jinja template with the document in scope |
| `Spacer` | `height`, in pixels |
| `Divider` | nothing |
| `Image` | `fieldname` or `image_url`, plus `align` and `width` |
| `Barcode` | `fieldname`, plus `align` and `width` |

`justify` is one of `space-between`, `space-evenly`, `center`, `right-end` —
each names a CSS class in the generator's template, which is why the set is
closed rather than merely documented.

Everything the browser sends goes through `printing._layout`, which drops what
it does not recognise **one element at a time** — a format is drawn over
minutes and a single unknown key should not lose the drawing — with one
exception: a `fieldname` the doctype does not have is refused by name. That is
the only mistake whose symptom is a blank space on a printed invoice weeks
later rather than a missing box on a canvas somebody is looking at.

---

## The two doors

`workspace._printing_gate()` — the workspace's own admin role, the same door
the settings dialog uses. It matters more here than in most panels: a drawn
format may carry an HTML element, which the generator renders as a Jinja
template with the document in scope.

`workspace._printable_gate(doctype)` — that, **plus** the doctype being one
this workspace's own screens show. The desk's version of this page offers every
doctype on the site; ours offers what the manifest granted, so `Error Log` has
no route here at all.

Printing a *record* is gated differently again, in `spaceview`: the space, the
screen, and the record re-read through `record()` so the screen's filters and
this person's User Permissions both hold. A record a screen would not list is
not one it will print.

Frappe's own `Print Format` and `Letter Head` grant write to System Manager,
and every workspace member is a Website User by design — so the writes go
`ignore_permissions` **behind** the gates above. That is the same pattern as
`collab.py`: our check on the thing, then Frappe's write.

---

## Where it lives in the product

* **Settings → Printing** — the paper. Page size, font, PDF engine, margins,
  letter head on or off, drafts printable. A settings group like any other,
  driven by `workspace.GROUPS`.
* **Settings → Print formats** — what is drawn on it. The format list per
  doctype, the builder, and the letter heads.
* **The record header → Print** — a picker and a preview. Format, letter head,
  Download PDF, Print. Three questions, because the rest was decided once in
  settings for everybody.

The preview is an iframe in both places, and has to be: a print format's CSS is
written to win against a blank page — `body { font-size: 8pt }`, table resets,
page rules — so dropping the returned HTML into the app's document would
restyle the app around it. `sandbox=""` with nothing in it, because a format is
HTML somebody in the workspace wrote and a preview is not a place to run it.

---

## The builder

Three columns: what can go on the page, what is on it, and what the selected
thing is. The middle one is laid out the way it will print — a header band, the
body's sections, a footer band — rather than as a tree, because the question
being answered all day is "where on the page is this".

Dragging and clicking are the same path. A palette entry dropped on a column is
`dropped(entry)` spliced in at an index; an element dragged from one column to
another comes out of its source list first, then goes in — in that order, or
dragging a thing two places to its right lands it one place short.

The preview renders the **unsaved** layout through the same generator the PDF
uses (`printing.draft_preview`), against the newest record this person may
read. A canvas draws boxes; only the generator knows what the type renderers,
the letter head and the print style do to them.

---

## Naming

Frappe answers "what is this record called" three ways, and only one of them is
a customer's to change:

* **`autoname`** on the doctype — `hash`, `field:title`, or a literal series
  like `EV.#####`. Part of what the doctype *is*. Shown here, never set.
* **`naming_series`** — a Select field whose options are the prefixes this
  workspace uses. Stored as a Property Setter on the field rather than as an
  edit to the doctype, which is exactly why it is safe to offer.
* **`Document Naming Rule`** — a prefix chosen by condition. Not offered yet.

`naming._kind()` tells the first two apart, and the panel honours it: for an
`autoname` doctype the series is read-only and only the counter can move. The
server refuses the write either way, but a Save that is always refused is worse
than no Save at all.

The counter is read and written **per prefix**, because that is what `Series`
is keyed on — two doctypes sharing a prefix share a counter, which is a thing
people do on purpose and a thing nobody expects when they have not. Moving one
backwards re-issues ids that already exist, so Frappe writes a Version row for
the change and the panel says so.

---

## What a manifest may ship

A `OneSpace Space Screen` carries two fixture fields:

* **`naming_series`** — prefixes, one per line, applied to the screen's doctype.
* **`print_formats`** — a JSON list of `{name, default, layout, setup}`, each
  created as a drawn format.

Both are **fixtures, applied once**. `sync.sync_screen_fixtures` runs on every
sync and creates only what is missing: a series where no Property Setter exists
yet, a format where nothing of that name does. This is the opposite of
everything else in `sync.py` — roles, permissions and members are reconciled
every time, because the control plane owns them. A print format is not owned by
the control plane; an app gives a workspace somewhere to start and the
workspace owns what it does with it. Reconciling these would silently undo an
afternoon's work every fifteen minutes, and a customer whose invoice format
keeps reverting has no way at all of finding out why.

The preferred way to write a `layout` is to draw it in the builder, save it,
and read `format_data` back — so what an app ships and what a workspace draws
are the same kind of thing, and look it.

---

## What is not built

* **Document Naming Rule.** One series per doctype covers what a workspace
  needs; a prefix chosen by condition is a rule engine and wants its own
  surface.
* **The Typst renderer.** Frappe registers it through the `pdf_generator` hook
  and a format that uses it needs Typst installed. Chrome and wkhtmltopdf are
  what our sites have.
* **Print Designer.** A separate app with its own `format_data` schema. A
  format made by it still prints; it simply does not open in our builder, and
  says so.
* **Raw printing.** Escape/POS commands, for label printers. The store is there
  and nothing in the product reaches it.
