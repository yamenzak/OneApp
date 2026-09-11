"""What mail asks a model for, and the sentence it says about itself first.

The verbs themselves are not here. `onespace/ai/text.py` owns summarising and
rewriting for the whole product, because a summary in a mail thread and a
summary in a document differ in their subject and in nothing else, and two
copies would be two prompts to tune and two settings rows to keep in step.

What is here is the three things only mail knows.

**Which text.** A thread is a permission question before it is a prompt:
`mailbox.thread` decides which messages this person may read and this module
reads no other way. The quoted history is cut out of every reply, because a
ten-message thread otherwise arrives as the same ten messages ten times and
the model pays for all of it.

**What it is.** `about` is one sentence — who is writing to whom, on which
address, about what — and it travels as the gateway's `note`, which lands
after our instructions and after the workspace's own addendum. It is the
difference between "improve this" producing a business reply and producing a
blog post.

**Answering, which is mail's alone.** `mail.reply` is a declared feature of
its own rather than `text.rewrite` with a long instruction: what makes a
suggested reply good is matching the register of a thread, answering the
question actually asked, and stopping — and none of that is a rewrite of
anything.

Nothing here sends, files, or saves. A summary lands in a panel; a suggested
reply opens the composer with the words in it and a person presses Send.
"""

import re

import frappe
from frappe import _

from oneapp.onespace.ai import streaming, text as writing
from oneapp.onespace.ai.features import ai_feature

#: Messages of a thread a summary reads. A conversation longer than this is one
#: where the last forty are the ones that matter.
MAX_MESSAGES = 40

#: Characters taken from one message. A bounded body per message rather than a
#: bounded thread, so one enormous forwarded chain cannot crowd out the reply
#: underneath it.
MAX_BODY = 6_000

REPLY_SYSTEM = """You draft a reply to an email, for the person who received \
it to read, edit and send under their own name.

Answer with the body of the reply and nothing else. No subject line, no \
greeting line you were not given a name for, no signature, no "here is a \
draft" — and no Markdown or HTML. Paragraphs are separated by a blank line.

Match the thread. Its register, its language and its length are the ones to \
write in: a two-line question gets a two-line answer, and a formal supplier \
letter does not get answered chattily.

Answer what was actually asked. Address the last message's questions in the \
order they were asked, and say nothing about anything else.

Never commit to a fact you were not given. No prices, no dates, no quantities \
and no promises that are not already in the thread — where one is needed and \
missing, leave a short bracketed gap like [date] for the writer to fill. A \
draft with a hole in it is editable; a draft with an invented delivery date is \
a mistake that goes out over somebody's name.

If the last message needs no reply, say so in one line."""


@ai_feature(
	"mail.reply",
	label="Suggested replies",
	capability="Text Generation",
	system=REPLY_SYSTEM,
	description="Drafts a reply to a conversation, for a person to edit and send.",
	# A thread in, a message out. Between the two shapes in `ai/text.py`, and
	# its own feature because the prompt is about answering rather than
	# rewriting — see the module docstring.
	max_input_tokens=60_000,
	max_output_tokens=1_200,
)
def draft_reply(ai, conversation: str, about: str = "") -> dict:
	"""One reply, drafted from the thread."""
	answer = ai(conversation, note=about)
	return {"text": (answer.get("text") or "").strip(), "credits": answer.get("credits") or 0}


# --------------------------------------------------------------------------- #
# Reading a thread, as text and as a sentence about itself
# --------------------------------------------------------------------------- #

def _plain(html: str) -> str:
	"""A message body as text, without its quoted history.

	The split is `linking._words`' — the same three markers, for the same
	reason — and the rest is not: that one is scanning for ids and can afford
	to collapse a document into one line, and this is text a model reads, where
	a paragraph break is meaning.
	"""
	body = re.split(r"<blockquote|\n>\s|-----Original Message", html or "", maxsplit=1)[0]
	# Block ends become newlines before the tags go, or every message arrives
	# as one paragraph however it was written.
	body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6])>", "\n", body)
	body = re.sub(r"<[^>]+>", " ", body)
	body = frappe.utils.strip_html(body)
	body = re.sub(r"[ \t]+", " ", body)
	body = re.sub(r"\n{3,}", "\n\n", body)
	return body.strip()[:MAX_BODY]


