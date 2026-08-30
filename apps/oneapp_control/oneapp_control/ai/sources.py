"""Reading model prices out of what the providers actually publish.

No frappe in here on purpose: these are parsers over text, and a parser that
needs a database to test is a parser nobody re-tests when the page changes.

Two pages, two shapes, one problem in common — **there is no single unit**.
Gemini bills everything, including generated images and speech, per million
tokens. Workers AI bills text per million tokens, pictures per 512x512 tile and
per diffusion step, and speech per audio minute or per thousand characters. So
a rate is stored as (kind, modality, unit, cost for N of them) and nothing here
converts between units.

The other rule: **an unparseable rate is not a zero and not a default.** Every
parser returns what it could not read alongside what it could, and a model with
a gap comes out of the sync marked for review instead of being sold at a price
we invented.
"""

import re
from dataclasses import dataclass, field

MILLION = 1_000_000


@dataclass
class Price:
	kind: str          # Input | Cached Input | Cache Write | Output | Reasoning | Request | Search
	modality: str      # Text | Image | Audio | Video | File | Any
	unit: str          # Token | Image | Tile | Step | Second | Minute | Character | Request | Search
	cost_usd: float
	per_units: int = 1
	tier: str = "Standard"
	effective_from: str | None = None
	effective_to: str | None = None
	note: str = ""


@dataclass
class Parsed:
	prices: list[Price] = field(default_factory=list)
	# Wording no parser could turn into a rate. A model with any of these is
	# held back from sale — see catalogue.py.
	unparsed: list[str] = field(default_factory=list)
	# Rates that were read but are not the one we charge on: a second transport
	# priced differently, a tier we do not use. Recorded so the page and the
	# catalogue can be compared, not a reason to hold a model back.
	notes: list[str] = field(default_factory=list)

	def key(self, price: "Price") -> tuple:
		return (price.kind, price.modality, price.unit, price.tier,
		        price.effective_from, price.effective_to)

	def add(self, price: "Price"):
		"""Keep the first rate published for a slot, note any later one.

		Cloudflare lists Deepgram Nova-3 twice, once for HTTP and once for
		WebSocket, in rows that are otherwise identical. Adding both would bill
		a minute of audio at the sum of the two.
		"""
		if any(self.key(p) == self.key(price) for p in self.prices):
			self.notes.append(f"also published: {price.note}")
			return
		self.prices.append(price)


# --------------------------------------------------------------------------- #
# Workers AI — developers.cloudflare.com/workers-ai/platform/pricing
#
# Markdown tables, one per model family, under headings that already say what
# kind of model it is. The price column is free text of the form
# "$X per <something>", repeated.
# --------------------------------------------------------------------------- #

# Heading -> what a bare, unqualified rate in that section means. Whisper and
# MeloTTS both read "per audio minute"; one is charging for audio going in and
# the other for audio coming out, and only the section knows which.
WORKERS_SECTIONS = {
	"llm model pricing": "text",
	"embeddings model pricing": "text",
	"image model pricing": "image",
	"audio model pricing": "audio",
	"other model pricing": "text",
}

_AMOUNT = re.compile(r"\$\s*([0-9][0-9,]*\.?[0-9]*)")


def _money(raw: str) -> float:
	return float(raw.replace(",", ""))


def _workers_qualifier(text: str, section: str, capability: str | None) -> Price | None:
	"""Turn "per M cached input tokens" into a rate, or give up.

	Giving up is the point of the None: the caller records the wording verbatim
	and the model goes to review.
	"""
	q = " ".join(text.lower().split())
	q = q.strip(" .,")

	# A rate that is a product of two counts — "per input 512x512 tile, per
	# step" — cannot be stored as one unit, and multiplying the wrong pair is
	# worse than declining to price the model.
	if q.count(" per ") >= 1 and "tile" in q and "step" in q:
		return None
	if "mp" in q.split() or "megapixel" in q:
		return None

	is_input = "input" in q
	is_output = "output" in q
	cached = "cached" in q

	if "token" in q:
		kind = "Cached Input" if cached else ("Output" if is_output else "Input")
		return Price(kind, "Text", "Token", 0.0, MILLION)

	if "tile" in q:
		kind = "Input" if is_input else "Output"
		return Price(kind, "Image", "Tile", 0.0, 1)

	if "step" in q:
		return Price("Output", "Image", "Step", 0.0, 1)

	if "image" in q:
		per = MILLION if re.search(r"\bm\s+images\b", q) else 1
		# Only a model that makes pictures charges for pictures on the way out.
		# A classifier priced "per M images" is being paid to look at them.
		generates = capability in ("Image Generation",)
		kind = "Output" if (generates and not is_input) else "Input"
		return Price(kind, "Image", "Image", 0.0, per)

	if "audio minute" in q or "minute" in q:
		if is_input:
			kind = "Input"
		elif is_output:
			kind = "Output"
		else:
			kind = "Output" if capability == "Text to Speech" else "Input"
		return Price(kind, "Audio", "Minute", 0.0, 1)

	if "character" in q:
		per = 1000 if re.search(r"\b1k\b|\b1,000\b", q) else 1
		kind = "Output" if capability == "Text to Speech" and is_output else "Input"
		return Price(kind, "Text", "Character", 0.0, per)

	return None


