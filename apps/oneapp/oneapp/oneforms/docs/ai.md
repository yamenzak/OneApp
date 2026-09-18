# AI

Two things, and they are the two halves of making a form: **build this one**
and **make it look like this**. Both are `oneai/actions.py` kinds — `forms.build`
and `forms.style` — so a model proposes and a person presses Apply, and both
are registered through `ai_actions` and `onespace_chat_tools` in `hooks.py`.

Three tools:

* `the_forms_of_this_workspace` — the forms that exist, and every doctype a new
  one could be made over with the fields each has. Read-only, and it is what a
  model is told to call first: a form can only ever be over something one of
  their own spaces already shows them, so guessing a doctype name is guessing
  wrong.
* `propose_form` — a doctype, a title, an ordered field list, who may reach it,
  and an introduction.
* `propose_form_styling` — the whole stylesheet for one form's public page.

**The rules are not relaxed for a model, and they are asked at the moment it
proposes.** `service._admin` and `service._over` run in `check`, not in `apply`,
because a card offering a form over Salary Slip that then refused on the press
would have told somebody they could publish a page past every grant in the
product. Every fieldname is checked against the doctype's own at the same
moment, and a field the doctype itself requires stays required whatever the
model said.

**Applying is the same four calls the builder posts to** — `make`, `layout`,
`settings`, `style` — with no privileged path beside them, which is why
`oneforms/actions.py` is short. What it makes is a *draft*: publishing is a
person's press, because publishing is what opens a workspace to strangers.

**Who may reach it is one word rather than three switches.** `anyone`,
`signed-in`, `invitation`. Three booleans a model set independently is how a
page ends up refusing everyone.

**Styling is CSS and not JavaScript**, and that is a finding rather than
caution. `client_script` is written against `frappe.web_form.on(...)`, a runtime
Frappe's own Jinja page has and our Vue page does not, so a script saved here
would be dead code a customer had written. Giving it a runtime means shipping a
script evaluator to a stranger's browser, which is a bigger decision than
letting somebody style a page. The stylesheet goes through `service.check_css`
whoever wrote it — no `@import`, no `url()` to another site (a `data:` one is
fine), nothing that closes the element — and the page offers three hooks that
will not move when somebody reflows it: `[data-slot="public-form"]`,
`[data-slot="form-title"]`, `[data-slot="form-introduction"]`.

The same stylesheet is written by hand in OneCode's editor, from the Style
button in the builder. One field, two ways in.

Nothing is configured per tenant.
