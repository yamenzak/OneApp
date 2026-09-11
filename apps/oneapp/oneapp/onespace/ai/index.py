"""What a record is about, as a direction, so "which of these" has an answer.

This is the half of linking that is not a prompt. `docs/DOCUMENT-MAIL.md` §6
is exact about the shape and it does not bend: **retrieve deterministically,
then rank with a model.** Never "here is an email, which of our records is it
about?" — that is a hallucinated foreign key on a financial document. What a
model may be asked is "which of these five", with the five in front of it.

Producing the five is this module. An embedding per record turns the question
from a guess into a nearest-neighbour lookup, and the lookup is boring
arithmetic that can be checked.

Four decisions, and the first is the one that made the rest easy.

**The scan is a full scan, capped, in pure Python.** MariaDB has no vector
index and the honest way to get one is a vector database, which is a second
runtime and the thing this product keeps declining — so the question was
whether a scan is fast enough. Measured rather than assumed: 2,000 rows of
768 dimensions dot in about 60ms, because the vectors are stored normalised
and the inner loop is `sum(map(mul, …))` over an `array('f')`. That is fine
inside the background job that does the linking, and `MAX_SCAN` is that
number rather than a guess.

**Nothing is embedded twice for nothing.** `digest` is a hash of the text
that was embedded. A save that moved a date re-reads the record, hashes the
same text and spends no credits. Without it every save on the site would be a
metered call, which is the difference between this costing a few pounds and
costing a salary.

**Only what a space exposes.** The corpus is the doctypes the workspace's own
screens are about — `sync.granted_doctypes()`, the same set the assistant can
read — because a site's `Version` rows are not what anybody's mail is about
and embedding them would be paying to index a log.

**A vector belongs to the model that made it.** Two models' vectors are not
comparable at all, so `nearest` filters on the model in use and a workspace
that changes model gets an index that rebuilds rather than one that quietly
ranks noise.
"""

import array
import base64
import hashlib
import math
from operator import mul

import frappe

from oneapp.onespace.ai.features import ai_feature

EMBEDDING = "AI Embedding"

#: Rows one search reads. See the module docstring: a measured ceiling, not a
#: taste. Newest first, because a message arriving today is about something
#: somebody has touched recently far more often than not.
MAX_SCAN = 2_000

#: Characters of a record that get embedded. Past this it is a contract, and
#: what an embedding is for is what the record is *about*.
MAX_TEXT = 4_000

#: Records one build pass embeds. A pass that tried to do a whole site would
#: be one job holding a worker for an hour; this chains instead, enqueuing the
#: next pass while there is anything left.
BATCH = 50

#: Fieldtypes worth reading. A record is identified by its words and by who
#: and what it points at; its amounts and dates are what a *filter* is for and
#: put nothing into the meaning of "the Al Reem cladding quote".
WORDS = {"Data", "Small Text", "Text", "Long Text", "Text Editor", "Select",
         "Link", "Dynamic Link", "Read Only"}

#: Never, whatever a doctype says. Frappe's own bookkeeping, and the fields
#: that are ids rather than words.
NEVER = {"name", "owner", "modified_by", "parent", "parenttype", "parentfield",
         "idx", "docstatus", "naming_series", "amended_from"}


@ai_feature(
	"index.embed",
	label="Search index",
	capability="Text Embeddings",
	description="Turns a record into a vector, so mail can be matched to it.",
	# No system prompt: an embedding model takes text and returns a direction,
	# and there is nothing to instruct. The decorator is here for the other
	# four things it gives — the model picker, the switch, the credit hold and
	# the entry in the operator's registry.
	system="",
	allow_prompt_addendum=False,
	max_input_tokens=2_000,
)
def embed(ai, text: str) -> dict:
	"""One piece of text as a vector."""
	answer = ai(text[:MAX_TEXT])
	return {"vector": answer.get("embedding") or [],
	        "credits": answer.get("credits") or 0,
	        "model": answer.get("model") or ""}


# --------------------------------------------------------------------------- #
# Storing one
# --------------------------------------------------------------------------- #

def pack(values: list[float]) -> str:
	"""A vector as base64 of normalised float32.

	Normalised here rather than at read time, which is what makes the read a
	dot product instead of a dot product and two square roots per row.
	"""
	length = math.sqrt(sum(one * one for one in values)) or 1.0
	return base64.b64encode(
		array.array("f", [one / length for one in values]).tobytes()
	).decode()


def unpack(blob: str) -> "array.array":
	found = array.array("f")
	found.frombytes(base64.b64decode(blob or ""))
	return found


def digest_of(text: str) -> str:
	return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:32]


