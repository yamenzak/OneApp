"""Turning a folder and a search term into a query over `Communication`."""

import frappe
import re
from oneapp.oneapp_core.email.folders import FOLDER_FIELD, QUIET
from oneapp.oneapp_core.email.threading import THREAD_FIELD
from .scope import SENT, SPLIT, _accounts, _held, _like


# What "put away" means, and therefore what an inbox is not: the three quiet
# folders plus the archive.
#
# Archiving used to be a button that did nothing anybody could see. The inbox
# view is every *received* message on an address, and it did not care what
# folder the message was in — so "Archived" filed the conversation and left it
# exactly where it was in the list, and so did "Moved to Trash". Which is worse
# than not offering the action: the mail is gone from where somebody would look
# for it and still in front of them.
PUT_AWAY = QUIET | {"archive"}

# The scope that means "every message in this conversation I am allowed to
# read, wherever it is". Not a folder somebody can open — a word `file_thread`
# passes when it is *moving* mail rather than listing it.
#
# Undo is what needed it. `restore` puts an archived conversation back, and to
# move a conversation it first has to find it: through the inbox scope, which
# now excludes the archive, it found nothing and put nothing back.
EVERYWHERE = "everywhere"


def _put_away() -> list[str]:
	"""The folder names that mean "not in the inbox", across every address held.

	Names, not kinds, because that is what is on the message: `classify` read
	the kind off the server's SPECIAL-USE flags, so one person's archive is
	`Archive` and another's is `[Gmail]/All Mail`. Both are excluded here and
	both are one click away in the rail.
	"""
	names = set()
	for held in _accounts().values():
		for name, kind in (held.get("kinds") or {}).items():
			if kind in PUT_AWAY:
				names.add(name)
	return sorted(names)


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

	# Everything below this line is an inbox — one address's, or all of them —
	# so everything put away is out of it. `not in` is safe over a message with
	# no folder at all, which is what routed mail arrives as: Frappe writes the
	# condition as `IFNULL(folder, '') NOT IN (…)`.
	away = [] if folder == EVERYWHERE else _put_away()
	if away:
		base[FOLDER_FIELD] = ("not in", away)

	if folder and folder not in ("all", EVERYWHERE):
		if folder not in held:
			frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)
		base["recipients"] = ("like", f"%{_like(folder)}%")
		return base, None

	if len(held) == 1:
		base["recipients"] = ("like", f"%{_like(held[0])}%")
		return base, None

	return base, [["recipients", "like", f"%{_like(one)}%"] for one in held]


# How many messages a search may consider. The subject-or-body query answers
# names only and the real query then applies this person's own filter to them,
# so this is a cost bound and not a permission one — but it is a bound: a search
# for "the" on a busy site should not build a list of every message ever.
SEARCH_CEILING = 2000


# The words that mean something other than themselves in a search box.
#
# Gmail's, because Frappe Mail does not have them and every person who has used
# mail has used these: `from:hala has:attachment` is what somebody types when
# they are looking for the drawing Hala sent. Anything not recognised is left in
# the free text, so a search for "note: revised" still searches for those words.
OPERATORS = ("from", "to", "subject", "has", "is")

TOKEN = re.compile(
	r"\b(?P<key>" + "|".join(OPERATORS) + r"):(?P<value>\"[^\"]*\"|\S+)", re.IGNORECASE
)


def parse(search: str) -> dict:
	"""A search box's contents, split into what it asks for.

	Returns the free text under `words` and each operator under its own name;
	`has` and `is` collect, because "is:unread is:starred" is two questions.
	"""
	asked = {"words": "", "from": "", "to": "", "subject": "", "has": set(), "is": set()}

	def take(match):
		key = match.group("key").lower()
		value = match.group("value").strip('"')
		if key in ("has", "is"):
			asked[key].add(value.lower())
		else:
			# The last one wins, which is what somebody correcting a typed
			# search expects — they retype the operator rather than delete it.
			asked[key] = value
		return " "

	asked["words"] = TOKEN.sub(take, search or "").strip()
	return asked


def _matching(text: str) -> list[str]:
	"""The names of messages whose subject *or* body matches.

	Two OR groups cannot go in one `get_all`: the address scope is already an
	`or_filters`, and a second one would replace it rather than be added to it —
	which is the kind of mistake that turns a search into "everybody's mail".
	So the search runs first and answers names, and the real query filters those
	names by who is allowed to see them. Nothing leaks, because nothing but ids
	comes out of here and the gate is downstream.
	"""
	like = f"%{_like(text)}%"
	found = frappe.get_all(
		"Communication",
		filters={"communication_type": "Communication", "communication_medium": "Email"},
		or_filters=[["subject", "like", like], ["content", "like", like]],
		pluck="name",
		order_by="communication_date desc",
		limit_page_length=SEARCH_CEILING,
	)
	# Never empty: an `in` on an empty list matches nothing in some engines and
	# everything in others, and this one stands in front of the whole site.
	return found or [""]


