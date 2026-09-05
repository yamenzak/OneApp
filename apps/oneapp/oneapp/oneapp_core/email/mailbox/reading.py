"""The rail, the list of conversations, and one conversation."""

# `folder_ops`, not `folders`: this module has its own `folders()` — the rail
# endpoint — and importing the module under its own name binds the function over
# it. Python is happy, and the first call reaching for `folders.file` gets
# "'function' object has no attribute 'file'" at runtime.
from oneapp.oneapp_core.email import people
import frappe
import re
from oneapp.oneapp_core.email import folders as folder_ops
from oneapp.oneapp_core.email.folders import FOLDER_FIELD, QUIET
from oneapp.oneapp_core.email.threading import THREAD_FIELD
from .scope import ICONS, PAGE, SENT, SPLIT, _accounts, _held, normalise, strip_prefixes
from .flags import SEEN_KEY, SEEN_LIMIT, STARRED_KEY, _seen_set, _starred_set
from .query import _filters, _in_thread, _matching, _preview


@frappe.whitelist(methods=["GET"])
def folders() -> dict:
	"""What the rail shows.

	Every address held, and under an address that is a connected mailbox, the
	folders that mailbox actually has — Applicants, Suppliers, whatever somebody
	spent years sorting into. Read off the `IMAP Folder` rows, which
	`connect.refresh` fills from the server itself.

	`All` first where there is more than one address, because somebody with
	three of them mostly wants the union and only occasionally wants one — the
	same order Frappe's own inbox uses, and for the same reason. Deleted mail,
	spam and drafts come last and marked `quiet`: they are mirrored, because a
	mirror that silently omits folders is one nobody can trust, and they are not
	what a rail should open on.
	"""
	held = _accounts()
	rows = []
	if len(held) > 1:
		rows.append({
			"key": "all", "label": "All mail", "address": "", "folder": "",
			"icon": "lucide-inbox", "kind": "", "quiet": False, "depth": 0,
		})

	for address in sorted(held):
		info = held[address]
		rows.append({
			"key": address, "label": address, "address": address, "folder": "",
			"icon": "lucide-at-sign", "kind": "", "quiet": False, "depth": 0,
		})
		# Sent, and one of them per address rather than one for the workspace.
		#
		# An address has *one* outbox and two things end up in it: a reply
		# written here, and whatever the connected mailbox's own Sent folder
		# already held. Both are stored with `sent_or_received = "Sent"` and
		# this address as the sender, so one row covers both — which is why the
		# server's own Sent folder is skipped below, the same way INBOX is.
		# A separate top-level "Sent from here" read as a fourth mailbox
		# sitting beside somebody's real ones.
		rows.append({
			"key": f"{address}{SPLIT}{SENT}", "label": "Sent", "address": address,
			"folder": SENT, "icon": "lucide-send", "kind": "sent",
			"quiet": False, "depth": 1,
		})
		for name in info["folders"]:
			kind = info["kinds"].get(name, "")
			if kind in ("inbox", "sent"):
				# The address itself already *is* the inbox, and the row above
				# already is its Sent. A second of either would be the same
				# list twice under a different name.
				continue
			rows.append({
				"key": f"{address}{SPLIT}{name}",
				# The last segment, so `[Gmail]/Sent Mail` reads as `Sent Mail`
				# and `INBOX.Clients.Rua` as `Rua`. The full path is still the
				# key, so two folders with the same leaf are still two folders.
				"label": re.split(r"[/.]", name)[-1] or name,
				"address": address,
				"folder": name,
				"icon": ICONS.get(kind, "lucide-folder"),
				"kind": kind,
				"quiet": kind in QUIET,
				"depth": 1,
			})

	return {"folders": rows, "addresses": sorted(held)}


