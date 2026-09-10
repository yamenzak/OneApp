"""A field of a record the document reads, inside the prose.

`docs/WRITER.md` §9. A quotation's covering letter is prose with the
quotation's numbers in it. Typed out, those numbers are a second copy that
goes stale the first time somebody changes the quotation, and the person who
finds out is the customer, holding a letter whose total disagrees with the
schedule stapled behind it.

Two things can be put in the prose, and they are different shapes:

    a token   an inline atom naming `source.field` — one phrase in a sentence
    a block   a real table naming `source.table` — the quotation's lines

Both are stored as *names*. A token also carries the last answer with it, so a
reader with no app behind them — the HTML export, a mail client — sees words
rather than holes.

**The stored text is a cache, and the server overwrites it on the way out.**
That is the permission rule, and it is worth being blunt about because the
first version got it wrong: the last answer used to be served exactly as
stored, so a field behind a permlevel that one person could resolve became
readable by everyone who could open the document. `sanitise` now runs on every
read — `get_doc`, the export, the print page — and replaces every token's text
with what *this* reader resolves, or with nothing. What is on disk is never
what is shown.

The one deliberate way a value crosses that line is `settle`: somebody who can
see the number chooses to fix it into the prose. That is the same act as
typing it, and it is theirs to make.
"""

import json
import re

import frappe

from ..shared import binding

#: A token in stored HTML. The source is optional: a document written before
#: it had more than one record has tokens with no source, and they mean the
#: first one — see `binding.source`.
TOKEN = re.compile(
	r'(<span\b[^>]*\bdata-record-field="([A-Za-z_][A-Za-z0-9_]*)"[^>]*>)(.*?)(</span>)',
	re.DOTALL,
)

#: The source attribute inside a token's opening tag, read separately so the
#: pattern above stays one shape whether or not it is there.
SOURCE_ATTR = re.compile(r'\bdata-record-source="([A-Za-z_][A-Za-z0-9_]*)"')

#: The node the editor stores in the ProseMirror JSON.
NODE = "recordField"

#: And the block. A child table is not a phrase in a sentence.
TABLE_NODE = "recordTable"

#: `quotation.grand_total`. One string because it keys a flat answer, and a
#: flat answer is what a browser patches from without walking a tree.
SEP = "."


def _at(source: str, field: str) -> str:
	return f"{source or binding.FIRST}{SEP}{field}"


# --------------------------------------------------------------------------- #
# What the prose names
# --------------------------------------------------------------------------- #

def named(content: str) -> dict:
	"""Every field and table the body names, as `{fields, tables}`.

	Read off the JSON rather than the HTML: the JSON is what the editor saved,
	the HTML is derived from it, and a document whose HTML is a save behind
	still resolves the right things.

	Each entry carries its source, because two sources of the same doctype can
	name the same field and mean different records.
	"""
	try:
		node = json.loads(content or "{}")
	except ValueError:
		return {"fields": [], "tables": []}

	fields, tables, seen = [], [], set()

	def walk(one):
		if isinstance(one, list):
			for kid in one:
				walk(kid)
			return
		if not isinstance(one, dict):
			return
		kind = one.get("type")
		if kind in (NODE, TABLE_NODE):
			attrs = one.get("attrs") or {}
			source = (attrs.get("source") or "").strip()
			what = attrs.get("field") if kind == NODE else attrs.get("table")
			what = (what or "").strip()
			if what and (kind, source, what) not in seen:
				seen.add((kind, source, what))
				if kind == NODE:
					fields.append({"source": source, "field": what})
				else:
					tables.append({"source": source, "table": what,
					               "columns": attrs.get("columns") or []})
		walk(one.get("content") or [])

	walk(node)
	return {"fields": fields, "tables": tables}


def values(doc: str, content: str = "", asked: dict | None = None) -> dict:
	"""What this document's tokens and blocks say right now.

	`asked` is the editor saying what is on screen, and it matters: the saved
	body is a debounce behind, so a token inserted a second ago is in the
	editor and not yet on disk. Narrowed by `binding.offer` downstream either
	way, so a browser naming a field it should not have is answered nothing
	rather than obeyed.

	Nothing here throws. A document whose record was deleted, or whose source
	names a doctype this person cannot read, still opens — with blanks where
	the numbers were, which is the honest thing for it to show.
	"""
	wanted = asked if asked else named(content or (frappe.db.get_value(
		"Doc Body", doc, "content") or ""))

	said, drawn, by_source = {}, {}, {}
	for one in wanted.get("fields") or []:
		by_source.setdefault(one.get("source") or "", []).append(one["field"])

	for key, fieldnames in by_source.items():
		where = binding.source(doc, key)
		if not where or not where.get("reference_name"):
			continue
		try:
			answered = binding.resolve(where["reference_doctype"],
			                           where["reference_name"], fieldnames)
		except Exception:
			frappe.clear_last_message()
			continue
		for field, one in (answered.get("fields") or {}).items():
			said[_at(key, field)] = one.get("text") or ""

	for one in wanted.get("tables") or []:
		key = one.get("source") or ""
		where = binding.source(doc, key)
		if not where or not where.get("reference_name"):
			continue
		try:
			drawn[_at(key, one["table"])] = binding.rows(
				where["reference_doctype"], where["reference_name"],
				one["table"], one.get("columns") or [],
			)
		except Exception:
			frappe.clear_last_message()

	return {"fields": said, "tables": drawn}


