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

	# A workspace's own address wins over the built-in handlers, and that order
	# matters: `sales@` is a lead handler here and is also the first shared
	# address every workspace makes. Somebody who created it and granted it to
	# three people means "put it where those three can read it", not "guess".
	account = _account_for(to)
	if account:
		return {"ok": True, "local_part": local_part, **handle_address(payload, account)}

	handler = HANDLERS.get(local_part, handle_generic)
	result = handler(payload)

	return {"ok": True, "local_part": local_part, **(result or {})}


def _account_for(to: str):
	"""The workspace address this was sent to, if it is one.

	Matched on the whole address rather than the local part: the domain carries
	the tenant slug, so a message that reached this site is already known to be
	for this workspace, and comparing the whole thing costs nothing and cannot
	be fooled by a Worker bug into filing `sales@other.4dl.app` here.
	"""
	if not to:
		return None
	name = frappe.db.get_value("Email Account", {"email_id": to}, "name")
	return frappe.get_doc("Email Account", name) if name else None


def handle_address(payload: dict, account) -> dict:
	"""Mail to an address somebody in this workspace holds.

	Two things happen that the function handlers do not do.

	It files against whatever the address says to file against. `append_to` is
	Frappe's own field for this and it is what makes `ap@` land on a Purchase
	Invoice rather than nowhere — an address a manager made can say the same
	thing without a line of code.

    And it is *shared* with whoever holds the address. A Communication is an
	ordinary document with ordinary permissions, so without this the mail
	arrives and only an administrator can read it. `DocShare` is the framework's
	own answer and the one the timeline, the search and the list all already
	respect; a permission system of our own beside it would be two systems
	disagreeing about the same row.
	"""
	name = _communication(payload, reference_doctype=account.append_to or None)

	holders = frappe.get_all(
		"User Email", filters={"email_account": account.name}, pluck="parent", distinct=True
	)
	for user in holders:
		_share(name, user)

	return {"communication": name, "account": account.name, "shared_with": len(holders)}


def _share(communication: str, user: str):
	"""Let one person read one message.

	Read and not write: mail that arrived is a record of what arrived, and an
	inbox is not a place to edit what somebody sent you.
	"""
	try:
		frappe.share.add(
			"Communication", communication, user, read=1, write=0, share=0, flags={"ignore_share_permission": True}
		)
	except Exception:
		# One person's share failing must not lose the message for everybody
		# else — and the most likely cause is a User row that has gone.
		frappe.log_error(title="Inbound share failed", message=frappe.get_traceback())


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


def handle_bounce(payload: dict) -> dict:
	"""A delivery report. Never filed as correspondence — see `suppression`."""
	from oneapp.oneapp_core.email import suppression

	return {"queue": "bounce", **suppression.handle_bounce(payload)}


def handle_complaint(payload: dict) -> dict:
	from oneapp.oneapp_core.email import suppression

	return {"queue": "complaint", **suppression.handle_complaint(payload)}


HANDLERS = {
	"ap": handle_supplier_invoice,
	"invoices": handle_supplier_invoice,
	"support": handle_support,
	"help": handle_support,
	"leads": handle_lead,
	"sales": handle_lead,
	# The two that are machinery rather than mail. A bounce filed as a
	# Communication is a customer opening their inbox to find a delivery report
	# from a mail server, which reads as a bug in our product and is one.
	"bounce": handle_bounce,
	"bounces": handle_bounce,
	"abuse-report": handle_complaint,
	"complaints": handle_complaint,
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