@frappe.whitelist(methods=["GET"])
def threads(folder: str = "all", start: int = 0, search: str = "") -> dict:
	"""One page of conversations, newest first.

	Grouped after the fetch rather than in SQL. Grouping in SQL would need the
	normalised subject as a column, which would need it written on every
	Communication, which would need a patch over every row that already exists —
	for an ordering that a page of fifty can do in memory in microseconds.
	"""
	held = _held()
	if not held:
		return {"threads": [], "more": False, "next": 0}

	filters, or_filters = _filters(folder)

	if search:
		filters["name"] = ("in", _matching(search))

	rows = frappe.get_all(
		"Communication",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "subject", "sender", "sender_full_name", "recipients",
			"communication_date", "sent_or_received", "seen", "reference_doctype",
			"reference_name", "content", THREAD_FIELD,
		],
		order_by="communication_date desc",
		start=int(start),
		limit_page_length=PAGE + 1,
	)

	more = len(rows) > PAGE
	rows = rows[:PAGE]

	seen = _seen_set()
	starred = _starred_set()
	# Senders resolved once for the page, not once per row: fifty lookups to
	# draw one list is how a list that was fast stops being one.
	who = people.profiles([(row.sender, row.sender_full_name) for row in rows])

	grouped: dict[str, dict] = {}
	for row in rows:
		# The column where there is one. The fallback is the old subject
		# grouping, and it is only reached by mail that arrived before the
		# column existed and before the patch that fills it has run.
		key = row.get(THREAD_FIELD) or normalise(row.subject)
		thread = grouped.setdefault(
			key,
			{
				"key": key,
				# The conversation's subject, not the newest message's. Rows
				# arrive newest first, so taking `row.subject` verbatim titles
				# every answered conversation "Re: …" — which is the reply's
				# subject line and not what the conversation is called.
				"subject": strip_prefixes(row.subject) or "(no subject)",
				"from": row.sender_full_name or row.sender,
				"sender": row.sender,
				"who": who.get((row.sender or "").lower(), {}),
				"at": row.communication_date,
				"count": 0,
				"unread": 0,
				"latest": row.name,
				"reference_doctype": row.reference_doctype,
				"reference_name": row.reference_name,
				"preview": _preview(row.content),
				"starred": False,
			},
		)
		thread["count"] += 1
		if row.name not in seen and row.sent_or_received == "Received":
			thread["unread"] += 1
		# A conversation is starred if any message in it is: somebody stars the
		# thread, and which message they were looking at when they did is not
		# something they should have to remember.
		if row.name in starred:
			thread["starred"] = True

	return {
		"threads": list(grouped.values()),
		"more": more,
		# Where the next page starts. Messages consumed, not conversations
		# returned: fifty messages can be twelve conversations, and paging by
		# what came back would re-read the same rows forever.
		"next": int(start) + len(rows),
	}


@frappe.whitelist(methods=["GET"])
def thread(key: str, folder: str = "all") -> list[dict]:
	"""Every message in one conversation, oldest first — the order it happened."""
	held = _held()
	if not held:
		return []

	filters, or_filters = _filters(folder)
	# Narrowed at the database and then checked exactly in Python. The LIKE is
	# the cheap half — it turns "every message I can read" into "the handful
	# whose subject contains this" — and it cannot be the whole answer, because
	# a subject containing another subject is not the same conversation.
	# The conversation column where the message has one, and the old subject
	# narrowing for anything that predates it. Both, because a thread can hold
	# messages from either side of the upgrade — the exact check below sorts
	# them out, as it always did.
	filters["name"] = ("in", _in_thread(key))
	rows = frappe.get_all(
		"Communication",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "subject", "sender", "sender_full_name", "recipients", "cc",
			"communication_date", "sent_or_received", "content",
			"reference_doctype", "reference_name",
			# Which mailbox it is in, so filing knows whose server to talk to —
			# a conversation can span two addresses and only one half of it is
			# any given server's to move.
			"email_account", FOLDER_FIELD, THREAD_FIELD,
		],
		order_by="communication_date asc",
		limit_page_length=200,
	)

	wanted = [
		row for row in rows
		if (row.get(THREAD_FIELD) or normalise(row.subject)) == key
	]
	who = people.profiles([(row.sender, row.sender_full_name) for row in wanted])
	held = _attachments([row.name for row in wanted])
	for row in wanted:
		row["who"] = who.get((row.sender or "").lower(), {})
		row["attachments"] = held.get(row.name, [])
	return wanted


