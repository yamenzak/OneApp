"""Spaces this repository ships.

A space is data — a label, an icon, the doctypes it may reach and the screens
it puts in front of somebody — so a whole product for a customer is a module in
here and no console typing at all. `install` writes one onto the control plane
as `OneSpace Space` rows; everything downstream (the entitlement registry, the
sync payload, the rail, the resolver) reads those and knows nothing about this.

The same shape as `oneapp/onespace/plans/`, deliberately: a customer arriving
off their own system is a plan module and a space module, and between them they
are the whole delivery.

Idempotent, and re-run on every migration — so changing a screen is an edit and
a `bench migrate`, not an edit and a person remembering to press something.
"""

import importlib
import json
import pathlib

from oneapp_control.spaces import roles


def _modules() -> dict:
	"""Every space module in this directory, keyed by the code it declares.

	**Discovered rather than listed** — `docs/CLEANUP.md` stage 9. It was a
	dict somebody edited by hand, and in the two stages before this one it was
	edited by hand twice and forgotten in three other places: a space added
	here had to be added to the dev fixture's install loop, to the fixture's
	"codes the seeders rebuild" list, and to the snapshot generator. The one it
	was forgotten in left the dev site with six copies of OneBook on its rail,
	one per seed run, and nothing said a word.

	A module is a space when it declares `SPACE`. `roles.py` is the four seats
	every space has and `__init__.py` is this file, and neither does.

	Sorted by filename so the order is stable and has nothing to do with
	import order — the rail sorts by `sort_order` anyway, and a dict whose
	order drifts is a diff that looks like a change.
	"""
	here = pathlib.Path(__file__).parent
	found = {}
	for path in sorted(here.glob("*.py")):
		if path.stem.startswith("_") or path.stem == "roles":
			continue
		module = importlib.import_module(f"{__name__}.{path.stem}")
		space = getattr(module, "SPACE", None)
		if not space:
			continue
		found[space["space_code"]] = module
	return found


SPACES = _modules()

#: A space is **the control plane's own** when it declares `CONTROL_PLANE`.
#: There is one — the operator console — and the distinction is not cosmetic:
#: everything else in `SPACES` is offered to tenants and seeded onto a tenant
#: site, and the console's doctypes do not exist there.
CONTROL_PLANE = "CONTROL_PLANE"


def shipped() -> dict:
	"""The spaces a tenant can be entitled to. Everything but the console."""
	return {code: module for code, module in SPACES.items()
	        if not getattr(module, CONTROL_PLANE, False)}


