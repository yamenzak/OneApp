"""Keeping the model catalogue true, without anyone maintaining it.

Providers ship models weekly and re-price them without notice. A table of
models and prices typed by hand is wrong within a month, and the way you find
out is a margin, not an error. So this fetches: what exists and what it can do
from each provider's API, what it costs from the page each provider publishes.

Four rules hold the whole thing up:

  * **A model nothing could price is not sellable.** It lands as Needs Review
    with the wording that defeated the parser. There is no default price, because
    the failure mode of a default is billing a customer a number we invented.

  * **The sync never overrules an operator.** It creates rows and refreshes
    facts. Whether a model is offered is a decision, and the only decisions it
    makes on its own are the two it must: a model that stopped being priceable
    comes off sale, and a model the provider dropped is retired.

  * **Nothing is deleted.** Usage records point at models; a retired model still
    has to explain a charge from last March.

  * **Markup is ours.** `markup_override` and `is_recommended` are never touched
    here — they are the commercial decisions the catalogue exists to carry.
"""

import json

import frappe
import requests
from frappe.utils import now_datetime, today

from oneapp_control.ai import capabilities, sources

TIMEOUT = 60

CF_API = "https://api.cloudflare.com/client/v4"
CF_PRICING_URL = "https://developers.cloudflare.com/workers-ai/platform/pricing/index.md"
GOOGLE_API = "https://generativelanguage.googleapis.com/v1beta"
GOOGLE_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing.md.txt"

# Providers are the AI Gateway path segment, used verbatim in the request URL.
WORKERS = "workers-ai"
GOOGLE = "google-ai-studio"


class SyncError(Exception):
	pass


def settings():
	return frappe.get_single("OneApp Control Settings")


def _get(url, headers=None, params=None) -> requests.Response:
	try:
		response = requests.get(url, headers=headers or {}, params=params, timeout=TIMEOUT)
	except requests.RequestException as e:
		raise SyncError(f"{url}: {e}") from e
	if response.status_code != 200:
		raise SyncError(f"{url}: HTTP {response.status_code} {response.text[:200]}")
	return response


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #

def fetch_workers_models(account_id: str, token: str) -> list[dict]:
	"""Every Workers AI model Cloudflare will serve us, with its task."""
	models, page = [], 1
	while True:
		payload = _get(
			f"{CF_API}/accounts/{account_id}/ai/models/search",
			headers={"Authorization": f"Bearer {token}"},
			params={"per_page": 100, "page": page, "hide_experimental": "false"},
		).json()
		batch = payload.get("result") or []
		models.extend(batch)
		if len(batch) < 100:
			return models
		page += 1
		if page > 20:  # A runaway pager is a bug, not a very large catalogue.
			return models


def fetch_gemini_models(key: str) -> list[dict]:
	models, token = [], None
	while True:
		params = {"key": key, "pageSize": 200}
		if token:
			params["pageToken"] = token
		payload = _get(f"{GOOGLE_API}/models", params=params).json()
		models.extend(payload.get("models") or [])
		token = payload.get("nextPageToken")
		if not token or len(models) > 2000:
			return models


def _properties(model: dict) -> dict:
	"""Cloudflare's properties arrive as a list of id/value pairs."""
	out = {}
	for row in model.get("properties") or []:
		if isinstance(row, dict) and row.get("property_id"):
			out[str(row["property_id"])] = row.get("value")
	return out


def _flag(value) -> int:
	return 1 if str(value).strip().lower() in ("true", "1", "yes") else 0


def _int(value) -> int:
	try:
		return int(str(value).strip())
	except (TypeError, ValueError):
		return 0


# --------------------------------------------------------------------------- #
# Shaping a provider's answer into a catalogue row
# --------------------------------------------------------------------------- #

# Capabilities that do not take a text prompt at all. Everything else does, even
# where the interesting input is a picture — a vision model is asked a question.
NO_TEXT_INPUT = {"Speech to Text", "Object Detection"}


