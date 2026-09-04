"""Holding what somebody typed, so closing the composer does not lose it."""

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

	frappe.defaults.set_user_default(
		DRAFT_KEY, frappe.as_json(kept), frappe.session.user
	)
	return {"ok": True}


@frappe.whitelist(methods=["GET"])
def kept() -> dict:
	raw = frappe.defaults.get_user_default(DRAFT_KEY, frappe.session.user)
	return frappe.parse_json(raw) if raw else {}


@frappe.whitelist(methods=["POST"])
def forget() -> dict:
	frappe.defaults.set_user_default(DRAFT_KEY, "", frappe.session.user)
	return {"ok": True, "forgotten": True}
