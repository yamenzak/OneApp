"""One glyph per field, wherever that field is drawn.

A field's icon is the small mark in front of its label — on a record, at the
head of a list column, in the column picker, on a child table's grid, and in
the rail a document picks its tokens from. Every one of those used to answer
the question separately, and three of them did not answer it at all: the rail
had no icons, and the two grids drew a label with nothing in front of it.

**The fieldtype is the answer, and a manifest may overrule it.** `fieldtypes`
maps every Frappe fieldtype to a lucide name, which is right nearly always: a
Date is a calendar and a Currency is a wallet. It is wrong exactly where a
field means something its *type* does not say — `status` is a Select, and a
list icon in front of it says "this is a dropdown" when what a reader wants
is "this is where it stands". So a screen may declare `field_icons`, and the
override wins.

**Keyed by doctype, not by screen.** A screen declares it, because that is
where manifests are written and validated, but the map this builds is
`Doctype.fieldname` — so an icon chosen for Project's status is Project's
status everywhere, including the surfaces that have no screen behind them at
all. Two screens over one doctype disagreeing is a manifest mistake;
`tests/test_manifests.py` fails the build on one rather than picking.
"""

import json

import frappe

from . import fieldtypes

#: Where the built map lives for the rest of the request. Not Redis: it is
#: derived from `sync.state()`, which is itself cached, and rebuilding it is a
#: walk over a handful of screens.
_HELD = "oneapp_field_icons"


def declared() -> dict:
	"""`{"Doctype.fieldname": "lucide-…"}`, from every granted screen.

	A space nobody granted contributes nothing, which is the same rule the
	rail and `granted_doctypes` follow: what a workspace has is what it was
	given.
	"""
	held = getattr(frappe.local, _HELD, None)
	if held is not None:
		return held

	from . import sync

	found = {}
	try:
		spaces = sync.state().get("spaces") or []
	except Exception:
		# A site mid-install, or one whose Single has not been created yet.
		# An icon is not worth failing a page load over.
		spaces = []

	for space in spaces:
		for screen in space.get("screens") or []:
			doctype = (screen.get("document_type") or "").strip()
			if not doctype:
				continue
			for fieldname, icon in _map(screen.get("field_icons")).items():
				found[f"{doctype}.{fieldname}"] = icon

	setattr(frappe.local, _HELD, found)
	return found


def _map(raw) -> dict:
	"""One screen's declaration, however it arrived — JSON text, or a dict.

	Anything that is not a flat map of strings is nothing. A manifest with a
	broken `field_icons` draws the fieldtype's icons, which is what it drew
	before anybody wrote the key.
	"""
	if isinstance(raw, str):
		try:
			raw = json.loads(raw or "{}")
		except ValueError:
			return {}
	if not isinstance(raw, dict):
		return {}
	# Against the closed set, not just the `lucide-` prefix: Tailwind emits
	# CSS only for the names it saw in a source file, so an icon that exists
	# only in a manifest draws an empty box. Falling back to the fieldtype's
	# own is the quiet, correct answer; `tests/test_manifests.py` is what
	# makes it loud for a manifest we ship.
	return {
		str(name): icon
		for name, icon in raw.items()
		if name and isinstance(icon, str) and icon in fieldtypes.FIELD_ICONS
	}


def icon_for(fieldtype: str, doctype: str = "", fieldname: str = "") -> str:
	"""The glyph for this field. The one call every surface makes.

	Without a doctype and a fieldname this is `fieldtypes.icon_for` and
	nothing more, which is what a surface that only knows a type should get.
	"""
	if doctype and fieldname:
		found = declared().get(f"{doctype}.{fieldname}")
		if found:
			return found
	return fieldtypes.icon_for(fieldtype)


def forget():
	"""Drop the request's copy. What a manifest sync calls."""
	if hasattr(frappe.local, _HELD):
		delattr(frappe.local, _HELD)
