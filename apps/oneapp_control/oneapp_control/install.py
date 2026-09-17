"""Post-install setup for the control plane."""

import frappe


#: Space codes this repository used to ship under, deleted on every migration.
#:
#: `spaces.install_all()` writes a row per module and touches nothing else, and
#: a renamed space is an insert rather than a rename — so without this a
#: control plane that predates the rename carries both rows and draws the space
#: twice in the rail. Two of them, both from `docs/CLEANUP.md`: stage 7 renamed
#: the books space from `books` to `onebook`, and stage 8 renamed the console
#: from `onespace-ops` to `oneadmin`. Both are now the code the catalogue
#: always used.
#:
#: A list that can be emptied the day no control plane is older than stage 8.
#: It is not a migration and must never become one — it deletes a declaration,
#: never a customer's data, and every entitlement against a retired code was
#: pointing at a space that no longer exists either.
RETIRED = ("onespace-ops", "books")


def after_install():
	create_default_settings()
	setup_console()


def after_migrate():
	"""Re-seed the operator console from code on every migration.

	The console's shape lives in `spaces/oneadmin.py` rather than in a fixture
	somebody edits, so "change the console" is an edit and a migrate.
	Running it here rather than only at install means an existing control plane
	picks up a new screen without anybody remembering to.
	"""
	setup_console()


def setup_console():
	"""The two Spaces this site provides, and the DocPerms they depend on.

	Only where `oneapp` is installed — the console is a Space, and a Space with
	nothing to render it is a row nobody reads. A control plane running only
	this app is a perfectly good control plane; it just has no console yet.
	"""
	try:
		import oneapp  # noqa: F401
	except ImportError:
		return

	from oneapp_control import spaces
	from oneapp_control.entitlements import account

	for code in RETIRED:
		if frappe.db.exists("OneSpace Space", code):
			frappe.delete_doc("OneSpace Space", code,
			                  ignore_permissions=True, force=True)

	account.seed()
	# Every space this repository ships, rewritten from its module — the
	# operator console among them since `docs/CLEANUP.md` stage 8. Screens are
	# a declaration and not a customer's data, so "change a screen" is an edit
	# and a migrate rather than an edit and somebody remembering to retype it
	# into the console.
	spaces.install_all()
	# One call for all of them: `sync_permissions` reconciles every local
	# space's grants at once, and the account Space deliberately grants nothing.
	spaces.sync_permissions()
	frappe.db.commit()


def create_default_settings():
	settings = frappe.get_single("OneSpace Control Settings")
	if not settings.tenant_domain:
		settings.tenant_domain = "4dl.app"
	if not settings.press_api_url:
		settings.press_api_url = "https://cloud.frappe.io"
	settings.save(ignore_permissions=True)
	frappe.db.commit()
