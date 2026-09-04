"""The folders somebody already has, mirrored.

A person who connects the mailbox they have used for nine years has *sorted* it.
Applicants, Documents, Suppliers, Sent, Archive — those folders are how they
find things, and a product that pours all of it into one flat list has taken
their filing system away and called it a feature.

So the folders come across. Frappe already has the machinery: `Email Account`
carries an `IMAP Folder` child table, one row per folder, and the sync walks it
folder by folder with its own UID bookmark on each. Three things it does not do,
which are what this file is:

* **Ask the server what folders exist.** Frappe's own screen has you type the
  names in. `discover()` runs the IMAP `LIST` and answers with what is there,
  including which one the server says is Sent, Drafts, Trash or Junk — servers
  advertise that with SPECIAL-USE flags rather than making everyone guess at
  "Sent Items" versus "Sent Mail" versus "Gesendet".
* **Remember which folder a message came from.** `InboundMail` is handed the
  folder and drops it: nothing on `Communication` records where it was filed.
  A field, and the two small overrides that fill it in.
* **Let sent mail be sent mail.** Frappe refuses to import a message whose
  sender is the account itself — reasonable for an inbox, and it empties the
  Sent folder. In a folder the server flags as Sent, that check is turned off
  and the message is stored as Sent rather than Received.

The overrides are subclasses, and deliberately small ones: three methods on
`InboundMail` and one on `Email Account`. Everything else — the IMAP session,
the UID bookkeeping, the MIME parsing, the attachment handling — stays the
framework's, because it is the part that is hard and already works.
"""

import re

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.receive import InboundMail

# The field that remembers where a message was filed. A custom field rather than
# a doctype of our own: it is one string on a document the framework already
# owns, and the alternative is a join on every list.
FOLDER_FIELD = "custom_imap_folder"

# What the server says a folder is *for*, when it says anything. RFC 6154, and
# every mail host worth connecting to implements it — which is the only reason
# this does not need a table of every language's word for "Sent".
SPECIAL = {
	"\\sent": "sent",
	"\\drafts": "drafts",
	"\\trash": "trash",
	"\\junk": "junk",
	"\\archive": "archive",
	"\\flagged": "flagged",
	"\\all": "all",
}

# The names to fall back on where a server advertises nothing. Matched on the
# last path segment, lowercased, so `[Gmail]/Sent Mail` and `INBOX.Sent` both
# land — and it is a guess, which is why the flags above are tried first.
BY_NAME = {
	"sent": "sent", "sent items": "sent", "sent mail": "sent", "sent messages": "sent",
	"drafts": "drafts", "draft": "drafts",
	"trash": "trash", "deleted": "trash", "deleted items": "trash", "bin": "trash",
	"junk": "junk", "spam": "junk", "junk e-mail": "junk", "bulk mail": "junk",
	"archive": "archive", "all mail": "all",
}

# Folders that are mirrored but not offered in the rail. Deleted mail and spam
# are still *fetched* — a mirror that quietly omits two folders is a mirror
# somebody cannot trust — but a rail that opens on somebody's junk is a rail
# nobody wants. They are one click away under "More folders" and no closer.
QUIET = {"trash", "junk", "drafts"}

# `* LIST (\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"`, and the same line
# with an unquoted name, and the same again with a NIL delimiter. Written out
# rather than pulled from a library because it is one line of IMAP and a
# dependency that parses it would be a dependency to keep.
LIST_LINE = re.compile(
	r'^\((?P<flags>[^)]*)\)\s+(?:"(?P<sep>[^"]*)"|NIL)\s+(?:"(?P<quoted>.*)"|(?P<bare>\S+))$'
)


def classify(name: str, flags: str) -> str:
	"""What kind of folder this is: `sent`, `junk`, … or `` for an ordinary one."""
	lowered = (flags or "").lower()
	for flag, kind in SPECIAL.items():
		if flag in lowered:
			return kind
	tail = re.split(r"[/.\\]", (name or "").strip())[-1].strip().lower()
	if tail == "inbox":
		return "inbox"
	return BY_NAME.get(tail, "")


def parse_list(rows) -> list[dict]:
	"""Turn imaplib's `LIST` response into folders.

	`\\Noselect` rows are containers, not folders — `[Gmail]` is the classic
	one — and selecting them fails, so they are dropped here rather than
	discovered later as a sync error nobody can act on.
	"""
	found = []
	for row in rows or []:
		if isinstance(row, bytes):
			row = row.decode("utf-8", "replace")
		if isinstance(row, tuple):  # a literal, which imaplib splits in two
			row = " ".join(
				part.decode("utf-8", "replace") if isinstance(part, bytes) else str(part)
				for part in row
			)
		match = LIST_LINE.match(str(row).strip())
		if not match:
			continue
		flags = match.group("flags") or ""
		if "\\noselect" in flags.lower() or "\\nonexistent" in flags.lower():
			continue
		name = match.group("quoted") or match.group("bare") or ""
		if not name:
			continue
		found.append({"name": name, "flags": flags, "kind": classify(name, flags)})
	return found


