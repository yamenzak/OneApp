"""Which records a message is about.

Mail in this product has always been a `Communication`, and a Communication has
always had somewhere to say what it is about. Nothing filled it in.
`inbound.handle_address` set `reference_doctype` from the address's `append_to`
and never `reference_name`, so `ap@` recorded that a message was about *a*
purchase invoice and not which one, and every reply inherited those two nulls.

## Two places to store a link, and both are used

`reference_doctype` / `reference_name` is Frappe's single link. It is what the
desk timeline reads, what `append_to` fills in, and what the framework's own
reply resolution sets. Keeping it is not compatibility theatre — a message with
a blank reference is invisible to half the framework.

`timeline_links` is the framework's child table of `Communication Link` rows,
and it is where several links live: a supplier statement naming eleven invoices
is one message about eleven documents, and `reference_name` can hold one of
them. So both are written — every link is a row, and the **first** link is also
the primary reference.

Each row carries how it was made, in `custom_linked_by`. A link nobody can
explain is a link nobody will trust, and the ones a model makes have to be
distinguishable from the ones a person made to be reviewable at all.

## What decides, and in what order

    thread    the conversation already has a reference — take it
    text      an id this site issues, written in the subject or the body

Exact first, then deterministic, then nothing. There is no guessing here and
deliberately so: the residue this leaves — prose that names no id — is what a
model is for, and a model is worth nothing until the cases it is not needed for
are already handled without it.

## What a link is not

A link is not a grant. A `Communication` is shared with the holders of the
address it arrived on, and linking it to a document must not make it readable to
everybody who can read that document — or filing a message against a project
becomes a way to publish somebody's mail to the workspace. Nothing here calls
`frappe.share`, and the record's own reader filters by the reader's access to
each message rather than to the record.
"""

import re

import frappe

from oneapp.oneapp_core import sync

# How a link was made. Written on every row, and the reason the model's own
# links will be reviewable when there are any. Two are made here and one by a
# person; a fourth for a model is what §6 of `docs/DOCUMENT-MAIL.md` is about.
BY_THREAD = "thread"
BY_TEXT = "text"
BY_MANUAL = "manual"

LINK_BY = "custom_linked_by"

# How much of a body is scanned for an id. A quoted reply carries every earlier
# message in it, and the ids in the quoted part were already found when the
# message that quoted them arrived.
SCAN_CHARS = 20000

# The shape of a document name after its series prefix: what Frappe's own
# `format:` and `naming_series` produce, plus the slashes a human writes.
TAIL = r"[A-Za-z0-9\-/]{1,32}"


def links_of(doc) -> list[dict]:
	"""Every record this message is about, as plain rows."""
	return [
		{
			"doctype": row.link_doctype,
			"name": row.link_name,
			"by": row.get(LINK_BY) or "",
		}
		for row in (doc.get("timeline_links") or [])
	]


def add(doc, doctype: str, name: str, by: str) -> bool:
	"""Note that this message is about one record.

	In memory, on a document not yet saved — `before_insert` is where this runs,
	so the link is part of the row being written rather than a second write and
	a second Version on a doctype people already find noisy.

	The first link is also the primary reference, because that is the one the
	framework reads. Later ones are rows only.
	"""
	if not (doctype and name):
		return False
	for row in doc.get("timeline_links") or []:
		if row.link_doctype == doctype and row.link_name == name:
			return False

	doc.append("timeline_links", {
		"link_doctype": doctype,
		"link_name": name,
		LINK_BY: by,
	})

	if not doc.get("reference_name"):
		doc.reference_doctype = doctype
		doc.reference_name = name
	return True


def place(doc) -> list[dict]:
	"""Work out what this message is about, and say so on it.

	Returns the links *this* made — read from the document rather than tracked,
	because at `before_insert` nothing else has touched `timeline_links` yet, and
	sorted so the caller writing provenance and the reader reading it agree.

	An empty list is the honest answer for a message about nothing, and is also
	the queue a model would later be given.
	"""
	before = {(row.link_doctype, row.link_name) for row in (doc.get("timeline_links") or [])}
	by = {}
	if from_thread(doc):
		by[BY_THREAD] = True
	if from_text(doc):
		by[BY_TEXT] = True
	if not by:
		return []

	return [
		one for one in links_of(doc)
		if (one["doctype"], one["name"]) not in before
	]


def from_thread(doc) -> bool:
	"""The conversation this message joins already knows what it is about.

	One query, exact, and it covers every reply in a conversation that was
	placed once — which is the great majority of messages, because mail about a
	record is nearly always a thread rather than a first contact.

	`custom_thread` rather than `in_reply_to`: the thread key is inherited down
	the whole chain by `email/threading.py`, so this finds the answer even where
	the reply arrived with its headers stripped and was threaded on the subject.
	"""
	from oneapp.oneapp_core.email.threading import THREAD_FIELD

	if doc.get("reference_name"):
		return False

	thread = doc.get(THREAD_FIELD)
	if not thread:
		return False

	earlier = frappe.get_all(
		"Communication",
		filters={
			THREAD_FIELD: thread,
			"reference_doctype": ["is", "set"],
			"reference_name": ["is", "set"],
		},
		fields=["reference_doctype", "reference_name"],
		order_by="creation asc",
		limit_page_length=1,
	)
	if not earlier:
		return False

	row = earlier[0]
	if not _granted(row.reference_doctype):
		return False
	return add(doc, row.reference_doctype, row.reference_name, BY_THREAD)


