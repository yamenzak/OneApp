"""Connecting a mailbox somebody already has.

Everything else in this module is an address on a domain we route. This is the
other half, and for most customers it is the half that matters: the address they
have used for nine years, at Gmail or Outlook or a host their accountant picked,
which they are not going to give up because a new product would prefer it.

This is the one place Frappe's own receiving machinery runs unmodified. There
*is* an IMAP server to poll, so `enable_incoming` means what it says and the
scheduled sync does the work — see `frappe/email/receive.py`. Nothing here
reimplements any of it; what is here is the shape of the question we ask and the
refusals that keep an answer from becoming a support ticket.

Two ways in:

* **A password.** Host, port, and a password — which for Gmail and Outlook is
  an app password rather than the account's own, because both stopped accepting
  the real one years ago. The commonest failure by far, so it is named in the
  error rather than left as "authentication failed".
* **OAuth.** Frappe ships `Connected App`, and where an operator has registered
  one for Google or Microsoft this is the better path: no password stored, and
  a token the customer can revoke from their own account page.

What is deliberately *not* here is a mail client's worth of settings. Frappe's
Email Account has forty fields; a person connecting their mailbox is asked for
four, and everything else takes the default that works.
"""

import frappe
from frappe import _

from oneapp.oneapp_core.email import folders
from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

# The hosts worth knowing by name. A person who types their address is telling
# us where their mail lives, and asking them for `imap.gmail.com` after that is
# asking them to look up something we know.
KNOWN = {
	"gmail.com": {
		"label": "Gmail",
		"email_server": "imap.gmail.com",
		"smtp_server": "smtp.gmail.com",
		"note": _("Google needs an app password, not your account password."),
	},
	"googlemail.com": {"label": "Gmail", "email_server": "imap.gmail.com",
	                   "smtp_server": "smtp.gmail.com", "note": ""},
	"outlook.com": {
		"label": "Outlook",
		"email_server": "outlook.office365.com",
		"smtp_server": "smtp.office365.com",
		"note": _("Microsoft needs an app password where two-factor is on."),
	},
	"hotmail.com": {"label": "Outlook", "email_server": "outlook.office365.com",
	                "smtp_server": "smtp.office365.com", "note": ""},
	"live.com": {"label": "Outlook", "email_server": "outlook.office365.com",
	             "smtp_server": "smtp.office365.com", "note": ""},
	"yahoo.com": {"label": "Yahoo", "email_server": "imap.mail.yahoo.com",
	              "smtp_server": "smtp.mail.yahoo.com",
	              "note": _("Yahoo needs an app password.")},
	"icloud.com": {"label": "iCloud", "email_server": "imap.mail.me.com",
	               "smtp_server": "smtp.mail.me.com",
	               "note": _("iCloud needs an app-specific password.")},
	"zoho.com": {"label": "Zoho", "email_server": "imap.zoho.com",
	             "smtp_server": "smtp.zoho.com", "note": ""},
}

# Ports, and they are not negotiable enough to ask about. 993 is IMAP over TLS
# and 587 is submission with STARTTLS; a host that wants anything else is a host
# whose owner already knows what they want and can say so.
IMAP_PORT = 993
SMTP_PORT = 587


def suggest(email_id: str) -> dict:
	"""What we can fill in from the address alone."""
	domain = (email_id or "").split("@")[-1].lower()
	known = KNOWN.get(domain)
	if known:
		return {"known": True, **known}
	# A guess for everybody else, and said to be a guess. `imap.` and `smtp.`
	# in front of the domain is what most hosts use and is right often enough
	# to be worth offering; being wrong here costs one corrected field.
	return {
		"known": False,
		"label": domain,
		"email_server": f"imap.{domain}" if domain else "",
		"smtp_server": f"smtp.{domain}" if domain else "",
		"note": _("We guessed these from your address. Change them if your host differs."),
	}


@frappe.whitelist(methods=["GET"])
def suggestion(email_id: str) -> dict:
	return suggest(email_id)


def _mine(account: str) -> bool:
	return bool(
		frappe.db.exists("User Email", {"parent": frappe.session.user, "email_account": account})
	)


