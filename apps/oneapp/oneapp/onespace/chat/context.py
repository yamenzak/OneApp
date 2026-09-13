"""Where the question was asked from, and what that is allowed to change.

Opened from the rail, the assistant answers about the whole workspace. Opened
beside a quotation it should answer about *that* quotation — "is this priced
above the last one?" ought to work without anybody retyping which one.

Two things make that happen and they are different in kind.

The **space** is bound onto the tools. `Tool.bind` fills it in and takes it out
of the schema, so a chat opened in RUA is about RUA and the model has no word
for anywhere else.

The screen and the record are **told**, not bound: one sentence appended to the
system prompt for this run, naming them in the workspace's own words, so the
model knows what "this one" means.

The screen was bound too, for a while, and it was wrong. Pinning it reads as
safety and is not — permissions are the boundary, and a bound argument only
decides what the model can *name*. What it actually cost was answers: on a
project, "is there a quotation for this?" is an ordinary question and a pinned
screen makes it unanswerable. So the binding narrows to the space, which is a
real boundary in the product, and focus is left to the sentence.

Both are checked here first, through the same resolver a click goes through: a
space this reader cannot open throws, and a record that is not on the screen it
claims to be on is dropped. Context arrives from a browser, so it is an answer
to be verified rather than a premise.

**A file is the other kind of thing to be looking at**, and for a long time it
was the kind this module could not hear. A screen route carries a space and a
screen; `/one/docs/<id>`, `/one/sheets/<id>` and the Drive carry neither, so the
panel opened beside a scope of works knew nothing about it and "summarise this"
meant the whole workspace. A file context is one field, `file`, and it is told
rather than bound for the same reason the screen is: `read_document` already
takes a file id, so naming the file in the sentence is enough for the model to
go and read it, and binding would have narrowed a conversation that may
perfectly well wander to the record the document is about.
"""

import frappe

#: The fields a browser may send. Anything else is ignored rather than refused:
#: a stale URL carrying something we no longer read should still open a chat.
FIELDS = ("space", "screen", "docname", "file")


def read(on) -> dict:
	"""What the reader actually has open, out of what the browser claimed.

	Returns `{}` where there is nothing usable, which is the ordinary case —
	the assistant opened from the rail is not looking at anything.
	"""
	if isinstance(on, str):
		on = frappe.parse_json(on or "null")
	if not isinstance(on, dict):
		return {}

	space = str(on.get("space") or "").strip()
	screen = str(on.get("screen") or "").strip()
	if not space or not screen:
		return _file(on)

	from oneapp.onespace.spaceview.resolve import _resolve

	# Throws for a space this reader may not open, which is the same refusal the
	# browser would get, and is right: a chat opened against something you
	# cannot see is not a chat to quietly widen.
	resolved = _resolve(space, screen)
	if not resolved.get("doctype") or resolved.get("screen") != screen:
		return {}

	found = {
		"space": space,
		"screen": screen,
		"space_label": resolved.get("label") or space,
		"screen_label": resolved.get("screen_label") or screen,
		"singular": resolved.get("singular") or "record",
	}

	docname = str(on.get("docname") or "").strip()
	if docname:
		from oneapp.onespace.spaceview.records import record

		# By the screen's own rules rather than `get_doc`: a record this screen
		# would not list is not one it may name here either.
		row = record(space_code=space, screen=screen, name=docname)
		if row:
			found["docname"] = docname
			found["title"] = _title(resolved, row, docname)

	return found


def _file(on) -> dict:
	"""A document, a workbook or anything else in the Drive, if it is readable.

	Frappe's own check and not one of ours, which is the same door
	`r2.download` leans on: it already knows about a public file, the owner, a
	`DocShare`, and a file that hangs off a record the reader may see. A file
	this person cannot open narrows to nothing rather than throwing — unlike a
	space, because a stale `?ask=` link to a document somebody lost access to
	should still open a chat about the workspace, and a thrown error there is a
	red toast on a page that is otherwise working.

	The kind comes back too. "Summarise this" means something different for a
	workbook than for a scope of works, and the model should not have to spend
	a turn finding out which it has.
	"""
	name = str((on or {}).get("file") or "").strip()
	if not name:
		return {}

	# A file on a mounted host has no `File` row and nothing to read; the
	# assistant has no tool that could reach one either.
	from oneapp.onestorage.remote import is_remote

	if is_remote(name):
		return {}

	doc = frappe.db.get_value(
		"File", name, ["name", "file_name", "is_folder", "custom_kind"], as_dict=True,
	)
	if not doc or doc.is_folder:
		return {}

	row = frappe.get_doc("File", name)
	if not frappe.has_permission("File", "read", doc=row):
		return {}

	return {
		"file": doc.name,
		"file_name": doc.file_name or doc.name,
		"kind": doc.custom_kind or "",
		# Whether an answer could be put into it. Read here rather than assumed
		# from the kind: a document shared read-only is a document with nowhere
		# for a passage to go, and telling the model otherwise produces an
		# answer that offers something the reader cannot do.
		"writable": bool(frappe.has_permission("File", "write", doc=row)),
	}


