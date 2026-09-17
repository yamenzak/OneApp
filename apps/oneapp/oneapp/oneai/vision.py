"""Looking at a picture, which is the one thing the rest of this arc cannot do.

Every other feature here reads text and writes text. A photograph of a
delivery note, a scanned invoice, a screenshot somebody pasted into a chat —
all of them arrive as files the product can store, list, share and preview, and
none of which anything could *read*. The capability was declared from the
start: `Image Understanding` is in `scripts/ai_capabilities.py`, a model row
carries `input_modalities`, and a price row has a `modality` column precisely
so an image tile bills differently from a token. Nothing declared it, so the
settings page had no row and there was nothing to bind a model to.

This is the row.

**A separate feature rather than a multimodal chat.** The assistant declares
`Text Generation` and the model a workspace picked for it may have no eyes;
making the chat multimodal would mean a workspace that wants to read one
invoice has to run every conversation on a vision model and pay for the
privilege. So the chat asks *this* instead, as a tool, and this has its own
picker, its own ceiling and its own switch — which is the whole argument
`ai/text.py` makes for one feature per cost shape, applied to a cost shape
that is not text at all.

**It answers with words and nothing else.** What comes back is a description
the asking model reads like any other tool result, so the picture is looked at
once, by the model chosen to look at pictures, and never travels further.

**And the bytes are somebody's file.** `look` takes them already read and
already permitted: `chat/toolbox.py` is where a file is checked, in front of
`frappe.has_permission`, and a feature that fetched its own would be a second
place that decides who may see what.
"""

import frappe
from frappe import _

from oneapp.oneai.features import ai_feature

#: What a picture may weigh, as base64, before this refuses to look at it.
#:
#: Six megabytes of base64 is about four and a half of image, which is a phone
#: photograph at full size and more than any provider takes inline. Refused
#: rather than downscaled: resizing an image on a web worker to save a call is
#: a second image nobody can see, and what it would answer about is not what
#: the person is looking at.
MAX_BYTES = 6 * 1024 * 1024

#: Types worth sending. Everything a browser will render and the one document
#: format Gemini reads whole — a PDF goes inline as itself rather than as
#: pages, which is why there is no rasteriser in this repository.
SEEN = {
	"image/png", "image/jpeg", "image/webp", "image/gif", "image/heic",
	"image/heif", "application/pdf",
}

SYSTEM = """You are shown one file from somebody's workspace and asked about \
it.

Say what is actually there. Read the text you can see — labels, totals, dates, \
names, a handwritten note in a margin — and give it back as text, keeping the \
structure it has: a table stays a table, a list stays a list, a form's fields \
stay beside their values.

Where something is unreadable, say so and say where, rather than guessing at \
it. A figure you were not sure of is worse than a gap, because a gap is a \
question somebody can answer and a wrong figure is one nobody thinks to ask.

Do not describe the medium. "A scanned invoice on white paper" is a sentence \
about the photograph; what was asked for is what it says. No preamble, no \
"this image shows", no Markdown.

If you are asked a specific question about it, answer that question first and \
then give whatever else is on the file that bears on it."""


@ai_feature(
	"ai.vision.read",
	label="Reading pictures",
	capability="Image Understanding",
	system=SYSTEM,
	description="Reads what a photograph, a scan or a screenshot says.",
	# Input is a picture rather than a transcript, and a picture costs what it
	# costs whatever we declare — the ceiling that matters here is the output,
	# which is somebody reading a delivery note back, not writing an essay
	# about it.
	max_input_tokens=32_000,
	max_output_tokens=2_000,
)
def read(ai, mime: str, data: str, question: str = "", note: str = "") -> dict:
	"""One file, looked at. `data` is base64 and is already this person's.

	The question is the asker's own words where there are any — "what is the
	total?" gets a total, and nothing gets a transcription. Either way what
	comes back is text.
	"""
	if mime not in SEEN:
		raise ValueError(f"Nothing here can look at {mime}.")
	if not data:
		raise ValueError("There is nothing to look at.")
	if len(data) > MAX_BYTES:
		raise ValueError("That file is too big to look at.")

	asked = (question or "").strip() or "Read this and give back what it says."

	# A transcript of one, carrying the bytes — `ai/transcript.py` turns
	# `attachments` into the part each provider wants.
	answer = ai(
		messages=[{
			"role": "user",
			"content": asked,
			"attachments": [{"mime": mime, "data": data}],
		}],
		note=note,
	)
	return {"text": (answer.get("text") or "").strip(),
	        "credits": answer.get("credits") or 0}


def can_see(mime: str) -> bool:
	"""Whether this is a file anything could be asked to look at."""
	return mime in SEEN
