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


@frappe.whitelist(methods=["GET"])
def folders() -> dict:
	"""What the rail shows: every address held, and the two pseudo-folders.

	`All` first where there is more than one, because somebody with three
	addresses mostly wants the union and only occasionally wants one of them —
	the same order Frappe's own inbox uses, and for the same reason.
	"""
	held = _held()
	rows = []
	if len(held) > 1:
		rows.append({"key": "all", "label": "All mail", "address": "", "icon": "lucide-inbox"})
	for one in sorted(held):
		rows.append({"key": one, "label": one, "address": one, "icon": "lucide-at-sign"})
	rows.append({"key": "sent", "label": "Sent", "address": "", "icon": "lucide-send"})
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
		return {**base, "sent_or_received": "Sent", "sender": ("in", held)}, None

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
		],
		order_by="communication_date asc",
		limit_page_length=200,
	)

	wanted = [row for row in rows if normalise(row.subject) == key]
	for row in wanted:
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
         in_reply_to: str = "", cc: str = "") -> dict:
	"""Send, through the framework's queue like everything else.

	`sender` must be an address this person holds — checked here rather than
	trusted, because the alternative is a whitelisted endpoint that will send as
	anybody on the site for whoever asks.

	The rate limit, the suppression list and the suspension gate all apply: they
	are hooks on `Email Queue`, and this puts a row in `Email Queue`.
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
			**reference,
		}
	).insert(ignore_permissions=True)

	doc.send_email()
	return {"ok": True, "name": doc.name}