# --------------------------------------------------------------------------- #
# Rendering, and the rule that the stored text is never trusted
# --------------------------------------------------------------------------- #

def sanitise(content: str, said: dict) -> str:
	"""Every token's text replaced by what *this* reader resolves.

	The permission rule. A token's stored text was written by whoever last had
	the document open, and they may have been able to read a field this reader
	cannot — so what is on disk is never what is served. A field that does not
	resolve comes back empty rather than stale.

	A block's rows are emptied here too: they travel beside the body rather
	than in it, so that the same rule holds for a schedule.
	"""
	try:
		node = json.loads(content or "{}")
	except ValueError:
		return content or ""

	def walk(one):
		if isinstance(one, list):
			return [walk(kid) for kid in one]
		if not isinstance(one, dict):
			return one
		if one.get("type") == NODE:
			attrs = one.get("attrs") or {}
			key = _at(attrs.get("source") or "", attrs.get("field") or "")
			one = {**one, "attrs": {**attrs, "text": said.get(key, "")}}
		elif one.get("type") == TABLE_NODE:
			one = {**one, "attrs": {**(one.get("attrs") or {}), "rows": []}}
		if one.get("content"):
			one = {**one, "content": walk(one["content"])}
		return one

	return json.dumps(walk(node))


def fill(html: str, said: dict) -> str:
	"""Put the current text inside every token in this HTML.

	What the export and the print preview run. A token that did not resolve is
	emptied rather than left as it was — the same rule as `sanitise`, for the
	same reason.
	"""
	if not html:
		return ""

	def swap(found):
		opening, field = found.group(1), found.group(2)
		named_source = SOURCE_ATTR.search(opening)
		key = _at(named_source.group(1) if named_source else "", field)
		return opening + frappe.utils.escape_html(said.get(key, "")) + found.group(4)

	return TOKEN.sub(swap, html)


def freeze(html: str) -> str:
	"""Every token replaced by the text it says. After this it is prose.

	No resolution here on purpose — `fill` runs first if the caller wants the
	latest, and freezing is about *stopping*, not about refreshing.
	"""
	return TOKEN.sub(lambda found: found.group(3), html or "")


def frozen_content(content: str, said: dict | None = None) -> str:
	"""The same flattening, over the ProseMirror JSON the editor reads back.

	Both halves have to be done together or the document contradicts itself:
	the HTML is what search and export read, the JSON is what the editor
	loads, and a token frozen in one and live in the other comes back the
	moment somebody opens it.

	A block is left alone. Freezing a schedule would mean writing a real table
	into the prose, which is a larger thing than fixing a number and is not
	what anybody presses this for.
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
			key = _at(attrs.get("source") or "", attrs.get("field") or "")
			text = said.get(key, attrs.get("text") or "")
			# A text node with no marks: the same words, now typed rather than
			# named. An empty one is dropped — ProseMirror refuses a text node
			# with no text and would fail to load the document.
			return {"type": "text", "text": text} if text else None
		if one.get("content"):
			kept = [kid for kid in walk(one["content"]) if kid is not None]
			one = {**one, "content": kept}
		return one

	return json.dumps(walk(node))


def as_html(drawn: dict) -> dict:
	"""Each block's rows as a plain HTML table, for the export.

	Its own function because the export has no app behind it: the browser
	draws a block from `{columns, rows}` and a mail client cannot, so what
	leaves has to be a real `<table>`.
	"""
	made = {}
	for key, table in (drawn or {}).items():
		head = "".join(f"<th>{frappe.utils.escape_html(one['label'])}</th>"
		               for one in table.get("columns") or [])
		body = "".join(
			"<tr>" + "".join(f"<td>{frappe.utils.escape_html(cell or '')}</td>"
			                 for cell in row) + "</tr>"
			for row in table.get("rows") or []
		)
		made[key] = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
	return made


# --------------------------------------------------------------------------- #
# What the editor calls
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def refresh(name: str, asked: str | dict | None = None) -> dict:
	"""Ask the records again. What the Refresh control does.

	`asked` is what the editor has on screen — `{fields, tables}` in the shape
	`named` returns. Without it this reads the saved body, which is a debounce
	behind: a token inserted a second ago would not be in it.
	"""
	from . import body

	body._mine(name, "read")
	if isinstance(asked, str):
		asked = frappe.parse_json(asked) if asked.strip().startswith("{") else None
	if not isinstance(asked, dict):
		asked = None

	held = {"content": ""} if asked else body.load(name)
	return {"name": name, "sources": binding.file_sources(name),
	        **values(name, held["content"], asked)}


@frappe.whitelist(methods=["POST"])
def settle(name: str) -> dict:
	"""Freeze every token in this document, permanently.

	The records are asked once more first, so what is frozen is what they say
	at the moment of freezing rather than what the screen happened to be
	showing — somebody presses this because they are about to send the
	document.
	"""
	from . import body

	body._mine(name, "write")
	held = body.load(name)
	said = values(name, held["content"])["fields"]

	content = frozen_content(held["content"], said)
	html = freeze(fill(held["html"], said))
	head = body.store(name, content, html)

	return {"name": name, "head_seq": head, "content": content}
