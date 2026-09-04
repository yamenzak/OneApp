"""Reading mail, which is a Communication list with the right questions asked.

The whole reason this is thin: mail in this product is already a document.
Inbound writes a `Communication`, Frappe's own IMAP sync writes a
`Communication`, and replying writes one too. So there is no mail store to
build — there is a list to filter and an ordering to get right.

What the framework does not answer, and this does:

* **Which addresses am I allowed to see?** `User Email` says, and it is the same
  answer the settings screen writes. A person sees the mail of the addresses
  they hold and nothing else, including where an administrator has forgotten to
  restrict something — the filter is on the query, not on the render.
* **Threads, not messages.** Mail arrives as messages and is read as
  conversations. Frappe's Communication has no thread key, so the subject with
  its `Re:` and `Fwd:` prefixes stripped is the grouping — which is what mail
  clients did for twenty years before message-id threading, and is right often
  enough that being cleverer would cost more than it returns.
* **Unread.** `Communication.seen` is Frappe's own flag and is per document
  rather than per person, which is wrong for a shared address and is the one
  place this cannot use what the framework has: two people on `sales@` each need
  their own idea of what they have read. `Document Follow` is not it either. So
  unread is a read receipt of our own: a bounded list of ids under that person's
  own user defaults. Not a doctype, because a table with a row per person per
  message would exist to answer a question only that person ever asks.
"""

import re

import frappe
from frappe import _
from frappe.utils import escape_html

# `folder_ops`, not `folders`: this module has its own `folders()` — the rail
# endpoint — and importing the module under its own name binds the function over
# it. Python is happy, and the first call reaching for `folders.file` gets
# "'function' object has no attribute 'file'" at runtime.
from oneapp.oneapp_core.email import people
from oneapp.oneapp_core.email import folders as folder_ops
from oneapp.oneapp_core.email.folders import FOLDER_FIELD, QUIET

# `Re:`, `Fwd:`, `FW:`, `RE :`, and the same again nested five deep, which is
# what a thread looks like after two people and a phone. Stripped repeatedly
# rather than once, because "Re: Fwd: Re: quote" is one conversation.
PREFIX = re.compile(r"^\s*(re|fw|fwd|aw|sv|vs|antw)\s*(\[\d+\])?\s*:\s*", re.I)

PAGE = 50


def _held() -> list[str]:
	"""The addresses this person may read, as email ids."""
	return frappe.get_all(
		"User Email",
		filters={"parent": frappe.session.user},
		pluck="email_id",
		distinct=True,
	)


def strip_prefixes(subject: str) -> str:
	"""The subject with its `Re:` and `Fwd:` taken off, case left alone."""
	subject = (subject or "").strip()
	while True:
		stripped = PREFIX.sub("", subject, count=1)
		if stripped == subject:
			return stripped.strip()
		subject = stripped


def normalise(subject: str) -> str:
	"""The same, lowercased — the key two messages are one conversation under."""
	return strip_prefixes(subject).lower() or "(no subject)"


