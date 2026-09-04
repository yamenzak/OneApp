"""Tags and shares, as Frappe models them."""

import frappe
from frappe import _
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
from .guard import _reachable
from .assign import _colleagues, assignees


@frappe.whitelist(methods=["GET"])
def tags(space_code: str, screen: str, name: str) -> dict:
	"""This record's tags, and what else the workspace calls things."""
	doctype = _reachable(space_code, screen, name)
	held = collab.tags_of(doctype, name)
	return {"tags": held, "options": collab.tag_options(exclude=held)}


@frappe.whitelist(methods=["GET"])
def tag_options(space_code: str, screen: str, name: str, query: str = "") -> list:
	"""Tags to pick from, as somebody types.

	The workspace's whole vocabulary rather than this doctype's: "urgent" means
	the same thing on an invoice and on a task, and offering it only where it
	has been used already is how one word becomes three spellings of it.
	"""
	doctype = _reachable(space_code, screen, name)
	return collab.tag_options(query, exclude=collab.tags_of(doctype, name))


@frappe.whitelist(methods=["POST"])
def set_tag(space_code: str, screen: str, name: str, tag: str,
            on: str | int = 1) -> dict:
	"""Put a tag on this record, or take it off.

	One endpoint rather than two: it is a toggle in the UI, the permission is
	the same, and the answer is the same — the tags as they stand afterwards,
	re-read rather than reported from the argument.
	"""
	doctype = _reachable(space_code, screen, name)
	held = collab.set_tag(doctype, name, tag, on=frappe.utils.sbool(on))
	return {"tags": held, "options": collab.tag_options(exclude=held)}


@frappe.whitelist(methods=["GET"])
def shares(space_code: str, screen: str, name: str) -> dict:
	"""Who this record has been given to, and how far."""
	doctype = _reachable(space_code, screen, name)
	return {
		**collab.shares_of(doctype, name),
		# Asked here rather than taken from the spec: a control that is drawn
		# and a write that is allowed have to read the same flag at the same
		# moment, and `share` is a permission on the doctype like any other.
		"can_share": bool(frappe.has_permission(doctype, "share", doc=str(name))),
	}


@frappe.whitelist(methods=["POST"])
def set_share(space_code: str, screen: str, name: str, user: str | None = None,
              everyone: str | int = 0, level: str = "read") -> dict:
	"""Share it with somebody, or change how far their share goes."""
	doctype = _reachable(space_code, screen, name)
	if user and user not in _colleagues():
		# The same bound the assignment picker uses: sharing is a thing you do
		# with the people on this workspace, and a share with an account from
		# somewhere else on the site is a hole rather than a feature.
		frappe.throw(_("{0} is not on this workspace.").format(user))
	return {
		**collab.share(doctype, name, user=user, everyone=everyone, level=level),
		"can_share": True,
	}


@frappe.whitelist(methods=["POST"])
def unshare(space_code: str, screen: str, name: str, user: str | None = None,
            everyone: str | int = 0) -> dict:
	"""Take a share back."""
	doctype = _reachable(space_code, screen, name)
	return {
		**collab.unshare(doctype, name, user=user, everyone=everyone),
		"can_share": True,
	}


@frappe.whitelist(methods=["GET"])
def shareable(space_code: str, screen: str, query: str = "") -> list[dict]:
	"""Who this record can be shared with: the workspace, minus nobody.

	The same list the assignment picker offers and for the same reason — these
	are colleagues, and an account that holds no role on any space this
	workspace granted is not one.
	"""
	return assignees(space_code, screen, query)