def install(name: str) -> str:
	"""Write one shipped space onto this control plane.

	The space is rewritten from the module every time, screens included: a
	screen list is a declaration and not a customer's data, and merging the two
	versions of one by hand is how a manifest starts lying about what it shows.

	What is *not* rewritten is who may see it. `availability` and the
	entitlements granting it are an operator's decisions about a customer, and
	an edit to a label must not quietly hand a bespoke space to everybody.
	"""
	# Imported here rather than at the top so that importing this package
	# needs no bench. A space module is a *declaration* — a label, a grant
	# list, a screen list — and the guards that read them back should be able
	# to do it without a site, which is what `tests/test_space_screens.py`
	# does by loading each one off its path.
	import frappe

	module = SPACES[name]
	code = module.SPACE["space_code"]
	known = frappe.db.exists("OneSpace Space", code)

	doc = frappe.get_doc("OneSpace Space", code) if known else frappe.new_doc("OneSpace Space")
	doc.doctypes = []
	doc.screens = []
	doc.roles = []

	doc.update({k: v for k, v in module.SPACE.items() if k != "availability"})
	doc.is_active = 1
	if not known:
		# Restricted unless a module says otherwise, and only on the way in.
		# Reaching every customer's launcher should be something somebody opted
		# into rather than something a space got by forgetting to say — and
		# after that first write it is the operator's call, not this file's.
		doc.availability = module.SPACE.get("availability", "Restricted")

	# The four seats, the same four for every space — `spaces/roles.py` says
	# why. Not a module attribute any more: a space does not get to invent what
	# a word means, and the twelve words five spaces used to invent between
	# them were twelve things a customer had to learn.
	for row in roles.ROLES:
		doc.append("roles", dict(row))

	# Three parts or four. The fourth is one of the four keys, and it names
	# **the lowest seat that may do this**: the seats above it inherit, and
	# Audit gets the same doctype at Read. Leaving it off is the User rung,
	# which is what a manifest written before roles existed meant and is also
	# the honest way to say "anybody in this space".
	for row in module.DOCTYPES:
		document_type, access, if_owner = row[:3]
		role = row[3] if len(row) > 3 else ""
		if role and role not in roles.LABELS:
			# A `ValueError` rather than a `frappe.throw`: nobody but us ever
			# reads it. A manifest naming a seat that does not exist is a
			# typo in this repository, caught on migrate, and the alternative
			# is a grant that silently reaches nobody.
			raise ValueError(f"{code} grants {document_type} to '{role}', "
			                 f"which is not one of {sorted(roles.LABELS)}")
		doc.append("doctypes", {"document_type": document_type,
		                        "access": access, "if_owner": if_owner,
		                        "role": role})

	for screen in getattr(module, "SCREENS", []):
		doc.append("screens", dict(screen))

	# The schema its screens read. A module attribute rather than a key in
	# SPACE, for the same reason DOCTYPES and SCREENS are: it is a list, and a
	# list belongs beside the other lists rather than inside the dictionary of
	# scalars at the top of the file.
	doc.custom_fields = json.dumps(getattr(module, "CUSTOM_FIELDS", None) or [], indent=1)

	# And the notifications it arrives with. Same shape and the same contract as
	# the custom fields above: seeded once by the tenant and then the
	# workspace's, because a rule a customer paused is a rule they paused.
	doc.alerts = json.dumps(getattr(module, "ALERTS", None) or [], indent=1)

	# And which of its fields are private to which of its roles. Reconciled by
	# the tenant rather than seeded once, unlike everything else here: a
	# permlevel is a security control, not somewhere to start from.
	doc.field_levels = json.dumps(
		getattr(module, "FIELD_LEVELS", None) or [], indent=1)

	doc.insert(ignore_permissions=True) if not known else doc.save(ignore_permissions=True)
	return doc.name


def install_all() -> list[str]:
	return [install(name) for name in SPACES]


def sync_permissions() -> None:
	"""Write the DocPerms every space *this* site serves depends on.

	`_granted_doctypes` reads Custom DocPerm rows for a space's seats — that is
	what makes a screen an allowlist rather than a label — so without these the
	console resolves and every screen refuses.

	A tenant gets these from `sync.sync_permissions` off the control plane's
	manifest. This is the same function fed the same shape from the local
	registry, so there is one implementation of what a manifest means.

	It lived in `entitlements/operator.py` and moved here with the console —
	`docs/CLEANUP.md` stage 8. It was never about the console: it reconciles
	every local space at once, and it has to, because `sync_permissions`
	*removes* what it is not given and two calls leave whichever ran last.
	"""
	import frappe

	try:
		from oneapp.onespace import sync
	except ImportError:
		# `oneapp` is not installed here, so there is nothing to render a space
		# and nothing to grant for.
		return

	from oneapp_control.entitlements import registry

	manifest_rows = []
	for space in registry.local_spaces():
		if not space.get("role_name"):
			continue
		rows = frappe.get_all(
			"OneSpace Space Doctype",
			filters={"parent": space["space_code"], "parenttype": "OneSpace Space"},
			fields=["document_type", "access", "if_owner", "role"],
		)
		# Through the ladder, not flat onto `role_name`. Before stage 8 this
		# addressed every grant to the bare prefix, which is a role no seat
		# holds — so on this site the console worked because its one role *was*
		# the prefix, and the five tenant spaces beside it were granting to
		# nobody.
		seats_here = frappe.get_all(
			"OneSpace Space Role",
			filters={"parent": space["space_code"],
			         "parenttype": "OneSpace Space"},
			fields=["role_key", "label"],
		)
		manifest_rows += registry.laddered(space, seats_here, rows)

	sync.sync_permissions(manifest_rows)