def _workers_modalities(capability: str, prices: list) -> tuple[str, str]:
	inputs = set() if capability in NO_TEXT_INPUT else {"text"}
	outputs = set()

	for price in prices:
		if price.kind in ("Input", "Cached Input") and price.modality != "Text":
			inputs.add(price.modality.lower())
		if price.kind == "Output" and price.modality != "Text":
			outputs.add(price.modality.lower())

	if capability in ("Image Understanding", "Classification", "Object Detection"):
		inputs.add("image")
	if capability == "Speech to Text":
		inputs.add("audio")
	if capability == "Image Generation":
		outputs.add("image")
	if capability == "Text to Speech":
		outputs.add("audio")
	if capability in ("Text Embeddings", "Reranking"):
		outputs = {"embedding"}

	order = ["text", "image", "audio", "video", "file", "embedding"]
	fmt = lambda s: ",".join(m for m in order if m in s)  # noqa: E731
	return fmt(inputs), fmt(outputs or {"text"})


def workers_rows(models: list[dict], pricing_md: str) -> list[dict]:
	tasks = {
		m.get("name"): ((m.get("task") or {}).get("name") or "")
		for m in models if m.get("name")
	}
	caps = {mid: capabilities.for_task(task) for mid, task in tasks.items()}
	priced = sources.parse_workers_pricing(pricing_md, {k: v for k, v in caps.items() if v})

	rows = []
	for model in models:
		model_id = model.get("name")
		if not model_id:
			continue

		props = _properties(model)
		capability = caps.get(model_id)
		parsed = priced.get(model_id) or sources.Parsed()
		notes = list(parsed.notes)

		if not capability:
			notes.append(f"unrecognised task {tasks.get(model_id)!r}")
		if model_id not in priced:
			notes.append("no published price on the Workers AI pricing page")

		inputs, outputs = _workers_modalities(capability or "", parsed.prices)
		rows.append({
			"provider": WORKERS,
			"model_id": model_id,
			"display_name": model_id.split("/")[-1],
			"capability": capability,
			"input_modalities": inputs,
			"output_modalities": outputs,
			"context_window": _int(props.get("context_window")),
			"max_output_tokens": _int(props.get("max_output_tokens")),
			"supports_tools": _flag(props.get("function_calling")),
			"supports_json": _flag(props.get("json_mode") or props.get("function_calling")),
			"supports_reasoning": _flag(props.get("reasoning")),
			"supports_streaming": 1 if capability == "Text Generation" else 0,
			"deprecation_date": props.get("planned_deprecation_date") or None,
			"description": (model.get("description") or "")[:500],
			"source": "Cloudflare API",
			"prices": parsed.prices,
			"unparsed": parsed.unparsed,
			"notes": notes,
			"preview": _flag(props.get("beta")),
		})
	return rows


def gemini_rows(models: list[dict], pricing_txt: str) -> list[dict]:
	priced = sources.parse_gemini_pricing(pricing_txt)
	rows = []

	for model in models:
		model_id = (model.get("name") or "").split("/")[-1]
		if not model_id:
			continue

		methods = model.get("supportedGenerationMethods") or []
		capability = sources.gemini_capability(model_id, methods)
		parsed = priced.get(model_id) or sources.Parsed()
		notes = list(parsed.notes)
		if model_id not in priced:
			notes.append("no published price on the Gemini pricing page")

		inputs, outputs = sources.gemini_modalities(model_id, capability, parsed.prices)
		preview = any(word in model_id for word in ("preview", "exp", "experimental"))

		rows.append({
			"provider": GOOGLE,
			"model_id": model_id,
			"display_name": model.get("displayName") or model_id,
			"capability": capability,
			"input_modalities": inputs,
			"output_modalities": "embedding" if capability == "Text Embeddings" else outputs,
			"context_window": _int(model.get("inputTokenLimit")),
			"max_output_tokens": _int(model.get("outputTokenLimit")),
			# Every current Gemini generative model takes tools and structured
			# output; the models API does not say so, and claiming otherwise
			# would hide features that work.
			"supports_tools": 1 if capability == "Text Generation" else 0,
			"supports_json": 1 if capability == "Text Generation" else 0,
			"supports_reasoning": _flag(model.get("thinking")),
			"supports_streaming": 1 if "streamgeneratecontent" in
			                      [m.lower() for m in methods] else 0,
			"description": (model.get("description") or "")[:500],
			"source": "Google API",
			"prices": parsed.prices,
			"unparsed": parsed.unparsed,
			"notes": notes,
			"preview": 1 if preview else 0,
		})
	return rows


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

