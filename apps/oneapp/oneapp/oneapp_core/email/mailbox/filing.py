"""Moving a conversation: to the bin, to the archive, to a folder.

The whitelisted half. `folders.py` does the IMAP; this decides whose mailbox
is being changed, which is the part that has to be right.
"""

import frappe
from oneapp.oneapp_core.email import folders as folder_ops
from .scope import _account_of
from .reading import thread


@frappe.whitelist(methods=["POST"])
def bin(key: str, address: str, folder: str = "all") -> dict:
	"""Delete a conversation, which means putting it in the mailbox's Trash.

	Not `frappe.delete_doc`. Deleting the document would remove it from the
	record it is filed against and from everybody else who holds the address,
	permanently, on a click that every mail client has taught people is
	reversible. Trash is reversible; emptying it is Frappe's own deletion and
	is not this button.
	"""
	return _into(key, address, folder, "trash", "Trash")


@frappe.whitelist(methods=["POST"])
def archive(key: str, address: str, folder: str = "all") -> dict:
	"""Out of the inbox and still there, which is what archiving is."""
	return _into(key, address, folder, "archive", "Archive")


def _into(key: str, address: str, folder: str, kind: str, fallback: str) -> dict:
	"""File a conversation into whichever folder plays a given role.

	The name is the server's, not ours: `classify` read it off the SPECIAL-USE
	flags, so this lands in `[Gmail]/Bin` or `Deleted Items` or whatever that
	mailbox actually calls it. Where the mailbox has none — a routed address has
	no server and so no Trash — one is made, once.
	"""
	account = _account_of(address)
	known = folder_ops.kinds(account.name)
	name = next((one for one, role in known.items() if role == kind), "")

	if not name:
		name = fallback
		if not any(row.folder_name == name for row in account.imap_folder or []):
			folder_ops.create(account, name)
		account.db_set(
			"custom_folder_kinds",
			frappe.as_json({**known, name: kind}),
			update_modified=False,
		)

	return file_thread(key, address, name, folder)


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
