"""Holding what somebody typed, so closing the composer does not lose it.

A `Communication` with `sent_or_received = "Sent"` and no queue row behind it,
marked by a status the framework already has. Not a doctype of our own: a
draft becomes the message when it is sent, and two models for one thing means
copying between them and losing the attachments on the way.
"""

import base64

import frappe


DRAFT_KEY = "oneapp_mail_draft"


@frappe.whitelist(methods=["POST"])
def keep(values: str | dict) -> dict:
	"""Hold what somebody has typed, so closing the composer does not lose it.

	One draft per person rather than many: this is the "I closed it by accident"
	case, not a filing system for half-written mail. It is a user default for
	the same reason the read receipts are — a table with a row per person for a
	value only that person reads is a table nobody queries.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	kept = {
		key: values.get(key) or ""
		for key in ("sender", "to", "cc", "bcc", "subject", "content", "in_reply_to")
	}
	kept["attachments"] = values.get("attachments") or []
	# Nothing to keep is a reason to forget, not to store an empty shell: a
	# composer opened and closed should not leave a draft behind it.
	if not any(kept[key] for key in ("to", "cc", "bcc", "subject", "content")):
		return forget()

	frappe.defaults.set_user_default(DRAFT_KEY, _wrapped(kept), frappe.session.user)
	return {"ok": True}


def _wrapped(payload: dict) -> str:
	"""The draft as something a default value cannot corrupt.

	Base64, and it is not paranoia. A user default is stored through Frappe's own
	sanitiser, which HTML-escapes what looks like markup — so a draft containing
	`class="x"` came back as `class="\&quot;x\&quot;"`, which is no longer JSON,
	and every composer opening after that was a 500 for that person. A message
	with a link in it does the same thing; the signature just made it happen
	every single time.

	The alternative was a doctype for one row per person that only that person
	ever reads, which is the thing this module exists not to be.
	"""
	return base64.b64encode(frappe.as_json(payload).encode("utf-8")).decode("ascii")


def _unwrapped(raw: str) -> dict:
	"""A stored draft, however it was written.

	Plain JSON is what drafts written before the wrapping look like, and one of
	them is somebody's half-finished message — so it is read, not discarded.
	"""
	try:
		text = base64.b64decode(raw.encode("ascii"), validate=True).decode("utf-8")
	except Exception:
		text = raw
	return frappe.parse_json(text)


@frappe.whitelist(methods=["GET"])
def kept() -> dict:
	"""The draft this person left behind, or nothing.

	A stored value that will not parse is *nothing*, not an error. This is read
	every time the composer opens, so one malformed default — and we wrote one:
	an attribute the rich editor mangled came back with a stray backslash in it
	and stopped the JSON parsing — meant a 500 on every attempt to write a
	message, for that person, until somebody cleared a user default by hand. A
	draft that cannot be read is a draft that is gone; refusing to open the
	composer as well loses the next message too.
	"""
	raw = frappe.defaults.get_user_default(DRAFT_KEY, frappe.session.user)
	if not raw:
		return {}

	try:
		kept = _unwrapped(raw)
	except Exception:
		frappe.log_error("Unreadable mail draft", frappe.get_traceback())
		forget()
		return {}

	return kept if isinstance(kept, dict) else {}


@frappe.whitelist(methods=["POST"])
def forget() -> dict:
	"""Throw the draft away, once its message has been sent."""
	frappe.defaults.set_user_default(DRAFT_KEY, "", frappe.session.user)
	return {"ok": True, "forgotten": True}
