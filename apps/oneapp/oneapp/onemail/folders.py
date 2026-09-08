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
from frappe import _
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


# --------------------------------------------------------------------------- #
# Making and using folders
# --------------------------------------------------------------------------- #
#
# Two kinds of address and one screen, and the difference is not a compromise.
#
# A **connected mailbox** has a real IMAP server. A folder made here is an IMAP
# `CREATE` on that server, so it appears in Outlook and on their phone; filing a
# message is an IMAP `MOVE`, and the message is in that folder everywhere. This
# is the whole reason to go through IMAP rather than keep our own labels: the
# customer's other clients are not going away, and a folder that exists only
# here would be a folder that disagrees with the one place they actually read
# their mail.
#
# An address **we route** — `sales@acme.4dl.app` — has no server, because
# Cloudflare gives routing and not storage. A folder there is a row and a value
# on the Communication, and nothing to disagree with: there is no Outlook
# showing that address. It is not a lesser folder, it is the only kind that can
# exist, and a product that refused to offer one would be refusing to organise
# the mail it owns outright.


def has_server(account) -> bool:
	"""Whether this account is a mailbox we can talk IMAP to."""
	return bool(account.enable_incoming and account.use_imap and account.email_server)


def _session(account):
	"""A logged-in IMAP connection, or `None` for an address we route."""
	if not has_server(account):
		return None
	return account.get_incoming_server(in_receive=False)


def create(account, name: str) -> dict:
	"""Make a folder, on the server where there is one.

	The IMAP call first and the row second, deliberately: a row written before
	a `CREATE` that fails is a folder in our rail that exists nowhere else, and
	the next sync would quietly skip it forever.
	"""
	name = (name or "").strip().strip("/")
	if not name:
		frappe.throw(_("A folder needs a name."))
	if any(row.folder_name.lower() == name.lower() for row in account.imap_folder or []):
		frappe.throw(_("{0} already exists.").format(name))

	server = _session(account)
	if server:
		try:
			status, detail = server.imap.create(_quote(name))
			if status != "OK":
				frappe.throw(_("The mail server refused that name: {0}").format(_say(detail)))
			# Subscribed as well as created: an unsubscribed folder exists and
			# is hidden by most clients, which is a folder somebody made here
			# and cannot find in Outlook.
			server.imap.subscribe(_quote(name))
		finally:
			try:
				server.logout()
			except Exception:
				pass

	account.append("imap_folder", {"folder_name": name, "append_to": "Communication"})
	account.save(ignore_permissions=True)
	_remember(account, name, "")
	return {"ok": True, "folder": name, "on_server": bool(server)}


def remove(account, name: str) -> dict:
	"""Take a folder away, and leave the mail.

	`DELETE` on the server removes the folder *and* everything in it, which is
	not what "remove this folder" means to anybody who has used a mail client
	with a Trash in it. So the messages move out first, back to INBOX, and what
	is deleted is an empty folder.
	"""
	rows = [row for row in (account.imap_folder or []) if row.folder_name == name]
	if not rows:
		frappe.throw(_("There is no folder called {0}.").format(name))
	if kinds(account.name).get(name) in ("inbox", "sent"):
		frappe.throw(_("{0} is not a folder you can remove.").format(name))

	server = _session(account)
	if server:
		try:
			_empty(server, name)
			status, detail = server.imap.delete(_quote(name))
			if status != "OK":
				frappe.throw(_("The mail server refused: {0}").format(_say(detail)))
		finally:
			try:
				server.logout()
			except Exception:
				pass

	frappe.db.set_value(
		"Communication",
		{"email_account": account.name, FOLDER_FIELD: name},
		FOLDER_FIELD,
		"INBOX",
		update_modified=False,
	)
	account.set(
		"imap_folder", [row for row in account.imap_folder if row.folder_name != name]
	)
	account.save(ignore_permissions=True)
	_remember(account, name, None)
	return {"ok": True, "removed": name}


def _empty(server, name: str):
	"""Move everything out of a folder before deleting it."""
	if not server.select_imap_folder(name):
		return
	_status, data = server.imap.uid("search", None, "ALL")
	uids = (data[0] or b"").split()
	if uids:
		server.imap.uid("MOVE", b",".join(uids), _quote("INBOX"))


def file(account, message: str, name: str) -> dict:
	"""Put one message in a folder, everywhere it is read.

	`MOVE` where the server has it (RFC 6851, and every host worth connecting
	to), falling back to the copy-and-flag pair it replaced. The UID changes on
	arrival, so the row's `uid` is cleared rather than left pointing at a
	message id that now means something else in a different folder.
	"""
	doc = frappe.get_doc("Communication", message)
	server = _session(account)
	if server:
		try:
			source = doc.get(FOLDER_FIELD) or "INBOX"
			if server.select_imap_folder(source) and doc.uid and int(doc.uid) > 0:
				uid = str(doc.uid).encode()
				status, detail = server.imap.uid("MOVE", uid, _quote(name))
				if status != "OK":
					status, detail = server.imap.uid("COPY", uid, _quote(name))
					if status != "OK":
						frappe.throw(_("The mail server refused: {0}").format(_say(detail)))
					server.imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
					server.imap.expunge()
		finally:
			try:
				server.logout()
			except Exception:
				pass

	doc.db_set(FOLDER_FIELD, name, update_modified=False)
	doc.db_set("uid", -1, update_modified=False)
	return {"ok": True, "filed": message, "folder": name}


def _quote(name: str) -> str:
	"""IMAP folder names are quoted, and a quote inside one is escaped."""
	return '"' + (name or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _say(detail) -> str:
	"""Whatever the server said, as something printable."""
	if isinstance(detail, list) and detail:
		detail = detail[0]
	if isinstance(detail, bytes):
		detail = detail.decode("utf-8", "replace")
	return str(detail)[:200]


def _remember(account, name: str, kind):
	"""Keep the cached folder-kind map in step with the rows.

	`None` forgets one. A map that still names a folder nobody has is a rail
	that draws a Sent icon beside a folder that is gone.
	"""
	known = kinds(account.name)
	if kind is None:
		known.pop(name, None)
	else:
		known[name] = kind
	account.db_set("custom_folder_kinds", frappe.as_json(known), update_modified=False)


def flag(messages: list[str], on: bool = True):
	"""Set or clear IMAP's `\\Flagged` on some messages, so a star is the same
	star in every client.

	Grouped by mailbox and by folder, because IMAP is a stateful protocol: each
	`STORE` applies to whatever folder is currently selected, and one connection
	per message would be one login per star.

	Never fatal. A star that did not reach the server is a star the next sync
	corrects; a star that threw is a button that looks broken.
	"""
	rows = frappe.get_all(
		"Communication",
		filters={"name": ("in", messages or [""])},
		fields=["name", "uid", "email_account", FOLDER_FIELD],
	)
	by_account: dict[str, dict[str, list]] = {}
	for row in rows:
		if not row.email_account or not row.uid or int(row.uid) < 1:
			continue
		by_account.setdefault(row.email_account, {}).setdefault(
			row.get(FOLDER_FIELD) or "INBOX", []
		).append(str(row.uid))

	for name, folders_ in by_account.items():
		account = frappe.get_doc("Email Account", name)
		if not has_server(account):
			continue
		try:
			server = _session(account)
			for folder_name, uids in folders_.items():
				if server.select_imap_folder(folder_name):
					server.imap.uid(
						"STORE", ",".join(uids), "+FLAGS" if on else "-FLAGS", "(\\Flagged)"
					)
			server.logout()
		except Exception:
			frappe.log_error(title=f"Could not flag mail on {account.email_id}")
