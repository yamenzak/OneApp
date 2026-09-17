# Permissions

**OneLegal has no roles**, and the two doctypes it owns are deliberately
asymmetric: one is readable by everybody, the other is evidence.

## Reading a document

**Open to anybody signed in.** `reading.catalogue`, `reading.document` and
`reading.history` are whitelisted and check nothing beyond a session, which
follows directly from what a gate is for: a person being asked to agree to
something has to be able to read it first, and refusing to show it until they
have agreed would be a contract nobody could read before signing.

`history(key, version)` is open for the same reason one step later — somebody
who agreed in March has to be able to read what they agreed to, not what it
says now.

## Accepting

`gate.accept` writes a `Legal Acceptance` **for the caller**. A person cannot
accept on somebody else's behalf, and there is no endpoint that takes a user.

The one exception is structural rather than a permission: a workspace-audience
document is accepted by whoever created the workspace, and that acceptance
binds everybody in it. That is not one person acting for another — it is the
organisation being the party, which is why `party` is a field on the row.

**A person-audience document cannot be accepted by the organisation.** Privacy
and Cookies describe the handling of *their* personal data and an employer
cannot agree to that for them. The audience on the document is what enforces
it, in `gate.py`, and it is the one rule in this module worth reading the code
for.

## Who may not

**Nobody edits a `Legal Document Version`.** It is written once, when a version
is first needed, and frozen. An editable record of what somebody agreed to is
not a record of what somebody agreed to.

**Nobody deletes a `Legal Acceptance`.** For the same reason, and because the
address and the agent on it are what make it evidence rather than a claim.

## What the guards check

`tests/test_legal.py` carries the hash of every document's assembled text and
fails when the text has moved without `revision` being bumped. That is not a
permission, but it is the check that stops the permission model being
circumvented by editing a document under people who already agreed to it.
