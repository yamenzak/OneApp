"""Inbound mail from the Cloudflare Email Routing Worker.

The Worker receives on the catch-all, works out which tenant a recipient belongs
to, and HMAC-POSTs the parsed message here. Local part decides what happens:

    ap@       supplier invoices — the highest-value one, given ERPNext underneath
    support@  issues
    leads@    CRM

An unrecognised local part is accepted and filed as a Communication rather than
rejected, because bouncing a customer's mail is worse than filing it somewhere
slightly wrong.
"""

import json

import frappe
from frappe import _

from oneapp.oneapp_core import control_client

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def _verify() -> dict:
	"""The Worker signs with this tenant's own secret."""
	import hashlib
	import hmac
	import time

	secret = frappe.conf.get("oneapp_hmac_secret")
	if not secret:
		frappe.throw(_("Site is not provisioned."), frappe.PermissionError)

	raw = frappe.request.get_data(as_text=True) or ""
	signature = _header("Signature")
	timestamp = _header("Timestamp")

	if not (signature and timestamp):
		frappe.throw(_("Missing signature."), frappe.PermissionError)

	try:
		if abs(time.time() - int(timestamp)) > 300:
			frappe.throw(_("Signature expired."), frappe.PermissionError)
	except ValueError:
		frappe.throw(_("Malformed signature."), frappe.PermissionError)

	expected = hmac.new(
		secret.encode(), f"{timestamp}.{raw}".encode(), hashlib.sha256
	).hexdigest()

	if not hmac.compare_digest(expected, signature):
		frappe.throw(_("Invalid signature."), frappe.PermissionError)

	return json.loads(raw or "{}")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	payload = _verify()

	message_id = payload.get("message_id")

	# Cloudflare retries on failure; the same message must not create two documents.
	if message_id and frappe.db.exists("Communication", {"message_id": message_id}):
		return {"ok": True, "duplicate": True}

	to = (payload.get("to") or "").lower()
	local_part = to.split("@")[0] if "@" in to else to

	handler = HANDLERS.get(local_part, handle_generic)
	result = handler(payload)

	return {"ok": True, "local_part": local_part, **(result or {})}


def _communication(payload: dict, reference_doctype=None, reference_name=None) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Email",
			"sent_or_received": "Received",
			"subject": (payload.get("subject") or "(no subject)")[:140],
			"content": payload.get("html") or payload.get("text") or "",
			"text_content": payload.get("text"),
			"sender": payload.get("from"),
			"recipients": payload.get("to"),
			"message_id": payload.get("message_id"),
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		}
	).insert(ignore_permissions=True)

	_attach(doc, payload.get("attachments") or [])
	return doc.name


def _attach(doc, attachments: list):
	"""Attachments land in R2 through the File override like any other upload."""
	import base64

	for item in attachments:
		content = item.get("content")
		if not content:
			continue

		try:
			decoded = base64.b64decode(content)
		except Exception:
			continue

		if len(decoded) > MAX_ATTACHMENT_BYTES:
			continue

		try:
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": item.get("filename") or "attachment",
					"attached_to_doctype": doc.doctype,
					"attached_to_name": doc.name,
					"is_private": 1,
					"content": decoded,
				}
			).insert(ignore_permissions=True)
		except Exception:
			# A rejected attachment (quota, size) must not lose the message itself.
			frappe.log_error(
				title="Inbound attachment failed", message=frappe.get_traceback()
			)


def handle_supplier_invoice(payload: dict) -> dict:
	"""ap@ — file the mail and its attachments for invoice processing."""
	name = _communication(payload)
	return {"communication": name, "queue": "supplier_invoice"}


def handle_support(payload: dict) -> dict:
	name = _communication(payload)
	return {"communication": name, "queue": "support"}


def handle_lead(payload: dict) -> dict:
	name = _communication(payload)
	return {"communication": name, "queue": "lead"}


def handle_generic(payload: dict) -> dict:
	return {"communication": _communication(payload), "queue": "generic"}


HANDLERS = {
	"ap": handle_supplier_invoice,
	"invoices": handle_supplier_invoice,
	"support": handle_support,
	"help": handle_support,
	"leads": handle_lead,
	"sales": handle_lead,
}


def _header(name: str) -> str | None:
	"""One header, under either name.

	The signing headers were `X-OneApp-*` and are `X-OneSpace-*`. Both ends are
	ours, but they deploy separately — a tenant on the old build talking to a
	control plane on the new one would be refused, and "signature missing" is
	not a message anybody would trace back to a rename. The sender writes the
	new name; the receiver takes either, for one release.
	"""
	headers = frappe.request.headers
	return headers.get(f"X-OneSpace-{name}") or headers.get(f"X-OneApp-{name}")
