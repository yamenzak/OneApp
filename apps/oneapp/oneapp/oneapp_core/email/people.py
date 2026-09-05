"""Who wrote this, as a person rather than an address string.

A mail list that says `h.nasser@alreem-consultants.ae` and a mail list that says
**Hala Nasser**, with her face and her firm under it, are the same data and not
the same product. Every mail client worth using resolves the sender, and the
reason ours can do it cheaply is that Frappe already has the person: `Contact`,
with an image, a company and a phone, and `Contact Email` holding every address
they write from.

Three rules, and each of them is the reason a line of this is not shorter:

* **Resolved in a batch, never per row.** A list of fifty conversations is one
  query for the contacts behind them. A lookup per row is fifty round trips to
  draw one page, which is how a list that was fast becomes a list that is not.
* **Nothing leaves the site.** No Gravatar, no avatar service — those work by
  sending a hash of somebody's email address to a third party for every message
  in the list, which is a correspondent list handed to a company the customer
  has never heard of. An image we hold, or initials.
* **Unknown is a real answer.** Most senders are not Contacts and never will be,
  and a page that made a Contact for everyone who writes in would turn an inbox
  into a directory of strangers. They get their name from the mail's own
  `From` header and initials from that.
"""

import re

import frappe

# What a person is, once resolved. Kept small deliberately: this rides along
# with every row of every mail list, and a fat profile per row is a page that
# transfers a directory to draw a list.
FIELDS = ("name", "full_name", "image", "company_name", "designation", "mobile_no", "phone")


def initials(name: str) -> str:
	"""Two letters, from a name or failing that from an address.

	`Hala Nasser` is HN; `h.nasser@…` is HN too, because the local part's own
	separators are word boundaries and using them beats taking the first two
	characters of `h.nasser`.
	"""
	text = (name or "").strip()
	if "@" in text and " " not in text:
		text = text.split("@")[0]
	words = [word for word in re.split(r"[\s._\-+]+", text) if word]
	if not words:
		return "?"
	if len(words) == 1:
		return words[0][:2].upper()
	return (words[0][0] + words[-1][0]).upper()


def _contacts(addresses: list[str]) -> dict:
	"""Address to Contact, for a page of senders, in one query.

	Two tables because Frappe keeps both: `Contact.email_id` is the primary one
	and `Contact Email` holds the rest, and somebody who writes from their
	second address is the same person.
	"""
	wanted = sorted({one.lower() for one in addresses if one})
	if not wanted:
		return {}

	found: dict[str, dict] = {}
	rows = frappe.get_all(
		"Contact",
		filters={"email_id": ("in", wanted)},
		fields=list(FIELDS) + ["email_id"],
	)
	for row in rows:
		found[(row.email_id or "").lower()] = row

	# The child table, for the addresses the first query did not answer.
	missing = [one for one in wanted if one not in found]
	if missing:
		links = frappe.get_all(
			"Contact Email",
			filters={"email_id": ("in", missing), "parenttype": "Contact"},
			fields=["email_id", "parent"],
		)
		names = sorted({row.parent for row in links})
		if names:
			by_name = {
				row.name: row
				for row in frappe.get_all(
					"Contact", filters={"name": ("in", names)}, fields=list(FIELDS)
				)
			}
			for row in links:
				contact = by_name.get(row.parent)
				if contact:
					found[(row.email_id or "").lower()] = contact

	return found


def profiles(senders: list[tuple[str, str]]) -> dict:
	"""One profile per address, keyed by the lowercased address.

	`senders` is `(address, name from the header)` pairs, because the header is
	the fallback and the caller already has it — asking for it again would mean
	reading every message twice.
	"""
	known = _contacts([one for one, _ in senders])
	out = {}
	for address, header_name in senders:
		key = (address or "").lower()
		if key in out:
			continue
		contact = known.get(key)
		label = (contact or {}).get("full_name") or header_name or address
		out[key] = {
			"email": address,
			"label": label,
			"initials": initials(label or address),
			"image": (contact or {}).get("image") or "",
			"contact": (contact or {}).get("name") or "",
			"company": (contact or {}).get("company_name") or "",
			"designation": (contact or {}).get("designation") or "",
			"phone": (contact or {}).get("mobile_no") or (contact or {}).get("phone") or "",
		}
	return out


@frappe.whitelist(methods=["GET"])
def profile(email: str) -> dict:
	"""One sender, with the last few conversations with them.

	What the card behind a name shows. The conversations go through the same
	filter every mail list does — `mailbox._filters` — so a card cannot become
	the one place somebody's mail is readable by a colleague who was never
	granted the address.
	"""
	from oneapp.oneapp_core.email import mailbox

	email = (email or "").strip().lower()
	if not email:
		return {}

	found = profiles([(email, "")])
	person = found.get(email, {})

	filters, or_filters = mailbox._filters("all")
	filters["sender"] = email
	person["threads"] = [
		{
			"key": mailbox.normalise(row.subject),
			"subject": mailbox.strip_prefixes(row.subject) or "(no subject)",
			"at": row.communication_date,
		}
		for row in frappe.get_all(
			"Communication",
			filters=filters,
			or_filters=or_filters,
			fields=["subject", "communication_date"],
			order_by="communication_date desc",
			limit_page_length=5,
		)
	]
	return person


@frappe.whitelist(methods=["GET"])
def suggest(text: str, limit: int = 8) -> list[dict]:
	"""Addresses to complete a To field with.

	Contacts first and people written to second. A Contact is somebody the
	workspace decided to keep; a correspondent is somebody who happened to be on
	a message, and there are hundreds of those. Both are already on this site —
	no address book to build, no directory to sync.

	Deduplicated on the address, keeping the first: a Contact's name beats the
	display name off a header, for the same reason it does in the list.
	"""
	text = (text or "").strip()
	if len(text) < 2:
		return []

	like = f"%{text}%"
	out: dict[str, dict] = {}

	for row in frappe.get_all(
		"Contact",
		or_filters=[["email_id", "like", like], ["first_name", "like", like],
		            ["last_name", "like", like], ["company_name", "like", like]],
		fields=["full_name", "email_id", "company_name"],
		limit_page_length=int(limit),
	):
		if row.email_id:
			out[row.email_id.lower()] = {
				"email": row.email_id,
				"label": row.full_name or row.email_id,
				"company": row.company_name or "",
			}

	# Then anybody this person has actually corresponded with, which is what
	# makes the field useful on the second day rather than only once somebody
	# has built a contact list.
	from oneapp.oneapp_core.email import mailbox

	filters, or_filters = mailbox._filters("all")
	for row in frappe.get_all(
		"Communication",
		filters={**filters, "sender": ("like", like)},
		or_filters=or_filters,
		fields=["sender", "sender_full_name"],
		order_by="communication_date desc",
		limit_page_length=int(limit) * 4,
	):
		key = (row.sender or "").lower()
		if key and key not in out:
			out[key] = {
				"email": row.sender,
				"label": row.sender_full_name or row.sender,
				"company": "",
			}

	return list(out.values())[: int(limit)]
