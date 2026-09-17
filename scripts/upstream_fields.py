"""Snapshot the doctypes our manifests name, so CI can check them without one.

Three shipped spaces are entirely over ERPNext's and HRMS's schema. The guards
in `tests/test_space_screens.py` check every fieldname in those manifests
against the real field list, and CI has neither app — so this writes the field
lists to `tests/fixtures/upstream_fields.json` and the guards read that when
there is no bench.

Only the doctypes a manifest actually names, which keeps the file to the
hundred-odd tables this repository has an opinion about rather than ERPNext's
fifteen hundred.

    python scripts/upstream_fields.py

Run it on a machine with a bench, after a manifest starts naming a doctype it
did not before. Where both the bench and this file exist the guards compare
them, so a stale snapshot fails loudly rather than passing quietly.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
# And the control app, because a space module may import its siblings — since
# `docs/CLEANUP.md` stage 2 they all import `spaces/roles.py` for the four
# seats. Without this the loader below raises on the first manifest and this
# script cannot be run outside a bench, which is the only place it is useful.
sys.path.insert(0, str(ROOT / "apps" / "oneapp_control"))

import upstream  # noqa: E402

SPACES = ROOT / "apps" / "oneapp_control" / "oneapp_control" / "spaces"


def declared(path: Path):
	spec = importlib.util.spec_from_file_location(f"space_{path.stem}", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def wanted() -> set[str]:
	"""Every doctype any shipped space grants, names on a screen or extends.

	Read off the modules rather than listed here: a space added tomorrow over a
	doctype nobody snapshotted is exactly the gap this is closing.
	"""
	found = set()
	for path in sorted(SPACES.glob("*.py")):
		if path.name == "__init__.py":
			continue
		module = declared(path)
		found |= {row[0] for row in getattr(module, "DOCTYPES", [])}
		found |= {s["document_type"] for s in getattr(module, "SCREENS", [])
		          if s.get("document_type")}
		found |= {f["dt"] for f in getattr(module, "CUSTOM_FIELDS", [])}
	return found


def main() -> int:
	apps = upstream.bench()
	if not apps:
		print("No bench with doctype JSON found. Set ONEAPP_BENCH.", file=sys.stderr)
		return 1

	kept, ours, missing = {}, [], []
	for doctype in sorted(wanted()):
		# Ours is already checked in as JSON. Snapshotting it too would be a
		# second copy of our own schema, which is a copy that goes stale —
		# `upstream._ours` reads the real one.
		if upstream._ours(doctype) is not None:
			ours.append(doctype)
			continue
		fields = upstream._off_bench(apps, doctype)
		if fields is None:
			missing.append(doctype)
			continue
		kept[doctype] = fields

	upstream.SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
	upstream.SNAPSHOT.write_text(json.dumps(kept, indent=1, sort_keys=True) + "\n")
	print(f"{len(kept)} doctypes written to {upstream.SNAPSHOT.relative_to(ROOT)}")
	if ours:
		print(f"{len(ours)} of ours, read from the repo rather than snapshotted")
	if missing:
		print("on no bench and not ours: " + ", ".join(missing))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
