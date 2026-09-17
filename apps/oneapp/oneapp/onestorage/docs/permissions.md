# Permissions

**OneCloud has no roles.** It is a service, so it is on for everybody with a
seat, and where it says no, that is the *record's* permission rather than a role
of ours — `docs/CLEANUP.md` §1.

## Which means Frappe's, and nothing beside it

A `File` row's own permissions decide who may read and write it, plus
`is_private`, plus `DocShare` for what has been shared with a person. There is
**no permission table of ours**, deliberately: two systems deciding one question
is two systems that will disagree, which is the same refusal `spaceview` and
`email/inbound` make.

An attachment inherits the argument from what it is attached to. A person who
cannot read a quotation does not see its drawings, and this module did not have
to know what a quotation is.

## The four places a check is actually written

**`linked.py`** — *nothing here takes a doctype, a filter or a fieldname from
the caller*. That is the module's doctrine, stated in its own docstring, and
`onecode/manifest.py` inherits it. A caller names a file; what may be done with
it is worked out from the file.

**`File Link`** is a capability, not an identity. A link carries a secret, a
`level` saying what it permits, an `expires_on` and a `revoked` flag, and
`open_link` checks all four. It outlives a session because a link in a mail has
to still work tomorrow — which is exactly why it must be revocable and is.

**`Drive Access`** is the WebDAV credential, and it stores a `secret_hash`
rather than a secret. It carries its own `scope`, `folder`, `read_only`,
`enabled` and `expires_on`, so a mount is narrower than the person who made it.

**`scopes.children`** is what a mount may walk, and it is the same resolver
`reading._records` uses for the Records tree. One resolver, so a mount and a
rail place cannot disagree about what a record has on it.

## A mount is read-only, and that is a permission

The Drive **reads** a remote host; it does not write to one. Browsed live and
never copied, so there is no sync to be wrong — and `copy_here` is the explicit
way across, which makes bringing something in a thing somebody did.

## The bin

Trashing sets `custom_trashed_on`; a sweep decides at thirty days. Anybody who
may write a file may bin it, and the thirty days is what makes that safe: the
alternative is Frappe's own delete, which takes the object with the row, and
whose only undo is a backup — which is not an undo, it is a support ticket.
