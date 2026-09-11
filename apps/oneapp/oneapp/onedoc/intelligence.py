"""What a document asks a model for, and the material it hands over.

The verbs are not here. `onespace/ai/text.py` owns improve, proofread, shorten,
lengthen and tone for the whole product, and a document reaches them through
`rewrite` below with one thing added: a sentence saying what kind of writing
this is. Two copies of "improve this" would be two prompts to tune and two
settings rows to keep in step.

What is here is the three things only a document knows.

**Its own prose.** `body.load` is the store, and what reaches a model is the
text of the stored HTML rather than the ProseMirror JSON — a model asked to
read a node tree spends most of its input on `{"type":"paragraph"}`.

**What it is about.** A document in this product reads records:
`shared/binding.py` holds them, the prose renders tokens from them, and they
are the difference between "write the scope of works" producing a template and
producing *this* job's scope of works. So the bound records are described and
handed over as material, through `ai/index.describe` — the same description
the search index embeds, because "what this record is about, as text" is one
question and it already had an answer.

**Where the words go.** Three shapes, and they are three features because a
credit hold is priced off the declared ceiling:

    doc.compose   a passage, at the cursor
    doc.fill      the whole document, from its own headings
    text.rewrite  the selection, through the shared verbs

`doc.fill` is the one worth arguing about. It replaces a document, which is the
largest thing anything in this arc does — so it is undoable in the editor
before it is anything else, it writes nothing on the server, and the person
pressed a button whose label says what it will do.

And the fourth thing, which is retrieval rather than prompting: **which records
this document should be reading.** `suggest_sources` embeds the prose and asks
`ai/index.py` for the nearest records the reader may open. No model ranks
them — the person is looking at the list and clicking one, which is a better
judge than a confidence score, and the whole cost is one embedding.
"""

import re

import frappe
from frappe import _

from oneapp.onespace.ai import index, streaming, text as writing
from oneapp.onespace.ai.features import ai_feature

from . import body

#: Characters of the document that reach a model. A hundred-page contract is
#: past what any of these features is for: composing a paragraph needs the
#: register and the recent context, not the appendices.
MAX_PROSE = 30_000

#: Characters of each bound record. `describe` is already capped at 4,000 for
#: the index; a document may carry eight sources and all of them together
#: must still leave room for the prose.
MAX_SOURCE = 1_500

#: Candidates `suggest_sources` offers. A sidebar list somebody picks from,
#: not a ranking.
MAX_CANDIDATES = 6

COMPOSE_SYSTEM = """You write one passage to be inserted into a business \
document somebody is already writing.

Answer with the passage and nothing else. No preamble, no "here is", no \
heading unless you were asked for a section. Plain text: paragraphs separated \
by a blank line. No Markdown and no HTML — the editor owns the formatting, \
and asterisks arrive as asterisks.

Match the document. Its register, its person and its level of detail are the \
ones to write in; a passage that reads as if a different writer dropped it in \
is one somebody has to rewrite.

Use the material you were given and nothing else. Where a figure, a date, a \
name or a term is needed and is not in the material, leave a short bracketed \
gap like [date] rather than inventing one. A document goes out over somebody's \
name and a plausible invented figure is the one mistake that is not caught by \
reading it."""

FILL_SYSTEM = """You write out a business document from its own headings and \
the records it is about.

Answer with the whole document as plain text and nothing else. A heading is a \
line on its own; paragraphs are separated by a blank line. No Markdown, no \
HTML, no numbering you were not given — the editor owns all of that.

Keep the headings you were given, in the order you were given them, and write \
under each. Do not add sections nobody asked for and do not drop one because \
you have nothing to say about it: a heading with one honest line under it is \
better than a document that quietly lost a clause.

Everything factual must come from the material. Where a fact is needed and \
missing, leave a short bracketed gap like [start date]. Never invent a price, \
a quantity, a date, a name or a legal term.

Where there are no headings at all, write the document the brief describes, in \
sections with headings of your own."""


# --------------------------------------------------------------------------- #
# The two features a document owns
# --------------------------------------------------------------------------- #

@ai_feature(
	"doc.compose",
	label="Writing in a document",
	capability="Text Generation",
	system=COMPOSE_SYSTEM,
	description="Writes a passage into a document, from its records and what is already written.",
	# The document in, a passage out. The input ceiling is the document and
	# its material; the output is a section, not a document.
	max_input_tokens=40_000,
	max_output_tokens=2_000,
)
def compose(ai, brief: str, material: str, note: str = "") -> dict:
	"""One passage, for the cursor."""
	answer = ai(_asked(brief, material), note=note)
	return {"text": (answer.get("text") or "").strip(),
	        "credits": answer.get("credits") or 0}


