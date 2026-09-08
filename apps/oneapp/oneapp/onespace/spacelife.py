"""What a space does when it is turned on, and when it is turned off.

Most spaces need nothing. A space is a manifest and some doctypes: enabling it
puts it in the launcher, disabling it takes it out, and the records sit in the
same tables either way. Nothing has to happen.

Some spaces are not like that. OneMobility declares fact tables — real MariaDB
tables, partitioned by day, outside the doctype system — and those have to be
*created* before the space works and are nobody's to clean up if the space goes
away. A future space with a cache, an external subscription or a scheduled feed
will be in the same position.

So: a space module may ship a `lifecycle.py` with `on_enable()` and
`on_disable(delete_data=False)`, and this calls it. Discovered rather than
registered, for the same reason `onelegal/assemble.py` discovers clauses — a
central list of which spaces have side effects is a list that goes stale the
first time somebody adds a space and forgets.

Two rules the callers rely on:

* **`on_enable` is idempotent.** It is called on every enable, including the
  re-enable of a space that was switched off for an afternoon, and it must not
  care.

* **`on_disable` does not delete by default.** Switching a space off is usually
  somebody tidying a launcher. Deleting the data is a separate, deliberate act
  with its own confirmation, and `remove_space` is the only path that asks for
  it — because that is the one the customer typed the space's name into.

Neither is allowed to fail the press. A space that cannot bring itself up is a
logged error and a launcher tile that does not work, not a marketplace button
that throws at somebody who pressed the right thing.
"""

import importlib

import frappe

#: Where a space's module lives, given its manifest key. A space is a Frappe
#: module in this app and its key is the module name — see
#: `docs/APPS-AND-SPACES.md`.
PACKAGE = "oneapp"


def _module(space: str):
	"""A space's `lifecycle`, or None if it does not have one."""
	name = (space or "").strip().replace("-", "_")
	if not name.isidentifier():
		return None
	try:
		return importlib.import_module(f"{PACKAGE}.{name}.lifecycle")
	except ModuleNotFoundError as missing:
		# A missing `lifecycle` is the normal case. A missing import *inside*
		# one is a bug, and must not be swallowed as "this space has none".
		if missing.name in (f"{PACKAGE}.{name}", f"{PACKAGE}.{name}.lifecycle"):
			return None
		raise


def on_enable(space: str) -> dict:
	"""Let a space bring itself up. Never fails the press."""
	module = _module(space)
	if not module or not hasattr(module, "on_enable"):
		return {"ran": False}
	try:
		module.on_enable()
		return {"ran": True}
	except Exception:
		frappe.log_error(title=f"Space {space}: could not bring itself up")
		return {"ran": False, "failed": True}


def on_disable(space: str, delete_data: bool = False) -> dict:
	"""Let a space wind itself down. Never fails the press."""
	module = _module(space)
	if not module or not hasattr(module, "on_disable"):
		return {"ran": False}
	try:
		return {"ran": True, **(module.on_disable(delete_data=delete_data) or {})}
	except Exception:
		frappe.log_error(title=f"Space {space}: could not wind itself down")
		return {"ran": False, "failed": True}
