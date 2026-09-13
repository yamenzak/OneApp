"""The doctypes we do not own, read off a bench.

Three of the shipped spaces are entirely over ERPNext's and HRMS's schema, and
every fieldname in those manifests reaches a query. A typo in one is silent in
every direction: `_columns` drops a column the doctype has not got, `_view_types`
drops a view whose field does not resolve, and `dashboard.shape` drops a widget
naming a field the screen does not offer — so a manifest that is wrong renders
as a screen that is merely *thinner than intended*, and nobody finds out.

Checking it needs a field list, and a field list needs one of those apps. CI has
neither, so this reads both ways:

  * where a bench is reachable, the doctypes are read straight off it;
  * everywhere else the checked-in snapshot at `fixtures/upstream_fields.json`
    stands in, so the manifest guards still bite on a typo in CI.

And where both exist the snapshot is checked *against* the bench, which is the
part that keeps it from quietly becoming fiction: ERPNext renames a field, the
snapshot says otherwise, and one test fails with the field named.

Regenerate with `python scripts/upstream_fields.py` on a machine with a bench.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "tests" / "fixtures" / "upstream_fields.json"

# Layout has no value and is never a column, a filter or a measure.
LAYOUT = {"Section Break", "Column Break", "Tab Break", "HTML", "Fold"}

# Frappe's own, on every doctype and in none of their JSON. A manifest may name
# these — `modified desc` is the default sort — so they are part of the answer.
STANDARD = {
	"name": "Data", "owner": "Link", "creation": "Datetime",
	"modified": "Datetime", "modified_by": "Link", "docstatus": "Int",
	"idx": "Int", "_assign": "Text", "_liked_by": "Text",
	"_comments": "Text", "_user_tags": "Data",
}


def _benches() -> list[Path]:
	"""Where an apps directory might be, most explicit first.

	`ONEAPP_BENCH` is the same variable `scripts/i18n.py` reads, and the two
	fall back to the same path for the same reason: it is one machine's, and a
	guard that only runs there is a guard nobody notices breaking.
	"""
	found = []
	if os.environ.get("ONEAPP_BENCH"):
		found.append(Path(os.environ["ONEAPP_BENCH"]) / "apps")
	found.append(Path("/home/frappe/bench1/apps"))
	found.append(ROOT.parent / "bench" / "apps")
	return found


def bench() -> Path | None:
	"""An apps directory that actually carries doctype JSON, or nothing.

	Not merely one that exists: the remote session's bench is a *sparse*
	checkout of frappe and erpnext for their locale and their JS, and picking
	it would make every guard below report that Project does not exist.
	"""
	for apps in _benches():
		if apps.is_dir() and any(apps.glob("*/*/*/doctype/*/*.json")):
			return apps
	return None


_read: dict[str, dict | None] = {}


def _off_bench(apps: Path, doctype: str) -> dict | None:
	slug = doctype.lower().replace(" ", "_").replace("-", "_")
	for path in apps.glob(f"*/*/*/doctype/{slug}/{slug}.json"):
		doc = json.loads(path.read_text())
		if doc.get("name") != doctype:
			continue
		return {
			field["fieldname"]: [field.get("fieldtype"), field.get("options") or ""]
			for field in doc["fields"]
			if field.get("fieldtype") not in LAYOUT
		}
	return None


def _ours(doctype: str) -> dict | None:
	"""The same read, against this repository's own doctypes.

	Tried before the snapshot and never written into it: our schema is already
	checked in as JSON, and a second copy of it in a fixture is a copy that
	goes stale. A space grants its own doctypes beside ERPNext's — RUA's
	Compliance Document beside its Sales Invoice — so the readers below have to
	answer for both without caring which is which.
	"""
	slug = doctype.lower().replace(" ", "_").replace("-", "_")
	for path in ROOT.glob(f"apps/*/*/*/doctype/{slug}/{slug}.json"):
		doc = json.loads(path.read_text())
		if doc.get("name") != doctype:
			continue
		return {
			field["fieldname"]: [field.get("fieldtype"), field.get("options") or ""]
			for field in doc["fields"]
			if field.get("fieldtype") not in LAYOUT
		}
	return None


def snapshot() -> dict:
	return json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}


def fields(doctype: str) -> dict | None:
	"""`{fieldname: [fieldtype, options]}` for one doctype, or nothing.

	Nothing means neither the bench nor the snapshot has heard of it, which for
	a doctype a manifest grants is itself the finding.
	"""
	if doctype in _read:
		return _read[doctype]

	found = _ours(doctype)
	if found is None:
		apps = bench()
		found = _off_bench(apps, doctype) if apps else None
	if found is None:
		found = snapshot().get(doctype)
	_read[doctype] = found
	return found


def fieldtype(doctype: str, fieldname: str) -> str:
	"""What kind of field that is — `''` where the doctype does not have one."""
	if fieldname in STANDARD:
		return STANDARD[fieldname]
	known = fields(doctype) or {}
	return (known.get(fieldname) or ["", ""])[0]


def options(doctype: str, fieldname: str) -> str:
	known = fields(doctype) or {}
	return (known.get(fieldname) or ["", ""])[1]


def has(doctype: str, fieldname: str) -> bool:
	if fieldname in STANDARD:
		return True
	return fieldname in (fields(doctype) or {})
