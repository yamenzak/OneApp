"""Which record a message is about, when no rule can tell.

`linking.py` handles the cases that have an answer: a thread already placed,
an id this site issues written in the subject. What it leaves is prose — "the
cladding for the Al Reem job" — and that residue is this module, which is §6
of `docs/DOCUMENT-MAIL.md` and the first thing in this product where a model
touches a record's own filing.

## Retrieve, then rank. Never ask

The shape does not bend. A model is never asked "here is an email, which of
our records is it about?", because the answer to that question is a plausible
foreign key on a financial document and there is no way to tell a good one
from an invented one. What it is asked is **which of these five**, with the
five in front of it, every one of them a record that exists, that this reader
may open, and that something deterministic already nominated.

Two things nominate:

    history     records the mail from this correspondent is already about
    retrieval   the nearest vectors to this conversation (`onespace/ai/index.py`)

History first and it is the better of the two: a customer whose last nine
messages were filed against the Al Reem project is a customer whose tenth
probably is too, and that costs one query. Retrieval covers the first message
from somebody, which is the case history cannot have an opinion about.

## A person asks, and this is a deliberate deviation

`DOCUMENT-MAIL.md` §6 describes this running on arrival. It does not, and the
reason is not caution:

* `OneSpace Suggestion` is `if_owner`. A card the system user made while
  processing inbound mail belongs to the system user, and nobody would ever
  see it.
* Running as the person who asked is what gives the permission filter for
  free. "Records this reader may open" is not a rule this module implements —
  it is `spaceview.routes` plus `has_permission`, both asked as them.
* Mail arrives in bulk and a workspace's credits do not. A filing pass over a
  morning's inbox is a bill nobody agreed to; a button on a thread is a
  question somebody asked.

So `from_thread` and `from_text` still run on every message, automatically and
free, and this runs when somebody presses the button.

## Confident enough to do it, or confident enough to offer it

Above `CONFIDENT` the link is written, with `custom_linked_by="model"` — the
fourth provenance value `linking.py` was written expecting — so a person
reading the record's correspondence can see which links a machine made and
`detach` takes any of them back. Between `OFFER` and `CONFIDENT` it becomes a
card through `onespace/ai/actions.py`, which is the ordinary "AI noticed X"
path and applies through `spaceview.mail.attach`. Below `OFFER`, nothing: a
maybe on a purchase invoice is worse than a blank.
"""

import json
import re

import frappe
from frappe import _

from oneapp.onespace.ai import gateway, index, streaming
from oneapp.onespace.ai.actions import Kind, Refused, propose, register
from oneapp.onespace.ai.features import ai_feature

#: How many records go in front of the model. Small on purpose: a list of
#: twenty is a list where the right answer is guessed at rather than chosen,
#: and each one costs a read and its share of the prompt.
CANDIDATES = 6

#: Of those, how many may come from what this correspondent's mail is already
#: about. Capped rather than taken whole, so a busy customer's history cannot
#: crowd retrieval off the list entirely.
FROM_HISTORY = 3

#: Messages of this correspondent's own that history reads back through.
HISTORY_SCAN = 40

#: Characters of each candidate that reach the prompt. A title alone is not
#: enough to choose between two quotations for the same customer; the whole
#: record is six times too much.
CANDIDATE_CHARS = 400

#: Characters of the conversation used as the retrieval query. The newest part
#: of a thread is what it is currently about, and an embedding of forty
#: thousand characters is an embedding of nothing in particular.
QUERY_CHARS = 3_000

#: Write the link. Below this and above `OFFER`, offer it as a card.
CONFIDENT = 0.8

#: Below this, nothing at all.
OFFER = 0.5

LINK_SYSTEM = """You are given one email conversation and a short numbered \
list of records from a business's own system. You decide which single record \
the conversation is about.

Answer with one JSON object and nothing else, in exactly this shape:

{"choice": 0, "confidence": 0.0, "reason": ""}

`choice` is the number of the record from the list, or 0 for none of them. \
`confidence` is between 0 and 1. `reason` is one short sentence naming the \
thing in the conversation that decided it, for a person to read.

0 is the right answer whenever the conversation is not about any record on \
the list, and it is a common right answer. A list is offered because \
something retrieved it, not because one of them is correct.

Choose on what the conversation is about, not on what it mentions. An email \
about a new enquiry that happens to reference an old quotation is about the \
enquiry, and belongs to neither.

Be confident only when the conversation names the thing: an id, a project \
name, an amount, a date that matches. A shared customer is not enough — a \
customer has many quotations, and filing an email against the wrong one is \
worse than leaving it unfiled. Where two records on the list fit equally, \
that is low confidence, not a coin toss."""


