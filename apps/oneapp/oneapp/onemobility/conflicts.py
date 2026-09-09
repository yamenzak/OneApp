"""Two sources claiming one key, and what is drawn when they disagree.

README §6 is the argument and it turns on one sentence: *"connect all your
sources and the system smartly handles duplicates" is the right feature and the
wrong sentence*. Software that silently drops one of two disagreeing numbers is
software nobody trusts twice — and in this market the disagreement is often the
interesting part, because the two answers came from a planning department and
from a vehicle.

So nothing here merges. Every entity carries a **natural key** from its feed,
every source's answer for that key is written down as a `Transit Claim`, and
the customer's **precedence** decides which claim the screens draw. The rest
stay, marked Overruled, next to the one that won.

**The winner is a whole claim, not a field at a time.** Taking each field from
whichever source ranks highest for it sounds better and is worse: it is how a
stop ends up named Alexanderplatz with Spandau's coordinates, and neither
source ever said that. A record stays internally consistent — one source's
answer, entire — and the other answers are one click away.

**Precedence is live.** A customer who reorders their sources expects the map
to change, so a change to the number re-settles every key that source claims
rather than waiting for the next delivery. That is what makes it a setting
instead of an import-time snapshot.

What is *not* a conflict is one source claiming a key nobody else does, which
is nearly every key on nearly every workspace. That case writes one claim, marks
it Drawn, and costs one row.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

#: Which fields of each reference noun a source is claiming, and the natural key
#: they are claimed against. Deliberately not "every field on the doctype": a
#: colour somebody chose in our UI, an emoji, a marker shape and a status are
#: the *workspace's* answers and no feed has an opinion about them. A source
#: that overwrote those on every delivery would make the record uneditable and
#: nobody would be able to say why.
CLAIMED = {
	"Transit Agency": ("agency_key", "Agency", "agency_name",
	                   ("agency_name", "timezone", "url")),
	"Transit Line": ("line_key", "Line", "line_name",
	                 ("short_name", "line_name", "agency", "mode")),
	"Transit Stop": ("stop_key", "Stop", "stop_name",
	                 ("stop_name", "stop_code", "latitude", "longitude", "zone")),
	"Transit Vehicle": ("vehicle_key", "Vehicle", "label",
	                    ("label", "mode", "seats", "standing")),
}

#: What a source with no precedence set counts as. The same default the doctype
#: carries, so a source somebody never thought about does not silently win.
DEFAULT_PRECEDENCE = 100


def _guard(write: bool = False):
	if not frappe.has_permission("Transit Line", "write" if write else "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def _apply(doctype: str, name: str, values: dict):
	doc = frappe.get_doc(doctype, name)
	doc.update(values)
	doc.save(ignore_permissions=True)


def record(doctype: str, key: str, values: dict, source: str = "", feed: str = "") -> str:
	"""One reference record, by natural key, with the claim behind it kept.

	Called by every importer in place of a bare upsert. Without a source — a
	fixture, a hand-made row — it is exactly the upsert it replaced, because a
	claim nobody can attribute is a row that answers no question.
	"""
	key_field, _entity, _label_field, _fields = CLAIMED[doctype]
	name = frappe.db.get_value(doctype, {key_field: key}, "name")
	if not name:
		doc = frappe.get_doc({"doctype": doctype, key_field: key, **values})
		doc.insert(ignore_permissions=True)
		name = doc.name

	if not source:
		_apply(doctype, name, values)
		return name

	remember(doctype, key, name, values, source, feed)
	settle(doctype, key, name)
	return name


def remember(doctype: str, key: str, name: str, values: dict, source: str, feed: str = ""):
	"""Write down what one source says about one key. One row per pair."""
	key_field, entity, label_field, fields = CLAIMED[doctype]
	claimed = {one: values.get(one) for one in fields if one in values}

	existing = frappe.db.get_value(
		"Transit Claim", {"entity": entity, "natural_key": key, "source": source}, "name"
	)
	row = {
		"label": str(claimed.get(label_field) or key)[:140],
		"record": name,
		"feed": feed or "",
		"precedence": _precedence(source),
		"claimed": json.dumps(claimed, default=str, sort_keys=True),
		"seen_on": now_datetime(),
	}
	if existing:
		frappe.db.set_value("Transit Claim", existing, row, update_modified=False)
		return existing
	return frappe.get_doc({
		"doctype": "Transit Claim", "entity": entity, "natural_key": key,
		"source": source, "verdict": "Drawn", **row,
	}).insert(ignore_permissions=True).name


def _precedence(source: str) -> int:
	value = frappe.db.get_value("Transit Source", source, "precedence")
	return cint(value) if value else DEFAULT_PRECEDENCE


def settle(doctype: str, key: str, name: str = "") -> dict:
	"""Decide which claim is drawn, apply it, and mark the others.

	Lowest precedence wins; a tie goes to whichever was seen most recently,
	which is the only tie-break that does not depend on row order. A claim that
	states the same values as the winner is neither drawn nor overruled — it
	Agrees, and two sources agreeing is a fact worth showing rather than a
	conflict worth flagging.
	"""
	key_field, entity, _label, _fields = CLAIMED[doctype]
	claims = frappe.get_all(
		"Transit Claim",
		filters={"entity": entity, "natural_key": key},
		fields=["name", "source", "precedence", "claimed", "seen_on"],
		order_by="precedence asc, seen_on desc",
	)
	if not claims:
		return {"drawn": "", "contested": False}

	winner = claims[0]
	won = _values(winner)
	contested = False
	verdicts = {}
	for claim in claims:
		if claim["name"] == winner["name"]:
			verdicts[claim["name"]] = ("Drawn", "")
			continue
		differs = sorted(
			one for one, value in _values(claim).items()
			if _differs(value, won.get(one))
		)
		contested = contested or bool(differs)
		verdicts[claim["name"]] = (
			"Overruled" if differs else "Agrees", ", ".join(differs)
		)

	for claim_name, (verdict, differs) in verdicts.items():
		frappe.db.set_value(
			"Transit Claim", claim_name,
			{"verdict": verdict, "differs": differs[:400], "contested": cint(contested)},
			update_modified=False,
		)

	target = name or frappe.db.get_value(doctype, {key_field: key}, "name")
	if target and won:
		_apply(doctype, target, won)
	return {"drawn": winner["source"], "contested": contested}


def _values(claim: dict) -> dict:
	try:
		return json.loads(claim.get("claimed") or "{}")
	except ValueError:
		return {}


def _differs(one, other) -> bool:
	"""Whether two claims about one field are actually different answers.

	Numbers compared as numbers and strings stripped, because two feeds writing
	`52.5` and `52.50000` — or a trailing space — is not a disagreement anybody
	wants to be shown a badge about.
	"""
	if isinstance(one, (int, float)) and isinstance(other, (int, float)):
		return abs(float(one) - float(other)) > 1e-6
	return str(one or "").strip() != str(other or "").strip()


def resettle(source: str) -> int:
	"""Every key this source claims, decided again.

	Run when its precedence changes, which is the whole reason precedence is a
	setting rather than an import-time snapshot: a customer who reorders their
	sources expects the map to change now, not after the next delivery.
	"""
	frappe.db.set_value(
		"Transit Claim", {"source": source}, "precedence", _precedence(source),
		update_modified=False,
	)
	byentity = {entity: doctype for doctype, (_k, entity, _l, _f) in CLAIMED.items()}
	claims = frappe.get_all(
		"Transit Claim", filters={"source": source}, fields=["entity", "natural_key"]
	)
	for claim in claims:
		doctype = byentity.get(claim["entity"])
		if doctype:
			settle(doctype, claim["natural_key"])
	return len(claims)


def on_source_change(doc, method=None):
	"""Frappe's `on_update`. Only a precedence change means anything here."""
	if doc.has_value_changed("precedence"):
		resettle(doc.name)