def parse_workers_pricing(markdown: str, capabilities: dict[str, str] | None = None) -> dict[str, Parsed]:
	"""Model id -> the rates published for it.

	`capabilities` is what the models API already told us each model is for. It
	settles the cases the price wording leaves open — see `_workers_qualifier`.
	"""
	capabilities = capabilities or {}
	out: dict[str, Parsed] = {}
	section = ""

	for line in markdown.splitlines():
		heading = re.match(r"^#{2,3}\s+(.*)$", line.strip())
		if heading:
			section = heading.group(1).strip().lower()
			continue

		if section not in WORKERS_SECTIONS or not line.strip().startswith("|"):
			continue

		cells = [c.strip() for c in line.strip().strip("|").split("|")]
		if len(cells) < 2 or not cells[0].startswith("@cf/"):
			continue

		# "@cf/deepgram/nova-3 (WebSocket)" is the same model on a different
		# transport, not another model; the id is the first token.
		model_id, published = cells[0].split()[0], cells[1]
		parsed = out.setdefault(model_id, Parsed())
		capability = capabilities.get(model_id)

		# "$0.027 per M input tokens  $0.201 per M output tokens" — split on the
		# amounts, so each qualifier is whatever followed its own dollar figure.
		pieces = _AMOUNT.split(published)
		for amount, qualifier in zip(pieces[1::2], pieces[2::2]):
			rate = _workers_qualifier(qualifier, WORKERS_SECTIONS[section], capability)
			phrase = f"${amount}{qualifier}".strip()
			if not rate:
				parsed.unparsed.append(phrase)
				continue
			rate.cost_usd = _money(amount)
			rate.note = " ".join(phrase.split())[:140]
			parsed.add(rate)

	return out


# --------------------------------------------------------------------------- #
# Gemini — ai.google.dev/gemini-api/docs/pricing
#
# Prose in table cells. One cell can carry several rates for several modalities
# and two of them can be dated:
#
#   "$0.75 through December 31, 2026. $1.50 starting January 1, 2027."
#   "$3 (text and thinking) $60.00 (images)"
#
# All of it is per million tokens, which is why generated images and speech are
# exactly meterable here — Google counts them in tokens and returns the count.
# --------------------------------------------------------------------------- #

GEMINI_ROWS = {
	"input price": "Input",
	"output price": "Output",
	"context caching price": "Cached Input",
}

# One line can name several models — "*[`veo-3.1-generate-preview`](...),
# [`veo-3.1-fast-generate-preview`](...)*" — and taking only the first leaves the
# rest of the family absent from the catalogue entirely.
_MODEL_LINE = re.compile(r"^\*\[`[a-z0-9.\-]+`\]")
_MODEL_ID = re.compile(r"`([a-z0-9.\-]+)`")
_MONTHS = {m: i + 1 for i, m in enumerate(
	["january", "february", "march", "april", "may", "june", "july",
	 "august", "september", "october", "november", "december"])}


def _date(text: str) -> str | None:
	m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
	if not m or m.group(1).lower() not in _MONTHS:
		return None
	return f"{m.group(3)}-{_MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"


def _gemini_modality(label: str) -> list[str]:
	"""Which modalities a "(text/image)" style label names."""
	l = label.lower()
	found = [name for key, name in (
		("text", "Text"), ("image", "Image"), ("audio", "Audio"), ("video", "Video"),
	) if key in l]
	return found or ["Text"]


def _gemini_cell(cell: str, kind: str, tier: str) -> Parsed:
	parsed = Parsed()
	body = re.sub(r"\^?\\?\*+\^?", "", cell)          # footnote markers
	body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)  # links

	# "$60.00 (images) Equivalent to $0.045 per 0.5K image, $0.067 per 1K image..."
	# Everything after "Equivalent to" restates the rate before it in per-image
	# terms. Parsed as further rates they collide with the real one, and which
	# survives comes down to which Google happened to write first.
	restated = ""
	if "equivalent to" in body.lower():
		cut = body.lower().index("equivalent to")
		body, restated = body[:cut], " ".join(body[cut:].split())[:140]

	if not _AMOUNT.search(body):
		# "Free of charge" and "Not available" are answers, not failures: one
		# means no paid rate applies, the other that the tier does not exist.
		if not re.search(r"free of charge|not available|no|yes", body, re.I):
			parsed.unparsed.append(" ".join(body.split())[:140])
		return parsed

	pieces = _AMOUNT.split(body)
	for amount, tail in zip(pieces[1::2], pieces[2::2]):
		# Storage rates are a per-hour charge on cached bytes, not a rate on
		# this call. Recorded as unparsed so nobody thinks it was priced.
		if "storage price" in tail.lower():
			parsed.notes.append(f"storage: ${amount} {' '.join(tail.split())[:100]}")
			continue

		label = re.search(r"\(([^)]*)\)", tail)
		window = tail.lower()
		effective_from = _date(tail) if "starting" in window else None
		effective_to = _date(tail) if "through" in window else None

		for modality in _gemini_modality(label.group(1) if label else ""):
			parsed.add(Price(
				kind=kind,
				modality=modality,
				unit="Token",
				cost_usd=_money(amount),
				per_units=MILLION,
				tier=tier,
				effective_from=effective_from,
				effective_to=effective_to,
				note=" ".join(f"${amount}{tail}".split())[:140],
			))

	if restated:
		parsed.notes.append(restated)

	return parsed


