"""Where a document stands, and what may be done to it next.

Two mechanisms, and the reason this is one module is that in Frappe they are
not two:

**`docstatus`** is the framework's own three-state machine — Draft, Submitted,
Cancelled — and it is what makes an accounting document an accounting
document. Submitting is what writes the ledger; cancelling is what unwrites it;
amending is a fresh draft that remembers what it came from. Frappe enforces the
transitions itself and checks `submit` and `cancel` on the way through.

**A `Workflow`** is a state machine an app declares *over* that one. Its states
each carry a `doc_status`, so approving something is what submits it — and
`frappe.model.workflow.apply_workflow` is what calls `doc.submit()`. Where a
workflow is active it therefore **owns** the transitions, and the plain Submit
and Cancel are not offered beside it. That is Frappe's own rule
(`can_submit()` in the desk's toolbar ends with `!this.has_workflow()`), and
offering both would be two buttons that mean the same thing and disagree about
who may press them.

So this module answers one question — *what can be done to this record now* —
and hands back one list either way. The record header renders that list and
never asks which mechanism produced it.

What is deliberately not here: **a way to build a workflow.** A Workflow is
part of what an app *is*, like its doctypes and its print formats, so it is
shipped by the app that owns the doctype rather than drawn by a customer. The
runtime honours whatever it finds.
"""

import frappe
from frappe import _

# Frappe's own three, in its own words. The desk shows these on the record and
# so do we, so a customer who has seen one Frappe screen reads ours the same.
DOCSTATUS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

# What a `Workflow State`'s style means to a badge. Frappe's own six, mapped
# onto the themes `lib/fields.js` draws — the same mapping a Document State
# gets, because a state is a state and one product should not colour the two
# kinds differently.
STYLES = {
	"Primary": "blue",
	"Info": "blue",
	"Success": "green",
	"Warning": "orange",
	"Danger": "red",
	"Inverse": "gray",
}

# The plain actions, by the docstatus they act on, and the permission each
# needs. `amend` is the one Frappe does not enforce for itself — submitting and
# cancelling go through `check_permission` inside the docstatus transition, but
# an amendment is an ordinary insert of a new draft, so `create` is all the
# framework asks for. Checking it here is what makes the permission mean
# something.
PLAIN = {
	0: ("submit", "Submit"),
	1: ("cancel", "Cancel"),
	2: ("amend", "Amend"),
}


def workflow_name(doctype: str) -> str:
	"""The active workflow over this doctype, or an empty string.

	Frappe's own lookup, which is cached per doctype and answers `""` rather
	than None for "asked and there is none" — so a doctype with no workflow
	costs one cache read on every record.
	"""
	from frappe.model.workflow import get_workflow_name

	return get_workflow_name(doctype) or ""


def _workflow(doctype: str):
	from frappe.model.workflow import get_workflow

	return get_workflow(doctype)


def _state_row(workflow, state: str):
	return next((row for row in workflow.states if row.state == state), None)


def editable(doc, meta=None) -> bool:
	"""Whether this person may write this record *right now*.

	Three things, and the third is the one that is easy to miss.

	A cancelled document is not editable at all — Frappe refuses the save.
	A submitted one is editable only in the fields marked `allow_on_submit`,
	which the form already knows about, so it counts as editable here.

	And a workflow state names a role in `allow_edit`: a purchase order in
	*Pending Approval* is the approver's to change and nobody else's. The desk
	enforces that in the browser only — `frappe.workflow.is_read_only` — which
	means the API underneath it does not. Ours is the only surface there is, so
	it is enforced on the way in as well as drawn on the way out; a rule that
	holds in one direction is a rule somebody will find the other way round.
	"""
	if int(doc.get("docstatus") or 0) == 2:
		return False

	name = workflow_name(doc.doctype)
	if not name:
		return True

	workflow = _workflow(doc.doctype)
	state = doc.get(workflow.workflow_state_field)
	if not state:
		# Before the first transition a document has no state, and Frappe's own
		# `validate_workflow` fills it with the first one on save. Editable, or
		# nothing could ever be saved into the workflow in the first place.
		return True

	row = _state_row(workflow, state)
	if not row or not row.allow_edit:
		return True
	return row.allow_edit in frappe.get_roles()


def state(doc, meta=None) -> dict:
	"""Where the record stands and what may be done to it, as one answer.

	The `actions` list is the whole point: a workflow's transitions and the
	plain Submit/Cancel/Amend arrive in the same shape, so the header renders a
	row of buttons without knowing which mechanism it is looking at. `kind`
	says which, because the two are applied through different endpoints — not
	so that anything renders differently.
	"""
	meta = meta or frappe.get_meta(doc.doctype)
	docstatus = int(doc.get("docstatus") or 0)
	submittable = bool(getattr(meta, "is_submittable", 0))
	name = workflow_name(doc.doctype)

	found = {
		"docstatus": docstatus,
		"status": DOCSTATUS.get(docstatus, ""),
		"submittable": submittable,
		"editable": editable(doc, meta),
		"workflow": None,
		"actions": [],
	}

	if name:
		found["workflow"] = _shape(doc, name)
		found["actions"] = _transitions(doc)
		return found

	if submittable:
		found["actions"] = _plain(doc, docstatus)
	return found


def _shape(doc, name: str) -> dict:
	"""The workflow's own answer about this record: which state, and its colour."""
	workflow = _workflow(doc.doctype)
	current = doc.get(workflow.workflow_state_field) or ""
	style = frappe.db.get_value("Workflow State", current, "style") if current else None

	return {
		"name": name,
		"state_field": workflow.workflow_state_field,
		"state": current,
		"theme": STYLES.get(style or "", "gray"),
	}


