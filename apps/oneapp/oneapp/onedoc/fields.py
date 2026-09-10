"""A field of the record, inside the prose.

`docs/WRITER.md` §8: a quotation's covering letter is prose with the
quotation's numbers in it. Typed out, those numbers are a second copy that
goes stale the first time somebody changes the quotation — and the person who
finds out is the customer, holding a letter whose total disagrees with the
schedule stapled behind it.

So a document bound to a record (`shared/binding.py`) may carry **field
tokens**: an inline node that is not text but a name, rendered from the record
every time the document is read. `RecordField` in the editor, and

    <span data-record-field="grand_total">AED 144,235.00</span>

on the way out. The text inside is the last answer and is what a reader sees
if nothing resolves it — a mail client, a word processor, a browser with the
site unreachable — which is why it is written into the markup at all rather
than left as an empty span for JavaScript to fill.

**Live until it is issued.** A draft resolves on every read. `freeze` is the
other half: it replaces every token with the text it currently says, and after
that the document is prose. That is what export does, and what the button on
the editor does, because a document that has been sent must never change
afterwards — a quotation the customer received is a fact about a day, not a
view onto a record that has moved on since.
"""

import json
import re

import frappe

from ..shared import binding

#: The token as it appears in stored HTML. Deliberately a narrow pattern over
#: a parser: this runs on every read of every bound document, the markup is
#: ours rather than a paste, and a regular expression that only matches what
#: `toDOM` writes cannot be talked into matching something else.
#:
#: Non-greedy over the inner text, and `.` matches a newline, because the
#: editor may wrap a long formatted value.
TOKEN = re.compile(
	r'(<span\b[^>]*\bdata-record-field="([A-Za-z_][A-Za-z0-9_]*)"[^>]*>)(.*?)(</span>)',
	re.DOTALL,
)

#: The node the editor stores in the ProseMirror JSON.
NODE = "recordField"


def named(content: str) -> list[str]:
	"""Every field this document's body names, in the order it first names them.

	Read off the JSON rather than the HTML: the JSON is what the editor saved
	and the HTML is derived from it, so a document whose HTML is a save behind
	still resolves the right fields.
	"""
	try:
		node = json.loads(content or "{}")
	except ValueError:
		return []

	found: list[str] = []

	def walk(one):
		if isinstance(one, list):
			for kid in one:
				walk(kid)
			return
		if not isinstance(one, dict):
			return
		if one.get("type") == NODE:
			field = ((one.get("attrs") or {}).get("field") or "").strip()
			if field and field not in found:
				found.append(field)
		walk(one.get("content") or [])

	walk(node)
	return found


def values(doc: str, content: str = "", asked: list | None = None) -> dict:
	"""What this document's tokens say right now.

	`{fieldname: text}` and nothing else — the editor renders text, and the
	number half of `binding.resolve` is the workbook's business.

	`asked` is the editor saying which fields are on screen, and it matters:
	the saved body is a debounce behind what somebody is looking at, so a
	token inserted a second ago is in the editor and not yet on disk. Reading
	the stored body instead left every freshly inserted field showing an em
	dash until the next save *and* the next refresh. Narrowed by
	`binding.offer` downstream either way, so a browser naming a field it
	should not have is answered nothing rather than obeyed.

	An empty answer is the ordinary one: most documents are bound to nothing,
	and one bound to a record whose fields nobody named has nothing to ask.
	Nothing here throws — a document whose record was deleted still opens, with
	its tokens showing what they last said.
	"""
	where = binding.bound(doc)
	if not where.get("name"):
		return {}

	if asked:
		wanted = [str(one) for one in asked if one][:binding.MAX_FIELDS]
	else:
		wanted = named(content if content else (frappe.db.get_value(
			"Doc Body", doc, "content") or ""))
	if not wanted:
		return {}

	try:
		answered = binding.resolve(where["doctype"], where["name"], wanted)
	except Exception:
		frappe.clear_last_message()
		return {}

	return {name: said.get("text") or ""
	        for name, said in (answered.get("fields") or {}).items()}