def parse_gemini_pricing(text: str) -> dict[str, Parsed]:
	"""Model id -> the rates published for it, across every tier."""
	out: dict[str, Parsed] = {}
	model_ids: list[str] = []
	tier = "Standard"

	for line in text.splitlines():
		stripped = line.strip()

		if _MODEL_LINE.match(stripped):
			model_ids = _MODEL_ID.findall(stripped)
			tier = "Standard"
			for model_id in model_ids:
				out.setdefault(model_id, Parsed())
			continue

		heading = re.match(r"^###\s+(Standard|Batch|Flex|Priority)\s*$", stripped)
		if heading:
			tier = heading.group(1)
			continue

		if re.match(r"^##\s+", stripped):
			# A new model section whose id line has not arrived yet. Dropping
			# the models here stops the rates under it landing on the previous
			# ones, which is the bug that silently halves someone's bill.
			model_ids = []
			continue

		if not model_ids or not stripped.startswith("|"):
			continue

		cells = [c.strip() for c in stripped.strip("|").split("|")]
		if len(cells) < 3:
			continue

		# "Output price (including thinking tokens)" is the same row as "Output
		# price"; Google qualifies these labels differently per model and an
		# exact match quietly drops the output rate of whichever model got a
		# parenthesis this month.
		label = re.sub(r"[^a-z ]", " ", cells[0].lower())
		label = " ".join(label.split())
		# `endswith` as well as `startswith` because Google qualifies on both
		# ends: "Output price (including thinking tokens)" and, on the embedding
		# models, "Text input price".
		kind = next((k for phrase, k in GEMINI_ROWS.items()
		             if label.startswith(phrase) or label.endswith(phrase)), None)
		if not kind:
			# A priced row that is not one of our rate slots. Search grounding
			# is the common one — a real charge, on a feature we do not call.
			# Veo's per-resolution video seconds and Lyria's per-song rate land
			# here too; those models end up with no rates at all, which is what
			# holds them back, not this note.
			if "$" in cells[2]:
				for model_id in model_ids:
					out[model_id].notes.append(
						f"{cells[0]}: {' '.join(cells[2].split())[:100]}")
			continue

		result = _gemini_cell(cells[2], kind, tier)
		for model_id in model_ids:
			for price in result.prices:
				out[model_id].add(price)
			out[model_id].unparsed.extend(result.unparsed)
			out[model_id].notes.extend(result.notes)

	return out


def gemini_capability(model_id: str, methods: list[str]) -> str:
	"""What a Gemini model is for.

	Google's models API does not say — `supportedGenerationMethods` separates
	embedding from generation and nothing else, so the name carries the rest.
	Every generative Gemini model takes text and images, so Text Generation is
	the honest default rather than a guess.
	"""
	methods = [m.lower() for m in methods or []]
	name = model_id.lower()

	if "embedcontent" in methods or "embedding" in name:
		return "Text Embeddings"
	if "tts" in name.split("-") or name.endswith("-tts") or "-tts-" in name:
		return "Text to Speech"
	if "transcribe" in name:
		return "Speech to Text"
	if "image" in name.split("-"):
		return "Image Generation"
	if name.startswith("veo"):
		return "Video Generation"
	if name.startswith("lyria"):
		return "Audio Generation"
	return "Text Generation"


def gemini_modalities(model_id: str, capability: str, prices: list[Price]) -> tuple[str, str]:
	"""Input and output modalities, read off the rates rather than assumed.

	The price table is the only place Google states this per model: a cell
	reading "$0.50 (text/image)" is the statement that the model takes images.
	"""
	inputs = {p.modality for p in prices if p.kind in ("Input", "Cached Input")}
	outputs = {p.modality for p in prices if p.kind in ("Output", "Reasoning")}

	inputs.add("Text")
	if capability == "Text to Speech":
		outputs.add("Audio")
	if capability == "Image Generation":
		outputs.add("Image")
	if capability == "Video Generation":
		outputs.add("Video")
	if capability == "Audio Generation":
		outputs.add("Audio")
	outputs = outputs or {"Text"}

	order = ["Text", "Image", "Audio", "Video", "File"]
	fmt = lambda s: ",".join(m.lower() for m in order if m in s)  # noqa: E731
	return fmt(inputs), fmt(outputs)
