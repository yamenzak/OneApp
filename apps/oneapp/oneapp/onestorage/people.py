"""Who owns a file, as a person rather than an address string.

Resolved against Frappe's own `Contact` and `Contact Email`, in one query per
page and never per row, and nothing leaves the site while a page is drawn: what
this serves is an image we hold, or initials. Moved here from the old mail
module when mail left for OneDesk; the file list was its last reader.
"""

import re

import frappe

# What a person is, once resolved. Kept small deliberately: this rides along
# with every row of a file list, and a fat profile per row is a page that
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
