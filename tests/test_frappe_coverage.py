"""`docs/FRAPPE.md` against the framework it claims to have read.

The table answers one question for each of Frappe's doctypes — screen, granted,
service, engine, refused, log, or nothing — and the answer is only worth
anything while it is complete. A doctype the framework adds next month is a row
nobody writes; a screen a manifest gains is a row that quietly says the wrong
thing. Both fail as *silence*, which is the failure mode this repository keeps
turning guards into tests for.

So four things are checked here, and none of them is prose:

  * every non-child doctype Frappe ships has exactly one row, and no row names
    a doctype that does not exist;
  * the rows marked **screen** are exactly the frappe doctypes a manifest
    declares a screen over;
  * the rows marked `granted` are exactly the rest of what a manifest grants;
  * `engine` and `refused` together are exactly `NEVER_GRANTED`, minus the
    control plane's own tables, which Frappe does not ship.

The doctype list comes from `tests/fixtures/frappe_doctypes.json` — written by
`scripts/frappe_doctypes.py` — and where a bench is reachable the snapshot is
checked against it, so it cannot become fiction.
"""

import ast
import collections
import importlib.util
import json
import re
from pathlib import Path

import pytest

import upstream

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "FRAPPE.md"
SNAPSHOT = ROOT / "tests" / "fixtures" / "frappe_doctypes.json"
SPACES = ROOT / "apps" / "oneapp_control" / "oneapp_control" / "spaces"
REGISTRY = SPACES.parent / "entitlements" / "registry.py"

ROW = re.compile(r"^\| ([^|]+?)(?: \*\(single\)\*)? \| ([^|]+?) \| ([^|]*?) \|$", re.M)
MARKS = {"**screen**": "screen", "granted": "granted", "service": "service",
         "engine": "engine", "refused": "refused", "log": "log", "—": "out"}


def shipped() -> dict:
	return json.loads(SNAPSHOT.read_text())


def table() -> dict[str, str]:
	"""`{doctype: answer}` for every row of the per-module tables."""
	found = {}
	for name, mark, _why in ROW.findall(DOC.read_text()):
		if mark not in MARKS:
			continue
		assert name not in found, f"{name} has two rows in docs/FRAPPE.md"
		found[name] = MARKS[mark]
	return found