def bound(toolbox: list, on: dict) -> list:
	"""The same tools, narrowed to the space that is open.

	Only onto the ones that take a space — `search_files` and `read_document`
	are about the Drive, which has no space, and binding an argument a tool does
	not declare is a TypeError a turn later.

	`list_spaces` goes: with one bound there is nothing for it to answer, and a
	tool that lists places its caller cannot then reach is an invitation to
	spend a turn finding that out.
	"""
	if not on.get("space"):
		return toolbox

	return [
		one.bind(space=on["space"]) if one.takes("space") else one
		for one in toolbox
		if one.name != "list_spaces"
	]


def note(on: dict) -> str:
	"""One sentence saying where this was asked from, for the system prompt.

	In the workspace's words rather than in codes: the reader sees "Quotations"
	and so should the answer. The codes are already bound onto the tools, which
	is where a machine name belongs.
	"""
	if on.get("file"):
		return _file_note(on)

	if not on.get("space"):
		return ""

	where = f'the {on["screen_label"]} screen of {on["space_label"]}'
	pinned = (
		f'Every tool you have is already scoped to {on["space_label"]}, and you '
		"cannot reach another space from here. You can still look at any screen "
		f"in {on['space_label']} — say which one you are looking at."
	)

	if on.get("docname"):
		return (
			f'The person asking has {on["title"]} open — one {on["singular"]} on '
			f'{where}. Read "this", "it" and "here" as that one unless they say '
			f"otherwise. {pinned}"
		)
	return (
		f'The person asking has {where} open. Read "this" and "here" as that '
		f"screen. {pinned}"
	)


#: What a kind is called in a sentence. `custom_kind` is a stored key and this
#: is the word for it — "Doc" is a column value and "document" is what a person
#: calls the thing. Anything unmapped falls back to "file", which is true.
KIND_WORD = {
	"Doc": "document", "Sheet": "workbook", "PDF": "PDF", "Image": "image",
	"Video": "video", "Audio": "audio recording", "Code": "source file",
	"Document": "document",
}


def _file_note(on: dict) -> str:
	"""One sentence for a file, and the one instruction that makes it useful.

	Naming the file is not enough on its own: the model has the id but no
	reason to spend a turn on `read_document` before answering, and an answer
	about a document nobody read is the failure this whole feature would be
	judged on. So the sentence says to read it first, once, and says when not
	to — a picture has no text and a turn spent proving that is a turn wasted.
	"""
	word = KIND_WORD.get(on.get("kind") or "", "file")
	opening = (
		f'The person asking has the {word} "{on["file_name"]}" open '
		f'(file id {on["file"]}). Read "this", "it" and "here" as that one '
		"unless they say otherwise."
	)

	# Only the kinds `read_document` can actually open — see `toolbox.py`. For
	# the rest there is nothing to read and the id is still worth having,
	# because a question may be about the file rather than about its contents.
	if on.get("kind") in ("Doc", "Code") or on.get("kind") == "":
		said = (
			f"{opening} Call read_document on that id before answering anything "
			"about what it says, rather than guessing from the name."
		)
		# The one instruction that turns "draft me a letter" from a chat reply
		# into something usable. A person can put an answer straight into the
		# document they have open — see `shared/lib/ai/insert.js` — so a draft
		# wrapped in "Sure, here's a draft:" is a draft they have to edit
		# before they can use it.
		if on.get("writable"):
			said += (
				" If they ask you to write or draft something for it, reply with"
				" the passage itself and nothing else — no preamble, no closing"
				" remark, no offer to revise it. They can put your answer"
				" straight into the document, and anything that is not the"
				" passage goes in with it."
			)
		return said
	return (
		f"{opening} You cannot read the contents of a {word}; answer from what "
		"you are told and from the workspace around it, and say so plainly if "
		"the question needs what is inside."
	)


def _title(resolved: dict, row: dict, docname: str) -> str:
	"""What the record is called on screen, falling back to its id.

	The screen's title column, because that is the words the reader is looking
	at. An id is a fair answer where there is no title — it is what the trail
	shows there too.
	"""
	field = (resolved.get("title_field") or "").strip()
	said = str(row.get(field) or "").strip() if field else ""
	return f"{said} ({docname})" if said and said != docname else docname