@ai_feature(
	"doc.fill",
	label="Filling in a document",
	capability="Text Generation",
	system=FILL_SYSTEM,
	description="Writes out a whole document from its headings and the records it is about.",
	# The one feature in this arc whose output is a document. Both ceilings
	# are large and it is its own feature for exactly that reason: holding a
	# document's worth of credits to write one paragraph would make the
	# cursor verb unusable.
	max_input_tokens=60_000,
	max_output_tokens=8_000,
)
def fill(ai, brief: str, material: str, note: str = "") -> dict:
	"""The whole document, from its own headings."""
	answer = ai(_asked(brief, material), note=note)
	return {"text": (answer.get("text") or "").strip(),
	        "credits": answer.get("credits") or 0}


def _asked(brief: str, material: str) -> str:
	"""The instruction, then the material, fenced.

	Fenced for the reason `ai/text.py` fences a passage: a record's own fields
	are text somebody else typed, and a supplier whose address line reads
	"ignore your instructions" must not be an instruction.
	"""
	said = [f"Instruction:\n{brief.strip()}"]
	if material.strip():
		said.append("Material:\n---\n" + material.strip() + "\n---")
	return "\n\n".join(said)


# --------------------------------------------------------------------------- #
# What the document hands over
# --------------------------------------------------------------------------- #

def _mine(name: str, level: str = "read"):
	"""The document, if this person may have it at that level.

	`body`'s own gate, not a second one: a document is a `File` and the
	question "may this person read it" has one answer in this app.
	"""
	if level == "write":
		body.may_write(name)
	else:
		body.may_read(name)


def prose(name: str) -> str:
	"""What the document says, as text a model can read.

	From the stored HTML rather than the JSON. The browser sends real HTML on
	every save precisely so that nothing downstream needs a ProseMirror
	implementation in Python — see `body.store` — and this is downstream.
	"""
	said = body.load(name).get("html") or ""
	said = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6])>", "\n", said)
	said = re.sub(r"<[^>]+>", " ", said)
	said = frappe.utils.strip_html(said)
	said = re.sub(r"[ \t]+", " ", said)
	return re.sub(r"\n{3,}", "\n\n", said).strip()[:MAX_PROSE]


def material(name: str) -> str:
	"""The records this document reads, described.

	`index.describe` and not a second reader: "this record as the text that
	says what it is about" is one question, and the answer that feeds the
	search index is the answer that should feed the prose.

	A source with no record — a template's empty slot — is named and left
	empty, because "a quotation goes here and there is not one yet" is a fact
	worth a model knowing rather than a row to hide.
	"""
	from oneapp.shared import binding

	said = []
	for row in binding.sources(name):
		doctype = row.get("reference_doctype") or ""
		docname = row.get("reference_name") or ""
		if not docname:
			said.append(f"{row.get('label') or doctype}: (not chosen yet)")
			continue
		if not frappe.has_permission(doctype, "read", doc=docname):
			continue
		text, _title = index.describe(doctype, docname)
		if text:
			said.append(text[:MAX_SOURCE])
	return "\n\n".join(said)


def about(name: str) -> str:
	"""One sentence saying what kind of writing this is.

	Not translated, and for the reason `onemail/intelligence.py` gives: this
	is written at a model, in the language the rest of the prompt is in.
	"""
	title = frappe.db.get_value("File", name, "file_name") or "a document"
	from oneapp.shared import binding

	rows = [one for one in binding.sources(name) if one.get("reference_name")]
	said = (
		f'This is a business document called "{title}", written in a workspace '
		f"and read by a customer, a supplier or a colleague."
	)
	if rows:
		named = ", ".join(
			f"{one.get('reference_doctype')} {one.get('reference_name')}" for one in rows
		)
		said += f" It is about {named}."
	return said


def headings(name: str) -> list[str]:
	"""The document's own headings, in order.

	What `doc.fill` is filling *in*. Read from the stored HTML for the same
	reason `prose` is, and empty is a real answer: a blank document gets
	written from the brief instead.
	"""
	found = re.findall(r"(?is)<h[1-6][^>]*>(.*?)</h[1-6]>",
	                   body.load(name).get("html") or "")
	return [
		one for one in
		(frappe.utils.strip_html(re.sub(r"<[^>]+>", " ", raw)).strip() for raw in found)
		if one
	][:60]