def _like(text: str) -> str:
	"""Escape what LIKE treats as a wildcard.

	A subject of "50% off" is one conversation, not every conversation starting
	with "50". Backslash first, or the escapes escape each other.
	"""
	return (text or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# A folder key is an address, or an address and one of its folders. `::` because
# neither half can contain it: a local part may not, and IMAP folder names use
# `/` or `.` as their separator.
SPLIT = "::"

# The one folder name that is not a folder on anybody's server. Prefixed so it
# cannot collide with a real one: IMAP names are ordinary text and somebody may
# genuinely have a folder called `Sent`, which is exactly the one this replaces.
SENT = "__sent"

# What each kind of folder is drawn as. Named rather than guessed from the
# folder's own name, because "Gesendet" and "Sent Items" are the same thing and
# the server already told us which — see `folders.classify`.
ICONS = {
	"inbox": "lucide-inbox",
	"sent": "lucide-send",
	"drafts": "lucide-file-pen",
	"trash": "lucide-trash-2",
	"junk": "lucide-shield-alert",
	"archive": "lucide-archive",
	"all": "lucide-layers",
	"flagged": "lucide-flag",
}


def _accounts() -> dict:
	"""Every address held, with the account behind it and that account's folders.

	One query for the grants and one for the accounts, rather than a document
	load each: this runs on every page of the rail and on the bell's poll.
	"""
	rows = frappe.get_all(
		"User Email",
		filters={"parent": frappe.session.user},
		fields=["email_id", "email_account"],
		distinct=True,
	)
	names = sorted({row.email_account for row in rows if row.email_account})
	if not names:
		return {row.email_id: {"account": "", "folders": [], "kinds": {}} for row in rows}

	kinds = {
		row.name: frappe.parse_json(row.custom_folder_kinds or "{}")
		for row in frappe.get_all(
			"Email Account",
			filters={"name": ("in", names)},
			fields=["name", "custom_folder_kinds"],
		)
	}
	listing: dict[str, list[str]] = {}
	for row in frappe.get_all(
		"IMAP Folder",
		filters={"parent": ("in", names)},
		fields=["parent", "folder_name"],
		order_by="idx asc",
	):
		listing.setdefault(row.parent, []).append(row.folder_name)

	return {
		row.email_id: {
			"account": row.email_account,
			"folders": listing.get(row.email_account, []),
			"kinds": kinds.get(row.email_account, {}),
		}
		for row in rows
	}


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


def _filters(folder: str) -> tuple[dict, list | None]:
	"""The pair of filters that scopes a query to what this person may read.

	Returned together, and that is the whole point of the shape. `recipients` on
	Communication is a comma-joined string, so the union of two addresses is a
	LIKE each and therefore an `or_filters` — and a caller that took the `filters`
	half and forgot the other would ask for "every received email", which the
	database would cheerfully answer with the whole site's mail. One function,
	one return value, impossible to use half of.
	"""
	held = _held()
	if not held:
		# Not an empty filter — an impossible one. A person who holds no
		# address sees no mail, and a missing filter here would show them
		# every Communication on the site.
		return {"name": ("=", "")}, None

	base = {"communication_type": "Communication", "communication_medium": "Email"}

	if folder == "sent":
		# Everything this person has sent, from any of their addresses. No
		# longer in the rail — Sent belongs to an address, not to the
		# workspace — but kept, because it is one honest query and a link
		# somebody saved should not stop working.
		return {**base, "sent_or_received": "Sent", "sender": ("in", held)}, None

	address, _, name = folder.partition(SPLIT) if folder else ("", "", "")

	if name:
		# One folder of one mailbox. Scoped by the address *as well as* the
		# folder name, because folder names are not unique across mailboxes —
		# two people on this site can both have an `Applicants`, and a filter on
		# the name alone would hand one of them the other's.
		if address not in held:
			frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)

		if name == SENT:
			# One address's outbox, whether the message was written here or
			# came out of that mailbox's own Sent folder. The sender is what
			# they have in common; the folder is not.
			return {**base, "sent_or_received": "Sent", "sender": address}, None

		# Scoped by the *address*, not by the Email Account behind it.
		#
		# `email_account` is only set on mail that came through an account —
		# Frappe's IMAP sync sets it, and the Worker that delivers our own
		# routed mail does not, because there is no account to name. Scoping on
		# it therefore did the wrong thing in the one case the whole product is
		# built around: a message on `sales@acme.4dl.app` could be filed into a
		# folder and then was in no folder anybody could open. Address it is,
		# which is what identifies a mailbox anyway.
		return (
			{**base, FOLDER_FIELD: name},
			[
				["recipients", "like", f"%{_like(address)}%"],
				# A folder can hold both halves of a correspondence. `sender`
				# catches the sent ones, which is what an Archive is full of.
				["sender", "=", address],
			],
		)

	base["sent_or_received"] = "Received"
	if folder and folder != "all":
		if folder not in held:
			frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)
		base["recipients"] = ("like", f"%{_like(folder)}%")
		return base, None

	if len(held) == 1:
		base["recipients"] = ("like", f"%{_like(held[0])}%")
		return base, None

	return base, [["recipients", "like", f"%{_like(one)}%"] for one in held]


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
		return {"threads": [], "more": False}

	filters, or_filters = _filters(folder)

	if search:
		filters["subject"] = ("like", f"%{_like(search)}%")

	rows = frappe.get_all(
		"Communication",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "subject", "sender", "sender_full_name", "recipients",
			"communication_date", "sent_or_received", "seen", "reference_doctype",
			"reference_name", "content",
		],
		order_by="communication_date desc",
		start=int(start),
		limit_page_length=PAGE + 1,
	)

	more = len(rows) > PAGE
	rows = rows[:PAGE]

	seen = _seen_set()
	# Senders resolved once for the page, not once per row: fifty lookups to
	# draw one list is how a list that was fast stops being one.
	who = people.profiles([(row.sender, row.sender_full_name) for row in rows])

	grouped: dict[str, dict] = {}
	for row in rows:
		key = normalise(row.subject)
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
			},
		)
		thread["count"] += 1
		if row.name not in seen and row.sent_or_received == "Received":
			thread["unread"] += 1

	return {"threads": list(grouped.values()), "more": more}


