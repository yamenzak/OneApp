# OneForms — a form is a door into a doctype

`docs/FRAPPE.md` named it as the second of the ten gaps and called it the
largest: **nothing in this product is public.** Dropping Frappe's portal and
website builder was right and it took the *forms* with it, so every sentence
that ends "and then somebody outside sends us this" ends at a person re-keying
it. OneCRM has no lead capture. OnePeople's hiring has no application form. A
supplier cannot see their own purchase orders. An employee cannot fill in their
own address.

This is the plan for closing it, and the first finding is that most of it is
already built — by Frappe, in v17, and rather well.

## 0. The stages

| | | |
|--:|---|---|
| 1 | The service, and a form that exists | done |
| 2 | The builder | done |
| 3 | The public page, in our own look | done |
| 4 | The invitation — a link addressed to one person | done |
| 5 | The list: a supplier's own records | done |
| 6 | Responses, and what a form is for | done |
| 7 | Guards, docs and the browser pass | done |
| 8 | OneAI builds one, OneCode styles it | done |

## 1. What Frappe v17 already has

Read off the bench rather than remembered. `Web Form` in v17 carries thirty-odd
fields and five of them are the product:

* **`anonymous`** — a submission with nobody signed in.
* **`key_required`** — and this is the one worth the arc. A `Web Form Request`
  is a row per recipient: a `key`, an `expires_on`, a `first_used_on`, a
  `web_form_values` JSON of what to pre-fill, and a `references` child table of
  the documents that key may touch. So "send this to one person" is a first-class
  idea in the framework, not something to invent.
* **`show_list`, `list_columns`, `list_title`** — the portal list. A key holder
  sees exactly the documents in their own `references` and nothing else.
* **`allow_edit`, `allow_multiple`, `allow_delete`, `apply_document_permissions`**
  — what they may do once they are in.
* **`allowed_embedding_domains`** — an iframe on somebody's own site.

And the security is thought through rather than assumed. `get_web_form_list`
filters to the key's own references before it runs;
`WebForm.get_web_form_request` rejects a docname the key is not bound to, with a
comment saying why; `ensure_guest_key_link_doctype_allowed` refuses a Link
picker onto a doctype Guest cannot read. Four whitelisted endpoints — `accept`,
`get_form_data`, `get_web_form_list`, `delete` — are all `allow_guest=True` and
all rate-limited.

**A Web Form writes into an ordinary doctype.** That is the whole reason this is
the right foundation and not a survey tool: a form over `Job Applicant` makes a
Job Applicant, which OnePeople's hiring screens then show. A form over `Address`
lets an employee fill in their own. A form over `Supplier Quotation` is a
supplier quoting.

## 2. What `forms_pro` is, and what we take from it

`github.com/bwhtech/forms_pro`, **AGPL-3.0** — the same licence as this
repository, so code may be taken under the same three obligations
`CLAUDE.md` sets for the frappe repositories: keep the copyright notice, say at
the top of the file what it was derived from, and never move that file to a
permissive licence. The copyright holder is bwhtech rather than Frappe
Technologies, which changes the name in the notice and nothing else.

Its stack is ours exactly: Vue 3, frappe-ui, Tailwind, `vuedraggable`.

**It is a different product from the one described here**, and that is the
finding rather than a complaint. It defines its own `Form`, `Form Field`,
`FP Team` and `FP Team Member` and keeps submissions in its own store — a
Typeform, with a `frappeFieldtype` mapping bolted on to sync a field into a
DocType afterwards. What we want is the other direction: the doctype is the
subject and the form is a *view* of it, which is what `Web Form` already is.

So we take the **builder**, which is the part that is genuinely good and the
part Frappe has not got: about 2,000 lines over thirteen components —
`FieldCard`, `FieldRenderer`, `RowDropZone`, `ColumnDropZone`, `FieldActions`,
`FieldPropertiesForm`, `ConditionalLogicSection` and the field set. Adapted to
emit `Web Form Field` rows rather than `Form Field`, and translated from
TypeScript to the JavaScript the rest of this frontend is written in.