#: What a message has to be, to be a message at all. Every names-only query
#: below starts here.
EMAIL = {"communication_type": "Communication", "communication_medium": "Email"}


def _ids(**filters) -> list[str]:
	"""Names of messages matching one narrow question, unscoped.

	`_ids` and not `_names`, which is what it was called for ten minutes:
	`sending._names` already exists and the package re-exports both, so the
	second one silently won and a guard that reads the source of "the unscoped
	queries" was reading the wrong function's.

	Unscoped for the same reason `_matching` is, and safe for the same reason:
	nothing but ids comes out, and the caller intersects them into a query that
	*is* scoped. See `_matching`.
	"""
	return frappe.get_all(
		"Communication",
		filters={**EMAIL, **filters},
		pluck="name",
		order_by="communication_date desc",
		limit_page_length=SEARCH_CEILING,
	)


def _with_attachments() -> list[str]:
	"""Messages that carry a file. `has:attachment`, which is how somebody
	looks for the drawing rather than for the sentence about the drawing."""
	return frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Communication", "attached_to_name": ("!=", "")},
		pluck="attached_to_name",
		limit_page_length=SEARCH_CEILING,
	)


def narrow(search: str, filters: dict) -> dict:
	"""Fold a search — words and operators — into a query's filters.

	One mutation, always `name`, and that is deliberate: the address scope owns
	`recipients` and `or_filters`, so an operator writing either of those
	directly would replace the gate rather than narrow it. Everything here
	answers with ids instead, and ids are intersected.

	`is:unread` is the one that cannot be a set of its own — it is a complement,
	and materialising "every message except the ones read" is the whole mailbox.
	So it subtracts where there is something to subtract from, and becomes a
	`not in` where it is the only thing asked.
	"""
	from .flags import _seen_set, _starred_set

	asked = parse(search)
	wanted = None

	def keep(names):
		nonlocal wanted
		found = set(names or [])
		wanted = found if wanted is None else (wanted & found)

	if asked["words"]:
		keep(_matching(asked["words"]))
	if asked["from"]:
		keep(_ids(sender=("like", f"%{_like(asked['from'])}%")))
	if asked["to"]:
		keep(_ids(recipients=("like", f"%{_like(asked['to'])}%")))
	if asked["subject"]:
		keep(_ids(subject=("like", f"%{_like(asked['subject'])}%")))
	if "attachment" in asked["has"]:
		keep(_with_attachments())
	if "starred" in asked["is"]:
		keep(_starred_set())

	unread = "unread" in asked["is"]
	if unread and wanted is None:
		# Nothing else was asked, so this is the whole inbox minus what has been
		# read. Bounded: the read receipt list is capped at `SEEN_LIMIT`.
		filters["name"] = ("not in", list(_seen_set()) or [""])
		filters["sent_or_received"] = "Received"
		return filters

	if unread:
		wanted = wanted - _seen_set()
		filters["sent_or_received"] = "Received"

	if wanted is not None:
		# Never empty: an `in` on an empty list matches nothing in some engines
		# and everything in others, and this one stands in front of the whole
		# site.
		filters["name"] = ("in", sorted(wanted) or [""])

	return filters


def _in_thread(key: str) -> list[str]:
	"""Names of messages that could belong to one conversation.

	Names only and unscoped, for the same reason `_matching` is: two OR groups
	cannot go in one `get_all`, and the address scope already owns the one this
	query would need. The gate is the caller's, which applies it to these names
	— so nothing but ids comes out of here.
	"""
	like = f"%{_like(key)}%"
	found = frappe.get_all(
		"Communication",
		filters={"communication_type": "Communication", "communication_medium": "Email"},
		or_filters=[[THREAD_FIELD, "=", key], ["subject", "like", like]],
		pluck="name",
		limit_page_length=SEARCH_CEILING,
	)
	return found or [""]


def _preview(html: str) -> str:
	"""The first line, with the markup taken out.

	Deliberately crude — a regex, not a parser. This is one line under a subject
	in a list; a message whose preview is slightly wrong costs nothing, and a
	dependency that turns every list into an HTML parse costs the list.
	"""
	text = re.sub(r"<[^>]+>", " ", html or "")
	text = re.sub(r"\s+", " ", text).strip()
	return text[:160]