def _require_mine_or_admin(account: str):
	if set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE}:
		return
	if not _mine(account):
		frappe.throw(_("That mailbox is not yours."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def connect(email_id: str, password: str, email_server: str = "", smtp_server: str = "",
            label: str = "") -> dict:
	"""Attach a mailbox to the person asking.

	Granted to the caller and nobody else. A mailbox somebody connected with
	their own password is theirs; an admin who wanted the workspace to have it
	would be asking for a shared address, which is a different thing on a
	different screen and does not involve anybody's personal credentials.
	"""
	email_id = (email_id or "").strip().lower()
	if "@" not in email_id:
		frappe.throw(_("That is not an email address."))

	if frappe.db.exists("Email Account", {"email_id": email_id}):
		frappe.throw(_("{0} is already connected.").format(email_id))

	guess = suggest(email_id)
	account = frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": label or email_id,
			"email_id": email_id,
			"password": password,
			# Both halves, because a person connecting their mailbox means both
			# and would be baffled to find they can read and not reply.
			"enable_incoming": 1,
			"use_imap": 1,
			"email_server": email_server or guess["email_server"],
			"incoming_port": IMAP_PORT,
			"use_ssl": 1,
			"enable_outgoing": 1,
			"smtp_server": smtp_server or guess["smtp_server"],
			"smtp_port": SMTP_PORT,
			"use_tls": 1,
			# Only what arrives from now on. A mailbox with nine years in it
			# would otherwise pull all of it into this site on first sync —
			# minutes of work, a storage bill, and nine years of somebody's
			# private mail in a workspace their colleagues can be granted.
			# `ALL`, not `UNSEEN`, and the difference is the whole feature.
			#
			# `UNSEEN` fetches unread mail, which for a mailbox somebody has
			# been using for years is almost nothing: their Applicants folder
			# is a hundred messages they have all read, and syncing it under
			# `UNSEEN` mirrors an empty folder. `ALL` takes the last
			# `initial_sync_count` UIDs *per folder* on the first pass — see
			# `check_imap_uidvalidity`, which sets the range from the folder's
			# own UIDNEXT — and everything new after that. Bounded, and bounded
			# per folder rather than per mailbox.
			"email_sync_option": "ALL",
			"initial_sync_count": 100,
			# INBOX to start with, and replaced a line below by whatever the
			# server actually offers.
			#
			# It has to be here rather than only there: Frappe refuses to save
			# an IMAP account with no folder row ("You need to set one IMAP
			# folder"), and the row everybody has is added by the *desk's*
			# JavaScript, which this product never runs. Without it the account
			# does not fail at first sync — it fails at insert, and the person
			# connecting their mailbox is told something about IMAP folders
			# that means nothing to them.
			"imap_folder": [{"folder_name": "INBOX", "append_to": "Communication"}],
			"create_contact": 0,
			"always_use_account_email_id_as_sender": 1,
		}
	)

	try:
		account.insert(ignore_permissions=True)
	except Exception as e:
		frappe.throw(_reason(e, guess))

	# The folders they already have. Only now, because it needs a saved account
	# to open a connection with, and it is deliberately not fatal: a mailbox
	# that connects and mirrors only its inbox is a working mailbox, and one
	# that refuses to connect because the folder listing timed out is not.
	found = _mirror(account)

	person = frappe.get_doc("User", frappe.session.user)
	person.append(
		"user_emails",
		{"email_account": account.name, "email_id": email_id, "enable_outgoing": 1},
	)
	person.save(ignore_permissions=True)

	return {"ok": True, "name": account.name, "email_id": email_id, "folders": found}


def _mirror(account) -> int:
	"""Ask the server what folders exist and write a row for each."""
	try:
		found = folders.discover(account)
	except Exception:
		frappe.log_error(title=f"Could not list folders for {account.email_id}")
		return 1

	if not found:
		return 1

	folders.apply(account, found)
	account.db_set(
		"custom_folder_kinds",
		frappe.as_json({one["name"]: one["kind"] for one in found}),
		update_modified=False,
	)
	account.save(ignore_permissions=True)
	return len(found)


@frappe.whitelist(methods=["POST"])
def refresh(name: str) -> dict:
	"""Re-read the folder list.

	A folder made in Outlook this morning is a folder this site has never heard
	of, and nothing tells us — IMAP has no folder-change notification worth
	relying on. So it is a button, and the alternative was a nightly job that
	re-lists every mailbox on the site to find the once-a-month case.
	"""
	_require_mine_or_admin(name)
	account = frappe.get_doc("Email Account", name)
	return {"ok": True, "folders": _mirror(account)}


def _reason(error: Exception, guess: dict) -> str:
	"""Turn a connection failure into something a person can act on.

	Frappe validates the connection on insert and raises whatever the library
	said, which for the commonest case is `AUTHENTICATIONFAILED` — true, and
	useless to somebody who typed the right password and does not know their
	provider stopped accepting it.
	"""
	text = str(error)
	if "AUTHENTICATIONFAILED" in text.upper() or "authentication" in text.lower():
		return guess["note"] or _(
			"That password was refused. Many providers need an app password "
			"rather than the one you sign in with."
		)
	if "getaddrinfo" in text or "Name or service not known" in text:
		return _("We could not reach {0}. Check the server name.").format(guess["email_server"])
	if "timed out" in text.lower():
		return _("The mail server did not answer. It may be blocking us, or the port may be wrong.")
	return _("We could not connect: {0}").format(text[:200])


@frappe.whitelist(methods=["POST"])
def disconnect(name: str) -> dict:
	"""Stop polling a mailbox, and forget the password.

	The Email Account goes; the mail that already arrived does not, for the same
	reason deleting an address does not delete its correspondence. Somebody
	disconnecting Gmail is saying "stop reading my mailbox", not "delete the
	last six months of my work".
	"""
	_require_mine_or_admin(name)

	for row in frappe.get_all("User Email", filters={"email_account": name}, pluck="name"):
		frappe.db.delete("User Email", row)

	frappe.delete_doc("Email Account", name, ignore_permissions=True, force=True)
	return {"ok": True, "disconnected": name}


@frappe.whitelist(methods=["GET"])
def mine() -> list[dict]:
	"""The mailboxes this person has connected, and whether they are working.

	`no_failed` is Frappe's own count of consecutive sync failures. Surfaced
	because the alternative is a mailbox that quietly stopped three weeks ago —
	a password changed, an app password revoked — and nobody finding out until
	they wonder why nothing has arrived.
	"""
	held = frappe.get_all(
		"User Email", filters={"parent": frappe.session.user}, pluck="email_account"
	)
	rows = []
	for name in held:
		if not frappe.db.exists("Email Account", name):
			continue
		doc = frappe.get_doc("Email Account", name)
		if not doc.enable_incoming:
			continue
		rows.append(
			{
				"name": doc.name,
				"email_id": doc.email_id,
				"server": doc.email_server,
				"failures": int(doc.no_failed or 0),
				"awaiting_password": int(doc.awaiting_password or 0),
				"last_received": doc.last_received_at,
			}
		)
	return rows
