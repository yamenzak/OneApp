"""What each seat of each space may do, written down so a test can read it.

`docs/CLEANUP.md` stage 13. The four seats decide everything a person can
reach — which screens resolve, which records they may write, which buttons
appear — and until now nothing checked the result. Stage 2's seats were
verified by opening the dev site and counting, which is a thing somebody did
once.

The obstacle is that the answer needs a bench. Not for the ladder — that is
`registry.laddered` and is a pure function — but for the **actions**: a screen
action is a Python function behind a hook, and two of the providers import HRMS
at the top of the module, so the list cannot be assembled on a machine without
it.

So this is the same arrangement `scripts/upstream_fields.py` uses and for the
same reason: run it where there is a bench, check the answer in, and let
`tests/test_seat_matrix.py` hold the rules against the file. Where both exist
the test compares them, so a stale matrix fails loudly rather than passing
quietly.

    ONEAPP_BENCH=… ONEAPP_SITE=… scripts/dev.sh run scripts/seat_matrix.py

What each cell holds is what a person can actually do on a screen:

    open    the seat may read the screen's doctype, so the screen resolves
    new     it may write, and the screen offers New
    press   the actions it may run — `run_action` asks for `write` on the
            screen's doctype, so this is the same question as `new` and is
            listed per action anyway, because the *set* is what a reader wants

`press` being derived rather than declared is worth saying out loud: an action
carries no seat of its own, and that is `spaceview/actions.py`'s design — the
permission is the record's, asked at the moment of running. This file is what
makes that derivation visible, and `test_seat_matrix.py` is what notices when
it produces a button nobody can press.
"""

import json
import pathlib
import sys

#: This repository's root.
#:
#: Not off `__file__`: `dev.sh run` executes the script's *source* inside the
#: bench's own interpreter, so there is no `__file__` to resolve — the path is
#: in `sys.argv`, after the sites path and the site name. Searching argv rather
#: than indexing it, because the first version indexed the site and wrote the
#: fixture into the bench's sites directory without a word. `__file__` is the
#: fallback, so the script still runs on its own for anybody reading it.
ROOT = pathlib.Path(next(
	(one for one in sys.argv if one.endswith("seat_matrix.py")),
	globals().get("__file__", ""),
) or "scripts/seat_matrix.py").resolve().parent.parent
OUT = ROOT / "tests/fixtures/seat_matrix.json"

sys.path.insert(0, str(ROOT / "apps" / "oneapp_control"))

#: Access levels in order, so "at least Read" is a comparison rather than a set.
LADDER = ("", "Read", "Write", "Manage")


def _rank(access: str) -> int:
	return LADDER.index(access) if access in LADDER else 0


def matrix() -> dict:
	import frappe  # noqa: F401  (the bench is what this script is for)

	from oneapp.onespace import spaceview
	from oneapp_control import spaces
	from oneapp_control.entitlements import registry
	from oneapp_control.spaces import roles

	found = {}
	for code, module in sorted(spaces.shipped().items()):
		space = dict(module.SPACE)
		rows = [
			{"document_type": row[0], "access": row[1], "if_owner": row[2],
			 "role": row[3] if len(row) > 3 else ""}
			for row in module.DOCTYPES
		]
		# The same expansion the tenant sync and the dev seeder both run, so
		# this cannot disagree with either.
		granted = registry.laddered(space, roles.ROLES, rows)

		# Seat -> doctype -> the widest access it holds.
		by_seat = {}
		for one in roles.ROLES:
			key = one["role_key"]
			role = registry.frappe_role_for(space, one)
			held = {}
			for row in granted:
				if row["role"] != role:
					continue
				name = row["doctype"]
				if _rank(row["access"]) > _rank(held.get(name, "")):
					held[name] = row["access"]
			by_seat[key] = held

		screens = []
		for screen in getattr(module, "SCREENS", []):
			doctype = screen.get("document_type")
			if not doctype:
				# A component screen draws itself and asks its own questions.
				continue
			actions = sorted(
				row["key"] for row in
				spaceview.actions(code, screen["screen"])
				if row.get("method")
			)
			seats = {}
			for key, held in by_seat.items():
				access = held.get(doctype, "")
				writes = _rank(access) >= _rank("Write")
				seats[key] = {
					"open": _rank(access) >= _rank("Read"),
					"new": bool(writes and not screen.get("hide_new")),
					"press": actions if writes else [],
				}
			screens.append({
				"screen": screen["screen"],
				"doctype": doctype,
				"hide_new": bool(screen.get("hide_new")),
				"actions": actions,
				"seats": seats,
			})

		found[code] = {
			"role_name": space.get("role_name") or "",
			"doctypes": by_seat,
			"screens": screens,
		}
	return found


def main() -> int:
	found = matrix()
	OUT.parent.mkdir(parents=True, exist_ok=True)
	OUT.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n",
	               encoding="utf-8")

	cells = sum(len(one["screens"]) * 4 for one in found.values())
	print(f"{OUT.relative_to(ROOT)}: {len(found)} spaces, "
	      f"{sum(len(one['screens']) for one in found.values())} screens, "
	      f"{cells} seat cells")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