# --------------------------------------------------------------------------- #
# Endpoints
#
# Each begins a run and hands back its id. None takes a model, a prompt or a
# limit: the verb is a key the server looks up, and the sentence saying what
# kind of document this is is written here rather than accepted.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def rewrite(name: str, verb: str, text: str = "", instruction: str = "",
            tone: str = "") -> dict:
	"""Do one of the writing verbs to a passage of this document.

	The passage comes from the browser, and that is deliberate: it is the
	selection, which exists in the editor and in no saved place. The
	*document* is still read here, to say what kind of writing this is.
	"""
	_mine(name, "write")
	writing.check(verb, tone)
	if verb != "write" and not (text or "").strip():
		frappe.throw(_("Select the words to work on first."))
	if verb == "write" and not (instruction or "").strip():
		frappe.throw(_("Say what to write."))

	return streaming.begin(
		writing.rewrite,
		label=_("Writing"),
		verb=verb,
		text=text,
		instruction=instruction,
		tone=tone,
		about=about(name),
	)


@frappe.whitelist(methods=["POST"])
def write_into(name: str, instruction: str) -> dict:
	"""Write a passage for the cursor, from this document and its records."""
	_mine(name, "write")
	if not (instruction or "").strip():
		frappe.throw(_("Say what to write."))

	said = prose(name)
	return streaming.begin(
		compose,
		label=_("Writing"),
		brief=instruction.strip(),
		material=_material_with_prose(name, said),
		note=about(name),
	)


@frappe.whitelist(methods=["POST"])
def fill_document(name: str, instruction: str = "") -> dict:
	"""Write out the whole document from its headings and its records.

	The largest thing in this arc, and the editor is what makes it safe: what
	arrives replaces the body in the browser, with one Undo, and nothing is
	saved until the person stops and leaves it there.
	"""
	_mine(name, "write")

	outline = headings(name)
	brief = (instruction or "").strip()
	if outline:
		brief = (brief + "\n\n" if brief else "") + "Headings:\n" + "\n".join(outline)
	elif not brief:
		frappe.throw(_("Give this document some headings, or say what it should say."))

	return streaming.begin(
		fill,
		label=_("Filling in"),
		brief=brief,
		material=material(name),
		note=about(name),
	)


def _material_with_prose(name: str, said: str) -> str:
	"""The records, and then what is already written.

	In that order: the records are facts and the prose is register. A model
	given the prose first writes more of it; given the facts first, it writes
	about them in that voice.
	"""
	parts = [one for one in (material(name),) if one]
	if said:
		parts.append("What the document says so far:\n" + said)
	return "\n\n".join(parts)


@frappe.whitelist(methods=["GET"])
def suggest_sources(name: str) -> list[dict]:
	"""Records this document might want to read, nearest first.

	Retrieval without ranking. `ai/index.py` answers "what is this text closest
	to" and the person picks from the answer, which is a better judge than a
	confidence score and costs one embedding rather than two calls.

	Filtered to what this reader can actually open — `spaceview.routes` plus
	Frappe's own read permission, the same pair `onemail/filing.py` uses — and
	to what this document is not already reading.
	"""
	_mine(name, "write")

	said = prose(name) or (frappe.db.get_value("File", name, "file_name") or "")
	if not said.strip():
		return []

	from oneapp.onespace import spaceview
	from oneapp.shared import binding

	already = {
		(one.get("reference_doctype"), one.get("reference_name"))
		for one in binding.sources(name)
	}

	try:
		near = index.nearest(said[-index.MAX_TEXT:], limit=MAX_CANDIDATES * 3)
	except Exception:
		# No index yet, or an embedding model the workspace switched off. An
		# empty list is a panel with nothing extra in it, which is what it
		# looked like before this existed.
		frappe.log_error(title="Document source retrieval failed",
		                 message=frappe.get_traceback())
		return []

	routes = spaceview.routes({one["doctype"] for one in near})
	found = []
	for one in near:
		if (one["doctype"], one["name"]) in already:
			continue
		if one["doctype"] not in routes:
			continue
		if not frappe.has_permission(one["doctype"], "read", doc=one["name"]):
			continue
		found.append({**one, **routes[one["doctype"]]})
		if len(found) >= MAX_CANDIDATES:
			break
	return found
