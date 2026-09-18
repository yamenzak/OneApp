# OneForms

A form is a door into a doctype, and until this module there was no door at all.
`docs/FRAPPE.md` called it the largest of the ten gaps: dropping Frappe's portal
and website builder was right, and it took the *forms* with it, so every
sentence that ends "and then somebody outside sends us this" ended at a person
re-keying it. OneCRM had no lead capture, OnePeople's hiring had no application
form, a supplier could not see their own purchase orders, and an employee could
not fill in their own address.

`docs/ONEFORMS.md` is the argument and the seven stages. This is what it is now.

## What it is over

**Frappe's own `Web Form`**, and in v17 that is most of the product already.
Five fields are the whole of why this module is small:

* `anonymous` — a stranger submits.
* `key_required` — a `Web Form Request` per recipient, carrying a key, an
  expiry, a first-used stamp, the values to pre-fill and a `references` table
  of the documents that key may touch.
* `show_list` with `list_columns` — somebody's own records, and only theirs.
* `allow_edit`, `allow_multiple`, `allow_delete` — what they may do once in.
* `allowed_embedding_domains` — an iframe on their own site.

And the security is thought through rather than assumed: `get_web_form_list`
filters to the key's own references before it runs, `get_web_form_request`
refuses a docname the key is not bound to, and a Link picker onto a doctype
Guest cannot read is refused outright.

**A Web Form writes into an ordinary doctype**, which is the whole reason this
is the right foundation and not a survey tool. A form over `Job Applicant`
makes a Job Applicant that OnePeople's hiring screens already show.

## A service, not a space

`catalogue.py` said so before the arc started, and `docs/CLEANUP.md` §1 is the
distinction: a space is a department you enter, a service is something every
department uses. A form is plainly the second — OneCRM wants one about leads,
OnePeople about applicants, OneBook about suppliers — so the shape is OneTask's.
A module, a dock tile, a window you keep open beside what you are doing, and a
route for the times you want the whole page. No rail, no four seats, no
entitlement.

## The decisions that cost something

**A form may only be made over a doctype a space this person holds already
shows them.** A `Web Form` can be pointed at anything on the site, so without
this rule a form is a way past every grant in the product: publish a page over
`Salary Slip` and read it back. `finding.placed` answers exactly that question
and is already the map the finder searches and the approvals inbox places rows
with, so there is one reading of "which doctypes are yours" rather than three.

**Making one is the workspace admin's.** A form is a route anybody on the
internet can reach that writes into a doctype, so "who may make one" is the same
question as "who may open the workspace to strangers", and that sits beside the
custom domain and the member list. `Web Form` ships with permissions for
`Website Manager` and nobody in a workspace holds that, so this checks the
reader and then writes with `ignore_permissions` — which is `alerts.py`'s
pattern, arrived at for the same reason.

**A form an app shipped is left alone.** Frappe installs two on every site and
an app may add more; each is part of what that app *is*, like its doctypes and
its print formats. `custom_onespace` marks the ones made here, the same field
and the same argument as the mark on `Notification`, `Assignment Rule` and
`Email Template`.

**Unpublished on the way in.** A form that went live the moment it was named
would be a URL somebody made by accident.

**A form counts who it invited and who answered, and not how many records it
made.** A `Web Form` writes an ordinary document and marks it in no way, so
"responses to this form" is not a question the database can answer. Making it
answerable means a column on every doctype a form is over — a schema change to
somebody else's table, for a number the space's own list screen already shows.
So each form carries the way to that screen instead, placed the same way
everything else in this product is placed.

**A model may build a form and style one; it may not publish either.** Both are
`oneai/actions.py` kinds, so a card is shown and a person presses Apply, and the
doctype rule and the admin gate are asked when the card is *proposed* rather
than when it is applied — offering a form over `Salary Slip` and refusing on the
press would have told somebody they could do something they could not.
`docs/ai.md` has the rest.

**Customising the page means the stylesheet, and that is a finding.**
`client_script` is written against `frappe.web_form.on(...)`, a runtime Frappe's
own Jinja page has and this Vue one does not, so a script saved here would be
dead code somebody had written and been charged for. Giving it a runtime means
shipping a script evaluator to a stranger's browser, which is a bigger and
different decision. `custom_css` gets a door of its own — checked for `@import`,
for a `url()` to another site, and for anything that closes the element — and
the page offers three `data-slot` hooks that will not move when it is reflowed.

## What is not built

1. **Payments.** A paid form is a gateway, a reconciliation and a refund policy,
   and none of those is a form.
2. **Branching by answer.** `Web Form Field` has `depends_on` and the form has
   `condition_json`; splitting a form into pages by what somebody answered is a
   survey tool's feature and is where `forms_pro` is genuinely ahead.
3. **Scripting the page.** The stylesheet has a door and JavaScript does not —
   see above. It is a decision rather than an omission.
4. **The website builder.** Still no portal, still no `Web Page`, still no
   theme. A form has a URL; it is not a site.