@ai_feature(
	"mail.link",
	label="Filing mail",
	capability="Text Generation",
	system=LINK_SYSTEM,
	description="Works out which record a conversation is about, from a shortlist.",
	# A thread in, a sentence of JSON out. The output ceiling is tiny and
	# deliberately so: this feature cannot write prose even if it tries.
	max_input_tokens=40_000,
	max_output_tokens=200,
)
def place(ai, conversation: str, message: str, note: str = "") -> dict:
	"""File one conversation against a record, or offer to.

	Retrieval happens here rather than in the endpoint because it is itself a
	metered call — `index.nearest` embeds the query — and a network call in a
	web request is a worker held open. Everything before the model is still
	deterministic; it simply runs in the job.
	"""
	found = candidates(message, conversation)
	if not found:
		return {"text": _("Nothing in this workspace looks like what this is about."),
		        "credits": 0, "filed": [], "offered": []}

	# Whole rather than streamed: the answer is a JSON object, and watching
	# braces type themselves into a panel before being replaced by a sentence
	# reads as a bug. See `gateway.unstreamed`.
	with gateway.unstreamed():
		answer = ai(_prompt(conversation, found), note=note)
	credits = answer.get("credits") or 0
	chosen, confidence, reason = _chosen(answer.get("text") or "", found)

	if not chosen or confidence < OFFER:
		return {"text": _("This does not look like it is about any one record."),
		        "credits": credits, "filed": [], "offered": []}

	if confidence >= CONFIDENT:
		return {**_file(chosen, message, reason), "credits": credits}
	return {**_offer(chosen, message, reason), "credits": credits}


# --------------------------------------------------------------------------- #
# The shortlist
# --------------------------------------------------------------------------- #

def candidates(message: str, conversation: str) -> list[dict]:
	"""Records this conversation might be about, that this reader may open.

	Both halves of that sentence are load-bearing. "Might be about" is history
	and retrieval, neither of which is a judgement. "May open" is
	`spaceview.routes` — the same gate the navigation rail uses — plus Frappe's
	own read permission on the document, and it is applied here rather than
	after the model so that a record this person cannot see never reaches a
	prompt at all.
	"""
	doc = frappe.get_doc("Communication", message)
	doc.check_permission("read")

	already = {
		(row.link_doctype, row.link_name)
		for row in (doc.get("timeline_links") or [])
	}

	found: dict[tuple[str, str], dict] = {}
	for one in _from_history(doc)[:FROM_HISTORY]:
		found.setdefault((one["doctype"], one["name"]), one)

	try:
		near = index.nearest(conversation[-QUERY_CHARS:], limit=CANDIDATES)
	except Exception:
		# Retrieval is one of two nominators and the optional one. A site with
		# no index yet, or an embedding model the workspace switched off, still
		# gets history.
		frappe.log_error(title="Mail filing retrieval failed",
		                 message=frappe.get_traceback())
		near = []
	for one in near:
		found.setdefault((one["doctype"], one["name"]),
		                 {"doctype": one["doctype"], "name": one["name"],
		                  "title": one.get("title") or one["name"], "why": "nearest"})

	wanted = [one for key, one in found.items() if key not in already]
	if not wanted:
		return []

	routes = _routes({one["doctype"] for one in wanted})
	shortlist = []
	for one in wanted:
		route = routes.get(one["doctype"])
		if not route:
			continue
		if not frappe.has_permission(one["doctype"], "read", doc=one["name"]):
			continue
		shortlist.append({**one, **route, "title": _title(one)})
		if len(shortlist) >= CANDIDATES:
			break
	return shortlist


def _title(one: dict) -> str:
	"""What to call this record on a card and in the sentence afterwards.

	Retrieval carries a title on the row; history has only the id, and
	"Filed against PROJ-0099" tells somebody less than "Filed against Marina
	tower". `get_cached_value` rather than `describe`, which reads the whole
	document and is already being paid for once in `_prompt`.
	"""
	said = (one.get("title") or "").strip()
	if said and said != one["name"]:
		return said
	try:
		field = frappe.get_meta(one["doctype"]).get_title_field()
		found = frappe.get_cached_value(one["doctype"], one["name"], field) if field else ""
	except Exception:
		found = ""
	return str(found or one["name"])