def _preview(html: str) -> str:
	"""The first line, with the markup taken out.

	Deliberately crude — a regex, not a parser. This is one line under a subject
	in a list; a message whose preview is slightly wrong costs nothing, and a
	dependency that turns every list into an HTML parse costs the list.
	"""
	text = re.sub(r"<[^>]+>", " ", html or "")
	text = re.sub(r"\s+", " ", text).strip()
	return text[:160]


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
	filters["subject"] = ("like", f"%{_like(key)}%")
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
			"email_account", FOLDER_FIELD,
		],
		order_by="communication_date asc",
		limit_page_length=200,
	)

	wanted = [row for row in rows if normalise(row.subject) == key]
	who = people.profiles([(row.sender, row.sender_full_name) for row in wanted])
	for row in wanted:
		row["who"] = who.get((row.sender or "").lower(), {})
		row["attachments"] = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Communication", "attached_to_name": row.name},
			fields=["name", "file_name", "file_size", "file_url"],
		)
	return wanted


# --------------------------------------------------------------------------- #
# Read receipts
# --------------------------------------------------------------------------- #
#
# Per person, because a shared address is read by several and `Communication.seen`
# is one flag for the document. Kept as a user setting rather than a doctype: it
# is a list of ids nobody queries across users, and a doctype would be a table
# with a row per person per message for a question only that person ever asks.

SEEN_KEY = "oneapp_mail_seen"

# Two thousand ids is roughly 36 KB, and it is loaded with the person's other
# user defaults on every request they make. That is the whole reason there is a
# number here: the list is a session cost, not a table, so it has to stay the
# size of something you would happily put in a cookie.
SEEN_LIMIT = 2000


def _seen_set() -> set:
	# `frappe.defaults`, not `frappe.db.get_default`. The latter reads the
	# *global* defaults, which every session on the site loads in full — one
	# person's read receipts would be paid for by everybody. Under the user it
	# is loaded with that user's own defaults and nobody else's.
	raw = frappe.defaults.get_user_default(SEEN_KEY, frappe.session.user) or ""
	return set(filter(None, raw.split(",")))


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


# --------------------------------------------------------------------------- #
# Replying
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def send(to: str, subject: str, content: str, sender: str = "",
         in_reply_to: str = "", cc: str = "", bcc: str = "",
         attachments: str | list = "") -> dict:
	"""Send, through the framework's queue like everything else.

	`sender` must be an address this person holds — checked here rather than
	trusted, because the alternative is a whitelisted endpoint that will send as
	anybody on the site for whoever asks.

	The rate limit, the suppression list and the suspension gate all apply: they
	are hooks on `Email Queue`, and this puts a row in `Email Queue`.

	`attachments` are File names already on the site — uploaded by the composer,
	or carried over from the message being forwarded. Names rather than content:
	the file is in R2 already and sending a copy of the bytes through this
	endpoint would be a second upload of something we are holding.
	"""
	held = _held()
	if not held:
		frappe.throw(_("You have no address to send from."), frappe.PermissionError)

	sender = (sender or held[0]).lower()
	if sender not in held:
		frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)

	reference = {}
	if in_reply_to and frappe.db.exists("Communication", in_reply_to):
		parent = frappe.get_doc("Communication", in_reply_to)
		reference = {
			"reference_doctype": parent.reference_doctype,
			"reference_name": parent.reference_name,
		}

	doc = frappe.get_doc(
		{
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Email",
			"sent_or_received": "Sent",
			"subject": subject or "(no subject)",
			"content": content,
			"sender": sender,
			"recipients": to,
			"cc": cc,
			"bcc": bcc,
			**reference,
		}
	).insert(ignore_permissions=True)

	# Attached before the send, because `send_email` reads the File rows off the
	# document to build the message — see `Communication.mail_attachments`.
	# Attaching afterwards produces a sent message with nothing on it and an
	# attachment nobody receives.
	names = _names(attachments)
	if names:
		_carry(doc.name, names)

	doc.send_email()
	return {"ok": True, "name": doc.name, "attached": len(names)}


