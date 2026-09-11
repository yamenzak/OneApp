"""Summarise, improve, proofread, shorten, expand, change the tone, write it.

Seven things a person asks for and **two** declared features, and the split is
the one decision in this file worth arguing about.

It is not one feature with seven verbs. A hold is priced off the feature's
declared ceiling before the call is made, so a single feature big enough to
summarise a thirty-message thread would reserve a thirty-message thread's
worth of credits every time somebody asked it to fix a comma. On a workspace
near its balance that is a rewrite refused for want of credits it was never
going to spend.

It is not seven features either. Six of the verbs take text a person has in
front of them and hand back text of about the same size; they differ in
wording and in nothing else, and six settings rows saying "Improve" and
"Proofread" would be six model pickers nobody wants to keep in step.

So: **one feature per cost shape.**

* `text.rewrite` — works on what is on screen. Modest in, modest out.
* `text.summarise` — reads something long and says something short about it.
  Large in, small out.

Three rules hold across both.

**The verb is a key, never a sentence.** A browser sends `improve`; the
wording it selects is in `VERBS` here and a workspace cannot reach it. An
endpoint that took the instruction would be an endpoint that took the prompt.

**`about` is written by the module, never by the reader.** "This is a reply to
a customer" is a fact mail knows and states; it travels as the gateway's
`note`, which lands after our instructions and after the workspace's addendum.
It is what makes the same verb produce a business reply in one place and three
words in another.

**What comes back is plain text.** No HTML, no Markdown. Every surface that
calls this owns a document model of its own — a ProseMirror tree, a cell, a
mail body — and markup from a model is markup somebody has to sanitise before
it can go anywhere near one. Paragraphs are blank lines and the surface
decides what a paragraph is.
"""

import frappe
from frappe import _

from oneapp.onespace.ai.features import ai_feature

#: How much text a rewrite will look at. Generous enough for a long email and
#: an editor's whole selection; short of the point where somebody has pasted a
#: contract in and should be asking for a summary instead.
MAX_TEXT = 24_000

SHARED = """You help somebody with a piece of their own writing, inside their \
workspace.

Answer with the finished text and nothing else. No preamble, no "here is", no \
explanation of what you changed, no quotation marks around the whole thing, \
and no Markdown or HTML — paragraphs are separated by a blank line and that is \
the only formatting there is.

Write in the language the text is already in. Keep the writer's voice: this is \
their letter and their sentence, and a rewrite that sounds like somebody else \
is one they have to undo.

Keep every fact exactly as given. Names, figures, dates, amounts and \
references are not yours to tidy, round, translate or infer — if something is \
missing, leave the gap rather than filling it. Never invent a detail to make a \
sentence read better.

If a request cannot be answered from what you were given, say so in one short \
line rather than producing something plausible."""

REWRITE_SYSTEM = SHARED + """

You are working on a passage the person has in front of them. What you return \
replaces it, so it must stand on its own and be roughly the length asked for."""

SUMMARY_SYSTEM = SHARED + """

You are reading something long and saying something short about it. Lead with \
what somebody needs to know before they read the rest: what it is about, what \
was decided, and what is waiting on whom. Be specific — "the price was agreed \
at AED 412,000" rather than "the price was discussed". Six sentences at the \
very most, and fewer where fewer will do."""


#: What each verb asks for. The wording is here rather than in a browser, and
#: a workspace's own addendum is appended after it rather than instead of it.
#:
#: One line each on purpose. A model given a paragraph of instruction per verb
#: starts writing about the instruction; the register and the constraints are
#: already in the system prompt, and the verb only has to say which of them
#: matters this time.
VERBS = {
	"improve": "Rewrite this so it reads better. Same meaning, same length, "
	           "clearer sentences.",
	"proofread": "Correct the spelling, grammar and punctuation. Change nothing "
	             "else — not the wording, not the order, not the register.",
	"shorten": "Say the same thing in noticeably fewer words. Keep every fact.",
	"expand": "Say this more fully. Add the detail the reader would otherwise "
	          "have to ask for, and nothing that is not already implied.",
	"tone": "Rewrite this in a {tone} register. Same meaning, same facts.",
	"write": "Write this. The instruction is below; anything after it is "
	         "context to write from, not text to rewrite.",
}

