"""Filing rules, and the out-of-office reply.

Both are the same idea from two directions: something a person decides once so
they do not have to decide it every morning.

**Rules.** Frappe has an `Email Rule` and it is not this — two fields, an
address and a spam flag. What people mean by a rule is a filing instruction, and
without one a shared inbox is sorted by hand forever.

Deliberately one condition per rule rather than a boolean tree. The rules people
write are "from the architect" or "with LPO in the subject"; a builder that can
express `(A or B) and not C` is a builder nobody uses to express anything, and
two rules are the answer to two conditions.

**Out of office.** Frappe already sends it — `Email Account.enable_auto_reply`
and `auto_reply_message`, fired from `EmailAccount.receive`. What is missing is
anywhere to turn it on without the desk, and dates: an auto-reply somebody
forgot to switch off answers their mail for a month.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from oneapp.oneapp_core.email import folders as folder_ops
from oneapp.oneapp_core.email.folders import FOLDER_FIELD

# What a rule can look at, and where to find it on a Communication.
LOOKS_AT = {
	"Sender": "sender",
	"Subject": "subject",
	"Recipient": "recipients",
	"Body": "content",
}


def _hit(operator: str, haystack: str, needle: str) -> bool:
	"""Whether one condition holds.

	Case-folded throughout, because nobody means the case when they type an
	address — and `Hala@Client.test` and `hala@client.test` are the same person
	to everyone except a comparison.
	"""
	haystack = (haystack or "").lower()
	needle = (needle or "").lower()
	if not needle:
		return False
	if operator == "Is":
		return haystack.strip() == needle
	if operator == "Starts with":
		return haystack.startswith(needle)
	if operator == "Ends with":
		return haystack.endswith(needle)
	return needle in haystack


def matching(doc, address: str):
	"""The first rule that matches, or `None`.

	First and not all: the rules are ordered and the first match wins, which is
	what makes a rule list readable. Two rules that both match and both act
	would be a coin toss dressed as a feature.
	"""
	for rule in frappe.get_all(
		"Mail Rule",
		filters={"address": address, "enabled": 1},
		fields=["name", "field", "operator", "matches", "into", "mark_read", "star"],
		order_by="priority asc, creation asc",
	):
		value = doc.get(LOOKS_AT.get(rule.field, "sender")) or ""
		if _hit(rule.operator, value, rule.matches):
			return rule
	return None


def apply_to(doc, address: str) -> dict:
	"""Run the rules for one address over one message.

	Called from inbound, after the message is stored. After rather than before:
	a rule that threw while the message was half-written would lose the message,
	and losing mail to a filing rule is the worst possible trade.
	"""
	rule = matching(doc, address)
	if not rule:
		return {"filed": False}

	if rule.into:
		account = frappe.db.get_value("Email Account", {"email_id": address}, "name")
		if account:
			target = frappe.get_doc("Email Account", account)
			if not any(row.folder_name == rule.into for row in target.imap_folder or []):
				folder_ops.create(target, rule.into)
			doc.db_set(FOLDER_FIELD, rule.into, update_modified=False)

	if rule.mark_read:
		# The document's own flag, not the per-person seen list: a rule is the
		# workspace saying nobody needs to look at this, which is a different
		# statement from one person having looked.
		doc.db_set("seen", 1, update_modified=False)

	if rule.star:
		_star_for_everyone(doc, address)

	return {"filed": True, "rule": rule.name, "into": rule.into or ""}


def _star_for_everyone(doc, address: str):
	"""A rule's star, which has no session user to hang off.

	Starring is per person — two people on `sales@` star different things — and
	`mailbox.reading.star` writes the user default of whoever pressed the
	button. A rule fires during inbound delivery, where there is nobody
	pressing anything, so it stars for every person who currently holds the
	address. That is what the rule means: *this* address's owner wanted these
	marked, and an address is held by one person or by a team.

	The IMAP flag goes on as well, so the star is the same star in Outlook —
	the same pairing `reading.star` makes.

	The column was stored, listed and fetched from the day rules shipped and
	acted on nowhere: a rule with Star ticked filed the message and left it
	unstarred, which is the failure mode nobody reports because it looks like
	forgetting to tick the box.
	"""
	from .folders import flag
	from .mailbox.flags import STARRED_KEY, SEEN_LIMIT, _starred_of

	holders = frappe.get_all(
		"User Email",
		filters={"email_id": address},
		pluck="parent",
		distinct=True,
	)

	for person in holders:
		starred = _starred_of(person) | {doc.name}
		if len(starred) > SEEN_LIMIT:
			starred = set(sorted(starred)[-SEEN_LIMIT:])
		frappe.defaults.set_user_default(STARRED_KEY, ",".join(sorted(starred)), person)

	# Never fatal, for the reason `folders.flag` gives: a star that did not
	# reach the server is one the next sync corrects.
	flag([doc.name], True)


# --------------------------------------------------------------------------- #
# Out of office
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def away(address: str) -> dict:
	"""What this address answers with while nobody is reading it."""
	from oneapp.oneapp_core.email.mailbox import _account_of

	account = _account_of(address)
	return {
		"enabled": bool(account.enable_auto_reply),
		"message": account.auto_reply_message or "",
		"until": account.get("custom_away_until") or "",
	}


@frappe.whitelist(methods=["POST"])
def set_away(address: str, enabled: int = 0, message: str = "", until: str = "") -> dict:
	"""Turn the out-of-office on, and say when it stops.

	The date is the part Frappe does not have and the part that matters: an
	auto-reply somebody forgot to switch off answers their mail for a month, and
	every person it answers learns they are away when they are not.
	"""
	from oneapp.oneapp_core.email.mailbox import _account_of

	account = _account_of(address)
	if int(enabled) and not (message or "").strip():
		frappe.throw(_("An out-of-office reply needs something to say."))
	if until and getdate(until) < getdate(nowdate()):
		frappe.throw(_("That date has already passed."))

	account.db_set("enable_auto_reply", 1 if int(enabled) else 0, update_modified=False)
	account.db_set("auto_reply_message", message, update_modified=False)
	account.db_set("custom_away_until", until or None, update_modified=False)
	return {"ok": True}


def expire_away():
	"""Switch off every auto-reply whose last day has passed.

	Daily. This is the whole reason the date exists — without something that
	acts on it, a date is a note to self.
	"""
	for name in frappe.get_all(
		"Email Account",
		filters={
			"enable_auto_reply": 1,
			"custom_away_until": ("<", nowdate()),
		},
		pluck="name",
	):
		frappe.db.set_value(
			"Email Account", name, "enable_auto_reply", 0, update_modified=False
		)


# --------------------------------------------------------------------------- #
# The rules somebody edits
# --------------------------------------------------------------------------- #
#
# Whitelisted here rather than left to the generic screen engine: a rule belongs
# to a mailbox, and every one of these has to check that the mailbox is one the
# caller holds. A screen over `Mail Rule` would show one workspace's filing
# instructions to anybody who could open the doctype.

FIELDS = (
	"name", "title", "address", "enabled", "priority",
	"field", "operator", "matches", "into", "mark_read", "star",
)


def _mine(address: str) -> str:
	"""Refuse an address this person does not hold, and answer it if they do."""
	from oneapp.oneapp_core.email.mailbox import _held

	address = (address or "").strip().lower()
	if address not in _held():
		frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)
	return address


@frappe.whitelist(methods=["GET"])
def listing(address: str) -> list[dict]:
	"""The rules on one address, in the order they run."""
	return frappe.get_all(
		"Mail Rule",
		filters={"address": _mine(address)},
		fields=list(FIELDS),
		order_by="priority asc, creation asc",
	)


@frappe.whitelist(methods=["POST"])
def save(values: str | dict) -> dict:
	"""Write a rule, new or existing.

	One endpoint for both, because a rule is small enough that "create" and
	"update" differ by one field and two screens for that is two screens to keep
	in step.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	address = _mine(values.get("address"))

	if values.get("name"):
		doc = frappe.get_doc("Mail Rule", values["name"])
		# Re-checked on the *stored* address, not the submitted one: otherwise
		# somebody could point a rule they do not own at an address they do.
		_mine(doc.address)
	else:
		doc = frappe.new_doc("Mail Rule")

	doc.update({key: values.get(key) for key in FIELDS if key != "name"})
	doc.address = address
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def drop(name: str) -> dict:
	"""Remove a filing rule. Checked against the address it is on, not the caller's list."""
	doc = frappe.get_doc("Mail Rule", name)
	_mine(doc.address)
	frappe.delete_doc("Mail Rule", name, ignore_permissions=True)
	return {"ok": True, "removed": name}