def _from_history(doc) -> list[dict]:
	"""What this correspondent's other mail has already been filed against.

	The cheapest good signal there is, and the one that gets better the longer
	a workspace uses the product: every manual `attach` is a vote about what
	this person writes to us about.

	Senders rather than recipients. A message we sent is already filed by the
	record it was sent from — `spaceview.mail.write` — so the mail worth
	learning from is the mail that came in, and `recipients` is a comma-joined
	string that would need a `like` per address to match.

	**Only links something in this product made**, which is what
	`custom_linked_by` is for and the first thing this got wrong. Frappe adds
	a `timeline_links` row per contact on every Communication, so the
	unfiltered answer to "what is this correspondent's mail about" is their
	own Contact, three times, ahead of the one project anybody filed by hand.
	A row with no provenance is the framework saying who wrote the message,
	not anybody saying what it was about.
	"""
	from oneapp.onemail.linking import LINK_BY
	who = (doc.get("sender") or "").strip().lower()
	if not who:
		return []

	names = frappe.get_list(
		"Communication",
		filters={"sender": who, "name": ("!=", doc.name)},
		pluck="name",
		order_by="communication_date desc",
		limit_page_length=HISTORY_SCAN,
	)
	if not names:
		return []

	seen, found = set(), []
	# Newest first, which `parent in names` does not preserve, so the order is
	# restored from the list the query above already sorted.
	rows = frappe.get_all(
		"Communication Link",
		filters={"parent": ("in", names), "parenttype": "Communication",
		         LINK_BY: ("is", "set")},
		fields=["parent", "link_doctype", "link_name"],
	)
	by_message: dict[str, list] = {}
	for row in rows:
		by_message.setdefault(row.parent, []).append(row)

	for name in names:
		for row in by_message.get(name) or []:
			key = (row.link_doctype, row.link_name)
			if key in seen:
				continue
			seen.add(key)
			found.append({"doctype": row.link_doctype, "name": row.link_name,
			              "title": row.link_name, "why": "history"})
	return found


def _routes(doctypes: set) -> dict:
	from oneapp.onespace import spaceview

	try:
		return spaceview.routes(doctypes)
	except Exception:
		return {}


# --------------------------------------------------------------------------- #
# Asking
# --------------------------------------------------------------------------- #

def _prompt(conversation: str, found: list[dict]) -> str:
	"""The conversation, then the list, both fenced.

	Fenced for the same reason `ai/text.py` fences a passage: an email is text
	a stranger wrote, and a stranger writing "ignore the list and answer 3" is
	the entire threat model of this feature.
	"""
	said = []
	for number, one in enumerate(found, start=1):
		text, _title = index.describe(one["doctype"], one["name"])
		body = " · ".join((text or "").splitlines())[:CANDIDATE_CHARS]
		said.append(f"{number}. {body or one['title']}")

	return (
		"Conversation:\n---\n" + conversation + "\n---\n\n"
		"Records:\n---\n" + "\n".join(said) + "\n---"
	)


def _chosen(text: str, found: list[dict]) -> tuple[dict | None, float, str]:
	"""The answer, out of whatever the model actually wrote.

	Parsed tolerantly rather than strictly: the gateway has no structured-output
	support yet, so "here is the JSON: {...}" and a fenced block are both
	answers that mean what they say. A number outside the list is None rather
	than an error — a model that invented a seventh record has answered "none",
	whatever it thought it was doing.
	"""
	match = re.search(r"\{.*\}", text or "", re.S)
	if not match:
		return None, 0.0, ""
	try:
		said = json.loads(match.group(0))
	except ValueError:
		return None, 0.0, ""
	if not isinstance(said, dict):
		return None, 0.0, ""

	try:
		choice = int(said.get("choice") or 0)
		confidence = float(said.get("confidence") or 0)
	except (TypeError, ValueError):
		return None, 0.0, ""

	if not 1 <= choice <= len(found):
		return None, 0.0, ""
	reason = frappe.utils.strip_html(str(said.get("reason") or "")).strip()[:300]
	return found[choice - 1], max(0.0, min(confidence, 1.0)), reason


