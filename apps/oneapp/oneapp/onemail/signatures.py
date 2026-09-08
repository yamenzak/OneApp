"""Whose signature goes on a message, which is not the question Frappe answers.

The framework signs a `Communication` in `before_save`: the *sender's* `User`
signature, and failing that whatever the site's default outgoing account signs
with. Both are right for a desk where a person sends as themselves and wrong
here, where an address is a mailbox several people share and the signature
belongs to the address. On a workspace whose notifications leave from `hello@`,
a reply written from `sales@` came out signed by `hello@` — and nobody could see
it happen, because it was appended after the message left the composer.

So the framework's rule is held off entirely and ours is applied where somebody
can see it: the composer puts the address's own signature in the message before
it is sent, above the quoted history, editable like the rest of it. A signature
you cannot see before you send is one you forget you have.
"""

import frappe


def hold_the_frameworks_signature(doc, method=None):
	"""Stop `set_signature_in_email_content` from signing this for us.

	Every email `Communication` on this site is ours — written in the composer,
	delivered by the Worker, or synced from a mailbox — and none of them wants
	the site's default outgoing signature appended on the way past. A message
	that arrived signed already keeps what it arrived with.
	"""
	if doc.communication_medium == "Email":
		doc.flags.skip_add_signature = True
