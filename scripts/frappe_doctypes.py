"""Snapshot Frappe's own doctype list, so the coverage table can be checked.

`docs/FRAPPE.md` answers one question for every doctype the framework ships:
is it part of OneSpace, and if not, why not. A table like that is worth exactly
as much as the thing that reads it back — a doctype Frappe adds next month is a
row nobody writes, and the table quietly becomes a list of what was true once.

So the names are snapshotted here and `tests/test_frappe_coverage.py` checks
the document against them. CI has no bench, which is the whole reason for the
file; where a bench *is* reachable the guard checks the snapshot against it
too, so a stale snapshot fails loudly rather than passing quietly.

    python scripts/frappe_doctypes.py

Frappe only — ERPNext and HRMS are a different question with a different
document, and their fifteen hundred tables are not what this one is about.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import upstream  # noqa: E402


def read(apps: Path) -> dict:
	found = {}
	for path in (apps / "frappe" / "frappe").glob("**/doctype/*/*.json"):
		if path.stem != path.parent.name:
			continue
		doc = json.loads(path.read_text())
		if doc.get("doctype") != "DocType":
			continue
		found[doc["name"]] = {
			"module": doc.get("module"),
			"child": int(doc.get("istable") or 0),
			"single": int(doc.get("issingle") or 0),
		}
	return dict(sorted(found.items()))


def main() -> int:
	apps = upstream.bench()
	if not apps:
		print("no bench with doctype JSON — run this where frappe is checked out")
		return 1
	found = read(apps)
	if not found:
		print(f"no frappe doctypes under {apps}")
		return 1
	out = ROOT / "tests" / "fixtures" / "frappe_doctypes.json"
	out.write_text(json.dumps(found, indent="\t") + "\n")
	print(f"{len(found)} doctypes → {out.relative_to(ROOT)}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
