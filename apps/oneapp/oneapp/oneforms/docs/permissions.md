# Permissions

Two gates, and between them they are the whole of it.

## Who may make a form

The workspace owner, or our support signed in as such — `_admin`, against
`OWNER_ROLE` and `SUPPORT_ROLE`. A form is a route anybody on the internet can
reach that writes into a doctype, so this is the same question as who may add a
custom domain or invite a member, and it belongs with those.

`Web Form` ships with permissions for `Website Manager`, which nobody in a
workspace holds. So every write here checks the reader first and then uses
`ignore_permissions` — `alerts.py`'s pattern, arrived at for the same reason and
with the same rule: the check is never skipped and never partial.

## What a form may be made over

**Only a doctype a space this person holds already shows them.** `offerable` is
`finding.placed`, which is every screen of every space they can open, and
`_over` refuses anything else with `frappe.PermissionError`.

This is the rule the module exists to keep. Without it a `Web Form` is a way
past every grant in the product: point one at `Salary Slip`, publish it, read it
back. With it, a form can only ever be a door onto something the maker could
already open.

## What it does not touch

A form an app shipped. `_ours` refuses anything without `custom_onespace`, so
Frappe's own two and anything an app installed are invisible here and
uneditable from here.

## And the person filling it in

Not this module's, and deliberately: `login_required`, `anonymous`,
`key_required` and `apply_document_permissions` are `Web Form`'s own fields and
Frappe's own enforcement. Stages 3 to 5 draw those surfaces; none of them
decides who may reach one.
