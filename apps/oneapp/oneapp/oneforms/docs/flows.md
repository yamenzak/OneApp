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

## Drawing it — `lib/layout.js`

The rows arrive flat and three of them are furniture. `pagesOf` reads the list
into `[{ sections: [{ label, columns }] }]`:

1. **Page Break** starts a step. The page draws one at a time, with a progress
   bar, a Back, a Next and Send only on the last.
2. **Section Break** starts a titled group inside the step.
3. **Column Break** puts what follows beside what came before — from `sm` up
   only, because two fields side by side on a phone is two fields nobody can
   type in.

Empty pages, sections and columns are dropped on the way out, so a builder that
left two breaks together does not produce a heading with nothing under it.

Next runs the browser's own `reportValidity`, which works because only the
current step is in the document. A refusal that comes back from Send is matched
against the field labels and sends the reader to the step it is about.

## Branching, and the limits — `showing.py`

A `Web Form Field` has carried `depends_on`, `max_length` and `max_value` since
stage 1 and nothing has ever read any of them.

`depends_on` nominally holds a JavaScript expression and Frappe's own renderer
evals it, which is what §12 refused for `client_script`. So a condition here is
a **grammar this module parses** — `field == "value"`, `field != ""`,
`field > 3`, `field in "a, b"` — canonicalised on save, sent to the page as a
`{field, op, value}` tuple, and compared. An `eval:` is refused by name, so a
form imported from a Frappe site says so on the way in rather than quietly not
branching.

Enforced on both sides and for one reason: a browser that declined to draw a
field is a browser, and `send` is open to anybody with the route. `hides` clears
what the condition puts away and `within` refuses an answer past its limit —
`validate_submission` checks `reqd` a layer down for exactly the same reason.
The page also declines to *send* what it stopped asking, so an answer to a
question somebody changed their mind about is not filed.

## The file — `attaching.py`

Out of the payload before `accept` sees it, and written afterwards. Not caution:
`accept` writes the `File` as the current user, `File` grants create to `All`,
Guest is not in `All`, and a keyed applicant attaching a CV got *"User Guest
does not have doctype access via role permission for document File"* after their
submission had already saved. Frappe's own guest web form has the same hole.

Three rules, and the second is why the module is worth its own file: it attaches
only to the document `accept` returned, never a name from the payload; the size
cap is enforced here, on the base64 length before the decode and on the bytes
after, because until this nothing on the server looked at it at all; and the
file is private, because `accept` does not set that and a CV at a guessable URL
is a data leak.

## What came in — `counting.py`

1. `make` calls **`ensure`**, which adds `custom_web_form` to the doctype the
   form is over: a hidden, read-only, indexed `Data` column. Here rather than at
   install, because which doctypes a workspace makes forms over is not knowable
   until it does.
2. `send` calls **`stamp`** after `accept`, onto the document that came back.
   Not through `accept`: it only sets the fields the form carries, and a hidden
   column a stranger could put a value in would let somebody file a submission
   as another form's.
3. `forms` calls **`how_many`**, which is one indexed count per form.
4. **`where`** builds the way through — `/one/space/<space>?screen=<screen>&narrow=custom_web_form:<form>`.
   Not a responses table: `finding.placed` says which screen owns the doctype
   and `narrow` is how a URL asks one for a filter, so what came in is the list
   somebody already knows, with its views, its actions and its columns.

## The look — `theming.py`, `service.look`

Six settings — buttons, the page behind, the form itself, the writing, the
lettering, the corner, the width, the mark — compiled into `custom_css` between
two markers. Not a second mechanism: the public page learns nothing, the two
halves cannot disagree about precedence, and a customer who outgrows the panel
can read what it wrote in OneCode and take it over.

The block goes **first**, so a hand-written rule after it wins. `into` replaces
the block and keeps everything around it; `without` takes it out, which is what
the panel's Clear does. A missing close marker is tolerated — somebody editing
in OneCode may delete half of it, and the answer is to treat what is left as
theirs.

Every value is checked and the refusal names the setting: a colour is `#rgb` or
`#rrggbb`, a size is a number in a range, a mark is a file on this site, and a
font is one of five **system** stacks. That last one is not a limitation worked
around: `check_css` refuses `@import` and `url()` to another site, so a form a
stranger opens fetches nothing from anywhere.

The compiled block goes out through `check_css` like anything else that reaches
`custom_css`. A compiler with its own door would be a door.

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