def _conversation(key: str, folder: str = "all") -> tuple[str, str, list]:
	"""One thread as (text, about, rows), through the ordinary permission path.

	`mailbox.thread` is what the reader's own browser calls, so a thread this
	person may not open comes back empty here exactly as it would there. There
	is no second query and no `ignore_permissions` anywhere in this module.
	"""
	from oneapp.onemail import mailbox

	rows = mailbox.thread(key, folder)[-MAX_MESSAGES:]
	if not rows:
		frappe.throw(_("There is nothing to read in that conversation."))

	said = []
	for row in rows:
		who = row.get("sender_full_name") or row.get("sender") or ""
		when = row.get("communication_date") or ""
		said.append(
			f"From: {who} <{row.get('sender') or ''}>\n"
			f"To: {row.get('recipients') or ''}\n"
			f"Date: {when}\n\n{_plain(row.get('content'))}"
		)

	# Not translated, either of them. Everything from here to `about` is one
	# sentence written *at a model*, in the language the rest of the prompt is
	# in; a fallback in Arabic inside an English instruction is a sentence in
	# two languages, which is worse than the gap it fills.
	subject = rows[0].get("subject") or "(no subject)"
	mine = ", ".join(_addresses()) or "this workspace"
	about = (
		f"This is an email conversation in the reader's mailbox. The subject is "
		f"\"{subject}\". It has {len(rows)} message(s). The reader holds "
		f"{mine}; everybody else on it is somebody they correspond with."
	)
	return "\n\n-----\n\n".join(said), about, rows


def _addresses() -> list[str]:
	"""This person's own addresses, from the same place the mail list reads.

	Only to say "the reader holds sales@" in the sentence about the call, so a
	site where this fails is a slightly vaguer prompt rather than a refusal.
	"""
	from oneapp.onemail.mailbox.scope import _held

	try:
		return list(_held() or [])
	except Exception:
		return []


def _composing(to: str = "", subject: str = "") -> str:
	"""The sentence a composer says about itself."""
	mine = ", ".join(_addresses())
	parts = [
		"This is an email being written in a business workspace"
		+ (f", from {mine}" if mine else "") + ".",
	]
	if to:
		parts.append(f"It is addressed to {to}.")
	if subject:
		parts.append(f'The subject is "{subject}".')
	parts.append(
		"It will be read by a customer, a supplier or a colleague, so it is "
		"business correspondence rather than a note to self."
	)
	return " ".join(parts)


# --------------------------------------------------------------------------- #
# Endpoints
#
# Each one begins a run and hands back its id. None of them takes a model, a
# prompt or a limit; the verb is a key the server looks up, and `about` is
# written here rather than accepted from anywhere.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def summarise_thread(thread: str, folder: str = "all") -> dict:
	"""The short version of a conversation. Starts a run; watch the socket."""
	conversation, about, _rows = _conversation(thread, folder)
	return streaming.begin(
		writing.summarise, label=_("Summary"), text=conversation, about=about
	)


@frappe.whitelist(methods=["POST"])
def suggest_reply(thread: str, folder: str = "all") -> dict:
	"""A reply, drafted from the thread, for a person to edit and send."""
	conversation, about, _rows = _conversation(thread, folder)
	return streaming.begin(
		draft_reply, label=_("Suggested reply"), conversation=conversation, about=about
	)


@frappe.whitelist(methods=["POST"])
def rewrite(verb: str, text: str = "", instruction: str = "", tone: str = "",
            to: str = "", subject: str = "") -> dict:
	"""Do one of the writing verbs to what somebody is composing.

	The passage comes from the browser, and that is the one place in this
	module where it does — it is the reader's own unsent draft, which exists
	nowhere else yet. `to` and `subject` are theirs too, and are used only to
	say what kind of letter this is.
	"""
	writing.check(verb, tone)
	if verb != "write" and not (text or "").strip():
		frappe.throw(_("There is nothing to work on yet."))
	if verb == "write" and not (instruction or "").strip():
		frappe.throw(_("Say what to write."))

	return streaming.begin(
		writing.rewrite,
		label=_("Writing"),
		verb=verb,
		text=text,
		instruction=instruction,
		tone=tone,
		about=_composing(to, subject),
	)
