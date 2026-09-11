"""A face on a contact and a logo on a company, fetched once and kept.

`people.py` says nothing leaves the site, and this is the amendment to that
rule rather than a hole in it. The thing it forbade is the one every other
product does: a Gravatar URL *in the page*, so that drawing a list of fifty
conversations tells a third party who fifty of the customer's correspondents
are, again on every render, from every reader's browser.

What happens here instead is one request, made by the server, the first time a
Contact is saved without a picture. What comes back is stored as a `File`
attached to that Contact, and every list afterwards serves our own bytes. The
correspondent list stays here; what leaves is a hash of one address and,
sometimes, one domain name — once per contact, ever.

What it costs, said plainly because nothing hides it behind a switch: a hash
of one address and, sometimes, one domain name go to Gravatar and to Google,
once per record, ever. A customer whose data-processing agreement enumerates
sub-processors should have those two on it. There is no setting, because a
workspace that wanted this off would be a workspace choosing initials over
faces, and nobody has.

## Where the picture comes from

**A person**: Gravatar, by the hash of their address, with `d=404`. The
default matters — Gravatar will happily generate an identicon, and a
procedural pattern is worse than the initials this product already draws well,
so a miss has to *be* a miss.

**An organisation**: Google's favicon service, by domain. Not a logo API and
not pretending to be one: it is the site's own icon, which for a company with
a website is their mark, and for one without is nothing. Free-mail domains are
skipped — `gmail.com` on every personal contact would be Google's envelope on
a third of somebody's address book.

## What it refuses

* **A picture somebody set.** Only an empty field is ever filled.
* **A second attempt.** A miss is recorded on the record, so a contact with no
  Gravatar is not one request per save for the rest of its life. `refresh()`
  is the way to ask again, and it is a person pressing something.
* **Anything but a small image** from those two hosts: https only, the host
  matched against a fixed pair, 256 KB, one short timeout, and a content type
  that has to start `image/`.
"""

import hashlib
import re
from urllib.parse import urlparse

import frappe
from frappe import _

#: Where a miss is remembered, so it is asked once rather than every save.
TRIED_FIELD = "custom_face_tried"

GRAVATAR = "https://www.gravatar.com/avatar/{hash}?s=200&d=404"

#: Google's favicon service, at the address `google.com/s2/favicons` is a 301
#: to — one request rather than two, and no redirect policy to get right.
#: A domain with no icon answers **404** with a grey globe in the body, which
#: the status check below refuses: the globe is the favicon service's `d=404`
#: and is exactly as unwanted as Gravatar's identicon.
FAVICON = (
	"https://t3.gstatic.com/faviconV2"
	"?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&size=128&url=https://{domain}"
)

#: The only two hosts this will talk to. A fixed pair rather than a validated
#: URL is the whole SSRF answer here: nothing a customer types decides where
#: the request goes, only what is in the query string.
HOSTS = {"www.gravatar.com", "t3.gstatic.com"}

MAX_BYTES = 256 * 1024
CONNECT_TIMEOUT = 3
READ_TIMEOUT = 4

#: Domains where the favicon is the mail provider's and not the person's firm.
#: Not exhaustive and does not need to be — a wrong logo here is one contact
#: wearing Google's envelope, and the list covers what an address book is
#: actually full of.
PUBLIC_MAIL = {
	"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "hotmail.co.uk",
	"live.com", "msn.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "icloud.com",
	"me.com", "mac.com", "aol.com", "proton.me", "protonmail.com", "pm.me",
	"gmx.com", "gmx.de", "gmx.net", "web.de", "mail.com", "zoho.com",
	"fastmail.com", "hey.com", "tutanota.com", "tuta.com", "yandex.com",
	"yandex.ru", "mail.ru", "qq.com", "163.com", "126.com", "naver.com",
	"hanmail.net", "daum.net", "rediffmail.com", "emirates.net.ae", "eim.ae",
}

#: Which doctypes get one, and how to read a person and a domain off each.
#: A table rather than four branches, because the next one somebody asks for —
#: `Customer`, `Supplier` — is a row and not a function.
KINDS = {
	"Contact": {"field": "image", "email": "email_id", "domain": None},
	"Company": {"field": "company_logo", "email": "email", "domain": "website"},
}


# --------------------------------------------------------------------------- #
# The hook
# --------------------------------------------------------------------------- #

def on_save(doc, method=None):
	"""Queue a look, where there is anything to look for.

	`after_insert` and `on_update` both, because a contact is very often
	created with no address and given one a minute later — and the save that
	adds the address is the first moment there is a question to ask.

	Enqueued rather than fetched here: a save must not wait on two foreign
	hosts, and a contact imported in a batch of four hundred must not be four
	hundred requests inside one transaction.
	"""
	if doc.doctype not in KINDS:
		return
	if not _wanted(doc):
		return

	frappe.enqueue(
		"oneapp.onemail.faces.fetch",
		queue="short",
		doctype=doc.doctype,
		name=doc.name,
		enqueue_after_commit=True,
	)


def _wanted(doc) -> bool:
	"""Whether this record is missing a picture and has not been asked about."""
	shape = KINDS[doc.doctype]
	if doc.get(shape["field"]):
		return False
	if doc.get(TRIED_FIELD):
		return False
	return bool(_address(doc) or _domain(doc))


# --------------------------------------------------------------------------- #
# The fetch
# --------------------------------------------------------------------------- #

