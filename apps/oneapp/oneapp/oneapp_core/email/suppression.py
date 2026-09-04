"""Bounces, complaints, and not sending to them again.

The reason this exists is not politeness. Every workspace on the platform sends
through one Cloudflare identity, so deliverability is a *shared* resource: one
tenant importing a bought list and sending to five hundred dead addresses moves
the spam score for every other tenant on the same sending domain. A suppression
list is the only mechanism that stops one customer spending everybody's
reputation, and it has to work without anybody noticing it.

Two kinds of signal, and they are not the same weight:

* **A hard bounce** — the address does not exist. Never send there again;
  nothing changes by trying.
* **A complaint** — somebody pressed "this is spam". Worse than a bounce, and
  the address may well be live. Never send there again either, and this one is
  worth a human looking at.

A soft bounce — a full mailbox, a greylist, a server having a bad afternoon — is
deliberately *not* suppressed. Frappe's Email Queue already retries, and
suppressing on a temporary failure means one bad hour costs a customer an
address permanently.

Kept on the tenant site because that is where the sending happens and where the
list has to be checked, and *reported* to the control plane because the
consequence outlives the tenant: a workspace that is deleted and remade must not
start again with a clean list of addresses that complained about it.
"""

import frappe
from frappe import _

# Why an address is on the list. Ordered by how sure we are.
COMPLAINT = "Complaint"
HARD_BOUNCE = "Hard bounce"
MANUAL = "Blocked by hand"

REASONS = (COMPLAINT, HARD_BOUNCE, MANUAL)

# The SMTP classes that mean "this address does not exist". 5.1.1 is the one
# that matters; the rest of 5.x is a permanent failure of some other kind, and
# several of those (5.7.1 — rejected for policy) say more about the *message*
# than about the recipient, so they do not suppress.
PERMANENT = ("5.1.1", "5.1.10", "5.1.2", "5.2.1")


def _key(email: str) -> str:
	return (email or "").strip().lower()


def is_suppressed(email: str) -> bool:
	if not _key(email):
		return False
	return bool(
		frappe.db.exists("Email Unsubscribe", {"email": _key(email), "reference_doctype": "Suppression"})
	)


def suppress(email: str, reason: str = HARD_BOUNCE, detail: str = "") -> dict:
	"""Stop sending to an address.

	Written as an `Email Unsubscribe` row, which is Frappe's own list and is
	already consulted by the queue — so suppression takes effect through the
	framework's path rather than through a check of ours that some future send
	might forget to call. `reference_doctype` marks ours apart from a person who
	genuinely unsubscribed from a newsletter, because the two mean different
	things and only one of them is reversible by the recipient.
	"""
	email = _key(email)
	if not email or reason not in REASONS:
		return {"ok": False}

	if is_suppressed(email):
		return {"ok": True, "already": True}

	frappe.get_doc(
		{
			"doctype": "Email Unsubscribe",
			"email": email,
			"reference_doctype": "Suppression",
			"reference_name": reason,
		}
	).insert(ignore_permissions=True)

	frappe.log_error(
		title=f"Suppressed {email}",
		message=f"{reason}\n\n{detail}"[:2000],
	)
	return {"ok": True, "email": email, "reason": reason}


@frappe.whitelist(methods=["POST"])
def release(email: str) -> dict:
	"""Take an address off the list.

	An admin's decision and nobody else's, and worth having: an address is
	suppressed by a signal that can be wrong — a server that was down for a day,
	a complaint from somebody who then asks why they stopped getting invoices.
	"""
	from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

	if not set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can do that."), frappe.PermissionError)

	email = _key(email)
	for row in frappe.get_all(
		"Email Unsubscribe",
		filters={"email": email, "reference_doctype": "Suppression"},
		pluck="name",
	):
		frappe.delete_doc("Email Unsubscribe", row, ignore_permissions=True, force=True)

	return {"ok": True, "email": email}


@frappe.whitelist(methods=["GET"])
def listing() -> list[dict]:
	"""Everything this workspace is not sending to, and why."""
	from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

	if not set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can see this."), frappe.PermissionError)

	return frappe.get_all(
		"Email Unsubscribe",
		filters={"reference_doctype": "Suppression"},
		fields=["email", "reference_name as reason", "creation"],
		order_by="creation desc",
		limit=500,
	)


# --------------------------------------------------------------------------- #
# Where the signals come from
# --------------------------------------------------------------------------- #

def on_queue_failure(doc, method=None):
	"""`on_update` on Email Queue — read the error and decide.

	Frappe records the failure text on the queue row and moves on. Reading it is
	the only bounce feedback available without a provider webhook, and it covers
	the case that matters most: an address that does not exist answers at SMTP
	time, synchronously, and the error is right there.

	Asynchronous bounces — a message accepted and then rejected, which is most
	of them — arrive as mail to the return path and are handled by
	`handle_bounce` below.
	"""
	if doc.get("status") != "Error":
		return

	error = (doc.get("error") or "")
	if not any(code in error for code in PERMANENT):
		return

	for recipient in doc.get("recipients") or []:
		suppress(recipient.recipient, HARD_BOUNCE, error)


def handle_bounce(payload: dict) -> dict:
	"""A delivery status notification, arriving as mail.

	The Worker sends anything addressed to the return path here. A DSN names the
	address that failed in its `Final-Recipient` field and the reason in
	`Status`; parsing the whole multipart/report is more than this needs, so it
	reads the two lines it cares about out of the text.
	"""
	text = (payload.get("text") or "") + (payload.get("html") or "")
	failed, status = "", ""

	for line in text.splitlines():
		line = line.strip()
		lowered = line.lower()
		if lowered.startswith("final-recipient:") and ";" in line:
			failed = line.split(";", 1)[1].strip().strip("<>")
		elif lowered.startswith("status:"):
			status = line.split(":", 1)[1].strip()

	if failed and any(status.startswith(code) for code in PERMANENT):
		return suppress(failed, HARD_BOUNCE, text[:1000])

	# Anything else is a soft failure or a report we do not understand. Kept,
	# not acted on: a suppression made from a guess is worse than none.
	return {"ok": True, "suppressed": False, "recipient": failed, "status": status}


def handle_complaint(payload: dict) -> dict:
	"""An abuse report (ARF). The `Original-Rcpt-To` is who complained."""
	text = (payload.get("text") or "")
	for line in text.splitlines():
		if line.lower().startswith("original-rcpt-to:"):
			return suppress(line.split(":", 1)[1].strip().strip("<>"), COMPLAINT, text[:1000])
	return {"ok": True, "suppressed": False}
