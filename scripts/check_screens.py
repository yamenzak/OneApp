"""Open every screen of every shipped space, the way the browser does.

A manifest is a declaration about a doctype, and **every way of getting one
wrong is silent**. `tests/test_space_screens.py` catches the ones that can be
seen in the source — a fieldname that is not a field, a widget in a vocabulary
the server does not know, a view type with nothing declared for it. What it
cannot catch is everything that depends on the *site*: a doctype the app did
not install, a field the reader may not read, a filter that refuses, a widget
whose query throws.

Those were all found by taking screenshots, one screen at a time, which is
forty-seven screenshots and an afternoon. This does the same pass in three
seconds: resolve each screen, ask for its rows under every view type it offers,
compute its dashboard, and report anything refused, dropped or drawn short.

    scripts/dev.sh run scripts/check_screens.py
    scripts/dev.sh run scripts/check_screens.py onehr

Exits non-zero when it finds something, so it can be a gate.

It is not a replacement for looking: a screen can resolve perfectly and read
badly, and this has no opinion about a dark card or a bar chart nobody can see.
It is the half a machine can do.
"""

import sys

import frappe


def spaces(only: str = "") -> list:
	from oneapp_control import spaces as shipped

	names = [only] if only else sorted(shipped.SPACES)
	return [shipped.SPACES[name] for name in names if name in shipped.SPACES]


def check(module) -> int:
	from oneapp.onespace import spaceview

	code = module.SPACE["space_code"]
	found = 0

	for screen in getattr(module, "SCREENS", []):
		name = screen["screen"]
		if screen.get("component"):
			# The escape hatch. Nothing here resolves against a doctype, and
			# whether the component renders is a question for the browser.
			continue

		try:
			resolved = spaceview._resolve(code, name)
		except Exception as raised:
			print(f"  {code}/{name}: {type(raised).__name__}: {raised}")
			found += 1
			continue

		if resolved.get("error"):
			print(f"  {code}/{name}: {resolved['error']}")
			found += 1
			continue

		offered = resolved.get("view_types") or []
		declared = [one.strip() for one in
		            (screen.get("view_types") or "list").split(",") if one.strip()]
		dropped = [one for one in declared if one not in offered]
		if dropped:
			# Almost always a field the reader may not read: the type needs it,
			# `_offerable` dropped it, and `_view_types` dropped the type.
			print(f"  {code}/{name}: offers {dropped} and does not get them")
			found += 1

		for view in offered:
			try:
				spaceview.rows(code, name, view_type=view, limit=5)
			except Exception as raised:
				print(f"  {code}/{name} [{view}]: {type(raised).__name__}: {raised}")
				found += 1

		declared_widgets = (resolved.get("view_settings", {}).get("dashboard") or {})
		if declared_widgets.get("widgets"):
			try:
				drawn = len(spaceview.dashboard_data(code, name).get("widgets") or [])
			except Exception as raised:
				print(f"  {code}/{name} dashboard: {type(raised).__name__}: {raised}")
				found += 1
				continue
			wanted = len(declared_widgets["widgets"])
			if drawn != wanted:
				print(f"  {code}/{name}: {wanted} widgets declared, {drawn} drawn")
				found += 1

	return found


def main(argv: list[str]) -> int:
	frappe.set_user("Administrator")
	only = argv[1] if len(argv) > 1 else ""

	total = 0
	for module in spaces(only):
		code = module.SPACE["space_code"]
		screens = [s for s in getattr(module, "SCREENS", []) if not s.get("component")]
		if not screens:
			continue
		found = check(module)
		total += found
		print(f"{code}: {len(screens)} screens, {found or 'no'} problems")

	return 1 if total else 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv))