def fetch(doctype: str, name: str) -> str:
	"""Find a picture for one record and attach it. The file url, or "".

	Runs in a worker. Re-reads the document rather than trusting what was
	queued: between the save and the job somebody may have set a picture by
	hand, and overwriting that would be the one unforgivable thing here.
	"""
	if doctype not in KINDS:
		return ""
	if not frappe.db.exists(doctype, name):
		return ""

	doc = frappe.get_doc(doctype, name)
	if not _wanted(doc):
		return ""

	shape = KINDS[doctype]
	found = _look(doc)

	# Written whether or not anything was found, and that is the point: a
	# contact with no Gravatar and no website must not be two foreign requests
	# every time somebody edits their phone number.
	doc.db_set(TRIED_FIELD, frappe.utils.now(), update_modified=False)
	if not found:
		return ""

	content, suffix = found
	return _attach(doc, shape["field"], content, suffix)


def _look(doc):
	"""The bytes and a file suffix, or `None`. Person first, then the firm."""
	address = _address(doc)
	if address:
		got = _get(GRAVATAR.format(hash=_gravatar_hash(address)))
		if got:
			return got

	domain = _domain(doc)
	if domain:
		return _get(FAVICON.format(domain=domain))
	return None


def _gravatar_hash(address: str) -> str:
	"""Gravatar's own rule: trimmed, lowercased, SHA-256.

	Their MD5 form still answers and is the one most code uses; this is the
	one they document now, and there is no reason to ship a new caller on the
	old digest.
	"""
	return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()


def _address(doc) -> str:
	value = (doc.get(KINDS[doc.doctype]["email"]) or "").strip().lower()
	return value if "@" in value else ""


def _domain(doc) -> str:
	"""The organisation's domain, from a website field or from an address.

	A free-mail address is not an organisation, so it answers nothing — the
	person still gets their Gravatar, and their contact card does not get
	Google's envelope on it.
	"""
	shape = KINDS[doc.doctype]
	if shape["domain"]:
		site = (doc.get(shape["domain"]) or "").strip()
		if site:
			host = urlparse(site if "//" in site else f"https://{site}").hostname or ""
			host = host.lower().removeprefix("www.")
			if _plausible(host):
				return host

	address = _address(doc)
	if not address:
		return ""
	host = address.rsplit("@", 1)[-1]
	if host in PUBLIC_MAIL or not _plausible(host):
		return ""
	return host


def _plausible(host: str) -> bool:
	"""A registrable-looking name, and nothing that could steer a request.

	The host only ever lands in a query string on a host we chose, so this is
	not the SSRF check — that is `HOSTS`. It is here so a typo in a website
	field is not a pointless round trip.
	"""
	return bool(re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9-]+)+", host or ""))


def _get(url: str):
	"""One small image from one of two known hosts. `(bytes, suffix)` or None."""
	parsed = urlparse(url)
	if parsed.scheme != "https" or parsed.hostname not in HOSTS:
		return None

	try:
		import requests

		answer = requests.get(
			url,
			timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
			stream=True,
			allow_redirects=False,
		)
		if answer.status_code != 200:
			return None

		kind = (answer.headers.get("Content-Type") or "").split(";")[0].strip().lower()
		if not kind.startswith("image/"):
			return None

		content = answer.raw.read(MAX_BYTES + 1, decode_content=True)
		if not content or len(content) > MAX_BYTES:
			return None
	except Exception:
		frappe.logger("oneapp").debug(f"no picture from {parsed.hostname}", exc_info=True)
		return None

	return content, {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
	                 "image/webp": "webp", "image/svg+xml": "svg"}.get(kind, "png")


def _attach(doc, field: str, content: bytes, suffix: str) -> str:
	"""Store it as a File on the record, and point the field at it.

	Both, and the second one is not redundant however much it looks it.
	`attached_to_field` is what makes the File know which field it belongs to
	— it is how a later rename or a change of privacy keeps the field in step,
	and it is what `frappe.core.api.file.upload_file` sets. What Frappe does
	*not* do is write the field on insert: that branch only runs when a file
	url actually changes. So the picture would be an attachment on the contact
	with nothing drawing it, which is how this was wrong the first time.

	Private, because a contact's face is the workspace's business. Frappe
	serves a private file behind a permission check on the record it hangs
	off, which is exactly the check that should govern it.
	"""
	stored = frappe.get_doc({
		"doctype": "File",
		"file_name": f"{frappe.scrub(doc.name)[:60]}-{field}.{suffix}",
		"attached_to_doctype": doc.doctype,
		"attached_to_name": doc.name,
		"attached_to_field": field,
		"is_private": 1,
		"content": content,
	}).insert(ignore_permissions=True)

	doc.db_set(field, stored.file_url, update_modified=False)
	return stored.file_url


# --------------------------------------------------------------------------- #
# Asking again
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def refresh(doctype: str, name: str) -> dict:
	"""Look again, for somebody who changed their website or grew a Gravatar.

	The escape hatch from the tried-once rule, and it is a person pressing
	something rather than a schedule: re-asking two foreign hosts about every
	contact on a timer is the traffic this whole design is arranged to avoid.
	"""
	if doctype not in KINDS:
		frappe.throw(_("{0} does not carry a picture.").format(doctype))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	doc.db_set(TRIED_FIELD, None, update_modified=False)

	url = fetch(doctype, name)
	return {"ok": True, "image": url, "found": bool(url)}