def remember(doctype: str, name: str) -> bool:
	"""Index one record, unless it is already indexed as it reads now.

	Returns whether a call was made, which is what the build pass counts to
	know when it has caught up.
	"""
	text, title = describe(doctype, name)
	if not text:
		return False

	want = digest_of(text)
	model = model_in_use()
	existing = frappe.db.get_value(
		EMBEDDING,
		{"reference_doctype": doctype, "reference_name": name},
		["name", "digest", "model_key"],
		as_dict=True,
	)
	if existing and existing.digest == want and existing.model_key == model:
		return False

	answer = embed(text)
	values = answer.get("vector") or []
	if not values:
		return False

	row = {
		"reference_doctype": doctype,
		"reference_name": name,
		"title": title[:140],
		"model_key": answer.get("model") or model,
		"dims": len(values),
		"digest": want,
		"vector": pack(values),
	}
	if existing:
		frappe.db.set_value(EMBEDDING, existing.name, row, update_modified=True)
	else:
		frappe.get_doc({"doctype": EMBEDDING, **row}).insert(ignore_permissions=True)
	return True


def forget(doctype: str, name: str) -> None:
	for row in frappe.get_all(EMBEDDING, filters={
		"reference_doctype": doctype, "reference_name": name,
	}, pluck="name", ignore_permissions=True):
		frappe.delete_doc(EMBEDDING, row, force=True, ignore_permissions=True)


def describe(doctype: str, name: str) -> tuple[str, str]:
	"""One record as the text that says what it is about, and its title.

	Built from the doctype's own meta rather than from a screen, because a
	record can be on two screens or none and what it is *about* does not
	change with where it is being looked at.

	Labelled lines rather than a bag of values: "Customer: Al Reem
	Consultants" and "Al Reem Consultants" mean different things to an
	embedding, and the first is the one that matches an email mentioning a
	customer.
	"""
	try:
		doc = frappe.get_doc(doctype, name)
		meta = frappe.get_meta(doctype)
	except Exception:
		return "", ""

	title = str(doc.get(meta.get_title_field() or "name") or name)
	said = [f"{doctype}: {title}", f"Reference: {name}"]

	for field in meta.fields:
		if field.fieldtype not in WORDS or field.fieldname in NEVER:
			continue
		# A field nobody may read at this level is a field that must not be in
		# a vector either: what is searchable is what is readable.
		if field.get("permlevel"):
			continue
		value = doc.get(field.fieldname)
		if value in (None, ""):
			continue
		value = frappe.utils.strip_html(str(value)).strip()
		if not value:
			continue
		said.append(f"{field.label or field.fieldname}: {value}")
		if sum(len(one) for one in said) > MAX_TEXT:
			break

	return "\n".join(said)[:MAX_TEXT], title


# --------------------------------------------------------------------------- #
# Reading them back
# --------------------------------------------------------------------------- #

def model_in_use() -> str:
	"""Which embedding model this workspace is on, or nothing.

	Nothing rather than an exception: a site whose catalogue has no embeddings
	model at all is a site with no index, and every caller here already treats
	an empty model as "do not filter on one". Letting `model_for` throw would
	turn the coverage panel into a 500 and a save hook into a logged error on
	a site that is simply not using this.
	"""
	from oneapp.onespace.ai import features, settings

	feature = features.get("oneapp.index.embed")
	if not feature:
		return ""
	try:
		return settings.model_for(feature)
	except Exception:
		return ""


def nearest(text: str, doctypes: list[str] | None = None,
            limit: int = 8) -> list[dict]:
	"""The indexed records closest in meaning to some text.

	Candidates, not an answer. What comes back is a list somebody — a model,
	or a person looking at a card — then chooses from, and every one of them
	is checked against the reader before it is shown. This function knows
	nothing about who is asking and deliberately does not: it is arithmetic
	over a table, and permission is the caller's to apply.
	"""
	asked = embed(text).get("vector") or []
	if not asked:
		return []
	return among(pack(asked), doctypes, limit)


def among(packed: str, doctypes: list[str] | None = None,
          limit: int = 8) -> list[dict]:
	"""The same, for a vector somebody already has."""
	model = model_in_use()
	filters = {"model_key": model} if model else {}
	if doctypes:
		filters["reference_doctype"] = ("in", list(doctypes))

	rows = frappe.get_all(
		EMBEDDING,
		filters=filters,
		fields=["reference_doctype", "reference_name", "title", "vector"],
		order_by="modified desc",
		limit_page_length=MAX_SCAN,
		ignore_permissions=True,
	)
	if not rows:
		return []

	query = unpack(packed)
	scored = []
	for row in rows:
		vector = unpack(row.vector)
		if len(vector) != len(query):
			# A row from another model, or from a model that changed its
			# dimensions under the same name. Skipped rather than scored:
			# a dot product over mismatched lengths is a number with no
			# meaning, and `zip` would quietly produce one.
			continue
		scored.append((sum(map(mul, query, vector)), row))

	scored.sort(key=lambda one: one[0], reverse=True)
	return [
		{
			"doctype": row.reference_doctype,
			"name": row.reference_name,
			"title": row.title or row.reference_name,
			"score": round(score, 4),
		}
		for score, row in scored[:limit]
	]


# --------------------------------------------------------------------------- #
# Keeping it up to date
# --------------------------------------------------------------------------- #

