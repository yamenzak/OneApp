"""Sending a message, and the window in which that can be taken back."""

import frappe
from frappe import _
from frappe.utils import add_to_date, escape_html, now_datetime
from .scope import _held


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
				"folder": "Home/Attachments",
			}
		).insert(ignore_permissions=True)
