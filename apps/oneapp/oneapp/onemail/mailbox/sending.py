"""Sending a message, and the window in which that can be taken back."""

import frappe
from frappe import _
from frappe.utils import add_to_date, escape_html, now_datetime
from .scope import _held


#: This person's own choice of which address to send from, when nothing about
#: the message decides it. A user default, like the notification mutes: one
#: string per person, and no doctype worth making for it.
DEFAULT_KEY = "onespace_default_sender"


@frappe.whitelist(methods=["GET"])
def sending_from(in_reply_to: str = "", doctype: str = "", name: str = "") -> dict:
	"""Which address a message would go out as, and what else it could be.

	The composer reads this rather than picking the first row it was handed.
	`held[0]` is whatever `User Email` came back first — so a member with a
	company address and a `4dl.app` one sent from whichever the database
	happened to order first, which is the one thing about this that customers
	would notice and not forgive.
	"""
	held = _held()
	return {
		"sender": default_sender(in_reply_to, doctype, name, held),
		"addresses": held,
		"default": frappe.defaults.get_user_default(DEFAULT_KEY) or "",
	}


@frappe.whitelist(methods=["POST"])
def set_default_sender(address: str) -> dict:
	"""Choose which of your addresses is the one you write from."""
	address = (address or "").strip().lower()
	if address and address not in _held():
		frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)

	frappe.defaults.set_user_default(DEFAULT_KEY, address, frappe.session.user)
	frappe.db.commit()
	return {"ok": True, "default": address}


def default_sender(in_reply_to: str = "", doctype: str = "", name: str = "",
                   held: list[str] | None = None) -> str:
	"""The address to send from, in order of what the message itself says.

	Four rules, most specific first, and each one is a thing somebody would
	otherwise have to remember:

	  1. **A reply goes out as the address it arrived at.** Answering a message
	     to `sales@` from your own address is the mistake this whole ordering
	     exists to prevent — the customer sees a stranger.
	  2. **A record answers as whatever last spoke for it.** The correspondence
	     on a quotation is a conversation, and the second message in it should
	     come from the same place as the first.
	  3. **Otherwise this person's chosen default**, which is the Mailbox tab.
	  4. **Otherwise the one they have** — and if they have several and have
	     chosen none, their own address on our domain before a shared one,
	     because a shared address is a team's and signing as it by accident is
	     the same mistake as rule 1 the other way round.
	"""
	held = _held() if held is None else held
	if not held:
		return ""

	if in_reply_to:
		if landed := _landed_on(in_reply_to, held):
			return landed

	if doctype and name:
		if before := _last_on_record(doctype, name, held):
			return before

	# The person's own, not the site's: `frappe.db.get_default` reads the
	# global row, which every session on the site loads whole.
	chosen = (frappe.defaults.get_user_default(DEFAULT_KEY) or "").lower()
	if chosen in held:
		return chosen

	from oneapp.onemail.addresses import is_ours

	personal = [one for one in held if is_ours(one)]
	return (personal or held)[0]


def _landed_on(message: str, held: list[str]) -> str:
	"""The address of ours a message came to, if it is one this person holds."""
	if not frappe.db.exists("Communication", message):
		return ""
	row = frappe.db.get_value(
		"Communication", message, ["recipients", "cc", "sender"], as_dict=True)
	if not row:
		return ""

	where = f"{row.recipients or ''},{row.cc or ''}".lower()
	for one in held:
		if one in where:
			return one
	# A message this person *sent* is replied to from the same address again.
	return (row.sender or "").lower() if (row.sender or "").lower() in held else ""


def _last_on_record(doctype: str, name: str, held: list[str]) -> str:
	"""The address this record's correspondence has been using."""
	# `get_list` and not `get_all`: this is the one query here that is scoped by
	# a *record* rather than by the address scope every other read in this
	# package goes through, so the permission check has to be the framework's.
	rows = frappe.get_list(
		"Communication",
		filters={"reference_doctype": doctype, "reference_name": name,
		         "communication_medium": "Email"},
		fields=["sender", "recipients", "cc"],
		order_by="creation desc",
		limit_page_length=10,
		ignore_permissions=False,
	)
	for row in rows:
		where = f"{row.get('sender') or ''},{row.get('recipients') or ''}," \
		        f"{row.get('cc') or ''}".lower()
		for one in held:
			if one in where:
				return one
	return ""


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

	# Not `held[0]`, which is whatever the database ordered first. See
	# `default_sender` for the four rules and why each one is there.
	sender = (sender or default_sender(in_reply_to, held=held)).lower()
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
			# The window in which "Sent" can be taken back. The framework's own
			# field, and the queue's picker already refuses rows whose
			# `send_after` has not arrived — so this is a real delay in the
			# sending and not a countdown in the browser that a closed tab
			# defeats.
			"send_after": add_to_date(now_datetime(), seconds=UNDO_SECONDS),
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
	return {
		"ok": True,
		"name": doc.name,
		"attached": len(names),
		"undo_seconds": UNDO_SECONDS,
	}


# How long "Sent" stays undoable. Long enough to notice the wrong recipient,
# short enough that nobody wonders why their mail has not arrived.
UNDO_SECONDS = 15


@frappe.whitelist(methods=["POST"])
def unsend(name: str) -> dict:
	"""Take back a message the queue has not sent yet.

	Only while every row for it is still `Not Sent`. Once a row is Sending or
	Sent the message is somebody else's, and a button that claimed otherwise
	would be lying about the one thing it exists to promise.
	"""
	doc = frappe.get_doc("Communication", name)
	if (doc.sender or "").lower() not in _held():
		frappe.throw(_("That is not your message."), frappe.PermissionError)

	rows = frappe.get_all(
		"Email Queue", filters={"communication": name}, fields=["name", "status"]
	)
	if any(row.status != "Not Sent" for row in rows):
		return {"ok": False, "reason": "gone"}

	for row in rows:
		frappe.delete_doc("Email Queue", row.name, force=True, ignore_permissions=True)
	frappe.delete_doc("Communication", name, force=True, ignore_permissions=True)
	return {"ok": True, "unsent": name}


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
			}
		).insert(ignore_permissions=True)