#: Cache of the doctypes worth indexing, for the same reason `written.py`
#: caches which ones carry a mark: the save hook runs on every save on the
#: site, and asking the sync state on each of them is a query to learn that
#: this one is a Version row.
INDEXED = "oneapp_ai_indexed_doctypes"


def indexable() -> set[str]:
	cached = frappe.cache.get_value(INDEXED)
	if cached is None:
		from oneapp.onespace import sync

		try:
			cached = sorted(sync.granted_doctypes())
		except Exception:
			cached = []
		frappe.cache.set_value(INDEXED, cached, expires_in_sec=600)
	return set(cached)


def on_save(doc, method=None) -> None:
	"""Keep one record's vector honest, when its words have changed.

	Enqueued rather than done here: an embedding is a network call and a save
	is not the place for one. `enqueue_after_commit` because a job that starts
	before the transaction lands reads the row as it was.
	"""
	if doc.doctype not in indexable():
		return
	if not enabled():
		return
	frappe.enqueue(
		"oneapp.onespace.ai.index.refresh",
		queue="long",
		enqueue_after_commit=True,
		# One job per record in flight. Ten saves of a record in a minute is
		# one embedding, not ten — and the digest would have caught the other
		# nine anyway, one metered call later each.
		job_id=f"ai-index::{doc.doctype}::{doc.name}",
		deduplicate=True,
		doctype=doc.doctype,
		name=doc.name,
	)


def on_delete(doc, method=None) -> None:
	if doc.doctype in indexable():
		forget(doc.doctype, doc.name)


def refresh(doctype: str, name: str) -> None:
	"""The job `on_save` enqueues. Never raises: an index is not the record."""
	try:
		remember(doctype, name)
	except Exception:
		frappe.log_error(title=f"Indexing {doctype} {name} failed",
		                 message=frappe.get_traceback())


def enabled() -> bool:
	"""Whether indexing can actually happen, which is three questions.

	The model is the third and it is not a formality: a site whose catalogue
	carries no embeddings model answers yes to the other two, and a build
	would then walk every record on the site logging one failed call each.
	"""
	from oneapp.onespace.ai import features, gateway

	return bool(
		gateway.is_configured()
		and features.is_enabled("oneapp.index.embed")
		and model_in_use()
	)


# --------------------------------------------------------------------------- #
# Building it in the first place
# --------------------------------------------------------------------------- #

def build(after: str = "") -> dict:
	"""Embed a batch of records that have none, and queue the next batch.

	Chained rather than scheduled, and that is the whole of this product's
	position on AI doing things nobody asked for: a build starts because
	somebody switched the feature on or pressed Rebuild, runs until it has
	caught up, and then stops. Nothing wakes it again.

	`after` is where the last pass got to, as `doctype::name`, so a site with
	forty thousand records walks it in order rather than re-reading the same
	page.
	"""
	if not enabled():
		return {"ok": False, "reason": "disabled"}

	doctypes = sorted(indexable())
	if not doctypes:
		return {"ok": True, "done": True, "embedded": 0}

	at_doctype, _, at_name = after.partition("::")
	embedded, last = 0, after

	for doctype in doctypes:
		if at_doctype and doctype < at_doctype:
			continue
		filters = {"name": (">", at_name)} if doctype == at_doctype and at_name else {}
		try:
			rows = frappe.get_all(doctype, filters=filters, pluck="name",
			                      order_by="name asc",
			                      limit_page_length=BATCH - embedded,
			                      ignore_permissions=True)
		except Exception:
			# A doctype a space declares and this site no longer has. The
			# build is not the place to find out loudly.
			continue

		for name in rows:
			refresh(doctype, name)
			embedded += 1
			last = f"{doctype}::{name}"
			if embedded >= BATCH:
				break
		if embedded >= BATCH:
			break
		# Finished this doctype; the next one starts from its beginning.
		at_doctype, at_name = "", ""

	if embedded >= BATCH:
		frappe.enqueue("oneapp.onespace.ai.index.build", queue="long",
		               job_id="ai-index-build", deduplicate=True, after=last)
		return {"ok": True, "done": False, "embedded": embedded, "after": last}

	return {"ok": True, "done": True, "embedded": embedded}


@frappe.whitelist(methods=["POST"])
def rebuild() -> dict:
	"""Start a build. An admin's button, and the only thing that starts one.

	Enqueued rather than run, because catching up a site is minutes of calls
	and a request that waits for it is a worker nobody gets back.
	"""
	from oneapp.onespace.workspace import require_owner

	require_owner()
	frappe.enqueue("oneapp.onespace.ai.index.build", queue="long",
	               job_id="ai-index-build", deduplicate=True)
	return {"ok": True}


@frappe.whitelist(methods=["GET"])
def coverage() -> dict:
	"""How much of the workspace is indexed, for the panel that offers Rebuild."""
	from oneapp.onespace.workspace import require_owner

	require_owner()
	model = model_in_use()
	return {
		"enabled": enabled(),
		"model": model,
		"indexed": frappe.db.count(EMBEDDING, {"model_key": model} if model else None),
		"doctypes": sorted(indexable()),
	}
