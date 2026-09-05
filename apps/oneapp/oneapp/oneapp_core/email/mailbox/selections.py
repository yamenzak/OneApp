"""One action over a selection, in one request — and a way back from it.

Named for what it acts on rather than for the endpoint it exposes: the whitelisted
function is `bulk`, and a module of that name would be shadowed by it in the
package's own namespace — which is not cosmetic, it is what decides whether a
test can reach in and stub the layer below.

Everything below this file acts on a conversation: archive one, bin one, star
one. That is the right shape for the API and the wrong shape for the screen,
where somebody ticks eleven conversations and archives them. Doing that by
calling `archive` eleven times from the browser is eleven round trips, eleven
IMAP moves opened and closed, and eleven chances to end up half done with no
record of which half.

So this is a loop, but it is a loop on the server, and it keeps a note of where
everything was on the way past. That note is what `restore` reads: a selection
someone archived by mistake goes back to the folders it came from, one request,
without the browser having to remember anything but the note.

Undo is not optional here. Bulk actions are the ones people get wrong — a
mis-shift-click takes forty conversations rather than four — and "Archived 40"
with no way back is how somebody loses a morning.
"""

import frappe

from oneapp.oneapp_core.email.folders import FOLDER_FIELD

from .query import EVERYWHERE
from .filing import archive, bin, file_thread
from .reading import mark_read, mark_unread, star, thread

#: What a selection can be told to do. The value is only documentation — the
#: dispatch is below — but a caller sending anything else gets told so rather
#: than silently doing nothing to forty conversations.
ACTIONS = {
	"archive": "out of the inbox, still there",
	"bin": "into the mailbox's Trash",
	"read": "as read, for this person",
	"unread": "back to unread, for this person",
	"star": "starred, for this person",
	"unstar": "not starred",
}

#: The ones that move mail, and so the ones `restore` can undo. Read, unread and
#: starring are per-person flags a second press already reverses.
MOVES = ("archive", "bin")


def _keys(given) -> list:
	"""A list of thread keys, however the request spelled it."""
	if isinstance(given, str):
		given = frappe.parse_json(given) if given.startswith("[") else [given]
	return [one for one in given if one]


@frappe.whitelist(methods=["POST"])
def bulk(action: str, keys, address: str = "", folder: str = "all") -> dict:
	"""Do one thing to every conversation in a selection.

	Returns what it did and, for the two that move mail, where each conversation
	was — so the browser can offer Undo without asking again.

	One address for the whole selection, which is the one limit worth knowing:
	the folders being moved between belong to a mailbox, and `file_thread`
	already leaves alone any message that is not on the named account. So a
	selection spanning two addresses moves the half that is on this one. The
	screen picks the address of the folder somebody is looking at, which is that
	address in every case but a mixed selection in the "all" view.
	"""
	if action not in ACTIONS:
		frappe.throw(f"{action} is not something a selection can be told to do")

	chosen = _keys(keys)
	was = []
	done = 0

	for key in chosen:
		rows = thread(key, folder)
		if not rows:
			continue

		if action in MOVES:
			# Where it was, before it is somewhere else. The newest message's
			# folder: a conversation whose messages sit in two folders is rare
			# and putting it back in one place is better than leaving half of it
			# archived, which is what a per-message note would have to choose.
			was.append({"key": key, "folder": rows[-1].get(FOLDER_FIELD) or ""})
			(archive if action == "archive" else bin)(key, address, folder)
		elif action == "read":
			mark_read([row["name"] for row in rows])
		elif action == "unread":
			mark_unread(key, folder)
		else:
			star(key, folder, 1 if action == "star" else 0)

		done += 1

	return {"ok": True, "action": action, "done": done, "was": was}


@frappe.whitelist(methods=["POST"])
def restore(was, address: str, folder: str = "all") -> dict:
	"""Put a selection back where `bulk` found it.

	`was` is that call's own answer, handed back unread — which is the point:
	the browser is carrying a note, not a model of the mailbox.
	"""
	if isinstance(was, str):
		was = frappe.parse_json(was)

	back = 0
	for row in was or []:
		key, into = row.get("key"), row.get("folder")
		if not key or not into:
			# A conversation with no folder recorded came from a mailbox with no
			# folders — a routed address. There is nowhere to put it back to,
			# and saying so is better than inventing an INBOX it never had.
			continue
		# `EVERYWHERE`, not the folder somebody is looking at: the conversation
		# is in the archive now, and every inbox scope excludes the archive —
		# which is exactly how Undo came to put nothing back the first time.
		file_thread(key, address, into, EVERYWHERE)
		back += 1

	return {"ok": True, "restored": back}