def _manifest(path: Path):
	spec = importlib.util.spec_from_file_location(f"{path.stem}_space", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _manifests() -> list[Path]:
	return sorted(p for p in SPACES.glob("*.py")
	              if p.stem not in ("__init__", "roles"))


def _screened() -> set[str]:
	"""Every doctype a manifest declares a screen over.

	Parsed rather than imported, because one manifest reaches for its own app
	on import and a guard that works for six of seven spaces is a guard that
	silently stops covering the seventh.
	"""
	found = set()
	for path in _manifests():
		for node in ast.parse(path.read_text()).body:
			if not isinstance(node, ast.Assign):
				continue
			if not any(getattr(t, "id", None) == "SCREENS" for t in node.targets):
				continue
			for screen in node.value.elts:
				if not isinstance(screen, ast.Dict):
					continue
				for key, value in zip(screen.keys, screen.values):
					if (isinstance(key, ast.Constant) and key.value == "document_type"
					        and isinstance(value, ast.Constant)):
						found.add(value.value)
	return found


def _granted() -> set[str]:
	found = set()
	for path in _manifests():
		for node in ast.parse(path.read_text()).body:
			if not isinstance(node, ast.Assign):
				continue
			if not any(getattr(t, "id", None) == "DOCTYPES" for t in node.targets):
				continue
			for row in node.value.elts:
				first = row.elts[0]
				if isinstance(first, ast.Constant):
					found.add(first.value)
	return found


def _never_granted() -> set[str]:
	for node in ast.parse(REGISTRY.read_text()).body:
		if not isinstance(node, ast.Assign):
			continue
		if not any(getattr(t, "id", None) == "NEVER_GRANTED" for t in node.targets):
			continue
		return {el.value for el in node.value.args[0].elts}
	raise AssertionError("no NEVER_GRANTED in entitlements/registry.py")


def test_the_snapshot_is_what_the_bench_has():
	apps = upstream.bench()
	if not apps:
		pytest.skip("no bench to check the snapshot against")
	import sys
	sys.path.insert(0, str(ROOT / "scripts"))
	import frappe_doctypes

	live = frappe_doctypes.read(apps)
	if not live:
		pytest.skip("bench has no frappe doctype JSON")
	missing = sorted(set(live) - set(shipped()))
	gone = sorted(set(shipped()) - set(live))
	assert not missing and not gone, (
		"tests/fixtures/frappe_doctypes.json is stale — "
		f"new: {missing[:8]}, gone: {gone[:8]}. "
		"Run `python scripts/frappe_doctypes.py`."
	)


def test_the_summary_counts_the_rows_it_has():
	"""The seven totals at the top, against the rows underneath them.

	A count in prose is the first thing to go stale — a row changes answer and
	the summary still says what was true last month, which is worse than no
	summary at all because it reads like a check somebody did.
	"""
	rows = table()
	counted = collections.Counter(rows.values())
	said = {}
	for line in DOC.read_text().splitlines():
		for mark, key in MARKS.items():
			if line.startswith(f"| {mark} |") and line.rstrip().endswith("|"):
				said[key] = int(line.rsplit("|", 2)[1].strip())
	assert said == dict(counted), (
		f"docs/FRAPPE.md's summary says {said}; the rows are {dict(counted)}"
	)
	total = counted["screen"] + counted["granted"] + counted["service"] + counted["engine"]
	assert f"**{total} of {len(rows)}** are reachable" in DOC.read_text(), (
		f"the summary sentence should read {total} of {len(rows)}"
	)


def test_every_doctype_frappe_ships_has_a_row():
	rows = table()
	wanted = {n for n, one in shipped().items() if not one["child"]}
	missing = sorted(wanted - set(rows))
	assert not missing, (
		f"{len(missing)} doctypes are not in docs/FRAPPE.md: {missing[:10]}"
	)


def test_no_row_names_something_frappe_does_not_ship():
	extra = sorted(set(table()) - set(shipped()))
	assert not extra, f"docs/FRAPPE.md names doctypes frappe has not got: {extra}"


def test_no_child_table_has_a_row_of_its_own():
	children = {n for n, one in shipped().items() if one["child"]}
	assert not sorted(set(table()) & children), (
		"a child table is part of its parent's form and never a row here"
	)


def test_the_screens_are_the_screens():
	said = {n for n, mark in table().items() if mark == "screen"}
	real = _screened() & set(shipped())
	assert said == real, (
		f"docs/FRAPPE.md says {sorted(said)} have a screen; the manifests say "
		f"{sorted(real)}"
	)


def test_the_grants_are_the_grants():
	rows = table()
	said = {n for n, mark in rows.items() if mark in ("screen", "granted")}
	real = _granted() & set(shipped())
	assert said == real, (
		f"docs/FRAPPE.md grants {sorted(said)}; the manifests grant {sorted(real)}"
	)


def test_engine_and_refused_are_never_granted():
	rows = table()
	said = {n for n, mark in rows.items() if mark in ("engine", "refused")}
	# Child tables have no row of their own, here or anywhere — `DocField` and
	# `DocPerm` are in NEVER_GRANTED and are part of DocType's form.
	real = {n for n in _never_granted() & set(shipped()) if not shipped()[n]["child"]}
	assert said == real, (
		f"docs/FRAPPE.md refuses {sorted(said)}; NEVER_GRANTED holds "
		f"{sorted(real)}"
	)


#: Grants that do nothing, named so a fifth one cannot arrive unnoticed.
#:
#: `laddered` skips a NEVER_GRANTED doctype, so no Custom DocPerm row is ever
#: written for these and `_granted_doctypes` never sees them. OneAdmin gets
#: away with it because all four of its screens are components with no
#: `document_type` — they read these tables through their own endpoints — so
#: the rows are dead rather than broken. A space that declared a *screen* over
#: one of them would refuse with "not part of OneAdmin", which is what the
#: second half of this checks.
DEAD_GRANTS = {"OneSpace Space", "Space Entitlement", "Tenant", "Workspace Role"}


def test_a_grant_registry_refuses_is_dead_and_known():
	overlap = _granted() & _never_granted()
	assert overlap == DEAD_GRANTS, (
		f"a manifest grants {sorted(overlap - DEAD_GRANTS)}, which registry.py "
		"refuses — no Custom DocPerm is written and the grant does nothing"
	)


def test_no_screen_stands_on_a_doctype_registry_refuses():
	standing = _screened() & _never_granted()
	assert not standing, (
		f"a screen over {sorted(standing)} would refuse with \"not part of\" — "
		"the grant behind it is skipped by `laddered`"
	)