def _names(value) -> list[str]:
	"""A list of File names out of whatever the request sent."""
	if isinstance(value, str):
		value = frappe.parse_json(value) if value.startswith("[") else ([value] if value else [])
	return [one for one in (value or []) if one]


def _carry(onto: str, files: list[str]):
	"""Attach existing Files to a Communication, by reference.

	A new `File` row pointing at the same `file_url`, which is what Frappe's own
	`add_attachments` does: the bytes stay where they are in R2 and a forward of
	a 40 MB drawing set copies a row rather than the drawings.

	Only files this person can already reach. The names come from the browser,
	so without this the endpoint would attach any file on the site to a message
	going anywhere.
	"""
	for name in files:
		if not frappe.has_permission("File", "read", doc=name):
			frappe.throw(_("That attachment is not yours to send."), frappe.PermissionError)

		source = frappe.get_doc("File", name)
		frappe.get_doc(
			{
				"doctype": "File",
				"file_url": source.file_url,
				"file_name": source.file_name,
				"is_private": source.is_private,
				"attached_to_doctype": "Communication",
				"attached_to_name": onto,
				"folder": "Home/Attachments",
			}
		).insert(ignore_permissions=True)


# --------------------------------------------------------------------------- #
# Making and using folders
# --------------------------------------------------------------------------- #
#
# The whitelisted half. `folders.py` does the IMAP; this decides whose mailbox
# is being changed, which is the part that has to be right.


def _account_of(address: str):
	"""The Email Account behind an address this person holds, or a refusal."""
	address = (address or "").strip().lower()
	if address not in _held():
		frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)

	name = frappe.db.get_value(
		"User Email", {"parent": frappe.session.user, "email_id": address}, "email_account"
	)
	if not name:
		frappe.throw(_("That address has no mailbox behind it."))
	return frappe.get_doc("Email Account", name)


@frappe.whitelist(methods=["POST"])
def add_folder(address: str, name: str) -> dict:
	"""Make a folder on one of this person's addresses.

	On a connected mailbox it is made on the server, so it turns up in Outlook.
	On an address we route there is no server to make it on and the folder is
	ours — which is not a lesser folder, because there is no other client
	showing that address to disagree with.
	"""
	account = _account_of(address)
	return folder_ops.create(account, name)


@frappe.whitelist(methods=["POST"])
def drop_folder(address: str, name: str) -> dict:
	"""Take a folder away and keep what was in it.

	Deleting a folder on an IMAP server deletes the mail in it, which is not
	what anybody means by removing a folder — so its messages go back to the
	inbox first and what is deleted is empty.
	"""
	account = _account_of(address)
	return folder_ops.remove(account, name)


@frappe.whitelist(methods=["POST"])
def file_thread(key: str, address: str, folder: str, from_folder: str = "all") -> dict:
	"""File a whole conversation.

	The conversation and not the message, because that is the unit somebody is
	looking at: filing the reply and leaving the original in the inbox is the
	behaviour every mail client got complained about until it stopped.

	Which messages those are is `thread()`'s answer, so a person can only file
	mail they can already read.
	"""
	account = _account_of(address)
	filed = []
	for row in thread(key, from_folder):
		if row.get("email_account") and row["email_account"] != account.name:
			# A conversation can span two addresses. Only the half that belongs
			# to this mailbox moves; the other half is not this server's to file.
			continue
		folder_ops.file(account, row["name"], folder)
		filed.append(row["name"])
	return {"ok": True, "filed": len(filed), "folder": folder}


