"""Whose mail this is: the addresses somebody holds, and their folders."""

import frappe
import re
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


def _addresses(value: str) -> list[str]:
	"""The addresses out of a header, dropping the display names.

	`"Hala Nasser" <hala@x.test>, ap@y.test` is two addresses, and the quoted
	comma inside the first is why this is not `value.split(",")`.
	"""
	found = re.findall(r"<([^>]+)>|([^\s,;<>\"]+@[^\s,;<>\"]+)", value or "")
	return [(angled or bare).strip() for angled, bare in found if (angled or bare).strip()]