# Capabilities whose whole product is the output, so a missing output rate means
# we would generate for free and bill for nothing.
#
# Not every model has an input rate and that is not a fault: Cloudflare bills
# Flux only for the picture it draws, and Deepgram's speech models only for the
# text going in. Requiring both would hold back models that are priced correctly.
NEEDS_OUTPUT_RATE = {"Text Generation", "Image Generation"}


def _status(row: dict) -> tuple[str, list[str]]:
	"""Whether a model can be sold, and why not when it cannot."""
	blockers = []
	kinds = {p.kind for p in row["prices"]}

	if not row["capability"]:
		blockers.append("capability unknown")
	if not row["prices"]:
		blockers.append("no rate could be read")
	elif row["capability"] in NEEDS_OUTPUT_RATE and "Output" not in kinds:
		blockers.append("no output rate")

	for phrase in row["unparsed"]:
		blockers.append(f"could not price: {phrase}")

	if blockers:
		return "Needs Review", blockers
	return ("Preview" if row["preview"] else "Available"), []


def _price_children(prices) -> list[dict]:
	return [
		{
			"kind": p.kind, "modality": p.modality, "unit": p.unit,
			"cost_usd": p.cost_usd, "per_units": p.per_units, "tier": p.tier,
			"effective_from": p.effective_from, "effective_to": p.effective_to,
			"note": p.note,
		}
		for p in prices
	]


def _upsert(row: dict, report: dict):
	key = f"{row['provider']}:{row['model_id']}"
	status, blockers = _status(row)
	note = "\n".join(blockers + row["notes"])[:1000]

	existing = frappe.db.exists("AI Model", key)
	doc = frappe.get_doc("AI Model", key) if existing else frappe.new_doc("AI Model")

	doc.update({
		"model_key": key,
		"provider": row["provider"],
		"model_id": row["model_id"],
		"display_name": row["display_name"],
		# A model whose task we could not place keeps whatever an operator set,
		# rather than being moved into a bucket we guessed.
		"capability": row["capability"] or doc.capability or "Text Generation",
		"input_modalities": row["input_modalities"],
		"output_modalities": row["output_modalities"],
		"context_window": row["context_window"],
		"max_output_tokens": row["max_output_tokens"],
		"supports_tools": row["supports_tools"],
		"supports_json": row["supports_json"],
		"supports_reasoning": row["supports_reasoning"],
		"supports_streaming": row["supports_streaming"],
		"deprecation_date": row.get("deprecation_date") or None,
		"description": row["description"],
		"source": row["source"],
		"sync_note": note,
		"last_synced": now_datetime(),
	})

	doc.set("prices", _price_children(row["prices"]))

	if not existing:
		doc.status = status
		report["created"].append(key)
	elif status == "Needs Review":
		# The one status the sync imposes: a model it can no longer price must
		# not keep selling at yesterday's rates.
		if doc.status != "Needs Review":
			report["withdrawn"].append(key)
		doc.status = "Needs Review"
	elif doc.status == "Needs Review":
		# It prices again, so put it back. Needs Review is this sync's own verdict
		# and never an operator's — their decisions are Available, Preview,
		# Deprecated and Retired, none of which are touched here. Leaving a model
		# held back after the reason went away would need someone to notice.
		doc.status = status
		report["restored"].append(key)
	else:
		report["updated"].append(key)

	doc.save(ignore_permissions=True)