# --------------------------------------------------------------------------- #
# Answering and passing on
# --------------------------------------------------------------------------- #
#
# Both are the same shape — a new message carrying an old one — and both are
# built on the server rather than in the browser, for one reason: the quoted
# body is the *stored* HTML, and the stored HTML is what Frappe sanitised on
# the way in. Quoting from what the reader is looking at would quote the copy
# with its images held back, and send somebody a reply full of empty `<img>`.


@frappe.whitelist(methods=["GET"])
def draft(message: str, kind: str = "reply") -> dict:
	"""What the composer opens with, for a reply, a reply-all or a forward.

	Built here and not in the browser so the three differ in one place. They are
	nearly the same message: the difference is who it goes to and whether the
	attachments come along.
	"""
	if kind not in ("reply", "reply_all", "forward"):
		frappe.throw(_("Not something a message can be turned into."))

	held = _held()
	original = frappe.get_doc("Communication", message)

	# The same gate every list goes through. A draft is a way of reading a
	# message, so it has to be one this person could already read.
	mine = [one for one in held if one in (original.recipients or "")
	        or one == (original.sender or "").lower()]
	if not mine:
		frappe.throw(_("That is not your message."), frappe.PermissionError)

	subject = strip_prefixes(original.subject)
	prefix = "Fwd: " if kind == "forward" else "Re: "

	if kind == "forward":
		to, cc = "", ""
	else:
		# Reply goes to whoever wrote it. Reply-all adds everyone else who was
		# on it, minus this person's own addresses — answering yourself is the
		# oldest bug in mail.
		to = original.sender
		cc = ""
		if kind == "reply_all":
			others = _addresses(original.recipients) + _addresses(original.cc)
			cc = ", ".join(
				one for one in dict.fromkeys(others)
				if one.lower() not in held and one.lower() != (original.sender or "").lower()
			)

	return {
		"to": to,
		"cc": cc,
		"subject": f"{prefix}{subject}" if subject else prefix.strip(),
		"content": _quote(original),
		# A forward carries the attachments — a forwarded invoice without the
		# invoice is the reason people go back to Outlook. A reply does not:
		# the person being replied to sent them.
		"attachments": (
			[
				{"name": row.name, "file_name": row.file_name, "file_size": row.file_size}
				for row in frappe.get_all(
					"File",
					filters={"attached_to_doctype": "Communication",
					         "attached_to_name": original.name},
					fields=["name", "file_name", "file_size"],
				)
			]
			if kind == "forward" else []
		),
		"in_reply_to": original.name,
		# The address it arrived at is the one to answer from. Replying to mail
		# that reached `sales@` from a personal address is how a customer finds
		# out a shared mailbox is not shared.
		"sender": mine[0],
	}


def _addresses(value: str) -> list[str]:
	"""The addresses out of a header, dropping the display names.

	`"Hala Nasser" <hala@x.test>, ap@y.test` is two addresses, and the quoted
	comma inside the first is why this is not `value.split(",")`.
	"""
	found = re.findall(r"<([^>]+)>|([^\s,;<>\"]+@[^\s,;<>\"]+)", value or "")
	return [(angled or bare).strip() for angled, bare in found if (angled or bare).strip()]


def _quote(original) -> str:
	"""The original, under an attribution line, the way every client does it.

	A blockquote and not a `>` prefix: the body is HTML, and prefixing lines of
	HTML with a character produces neither quoted text nor valid markup.
	"""
	when = original.communication_date or ""
	who = escape_html(original.sender_full_name or original.sender or "")
	return (
		"<p><br></p>"
		f"<p>On {escape_html(str(when))}, {who} wrote:</p>"
		'<blockquote style="margin:0 0 0 .8ex;border-left:2px solid #ccc;padding-left:1ex">'
		f"{original.content or ''}"
		"</blockquote>"
	)