def discover(account) -> list[dict]:
	"""Every folder this account's server offers, INBOX first.

	INBOX first because it is the one everybody opens, and the rest in the
	server's own order — which for Gmail and Outlook is the order the person
	already sees them in, and is a better guess than alphabetical.
	"""
	server = account.get_incoming_server(in_receive=False)
	if not server:
		return []
	try:
		_status, rows = server.imap.list()
	finally:
		try:
			server.logout()
		except Exception:
			pass

	folders = parse_list(rows)
	folders.sort(key=lambda one: (one["kind"] != "inbox",))
	return folders


def apply(account, folders: list[dict]) -> int:
	"""Write one `IMAP Folder` row per folder, keeping the UID bookmarks.

	Rewritten rather than merged, except for the two columns that must survive:
	`uidvalidity` and `uidnext` are where the sync left off in that folder, and
	dropping them re-downloads it.
	"""
	kept = {
		row.folder_name: (row.uidvalidity, row.uidnext)
		for row in (account.imap_folder or [])
	}
	account.set("imap_folder", [])
	for one in folders:
		was = kept.get(one["name"], (None, None))
		account.append(
			"imap_folder",
			{
				"folder_name": one["name"],
				# Every folder files into Communication. Turning `Applicants`
				# into a Job Applicant document is an `append_to` away and is a
				# rule somebody has to choose — a mirror must not invent one.
				"append_to": "Communication",
				"uidvalidity": was[0],
				"uidnext": was[1],
			},
		)
	return len(folders)


def kinds(account_name: str) -> dict:
	"""Folder name to kind, for one account, read back off the server's flags.

	Cached on the Email Account rather than recomputed: `classify` is cheap and
	the IMAP `LIST` that feeds it is not, so the kind is stored beside the row
	the first time and read from there afterwards.
	"""
	stored = frappe.db.get_value("Email Account", account_name, "custom_folder_kinds")
	return frappe.parse_json(stored) if stored else {}


# --------------------------------------------------------------------------- #
# The two overrides
# --------------------------------------------------------------------------- #

class OneSpaceInboundMail(InboundMail):
	"""One message, which now remembers which folder it was in."""

	def __init__(self, *args, folder="", sent=False, **kwargs):
		super().__init__(*args, **kwargs)
		self.folder = folder
		self.from_sent_folder = sent

	def is_sender_same_as_receiver(self):
		"""Frappe's guard against pulling your own mail out of your own inbox.

		Right for an inbox and wrong for a Sent folder, where every message is
		from you and skipping them empties the folder. Off there, and only
		there — an inbox that filled with your own copies would be the bug this
		guard exists to prevent.
		"""
		if self.from_sent_folder:
			return False
		return super().is_sender_same_as_receiver()

	def as_dict(self):
		data = super().as_dict()
		data[FOLDER_FIELD] = self.folder
		if self.from_sent_folder:
			# It is sent mail, so it says so — otherwise the Sent folder fills
			# with messages the rest of the product treats as things that
			# arrived, and every unread count is wrong.
			data["sent_or_received"] = "Sent"
			data["seen"] = 1
		return data


class OneSpaceEmailAccount(EmailAccount):
	"""An Email Account whose inbound mail knows where it came from.

	One method. `get_inbound_mails` is the only place the framework holds the
	folder and the message at the same time, and it drops the folder on the
	floor — so this is the same walk with the folder carried through.
	"""

	def get_inbound_mails(self) -> list:
		if not self.enable_incoming or not self.use_imap or self.service == "Frappe Mail":
			return super().get_inbound_mails()

		known = kinds(self.name)
		mails = []
		try:
			server = self.get_incoming_server(
				in_receive=True, email_sync_rule=self.build_email_sync_rule()
			)
			for row in self.imap_folder:
				if not server.select_imap_folder(row.folder_name):
					continue
				server.settings["uid_validity"] = row.uidvalidity
				messages = server.get_messages(folder=f'"{row.folder_name}"') or {}
				sent = known.get(row.folder_name) == "sent"

				for index, message in enumerate(messages.get("latest_messages", [])):
					uid = messages["uid_list"][index] if messages.get("uid_list") else None
					seen = messages.get("seen_status", {}).get(uid)
					if self.email_sync_option == "UNSEEN" and seen == "SEEN":
						continue
					mails.append(
						OneSpaceInboundMail(
							message,
							self,
							frappe.safe_decode(uid),
							seen,
							row.append_to,
							folder=row.folder_name,
							sent=sent,
						)
					)
			server.logout()
		except Exception:
			self.log_error(title=f"Error while connecting to email account {self.name}")
			return []

		return mails
