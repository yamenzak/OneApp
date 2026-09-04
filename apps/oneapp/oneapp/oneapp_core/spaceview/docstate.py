"""Submit, cancel, amend, and the workflow transitions."""

import frappe
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
from .guard import _reachable


@frappe.whitelist(methods=["POST"])
def submit(space_code: str, screen: str, name: str) -> dict:
	"""Draft to submitted, where no workflow owns the transition."""
	doctype = _reachable(space_code, screen, name)
	doc = frappe.get_doc(doctype, name)
	docflow.submit(doc)
	return {"name": doc.name, "state": docflow.state(doc)}


@frappe.whitelist(methods=["POST"])
def cancel(space_code: str, screen: str, name: str) -> dict:
	"""Submitted to cancelled. The ledger this wrote is unwritten by Frappe."""
	doctype = _reachable(space_code, screen, name)
	doc = frappe.get_doc(doctype, name)
	docflow.cancel(doc)
	return {"name": doc.name, "state": docflow.state(doc)}


@frappe.whitelist(methods=["POST"])
def amend(space_code: str, screen: str, name: str) -> dict:
	"""A fresh draft from a cancelled document, which the reader then opens.

	The new name comes back rather than the old one, because the answer to
	"amend this" is a different record and the pane has to follow.
	"""
	doctype = _reachable(space_code, screen, name)
	made = docflow.amend(frappe.get_doc(doctype, name))
	return {"name": made}


@frappe.whitelist(methods=["POST"])
def workflow_action(space_code: str, screen: str, name: str, action: str) -> dict:
	"""One step through the workflow, whatever that step turns out to mean.

	Approving may save, submit or cancel — the two states' `doc_status` decides
	and `apply_workflow` does it. Nothing here knows which, deliberately: that
	is the workflow's business and reading it twice is how two answers appear.
	"""
	doctype = _reachable(space_code, screen, name)
	doc = frappe.get_doc(doctype, name)
	docflow.apply(doc, action)
	# Re-read: the transition may have submitted the document, run an update
	# field, or fired a task that changed something else on it.
	doc = frappe.get_doc(doctype, name)
	return {"name": doc.name, "state": docflow.state(doc)}
