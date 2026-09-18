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

## And a model

The same two gates, asked in `oneai/actions.py`'s `check` rather than in
`apply`. `_admin` and `_over` run when the card is proposed, so a model that
offered a form over `Salary Slip` is refused on the turn it tried — a card that
waited until Apply would have told somebody they could publish a page past
every grant in the product. A model cannot publish: what a card makes is a
draft.

The stylesheet is the same door, `check_css`, whoever wrote it.

## What it does not touch

A form an app shipped. `_ours` refuses anything without `custom_onespace`, so
Frappe's own two and anything an app installed are invisible here and
uneditable from here.

## And the person filling it in

Not this module's, and deliberately: `login_required`, `anonymous`,
`key_required` and `apply_document_permissions` are `Web Form`'s own fields and
Frappe's own enforcement.

`public.page` asks the access question through `WebForm.get_web_form_request`,
which is the same call Frappe's own page makes; `public.send` hands the write
to `frappe…accept`, which asks it again. `invite.theirs` hands the read to
`get_web_form_list`, which filters to the key's own `references` before it
queries. None of the three decides anything, and `tests/test_forms.py` reads
that off the syntax tree: no `new_doc`, no `insert`, no `get_all` in the public
half.

Three things this module does add, and each is a rule rather than a permission:

* **A key is refused for an open form.** An invitation to a page anybody can
  already reach is a link that says nothing.
* **The introduction is sanitised.** Only an admin can set it, and the page is
  served to strangers — so a script tag would run in *their* browser.
  `client_script` and `custom_css` are outside `SETTINGS` for the same reason.
* **Every refusal out there reads the same.** No such form, taken down,
  expired key, wrong key: one sentence. Inside the product the two refusals are
  deliberately different — `_refuse_ungranted` says why — and out here the
  difference is a fact a stranger has no business being told.
