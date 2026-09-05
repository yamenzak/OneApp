"""Opening the composer already filled in: a reply, or a forward.

Both are the same shape — a new message carrying an old one — and both are
built on the server rather than in the browser, for one reason: the quoted
body is the *stored* HTML, and the stored HTML is what Frappe sanitised on
the way in. Quoting from what the reader is looking at would quote the copy
with its images held back, and send somebody a reply full of empty `<img>`.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, escape_html, format_datetime, now_datetime
from .scope import _addresses, _held, strip_prefixes


@frappe.whitelist(methods=["GET"])
def draft(message: str, kind: str = "reply") -> dict:
	"""What the composer opens with, for a reply, a reply-all or a forward.

	Built here and not in the browser so the three differ in one place. They are
	nearly the same message: the difference is who it goes to and whether the
	attachments come along.
	"""
	if kind not in ("reply", "reply_all", "forward"):
		frappe.throw(_("Not something a message can be turned into."))

	held = _held()
	original = frappe.get_doc("Communication", message)

	# The same gate every list goes through. A draft is a way of reading a
	# message, so it has to be one this person could already read.
	mine = [one for one in held if one in (original.recipients or "")
	        or one == (original.sender or "").lower()]
	if not mine:
		frappe.throw(_("That is not your message."), frappe.PermissionError)

	subject = strip_prefixes(original.subject)
	prefix = "Fwd: " if kind == "forward" else "Re: "

	if kind == "forward":
		to, cc = "", ""
	else:
		# Reply goes to whoever wrote it. Reply-all adds everyone else who was
		# on it, minus this person's own addresses — answering yourself is the
		# oldest bug in mail.
		to = original.sender
		cc = ""
		if kind == "reply_all":
			others = _addresses(original.recipients) + _addresses(original.cc)
			cc = ", ".join(
				one for one in dict.fromkeys(others)
				if one.lower() not in held and one.lower() != (original.sender or "").lower()
			)

	return {
		"to": to,
		"cc": cc,
		"subject": f"{prefix}{subject}" if subject else prefix.strip(),
		"content": _quote(original),
		# A forward carries the attachments — a forwarded invoice without the
		# invoice is the reason people go back to Outlook. A reply does not:
		# the person being replied to sent them.
		"attachments": (
			[
				{"name": row.name, "file_name": row.file_name, "file_size": row.file_size}
				for row in frappe.get_all(
					"File",
					filters={"attached_to_doctype": "Communication",
					         "attached_to_name": original.name},
					fields=["name", "file_name", "file_size"],
				)
			]
			if kind == "forward" else []
		),
		"in_reply_to": original.name,
		# The address it arrived at is the one to answer from. Replying to mail
		# that reached `sales@` from a personal address is how a customer finds
		# out a shared mailbox is not shared.
		"sender": mine[0],
	}


def _quote(original) -> str:
	"""The original, under an attribution line, the way every client does it.

	A blockquote and not a `>` prefix: the body is HTML, and prefixing lines of
	HTML with a character produces neither quoted text nor valid markup.
	"""
	# Written the way a person writes a date, not the way a database stores one:
	# the attribution line said "On 2026-09-04 20:48:15.232563, Hala wrote:",
	# microseconds and all, in a message going to a customer.
	when = original.communication_date
	said = format_datetime(when, "EEE, d MMM yyyy 'at' HH:mm") if when else ""
	who = escape_html(original.sender_full_name or original.sender or "")
	return (
		"<p><br></p>"
		f"<p>On {escape_html(said)}, {who} wrote:</p>"
		'<blockquote style="margin:0 0 0 .8ex;border-left:2px solid #ccc;padding-left:1ex">'
		f"{original.content or ''}"
		"</blockquote>"
	)