def from_text(doc) -> bool:
	"""Ids this site issues, written in the subject or the body.

	"Please find attached invoice 4471 against your PO-2025-0088" is the
	commonest inbound shape there is and the framework files it nowhere: its own
	subject scan only ever looks for a name inside `#(...)`, which is a token
	*we* put there and a stranger never will.

	We know every series this site issues — the doctypes are declared and the
	prefixes are on them — so the prefixes are a small, exact vocabulary to look
	for. Every candidate is then checked against the database, because a prefix
	match is a guess and `db.exists` is not.
	"""
	text = " ".join([
		str(doc.get("subject") or ""),
		_words(doc.get("content") or doc.get("text_content") or ""),
	])
	if not text.strip():
		return False

	added = False
	for prefix, doctypes in prefixes().items():
		for match in re.finditer(re.escape(prefix) + TAIL, text):
			token = match.group(0).rstrip("-/.,;:")
			for doctype in doctypes:
				if frappe.db.exists(doctype, token):
					added = add(doc, doctype, token, BY_TEXT) or added
					break
	return added


def prefixes() -> dict[str, list[str]]:
	"""Series prefix -> the granted doctypes named by it.

	Granted rather than every doctype on the site, the same scope the naming and
	printing settings use: a message must not be able to link itself to the
	platform's own bookkeeping because a stranger wrote a plausible id in a
	subject line.

	Cached, because it changes when a space is enabled or a series is edited and
	not between two messages arriving.
	"""
	key = "onespace_mail_series"
	found = frappe.cache().get_value(key)
	if found is not None:
		return found

	from oneapp.oneapp_core import naming

	found = {}
	for doctype in sorted(sync.granted_doctypes()):
		for option in naming.options(doctype):
			prefix = _literal(option.get("prefix") or "")
			if not prefix:
				continue
			found.setdefault(prefix, [])
			if doctype not in found[prefix]:
				found[prefix].append(doctype)

	frappe.cache().set_value(key, found, expires_in_sec=300)
	return found


# Autoname schemes that are not a series and have no prefix to look for.
# `naming.options` reports a doctype's raw `autoname` where it has no
# `naming_series` field, so `hash` and `field:title` arrive here as if they were
# templates — and `hash` as a prefix would match the word in any message.
NOT_A_SERIES = ("hash", "field:", "prompt", "autoincrement", "expression")


def _literal(series: str) -> str:
	"""The fixed head of a series template.

	`PINV-.YYYY.-` is `PINV-`, `ACC-JV-.YYYY.-` is `ACC-JV-`, `MR-{#####}` is
	`MR-`. Everything after the first placeholder varies per document and is
	what the tail pattern matches instead.

	Two characters minimum. A one-letter prefix would match a word.
	"""
	text = str(series).strip()
	if text.lower().startswith(NOT_A_SERIES):
		return ""
	# `format:CD-{#####}` is a series with a scheme in front of it, and the
	# scheme is not part of any document's name.
	if text.lower().startswith("format:"):
		text = text[len("format:"):]
	head = re.split(r"[.{#]", text, maxsplit=1)[0]
	return head if len(head) >= 2 else ""


def _words(html: str) -> str:
	"""A body as text, bounded, without its quoted history.

	The quoted part of a reply is every earlier message in the thread, and their
	ids were already found when those messages arrived. Scanning them again
	links a reply to everything the conversation ever mentioned.
	"""
	# `\n>` rather than a multiline `^>`: an inline flag in the middle of a
	# pattern is a `re.error` in Python 3.11, and this one would have been
	# swallowed by `on_insert` and silently turned text linking off.
	body = re.split(r"<blockquote|\n>\s|-----Original Message", html, maxsplit=1)[0]
	return re.sub(r"<[^>]+>", " ", body)[:SCAN_CHARS]


def _granted(doctype: str) -> bool:
	return doctype in sync.granted_doctypes()


def on_insert(doc, method=None):
	"""Place every new message, after it has been given its thread key.

	`before_insert`, and after `threading.on_insert` in the hook list, because
	`from_thread` reads the key that one writes.

	Never raises. A message that could not be placed is a message in the inbox;
	a message lost to a filing rule is the worst trade there is, and this is a
	filing rule.
	"""
	if doc.get("communication_medium") != "Email":
		return
	try:
		# Remembered on the document, because the rows this wrote will not
		# survive to `after_insert` — see `stamp`.
		doc._onespace_links = place(doc)
	except Exception:
		frappe.log_error(title="Mail linking failed", message=frappe.get_traceback())


def remember(message: str, doctype: str, name: str, by: str):
	"""Write how one link was made, after the document has been saved.

	`Communication.deduplicate_timeline_links` runs in `validate` — on every
	save, not only the first — and rebuilds every link row from
	`(link_doctype, link_name)` alone: it iterates a set of those pairs and
	calls `add_link` for each, so anything else the row carried is dropped.
	Setting provenance on the row therefore writes it and then watches the
	framework throw it away, silently, with the link itself intact.

	So it is written afterwards, straight onto the child row. `db.set_value`
	rather than another save, because another save would run the validation
	that just destroyed it.
	"""
	frappe.db.set_value(
		"Communication Link",
		{"parent": message, "link_doctype": doctype, "link_name": name,
		 "parenttype": "Communication"},
		LINK_BY,
		by,
		update_modified=False,
	)


def stamp(doc, method=None):
	"""Write how each link was made, once the framework has stopped rewriting them.

	For the links *this* made and no others — the contact links the framework
	adds are the framework's. See `remember` for why it is a second write.
	"""
	made = getattr(doc, "_onespace_links", None)
	if not made:
		return
	try:
		for link in made:
			remember(doc.name, link["doctype"], link["name"], link["by"])
	except Exception:
		frappe.log_error(title="Mail link provenance failed",
		                 message=frappe.get_traceback())
