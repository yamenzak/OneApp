# Flows

Almost everything here is ERPNext's own flow drawn on our screens, so this is
short by construction. Two things happen that are ours.

## 1. A document is stamped with where it came from

On every save of a `Sales Invoice`, `Purchase Invoice`, `Payment Entry` or
`Journal Entry`:

1. `hooks.py` calls `oneapp.onebook.origin.stamp` on `validate`.
2. `stamp` asks `doc.meta.has_field("custom_origin")` and returns if not.
   Custom fields are applied by the **tenant seeder** and not by migrate, so
   between installing the app and seeding the space every one of these doctypes
   exists without the column.
3. `_origin_of` reads the document's own links, people first:
   * a `Journal Entry` with an account row whose `reference_type` is one of
     `FROM_PEOPLE` → `onehr`;
   * a `Payment Entry` with a reference row naming one of them → `onehr`,
     otherwise its `project` → `oneproject`;
   * either invoice, its `project` or any item's → `oneproject`;
   * anything else → an empty string, which means somebody raised it here.
4. The value is set on the document. It is rewritten on every save rather than
   set once, because the thing it is derived from is editable until submit.

`origin.restamp(doctype)` does the same over every existing row, for a workspace
that had ERPNext before it had OneBook. It writes with `db_set` and no version
row: this is a cache of something that has not changed, and a hundred Version
rows saying so would be noise on submitted documents.

## 2. The four seats decide what a screen can do

There is no code in this module for it, and that is the interesting part. The
engine reads `frappe.has_permission` to decide whether a screen draws a New
button, a Save or a Submit, so a grant of `Read` on `Salary Slip` produces a
read-only payroll screen with no further instruction. See `permissions.md`.

## What the space does not do

**It does not post anything automatically.** Nothing here watches OnePeople or
OneProject and raises a document in response. A payroll run's bank entry is
written by HRMS when somebody presses **Make the bank entry** in OnePeople —
`docs/ERP-SPACES.md`, "The line that moved" — and it appears here because it is
a `Journal Entry`, not because this module was told about it.

That is the whole shape of the integration: the other spaces draft and this one
reads, posts and pays. There is no message, no queue and nothing to keep in
step.