def _transitions(doc) -> list[dict]:
	"""What this person may do to this record, from the state it is in.

	Frappe's own `get_transitions` decides: it filters by the state, by the
	roles the reader holds, and by each transition's `condition`, which is a
	safe-eval'd expression over the document. Never re-implemented here — a
	second reading of who may approve what is a second answer to drift from.

	It throws `WorkflowStateError` on a record with no state yet, which is an
	ordinary thing for a record created before the workflow existed. No
	transitions is the truthful answer, not an error page.
	"""
	from frappe.model.workflow import WorkflowStateError, get_transitions

	try:
		found = get_transitions(doc, raise_exception=True)
	except WorkflowStateError:
		frappe.clear_last_message()
		return []

	return [
		{
			"kind": "workflow",
			"action": row.get("action"),
			"next": row.get("next_state"),
			# A transition into a cancelling state is the destructive one, and
			# the header asks before running it. Read off the state's own
			# `doc_status` rather than from the action's wording: "Reject" and
			# "Return to draft" are the same word to a reader and different
			# things to the ledger.
			"cancels": _cancels(doc.doctype, row.get("next_state")),
		}
		for row in found
	]


def _cancels(doctype: str, next_state: str) -> bool:
	row = _state_row(_workflow(doctype), next_state)
	return bool(row and str(row.doc_status or "0") == "2")


def _plain(doc, docstatus: int) -> list[dict]:
	"""Submit, Cancel or Amend — whichever this docstatus admits."""
	entry = PLAIN.get(docstatus)
	if not entry:
		return []

	permission, label = entry
	if not frappe.has_permission(doc.doctype, permission, doc=doc):
		return []

	if docstatus == 2 and _amended(doc.doctype, doc.name):
		# Amending twice makes two drafts from one cancelled document and
		# nothing says which is the real one. The desk hides the button for the
		# same reason, through `frappe.client.is_document_amended`.
		return []

	return [{"kind": permission, "action": label, "next": "", "cancels": docstatus == 1}]


def _amended(doctype: str, name: str) -> bool:
	try:
		return bool(frappe.db.exists(doctype, {"amended_from": name}))
	except Exception:
		# A doctype with no `amended_from` column is one Frappe never made
		# submittable, so nothing was ever amended from it.
		frappe.clear_last_message()
		return False


# --------------------------------------------------------------------------- #
# Doing it
#
# Every one of these takes a document the caller has already resolved through
# the screen, so what is left here is the framework's own rule and the one
# refusal Frappe does not make for itself.
# --------------------------------------------------------------------------- #


def submit(doc) -> None:
	_no_workflow(doc, "submitted")
	if int(doc.get("docstatus") or 0) != 0:
		frappe.throw(_("Only a draft can be submitted."))
	doc.submit()
	frappe.db.commit()


def cancel(doc) -> None:
	_no_workflow(doc, "cancelled")
	if int(doc.get("docstatus") or 0) != 1:
		frappe.throw(_("Only a submitted document can be cancelled."))
	doc.cancel()
	frappe.db.commit()


def amend(doc) -> str:
	"""A fresh draft that remembers what it came from.

	`copy_doc(ignore_no_copy=False)` rather than a hand-built dict: a doctype
	marks the fields that must not survive a copy — a posting date, an external
	reference, a signature — and honouring `no_copy` is the difference between
	an amendment and a duplicate that quietly carries last month's numbers.

	Frappe fills the new name itself: `amended_from` is what its naming reads to
	produce `ACC-SINV-2026-0001-1` rather than a second document with no
	relationship to the first.
	"""
	_no_workflow(doc, "amended")
	if int(doc.get("docstatus") or 0) != 2:
		frappe.throw(_("Only a cancelled document can be amended."))
	if not frappe.has_permission(doc.doctype, "amend", doc=doc):
		# The one the framework does not make for itself: an amendment is an
		# ordinary insert, so without this `create` would be enough to make one.
		frappe.throw(_("You cannot amend this."), frappe.PermissionError)
	if _amended(doc.doctype, doc.name):
		frappe.throw(_("This has already been amended."))

	made = frappe.copy_doc(doc, ignore_no_copy=False)
	made.amended_from = doc.name
	made.docstatus = 0
	made.insert()
	frappe.db.commit()
	return made.name


def apply(doc, action: str) -> str:
	"""One workflow transition, through the framework's own machinery.

	`apply_workflow` does the whole of it — finds the transition, refuses a
	self-approval where the transition forbids one, writes the state field,
	applies the state's `update_field`, runs its transition tasks, calls
	`save`, `submit` or `cancel` according to the two states' `doc_status`, and
	leaves a comment on the record saying what happened. Reimplementing any
	part of that would be a second workflow engine.
	"""
	from frappe.model.workflow import apply_workflow

	if not workflow_name(doc.doctype):
		frappe.throw(_("Nothing here runs on a workflow."))

	apply_workflow(doc, action)
	frappe.db.commit()
	return doc.name


def _no_workflow(doc, verb: str) -> None:
	"""A workflow owns the submit, so the plain door is closed while one exists.

	Not a formality: a workflow's states carry the docstatus, so submitting
	around it would leave the document submitted and its workflow state saying
	it is still waiting for somebody.
	"""
	if workflow_name(doc.doctype):
		frappe.throw(
			_("{0} runs on a workflow, so it is {1} by taking the next step in it.")
			.format(_(doc.doctype), _(verb))
		)
