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
