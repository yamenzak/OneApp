"""Which conversation a message belongs to.

The subject with its `Re:` and `Fwd:` stripped is what mail clients threaded on
for twenty years, and it is wrong in both directions: two people who each write
"Invoice" become one conversation, and a reply somebody renamed becomes a new
one. Neither is rare — "Invoice" is the commonest subject line there is, and
renaming a reply is what people do when a thread wanders.

The headers say it properly. `In-Reply-To` and `References` are what every
client has written since RFC 822, and Frappe already stores the first as
`Communication.in_reply_to` and the message's own id as `message_id`.

So: a message that answers another one takes that one's key, and a message that
answers nothing starts a key of its own. The chain holds however far the subject
drifts, and two strangers writing "Invoice" stay two conversations.

Written once, on insert, into a column — rather than walked at read time. A page
of fifty conversations would otherwise be fifty chains to climb, each one a
query, to draw a list.
"""

import frappe

THREAD_FIELD = "custom_thread"

# How far back a chain is followed before giving up. A loop cannot happen with
# honest data and can happen with a forged `In-Reply-To`, which is a header the
# sender controls.
DEPTH = 20


def key_for(doc) -> str:
	"""The conversation key for one message.

	The parent's, where it has a parent we know about. Its own normalised
	subject otherwise — which is the old behaviour, and is what a message that
	starts a conversation should get anyway.
	"""
	from oneapp.oneapp_core.email.mailbox import normalise

	parent = doc.get("in_reply_to")
	seen = set()
	while parent and parent not in seen and len(seen) < DEPTH:
		seen.add(parent)
		row = frappe.db.get_value(
			"Communication", parent, [THREAD_FIELD, "in_reply_to"], as_dict=True
		)
		if not row:
			break
		if row.get(THREAD_FIELD):
			return row[THREAD_FIELD]
		# A parent written before this field existed: keep climbing rather than
		# stopping, because its own parent may have one.
		parent = row.get("in_reply_to")

	return normalise(doc.get("subject"))


def on_insert(doc, method=None):
	"""Give every new message its conversation key.

	`before_insert` and not `after_insert`: the value belongs to the row being
	written, and a second write to set it would be a second version row on a
	doctype people already find noisy.
	"""
	if doc.get("communication_medium") != "Email":
		return
	if not doc.get(THREAD_FIELD):
		doc.set(THREAD_FIELD, key_for(doc))
