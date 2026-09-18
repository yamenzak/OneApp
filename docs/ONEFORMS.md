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
| 1 | The service, and a form that exists | not started |
| 2 | The builder | not started |
| 3 | The public page, in our own look | not started |
| 4 | The invitation — a link addressed to one person | not started |
| 5 | The list: a supplier's own records | not started |
| 6 | Responses, and what a form is for | not started |
| 7 | Guards, docs and the browser pass | not started |

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

## What this arc does not do

**A form over a doctype the space does not grant.** Stage 1's rule, and it is
the one that keeps a form from becoming a way around the permission model.

**Payments.** A paid form is a payment gateway, a reconciliation and a refund
policy, and none of those is a form.

**Logic beyond a field's condition.** `Web Form Field` has `depends_on` and the
form has `condition_json`; branching a form into pages by answer is a survey
tool's feature and is where `forms_pro` is genuinely ahead. Left out until
somebody asks.

**The website builder.** Still no portal, still no `Web Page`, still no theme.
A form has a URL; it is not a site.
