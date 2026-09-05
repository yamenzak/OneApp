"""Spaces this repository ships.

A space is data — a label, an icon, the doctypes it may reach and the screens
it puts in front of somebody — so a whole product for a customer is a module in
here and no console typing at all. `install` writes one onto the control plane
as `OneSpace Space` rows; everything downstream (the entitlement registry, the
sync payload, the rail, the resolver) reads those and knows nothing about this.

The same shape as `oneapp/oneapp_core/plans/`, deliberately: a customer arriving
off their own system is a plan module and a space module, and between them they
are the whole delivery.

Idempotent, and re-run on every migration — so changing a screen is an edit and
a `bench migrate`, not an edit and a person remembering to press something.
"""

import json

import frappe

from oneapp_control.spaces import books, rua

SPACES = {"books": books, "rua": rua}


def install(name: str) -> str:
	"""Write one shipped space onto this control plane.

	The space is rewritten from the module every time, screens included: a
	screen list is a declaration and not a customer's data, and merging the two
	versions of one by hand is how a manifest starts lying about what it shows.

	What is *not* rewritten is who may see it. `availability` and the
	entitlements granting it are an operator's decisions about a customer, and
	an edit to a label must not quietly hand a bespoke space to everybody.
	"""
	module = SPACES[name]
	code = module.SPACE["space_code"]
	known = frappe.db.exists("OneSpace Space", code)

	doc = frappe.get_doc("OneSpace Space", code) if known else frappe.new_doc("OneSpace Space")
	doc.doctypes = []
	doc.screens = []

	doc.update({k: v for k, v in module.SPACE.items() if k != "availability"})
	doc.is_active = 1
	if not known:
		# Restricted unless a module says otherwise, and only on the way in.
		# Reaching every customer's launcher should be something somebody opted
		# into rather than something a space got by forgetting to say — and
		# after that first write it is the operator's call, not this file's.
		doc.availability = module.SPACE.get("availability", "Restricted")

	for document_type, access, if_owner in module.DOCTYPES:
		doc.append("doctypes", {"document_type": document_type,
		                        "access": access, "if_owner": if_owner})

	for screen in getattr(module, "SCREENS", []):
		doc.append("screens", dict(screen))

	# The schema its screens read. A module attribute rather than a key in
	# SPACE, for the same reason DOCTYPES and SCREENS are: it is a list, and a
	# list belongs beside the other lists rather than inside the dictionary of
	# scalars at the top of the file.
	doc.custom_fields = json.dumps(getattr(module, "CUSTOM_FIELDS", None) or [], indent=1)

	doc.insert(ignore_permissions=True) if not known else doc.save(ignore_permissions=True)
	return doc.name


def install_all() -> list[str]:
	return [install(name) for name in SPACES]