def fill(html: str, said: dict) -> str:
	"""Put the current text inside every token in this HTML.

	What the export and the print preview run, so a document that leaves is a
	document that agrees with the record as of the moment it left. A token
	naming a field that did not resolve keeps what it had, which is the whole
	reason the last answer is stored in the markup.
	"""
	if not html or not said:
		return html or ""

	def swap(found):
		field = found.group(2)
		if field not in said:
			return found.group(0)
		return found.group(1) + frappe.utils.escape_html(said[field] or "") + found.group(4)

	return TOKEN.sub(swap, html)


def freeze(html: str) -> str:
	"""Every token replaced by the text it says. After this it is prose.

	No resolution here on purpose — `fill` runs first if the caller wants the
	latest, and freezing is about *stopping*, not about refreshing. Splitting
	the two means "freeze what is on the screen" and "freeze what the record
	says now" are both expressible, and the caller decides which it meant.
	"""
	return TOKEN.sub(lambda found: found.group(3), html or "")


def frozen_content(content: str, said: dict | None = None) -> str:
	"""The same flattening, over the ProseMirror JSON the editor reads back.

	Both halves have to be done together or the document contradicts itself:
	the HTML is what search and export read, the JSON is what the editor loads,
	and a token frozen in one and live in the other comes back the moment
	somebody opens it.
	"""
	try:
		node = json.loads(content or "{}")
	except ValueError:
		return content or ""

	said = said or {}

	def walk(one):
		if isinstance(one, list):
			return [walk(kid) for kid in one]
		if not isinstance(one, dict):
			return one
		if one.get("type") == NODE:
			attrs = one.get("attrs") or {}
			field = (attrs.get("field") or "").strip()
			text = said.get(field, attrs.get("text") or "")
			# A text node with no marks: the same words, now typed rather than
			# named. An empty one is dropped — ProseMirror refuses a text node
			# with no text and would fail to load the document.
			return {"type": "text", "text": text} if text else None
		if one.get("content"):
			kept = [kid for kid in walk(one["content"]) if kid is not None]
			one = {**one, "content": kept}
		return one

	return json.dumps(walk(node))


# --------------------------------------------------------------------------- #
# What the editor calls
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def refresh(name: str, asked: str | list | None = None) -> dict:
	"""Ask the record again. What the Refresh control on a bound document does.

	Its own endpoint rather than part of opening the document, because the
	whole point is asking a second time — the document has been open for an
	hour and somebody wants to know whether the total moved.

	`asked` is the field list the editor has on screen. Without it this reads
	the saved body, which is a debounce behind: a token inserted a second ago
	would not be in it, and the field somebody just added would show an em
	dash until the next save.
	"""
	from . import body

	body._mine(name, "read")
	if isinstance(asked, str):
		asked = frappe.parse_json(asked) if asked.strip().startswith("[") else \
			[one.strip() for one in asked.split(",") if one.strip()]
	if not isinstance(asked, list):
		asked = []

	held = body.load(name) if not asked else {"content": ""}
	return {"name": name, "bound": binding.bound(name),
	        "fields": values(name, held["content"], asked)}


@frappe.whitelist(methods=["POST"])
def settle(name: str) -> dict:
	"""Freeze every token in this document, permanently.

	The record is asked once more first, so what is frozen is what the record
	says at the moment of freezing rather than what the screen happened to be
	showing — somebody presses this because they are about to send the
	document, and the last thing they want kept is an hour-old number.
	"""
	from . import body

	body._mine(name, "write")
	held = body.load(name)
	said = values(name, held["content"])

	content = frozen_content(held["content"], said)
	html = freeze(fill(held["html"], said))
	head = body.store(name, content, html)

	return {"name": name, "head_seq": head, "content": content}