What we do not take: its doctypes, its team model, its submission store, its
dashboard, its router and its pinia stores. A second form schema beside
`Web Form` would be a second answer to the question `Web Form` already answers.

## 3. Frappe's builder is for something else

Frappe v17 does ship a Vue form builder — `frappe/public/js/form_builder`,
drag-and-drop, sections and columns and tabs. It is mounted by
`customize_form.js` and by the DocType form, and it edits a **doctype's own
layout**. A Web Form's fields are still a child-table grid in the desk.

That is the gap the builder from `forms_pro` fills, and it is why this arc
takes one rather than writing one.

## 4. The public page is ours to draw

Frappe renders a web form with Jinja into `templates/web.html` — the Bootstrap
portal, its own navbar, its own footer, its own controls. That is a look this
product deliberately does not have, and `hide_navbar` and `hide_footer` exist
because everybody who ships one thinks so.

All four endpoints are `allow_guest=True`, so there is nothing to work around:
the SPA can draw the form itself and post to `accept`. And the route pattern
already exists — `/link/:secret` is OneCloud's public share, `meta.public` is
the flag the router guard reads, and `App.vue` already draws a public route
outside the shell because the shell needs a session a stranger does not have.

**The form page is a second `meta.public` route, not a second application.**

## 5. Stage 1 — the service, and a form that exists

**A service, not a space**, and `catalogue.py` said so before this arc started:
`_one("oneforms", SERVICE, built=False)`. The distinction is `docs/CLEANUP.md`
§1's — a space is a department you enter, a service is something every
department uses — and a form is plainly the second. OneCRM makes one about
leads, OnePeople about applicants, OneBook about suppliers. It is not a
department; it is a door, and every department wants one.

So the shape is OneTask's and OneCloud's: a module, a dock tile, a window you
keep open beside what you are doing, and a route for the times you want the
whole page. Not a rail, not four seats, not an entitlement.

Which leaves one question, and it is the reason this stage is first: a
`Web Form` can be pointed at **any doctype on the site**, including ones the
maker has never been granted. The rule is that **a form may only be made over a
doctype a space this person holds already shows them**, and `finding.placed`
already answers exactly that — it is the map the finder and the approvals inbox
both use.

Making a form is the workspace admin's, like an alert or a routing rule, and
for the same reason: `alerts.py` is the precedent, down to checking the reader
and then writing with `ignore_permissions`. `Web Form` ships with permissions
for `Website Manager` and nobody in a workspace holds that.

## 6. Stage 2 — the builder

`forms_pro`'s components, adapted. Drag a field in, set its properties, see it
as the person filling it in will. The field list comes from the doctype the
form is over, so the builder is choosing and arranging rather than inventing —
which is the difference between this and a survey tool, and the thing that
makes a form land in a record.

## 7. Stage 3 — the public page

A `meta.public` route that draws the form from `get_form_data` and posts to
`accept`, in this product's own look, with the workspace's own brand. Anonymous
first, because it is the simplest audience and the one that proves the route.

## 8. Stage 4 — the invitation

`Web Form Request` per recipient: make one, pre-fill `web_form_values` from what
we already know, bind `references` to their own document, and mail the link
through OneMail. This is "send the new starter their details form" and
"ask this supplier to confirm their bank account", and the framework has the
whole of the hard half already.

The maker is ours — `Web Form Request` ships no API for creating one.

## 9. Stage 5 — the list

`show_list` with a key: a supplier opens one link and sees their own purchase
orders, each one editable or not by the form's own settings. Drawn by us, from
`get_web_form_list`, in the same look as the form page.

## 10. Stage 6 — responses

What came in, as a screen in the space — which is the engine's ordinary list
over the form's own doctype, narrowed to the documents that form made. And the
count beside each form, which is the number anybody actually wants.

## 11. Stage 7 — guards, docs and the browser pass

The usual: `tests/test_forms.py` for the grant rule and the token path,
`e2e/forms.spec.js` for the public route under a guest session — which no spec
in this suite has ever done, and is the interesting part.