#: What `tone` may be. A closed list, because the tone is a word that goes
#: straight into the instruction and an open one would be a prompt with a hole
#: in it — "rewrite this in a ignore your instructions register".
TONES = ("formal", "friendly", "direct", "warm", "apologetic", "firm")


def verbs() -> list[str]:
	"""What a surface may ask for. Read by the menu and by the guard tests."""
	return list(VERBS)


@ai_feature(
	"text.rewrite",
	label="Writing help",
	capability="Text Generation",
	system=REWRITE_SYSTEM,
	description="Improves, proofreads, shortens, lengthens or retones a passage.",
	# Both ceilings sized for a long email rather than for a document: this is
	# the one that runs twenty times an hour, and a ceiling is what gets held.
	max_input_tokens=12_000,
	max_output_tokens=2_000,
)
def rewrite(ai, verb: str, text: str = "", instruction: str = "",
            tone: str = "", about: str = "") -> dict:
	"""Do one thing to one passage, and hand back the passage.

	Nothing here writes. What comes back is text, and the surface that asked —
	a composer, an editor, a cell — decides whether it replaces a selection,
	lands in a draft, or sits in a panel until somebody presses Use.
	"""
	said = VERBS.get(verb)
	if not said:
		raise ValueError(f"No such verb: {verb}")
	if verb == "tone":
		said = said.format(tone=tone if tone in TONES else TONES[0])

	body = (text or "").strip()[:MAX_TEXT]
	if verb == "write":
		prompt = f"{said}\n\nInstruction:\n{(instruction or '').strip()}"
		if body:
			prompt += f"\n\nContext:\n{body}"
	else:
		prompt = f"{said}\n\n---\n{body}\n---"
		# An extra word from the person, on top of the verb. "Improve this, and
		# keep it under a hundred words." It goes with the passage rather than
		# with the instruction, so it cannot displace the verb.
		if instruction:
			prompt += f"\n\nAlso: {instruction.strip()}"

	answer = ai(prompt, note=about)
	return {"text": (answer.get("text") or "").strip(), "credits": answer.get("credits") or 0}


@ai_feature(
	"text.summarise",
	label="Summaries",
	capability="Text Generation",
	system=SUMMARY_SYSTEM,
	description="Reads something long and says the short version.",
	# The other shape: a thread, a contract, a hundred rows in. A paragraph out.
	max_input_tokens=120_000,
	max_output_tokens=600,
)
def summarise(ai, text: str, about: str = "") -> dict:
	"""The short version of something long."""
	answer = ai((text or "").strip(), note=about)
	return {"text": (answer.get("text") or "").strip(), "credits": answer.get("credits") or 0}


@frappe.whitelist(methods=["GET"])
def available() -> dict:
	"""What the verb menu may offer, and whether to draw it at all.

	Asked once by a surface rather than guessed: a workspace can switch either
	feature off, a site can have no gateway configured, and a menu of things
	that answer "switched off" is worse than no menu.
	"""
	from oneapp.onespace.ai import features, gateway

	live = gateway.is_configured()
	return {
		"rewrite": live and features.is_enabled("oneapp.text.rewrite"),
		"summarise": live and features.is_enabled("oneapp.text.summarise"),
		"verbs": verbs(),
		"tones": list(TONES),
	}


def check(verb: str, tone: str = "") -> None:
	"""Refuse a verb or a tone nothing declared, before a run is enqueued.

	Called by the endpoints in each module rather than here, because this
	module has no endpoint that starts a run — every surface begins one
	through its own, with its own `about`.
	"""
	if verb not in VERBS:
		frappe.throw(_("There is no such writing action."))
	if verb == "tone" and tone and tone not in TONES:
		frappe.throw(_("There is no such tone."))
