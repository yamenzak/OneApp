# Flows

## Listing the forms — `service.forms`

1. **`_admin`** refuses anybody but the workspace owner or our support.
2. One `get_all` over `Web Form` filtered to `custom_onespace`, so a form an app
   shipped is not in the list and cannot be edited from here.
3. **`offerable`** comes back with it: every doctype this reader could make a
   form over, which is `finding.placed` and nothing else on the site.

## Making one — `service.make`

1. `_admin`, then **`_over`**, which refuses a doctype that is not in
   `offerable`. This is the rule the whole module hangs on.
2. **`_route`** scrubs the title to words and hyphens and suffixes it until it
   is free — two forms called "Contact us" is an ordinary thing to want.
3. Inserted **unpublished** and **login required**, with no fields on it.
   Publishing is a second press and the fields are the builder's.

## Renaming, publishing, deleting

`rename` leaves the route alone: it is a link people are holding. `publish` is
the only switch that changes who can reach the page. `forget` deletes the form
and not what it collected — those are ordinary records in an ordinary doctype,
and a form is a door rather than a folder.

Each goes through **`_ours`**, which refuses a form this workspace did not make.

## Building one — `service.read`, `service.layout`, `service.settings`

`read` answers the form, the fields on it, and `available` — the doctype's own
fields, read off its meta so a customised doctype offers the field somebody
added. `NEVER` is the only narrowing and every entry has a reason beside it.

`layout` **replaces** the fields, which is what drag-and-drop means: the browser
holds the whole list and reconciling two orderings would be inventing a conflict
nobody has. Every row is checked against `available`, the fieldtype is taken
from the doctype rather than the browser, and a field the doctype itself
requires stays required whatever the form says.

`settings` writes from the `SETTINGS` allowlist and no further. `client_script`
and `custom_css` are outside it: code on a page strangers load is not a setting.
Two rules are kept here rather than hoped for — a form open to anybody cannot
also require a sign-in, and a form showing a list must name its columns.

## Styling it — `service.style`

1. `_admin`, then `_ours`.
2. **`check_css`**, which is the door `custom_css` has instead of a place in
   `SETTINGS`. Three refusals, each naming the rule it broke: longer than
   `MAX_CSS`, an `@import` or a `url()` to another site (a `data:` one is fine),
   or anything matching `</style` — which ends the element the browser is
   reading, so everything after it is markup.
3. Saved. `read` hands it back beside the settings rather than in them, and the
   public page puts it in a `<style>` of its own and takes it away again when
   the reader navigates off.

Written two ways into the same field: OneCode's editor, from the Style button in
the builder, or `forms.style` — a card a model proposed and a person applied.

## Asking for one — `actions.BuildForm`, `actions.StyleForm`

1. A model calls `the_forms_of_this_workspace` to see what exists and what a new
   one could be over.
2. `propose_form` or `propose_form_styling` makes a card. **`check` asks
   `_admin`, `_over`, every fieldname and `check_css` right there**, so a
   refusal lands on the turn the model made the mistake rather than after
   somebody agreed to it.
3. Apply is `make`, `layout`, `settings` and `style` — the same four the builder
   posts to, with nothing privileged beside them. What it makes is a draft:
   publishing stays a person's press.

## The page a stranger sees — `public.page`, `public.send`

1. **`_form`** resolves the route, and answers the same sentence for "no such
   form" and "not published" — out there the difference is a fact about this
   workspace.
2. **`_admitted`** asks Frappe's own access question through
   `get_web_form_request`.
3. `page` shapes the fields for a browser and resolves a Link field's options
   through `get_link_options`, which stays on the server because its three
   checks only run there. The introduction is `sanitize_html`'d.
4. `send` hands everything to Frappe's `accept`, which re-checks published,
   binds the key to the docname, refuses a guest where a sign-in is required,
   and drops a signed-in session to Guest on an anonymous form.

## The invitation — `invite.invite`, `invite.invitations`, `invite.uninvite`

A `Web Form Request` with an expiry, the values to pre-fill and — where one is
named — the document it is bound to. Frappe validates the pre-fill against the
form's own fields on save. Mailed with `frappe.sendmail`, queued, where an
address was given; made either way, because sending a link by hand is ordinary.

`uninvite` deletes rather than expires: an invitation is not a record of
anything, and what it produced is a document of its own.

## What a key holder sees — `invite.theirs`

Straight through to `get_web_form_list`, which filters to the key's own
`references` before it queries. This adds the route lookup and nothing else: a
second reading of which rows a key may see is the one thing that must not
exist.