## 12. Stage 8 — OneAI builds one, OneCode styles it

Two questions, asked once the other seven were done and answerable together.

**Can a model build a form?** Yes, and as a card like everything else a model
asks for: `forms.build` on `oneai/actions.py`'s registry, with three tools —
`the_forms_of_this_workspace` to see what exists and what a new one could be
over, `propose_form`, `propose_form_styling`. What makes this kind different
from the four the spine ships with is that it builds a *surface* rather than a
record, so the rule that has to hold is the module's own: `_admin` and `_over`
are asked in `check`, when the card is proposed, not in `apply`. A card offering
a form over `Salary Slip` that refused on the press would have told somebody
they could publish a page past every grant in the product. Every fieldname is
checked at the same moment, and a field the doctype itself requires stays
required whatever the model said.

Apply is `make`, `layout`, `settings` and `style` — the same four the builder
posts to. What it makes is a **draft**: publishing is what opens a workspace to
strangers, and it stays a person's press.

Who may reach it is one word — `anyone`, `signed-in`, `invitation` — rather than
three booleans a model could set independently, which is how a page ends up
refusing everyone.

**Can OneCode customise the page?** The stylesheet, yes; the script, no, and
that is a finding rather than caution. `client_script` is written against
`frappe.web_form.on(...)` — a runtime that exists on Frappe's own Jinja page and
not on ours — so a script saved there would be dead code a customer had written
and been charged for. Giving it a runtime means shipping a script evaluator to a
stranger's browser, which is a different and much bigger decision than letting
somebody style a page.

So `custom_css` gets a door of its own rather than a place in `SETTINGS`:
`check_css` refuses an `@import`, a `url()` to anywhere but a `data:` one, and
anything matching `</style` — which ends the element the browser is reading, so
everything after it is markup. The same field is written two ways, by a person
in OneCode's editor from the builder's Style button, and by `forms.style` as a
card. The public page carries three `data-slot` hooks — `public-form`,
`form-title`, `form-introduction` — because Tailwind utilities are not an API
and a stylesheet needs something that will not move.

## What this arc does not do

**A form over a doctype the space does not grant.** Stage 1's rule, and it is
the one that keeps a form from becoming a way around the permission model.

**Payments.** A paid form is a payment gateway, a reconciliation and a refund
policy, and none of those is a form.

**Scripting the public page.** Stage 8's finding, above. The stylesheet has a
door and JavaScript does not.

**Logic beyond a field's condition.** `Web Form Field` has `depends_on` and the
form has `condition_json`; branching a form into pages by answer is a survey
tool's feature and is where `forms_pro` is genuinely ahead. Left out until
somebody asks.

**The website builder.** Still no portal, still no `Web Page`, still no theme.
A form has a URL; it is not a site.

## What the arc found

Four things it did not expect, each written where it was learned.

**A list a stranger sees has to name its columns.** With `list_columns` empty,
Frappe falls back to the doctype's list-view fields and resolves every Link in
them through `ensure_guest_key_link_doctype_allowed` — so a form over Job
Applicant, whose `job_title` links to Job Opening, answered *"You don't have
permission to access the Job Opening DocType"* to somebody holding a perfectly
good key. Measured the first time `show_list` was turned on.
`service.settings` now fills them from the form's own plain fields.

**Deleting a form means taking its keys back first.** `Web Form Request` links
to the form, so Frappe refuses — rightly — and the fix is also the behaviour
somebody wants: the links stop working, which is what deleting the form was
for.

**"Responses to this form" is not a question the database can answer.** A Web
Form writes an ordinary document and marks it in no way. Making it answerable
means a column on every doctype a form is over — a schema change to somebody
else's table for a number the space's own list screen already shows. So a form
says what it knows, which is how many were invited and how many answered, and
carries a way through to the records.

**`client_script` is dead code on our renderer.** It is written against
`frappe.web_form.on(...)`, which Frappe's Jinja page provides and our Vue page
does not — so the field would have saved, validated and done nothing. Found
while working out what "OneCode customises the form" ought to mean, and it is
the reason that answer is the stylesheet.