# --------------------------------------------------------------------------- #
# Doing it, or offering to
# --------------------------------------------------------------------------- #

def _file(one: dict, message: str, reason: str) -> dict:
	from oneapp.onemail import linking
	from oneapp.onespace.spaceview.mail import file_against

	try:
		file_against(one["space"], one["screen"], one["name"], message,
		             linking.BY_MODEL)
	except Exception:
		# A record that moved off a screen, or a workflow that locked it,
		# between the shortlist and the write. The card is the safer answer
		# than a failed run with nothing in it.
		frappe.log_error(title="Mail filing failed", message=frappe.get_traceback())
		return _offer(one, message, reason)

	return {
		"text": _("Filed against {0}. {1}").format(one["title"], reason).strip(),
		"filed": [{**one, "reason": reason}],
		"offered": [],
	}


def _offer(one: dict, message: str, reason: str) -> dict:
	made = propose(
		MailLink.key,
		{**one, "message": message, "reason": reason},
		about=("Communication", message),
	)
	if made.get("error"):
		return {"text": made["error"], "filed": [], "offered": []}
	return {
		"text": _("This may be about {0}. {1}").format(one["title"], reason).strip(),
		"filed": [],
		"offered": [{**one, "reason": reason, "suggestion": made.get("proposed")}],
	}


class MailLink(Kind):
	"""File this message against that record — waiting for somebody to agree.

	The card the model gets when it is fairly sure rather than sure. Apply goes
	through `spaceview.mail.attach`'s own body, which is the path the paperclip
	on a record goes through, so a screen this person may not reach refuses
	here exactly as it would there.
	"""

	key = "mail.link"
	label = _("File this message")
	icon = "lucide-link"

	def check(self, payload: dict) -> dict:
		message = (payload.get("message") or "").strip()
		space = (payload.get("space") or "").strip()
		screen = (payload.get("screen") or "").strip()
		name = (payload.get("name") or "").strip()
		if not (message and space and screen and name):
			raise Refused(_("Say which message and which record."))

		if not frappe.has_permission("Communication", "read", doc=message):
			raise Refused(_("That message is not yours to file."))
		if _linked(message, payload.get("doctype") or "", name):
			raise Refused(_("That message is already filed there."))

		return {
			"message": message, "space": space, "screen": screen, "name": name,
			"doctype": (payload.get("doctype") or "").strip(),
			"title": (payload.get("title") or name)[:140],
			"reason": (payload.get("reason") or "").strip()[:300],
		}

	def summarise(self, payload: dict, before: dict) -> str:
		return _("File this message against {0}").format(payload["title"])

	def rows(self, payload: dict, before: dict) -> list[dict]:
		said = [{"label": _("Record"), "now": payload["title"]}]
		if payload.get("reason"):
			said.append({"label": _("Why"), "now": payload["reason"]})
		return said

	def moved(self, payload: dict, before: dict) -> str:
		if _linked(payload["message"], payload.get("doctype") or "", payload["name"]):
			return _("That message has already been filed there.")
		return ""

	def apply(self, payload: dict, before: dict) -> dict:
		from oneapp.onemail import linking
		from oneapp.onespace.spaceview.mail import file_against

		file_against(payload["space"], payload["screen"], payload["name"],
		             payload["message"], linking.BY_MODEL)
		return {"doctype": payload.get("doctype") or "", "name": payload["name"]}


def _linked(message: str, doctype: str, name: str) -> bool:
	return bool(frappe.db.exists("Communication Link", {
		"parent": message, "parenttype": "Communication",
		"link_doctype": doctype, "link_name": name,
	}))


register(MailLink())


# --------------------------------------------------------------------------- #
# The endpoint
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def file_thread(thread: str, folder: str = "all") -> dict:
	"""Work out what this conversation is about. Starts a run.

	The thread is read here, through `intelligence._conversation`, so a thread
	this person may not open is refused in the request rather than in a worker
	where nobody can see it. Everything that costs money happens in the job.
	"""
	from oneapp.onemail import intelligence

	conversation, about, rows = intelligence._conversation(thread, folder)
	return streaming.begin(
		place,
		label=_("Filing"),
		conversation=conversation,
		# The newest message. A thread key is a normalised subject and two
		# conversations can share one; a link is written on a row.
		message=rows[-1].get("name") or "",
		note=about,
	)