# --------------------------------------------------------------------------- #
# What a person sees
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def disagreements(entity: str = "", limit: int = 50) -> dict:
	"""The keys two sources answer differently, with both answers.

	This is the honest version of "select all sources": it is not merging, it
	is choosing whose answer to draw, and it can always show you the others.
	"""
	_guard()
	rows = frappe.get_all(
		"Transit Claim",
		filters={"contested": 1, **({"entity": entity} if entity else {})},
		fields=["name", "entity", "natural_key", "label", "source", "record",
		        "verdict", "precedence", "differs", "claimed"],
		order_by="entity asc, natural_key asc, precedence asc",
		limit_page_length=max(10, min(cint(limit) or 50, 500)) * 4,
	)

	grouped: dict[tuple, dict] = {}
	for row in rows:
		at = grouped.setdefault(
			(row["entity"], row["natural_key"]),
			{"entity": row["entity"], "key": row["natural_key"],
			 "record": row["record"], "label": row["label"], "claims": []},
		)
		at["claims"].append({
			"claim": row["name"],
			"source": row["source"],
			"verdict": row["verdict"],
			"precedence": row["precedence"],
			"differs": [one for one in (row["differs"] or "").split(", ") if one],
			"values": _values(row),
		})

	found = [one for one in grouped.values() if len(one["claims"]) > 1]
	return {"disagreements": found[: max(10, min(cint(limit) or 50, 500))],
	        "total": len(found)}


@frappe.whitelist(methods=["POST"])
def accept_stop(stop: str) -> dict:
	"""Promote an inferred stop into the network, by hand.

	§6's last paragraph: a vehicle stopping where no feed declares a stop is a
	finding, drawn differently, and never silently promoted. This is the person
	saying it is real — which is the only thing that should be able to.
	"""
	if not frappe.has_permission("Transit Stop", "write", doc=stop):
		frappe.throw(_("You cannot change this stop."), frappe.PermissionError)

	status = frappe.db.get_value("Transit Stop", stop, "status")
	if status != "Inferred":
		return {"accepted": False, "status": status}

	frappe.db.set_value("Transit Stop", stop, "status", "Served")
	return {"accepted": True, "status": "Served"}
