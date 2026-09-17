"""What a model may ask a document to be.

One kind: **write this, as a document, and attach it to that record.** It is
the first thing in this product a model can ask for that produces a *file*
rather than a field, and the reason it is worth its own kind rather than being
a clever use of `record.save` is that it is the only shape of request where
what the person is agreeing to is prose somebody has to read before it goes
out over their name.

So the prose is written on the turn it is proposed, not on Apply. Two reasons
and the second is the one that matters:

* **A card shows what would happen.** `actions.py`'s whole argument is that a
  person agrees to the diff and not to a summary of it. A card that said
  "write a letter about this employee" and then produced four paragraphs
  nobody had seen would be the summary, and the four paragraphs would be the
  thing that actually happened.
* **Apply is a request a person made, and it should be short.** A model call
  inside Apply is thirty seconds of a person watching a spinner, a credit hold
  taken against a press rather than against a question, and a failure mode
  where the card says Failed for a reason that has nothing to do with them.

What Apply does is `writing.make` — the same call the New menu posts to — and
then `body.store`. Nothing privileged: a document lands in the asker's Home
folder as theirs, attached to the record only where they may write to it,
which `writing._may_attach` decides exactly as it does for a person pressing
New inside that record's room.

`docs/DESKTOP.md` has the other half of this: the applied card carries a way
in, and a document opens in a window rather than taking the page away.
"""

import re
from typing import Annotated

import frappe
from frappe import _

from oneapp.oneai import proposing
from oneapp.oneai.actions import Kind, Refused, register
from oneapp.oneai.tools import Tool, tool

#: Characters of prose one card may carry. A letter, a certificate, a summary,
#: a scope of works — all of them fit. What does not is a model that has
#: decided to write a book, and a card nobody scrolls to the end of is a card
#: nobody read before pressing Apply.
MAX_PROSE = 20_000

#: Characters shown on the card itself. The rest is there and is applied; this
#: is how much of it the panel draws, which is 384px wide.
PREVIEW = 600


class WriteDocument(Kind):
	"""A document, written and waiting to be made."""

	key = "document.write"
	label = _("Write a document")
	icon = "lucide-file-text"

	def check(self, payload: dict) -> dict:
		title = (payload.get("title") or "").strip()
		if not title:
			raise Refused(_("Say what the document is called."))

		said = (payload.get("text") or "").strip()
		if not said:
			raise Refused(_("Write the document. An empty one is not worth "
			                "asking somebody to approve."))
		if len(said) > MAX_PROSE:
			raise Refused(_("That is longer than one document may be written "
			                "in a single suggestion."))

		doctype = (payload.get("doctype") or "").strip()
		docname = (payload.get("docname") or "").strip()
		if doctype and docname:
			# Asked now rather than on Apply, which is the difference between
			# the model being told and a person being told after they agreed
			# to something that was never going to happen.
			if not frappe.db.exists(doctype, docname):
				raise Refused(_("There is no {0} called {1}.").format(doctype, docname))
			if not frappe.has_permission(doctype, "write", doc=docname):
				raise Refused(_("That record is not yours to attach anything to."))
		else:
			doctype = docname = ""

		return {"title": title[:280], "text": said,
		        "doctype": doctype, "docname": docname}

	def summarise(self, payload: dict, before: dict) -> str:
		if payload.get("docname"):
			return _("Write {0} and file it on {1}").format(
				payload["title"], self._called(payload))
		return _("Write {0}").format(payload["title"])

	def rows(self, payload: dict, before: dict) -> list[dict]:
		said = [{"label": _("Title"), "now": payload["title"]}]
		if payload.get("docname"):
			said.append({"label": _("About"), "now": self._called(payload)})
		said.append({"label": _("Document"), "now": self._preview(payload["text"])})
		return said

	def apply(self, payload: dict, before: dict) -> dict:
		from . import body, writing

		made = writing.make(
			title=payload["title"],
			doctype=payload.get("doctype") or "",
			docname=payload.get("docname") or "",
		)
		content = body.from_text(payload["text"])
		body.store(made["name"], content, body.html_of(content))
		return {"doctype": "File", "name": made["name"]}

	def opened(self, payload: dict, done: dict) -> dict:
		"""Where the document it made is. See `actions.Kind.opened`."""
		if not done.get("name"):
			return {}
		return {"label": _("Open it"), "file": done["name"], "kind": "Doc",
		        "title": payload["title"]}

	# --- what the record is called, which is not its id --------------------

	@staticmethod
	def _called(payload: dict) -> str:
		"""The record's title, or its id where it has none to show.

		`get_cached_value` on the title field rather than the whole document:
		this is drawn every time the card is listed, and a card in a thread
		is listed on every turn of it.
		"""
		doctype, docname = payload.get("doctype") or "", payload.get("docname") or ""
		if not (doctype and docname):
			return ""
		try:
			title = frappe.get_meta(doctype).get_title_field()
			said = frappe.db.get_value(doctype, docname, title) if title else ""
		except Exception:
			said = ""
		said = (said or "").strip()
		return f"{said} ({docname})" if said and said != docname else docname

	@staticmethod
	def _preview(said: str) -> str:
		"""The opening, on one card. A letter reads from the top.

		Paragraph breaks kept and everything else collapsed. Flattening the
		lot was the first version and it read as one run — "To whom it may
		concern, This is to certify that…" — which is the wrong shape for the
		one thing on this card somebody is actually meant to read.
		"""
		paragraphs = [" ".join(one.split())
		              for one in re.split(r"\n\s*\n", said or "")]
		flat = "\n".join(one for one in paragraphs if one)
		return flat if len(flat) <= PREVIEW else flat[:PREVIEW].rstrip() + "…"


register(WriteDocument())


# --------------------------------------------------------------------------- #
# The tool that asks for one
#
# Beside the kind rather than in `onespace/ai/proposing.py`, which holds the
# four the spine ships with: a document belongs to OneWriter, and the rule in
# `docs/ARCHITECTURE.md` is that a module owns both halves of its own feature.
# `onemail/intelligence.py` does the same for filing a message.
# --------------------------------------------------------------------------- #


@tool
def propose_document(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	title: Annotated[str, "What the document is called — what a person would "
	                      "see in a folder. No file extension."],
	text: Annotated[
		str,
		"The whole document, written out. Plain text: paragraphs separated by "
		"a blank line, single newlines inside a paragraph for an address block "
		"or a signature. No Markdown and no HTML — asterisks arrive as "
		"asterisks. Where a figure, a date or a name is needed and you were "
		"not given it, leave a short bracketed gap like [date] rather than "
		"inventing one.",
	],
) -> dict:
	"""Write a document and ask to file it. Nothing is made until the person approves.

	Read the record first, with read_record, and write from what it actually
	says. The document is attached to whatever the person has open, so a letter
	about an employee is filed on that employee without anybody saying so
	twice.

	Write the whole thing, not a description of it: the person is shown the
	prose and presses Apply, so a summary is a summary of something that does
	not exist yet. Afterwards, say what you have written and that it is waiting
	— do not say it is filed, because it is not.
	"""
	return proposing.ask("document.write", session, about_doctype, about_name, {
		"title": title, "text": text,
		"doctype": about_doctype or "", "docname": about_name or "",
	})


def tools() -> list[Tool]:
	"""What `onespace_chat_tools` asks this module for."""
	return [propose_document]