def _retire(seen: set[str], report: dict):
	"""A model the provider no longer lists cannot be called, whatever we think."""
	for name, status in frappe.get_all(
		"AI Model", fields=["name", "status"], as_list=True
	):
		if name in seen or status == "Retired":
			continue
		frappe.db.set_value("AI Model", name, {
			"status": "Retired",
			"sync_note": f"Not listed by the provider on {today()}.",
		})
		report["retired"].append(name)


@frappe.whitelist()
def sync() -> dict:
	"""Refresh the catalogue. Returns what changed and what needs a human."""
	conf = settings()
	report = {
		"created": [], "updated": [], "withdrawn": [], "restored": [],
		"retired": [], "errors": [],
	}
	seen: set[str] = set()

	for provider, run in (
		(WORKERS, lambda: _sync_workers(conf)),
		(GOOGLE, lambda: _sync_google(conf)),
	):
		try:
			rows = run()
		except SyncError as e:
			# One provider being unreachable must not retire the other's models.
			report["errors"].append(f"{provider}: {e}")
			seen |= set(frappe.get_all(
				"AI Model", filters={"provider": provider}, pluck="name"))
			continue

		for row in rows:
			seen.add(f"{row['provider']}:{row['model_id']}")
			_upsert(row, report)

	if not report["errors"]:
		_retire(seen, report)

	summary = ", ".join(
		f"{len(report[k])} {k}" for k in
		("created", "updated", "withdrawn", "restored", "retired") if report[k]
	)
	frappe.db.set_single_value("OneApp Control Settings", {
		"ai_catalogue_synced_on": now_datetime(),
		"ai_catalogue_note": (summary or "nothing changed") + (
			"\n" + "\n".join(report["errors"]) if report["errors"] else ""),
	})
	frappe.db.commit()
	return report


def _sync_workers(conf) -> list[dict]:
	account_id = conf.cf_account_id
	token = conf.get_password("cf_api_token", raise_exception=False)
	if not (account_id and token):
		raise SyncError("Cloudflare account id and API token are not set.")

	models = fetch_workers_models(account_id, token)
	return workers_rows(models, _get(CF_PRICING_URL).text)


def _sync_google(conf) -> list[dict]:
	key = conf.get_password("google_ai_key", raise_exception=False)
	if not key:
		raise SyncError("Google AI Studio key is not set.")

	models = fetch_gemini_models(key)
	return gemini_rows(models, _get(GOOGLE_PRICING_URL).text)


def scheduled_sync():
	"""Weekly, from hooks. Never raises — a failed sync leaves the old prices,
	which are the last ones we know were real."""
	try:
		sync()
	except Exception:
		frappe.log_error(title="AI catalogue sync failed", message=frappe.get_traceback())


def catalogue_for_tenant() -> list[dict]:
	"""What a workspace may choose from, with enough price to meter locally."""
	models = frappe.get_all(
		"AI Model",
		filters={"status": ["in", ["Available", "Preview"]]},
		fields=[
			"name as model_key", "display_name", "provider", "model_id", "capability",
			"input_modalities", "output_modalities", "context_window",
			"max_output_tokens", "supports_tools", "supports_json",
			"supports_reasoning", "is_recommended", "status",
		],
		order_by="capability asc, is_recommended desc, display_name asc",
	)
	for model in models:
		model["prices"] = frappe.get_all(
			"AI Model Price",
			filters={"parent": model["model_key"], "tier": "Standard"},
			fields=["kind", "modality", "unit", "cost_usd", "per_units",
			        "effective_from", "effective_to"],
			order_by="idx asc",
		)
	return models


def as_json(value) -> str:
	return json.dumps(value, default=str, sort_keys=True)