def _attachments(messages: list[str]) -> dict:
	"""Every message's files, in one query.

	This was a query per message inside the loop — twenty messages in a
	conversation, twenty round trips for a list most of them do not have.

	`custom_kind` comes back because the reader opens an attachment in the
	Drive's own previewer (`components/drive/FilePreview.vue`), and that is the
	column it reads to decide between an `<img>`, the browser's PDF viewer, a
	`<video>` and a text fetch. A mail attachment *is* a Drive file — same row,
	same object, same permission — so it previews the same way rather than
	through a second viewer that would drift.
	"""
	if not messages:
		return {}

	rows = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Communication",
			"attached_to_name": ("in", messages),
		},
		fields=["name", "file_name", "file_size", "file_url", "custom_kind", "attached_to_name"],
	)

	held = {}
	for row in rows:
		held.setdefault(row.pop("attached_to_name"), []).append(row)
	return held


@frappe.whitelist(methods=["POST"])
def mark_read(names: str | list) -> dict:
	"""Remember that this person has read these.

	Bounded, and the bound is the interesting part: a list that grows forever
	becomes a default value megabytes long that every request loads. Oldest go
	first, and a message old enough to fall off is a message nobody is about to
	find unread and be surprised by.
	"""
	if isinstance(names, str):
		names = frappe.parse_json(names) if names.startswith("[") else [names]

	seen = list(_seen_set())
	seen.extend(one for one in names if one and one not in seen)
	if len(seen) > SEEN_LIMIT:
		seen = seen[-SEEN_LIMIT:]

	frappe.defaults.set_user_default(SEEN_KEY, ",".join(seen), frappe.session.user)
	return {"ok": True, "seen": len(seen)}


@frappe.whitelist(methods=["POST"])
def star(key: str, folder: str = "all", on: int = 1) -> dict:
	"""Flag a conversation, or take the flag off.

	Per person for the same reason unread is: two people on `sales@` star
	different things. Where there is a real mailbox behind it the IMAP
	`\\Flagged` flag goes on too, so the star is the same star in Outlook.
	"""
	names = [row["name"] for row in thread(key, folder)]
	if not names:
		return {"ok": True, "starred": 0}

	starred = _starred_set()
	starred = (starred | set(names)) if int(on) else (starred - set(names))
	if len(starred) > SEEN_LIMIT:
		starred = set(list(starred)[-SEEN_LIMIT:])

	frappe.defaults.set_user_default(
		STARRED_KEY, ",".join(sorted(starred)), frappe.session.user
	)
	folder_ops.flag(names, bool(int(on)))
	return {"ok": True, "starred": len(names)}


@frappe.whitelist(methods=["POST"])
def mark_unread(key: str, folder: str = "all") -> dict:
	"""Put a conversation back to unread.

	The other half of `mark_read`, and the reason both exist: opening a message
	to see whether it matters is not the same as dealing with it, and every
	mail client learned to let somebody undo the first.
	"""
	names = {row["name"] for row in thread(key, folder)}
	remaining = _seen_set() - names
	frappe.defaults.set_user_default(
		SEEN_KEY, ",".join(sorted(remaining)), frappe.session.user
	)
	return {"ok": True, "unread": len(names)}


@frappe.whitelist(methods=["GET"])
def unread() -> int:
	"""How many received messages this person has not opened. For the bell."""
	held = _held()
	if not held:
		return 0

	filters, or_filters = _filters("all")
	rows = frappe.get_all(
		"Communication",
		filters=filters,
		or_filters=or_filters,
		pluck="name",
		limit_page_length=500,
	)
	return len(set(rows) - _seen_set())
