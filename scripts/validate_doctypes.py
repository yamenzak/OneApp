"""Structural checks on generated doctype JSON.

A malformed doctype fails at `bench migrate` — on a real site, mid-deploy. These
checks are cheap and catch it in CI instead.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_KEYS = {
	"doctype", "module", "name", "fields", "field_order", "permissions",
	"sort_field", "sort_order", "engine",
}

NEEDS_OPTIONS = {"Link", "Select", "Dynamic Link", "Table", "Table MultiSelect"}

# Layout fields carry no data and legitimately have no label.
LAYOUT = {"Section Break", "Column Break", "Tab Break", "HTML"}


def check(path: Path) -> list[str]:
	problems = []
	doc = json.loads(path.read_text())

	missing = REQUIRED_KEYS - set(doc)
	if missing:
		problems.append(f"missing top-level keys: {sorted(missing)}")

	fields = doc.get("fields", [])
	names = [f["fieldname"] for f in fields]

	if len(names) != len(set(names)):
		dupes = {n for n in names if names.count(n) > 1}
		problems.append(f"duplicate fieldnames: {sorted(dupes)}")

	if doc.get("field_order") != names:
		problems.append("field_order does not match fields")

	for field in fields:
		fieldname = field.get("fieldname")
		fieldtype = field.get("fieldtype")

		if not fieldname or not fieldtype:
			problems.append(f"field missing fieldname/fieldtype: {field}")
			continue

		if fieldtype in NEEDS_OPTIONS and not field.get("options"):
			problems.append(f"{fieldname}: {fieldtype} needs options")

		if fieldtype not in LAYOUT and not field.get("label"):
			problems.append(f"{fieldname}: no label")

		# A required field with no default that is also read-only can never be
		# saved through the UI.
		if field.get("reqd") and field.get("read_only") and not field.get("default"):
			problems.append(f"{fieldname}: reqd + read_only with no default")

	autoname = doc.get("autoname", "")
	if autoname.startswith("field:"):
		target = autoname.split(":", 1)[1]
		if target not in names:
			problems.append(f"autoname references unknown field '{target}'")
		else:
			field = next(f for f in fields if f["fieldname"] == target)
			if not field.get("reqd"):
				problems.append(f"autoname field '{target}' must be reqd")

	if autoname == "naming_series:" and "naming_series" not in names:
		problems.append("autoname is naming_series: but no naming_series field")

	return problems


def main() -> int:
	paths = sorted(ROOT.glob("apps/*/*/*/doctype/*/*.json"))
	if not paths:
		print("No doctype JSON found — check the glob.")
		return 1

	failed = 0
	for path in paths:
		problems = check(path)
		if problems:
			failed += 1
			print(f"\n{path.relative_to(ROOT)}")
			for problem in problems:
				print(f"  - {problem}")

	print(f"\n{len(paths)} doctypes checked, {failed} with problems")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
