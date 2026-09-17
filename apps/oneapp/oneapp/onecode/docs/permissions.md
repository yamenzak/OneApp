# Permissions

**OneCode has no roles.** It is a service, and `docs/CLEANUP.md` §1 says a
service has none: it is on for everybody with a seat, and where it has to say
no, that is the *record's* permission rather than a role of ours.

So the answer to "who may open this file" is OneCloud's answer, which is
Frappe's: the `File` row's own permissions, plus `Drive Access` for what has
been shared, plus `File.is_private`. A person who may read a file may open it
here; a person who may write it may save it. There is no second check and
there should not be, because a second check is a place for the two to disagree.

## What the guards actually check

Nothing in this module reads a role. Three things it does check, and each is
about what a *declaration* may claim rather than about who is asking:

**`routes.validate`** refuses the platform's own prefixes. A project claiming
`/app` or `/api` would shadow the desk or the REST layer for that workspace.

**`routes.check`** refuses a route that nests with one already taken, compared
by segment. Checked when the manifest is saved rather than when the page is
requested — the alternative discovers the collision on a page a customer has
already linked to.

**`manifest.validate`** refuses a key outside `KEYS`, and `manifest.context`
takes nothing from the request. This is the security story in one line: a
declaration is a list the server checks against; a script is a list the server
runs. `onestorage/linked.py` states the same doctrine one layer in — *nothing
here takes a doctype, a filter or a fieldname from the caller*.

## The one thing a tenant may never have

`context_script`. Frappe's `Web Page` carries it and it is exactly what a
tenant application wants. A tenant who can write server Python on their own
site can write it on ours. The cost of refusing is real and is accepted: a new
capability is a new key in `manifest.KEYS` rather than three lines a customer
writes.
