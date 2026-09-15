"""Docstatus and workflow — the rules that are ours rather than the framework's.

Frappe owns the mechanics: it enforces the docstatus transitions, checks
`submit` and `cancel` on the way through, and `apply_workflow` runs a
transition end to end. None of that is re-tested here.

What is pinned is the seam. Which actions are offered, the two refusals Frappe
does not make for itself, and the one rule that decides everything else: **a
workflow owns the transition**, so the plain Submit is never beside one.
"""

import types

import pytest


@pytest.fixture
def docflow(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	from oneapp.onespace import docflow as module

	return module


def doc(doctype="Invoice", name="INV-1", docstatus=0, **extra):
	"""A document, as thin as what this module asks of one."""
	held = {"doctype": doctype, "name": name, "docstatus": docstatus, **extra}
	return types.SimpleNamespace(
		doctype=doctype,
		name=name,
		get=held.get,
		submit=lambda: held.__setitem__("docstatus", 1),
		cancel=lambda: held.__setitem__("docstatus", 2),
		_held=held,
	)


def meta(submittable=1):
	return types.SimpleNamespace(name="Invoice", is_submittable=submittable, fields=[])


def no_workflow(docflow, monkeypatch):
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "")


# --- what is offered ------------------------------------------------------


def test_a_draft_is_offered_submit_and_nothing_else(docflow, stub_frappe, monkeypatch):
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True, raising=False)

	found = docflow.state(doc(docstatus=0), meta())
	assert [one["action"] for one in found["actions"]] == ["Submit"]
	assert found["status"] == "Draft"
	assert found["editable"] is True


def test_a_submitted_document_is_offered_cancel_and_says_so(docflow, stub_frappe,
                                                            monkeypatch):
	"""`cancels` rather than the word on the button: the header asks before
	running anything that unwrites a ledger, and "Reject" is a word too."""
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True, raising=False)

	found = docflow.state(doc(docstatus=1), meta())
	assert found["actions"] == [
		{"kind": "cancel", "action": "Cancel", "next": "", "cancels": True}
	]


def test_a_cancelled_document_is_not_editable(docflow, stub_frappe, monkeypatch):
	"""Frappe refuses the save, so offering the form is offering a refusal."""
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True, raising=False)

	assert docflow.state(doc(docstatus=2), meta())["editable"] is False


def test_an_action_nobody_may_take_is_not_offered(docflow, stub_frappe, monkeypatch):
	"""The button is drawn from the permission, not disabled after the fact."""
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: False, raising=False)

	assert docflow.state(doc(docstatus=0), meta())["actions"] == []


def test_a_doctype_that_does_not_submit_is_offered_nothing(docflow, stub_frappe,
                                                           monkeypatch):
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True, raising=False)

	found = docflow.state(doc(docstatus=0), meta(submittable=0))
	assert found["actions"] == []
	assert found["submittable"] is False


def test_a_document_already_amended_offers_no_second_amendment(docflow, stub_frappe,
                                                               monkeypatch):
	"""Two drafts from one cancelled document and nothing says which is real."""
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True, raising=False)
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: "INV-1-1")

	assert docflow.state(doc(docstatus=2), meta())["actions"] == []


# --- a workflow owns the transition ---------------------------------------


def test_the_plain_door_is_closed_while_a_workflow_exists(docflow, stub_frappe,
                                                          monkeypatch):
	"""The rule the whole module turns on, and Frappe's own — the desk's
	`can_submit()` ends with `!this.has_workflow()`.

	A workflow's states carry the docstatus, so submitting around one leaves
	the document submitted and its workflow state still saying it is waiting
	for somebody.
	"""
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "Invoice Approval")

	for verb in (docflow.submit, docflow.cancel, docflow.amend):
		with pytest.raises(stub_frappe.ValidationError) as raised:
			verb(doc(docstatus=0))
		assert "workflow" in str(raised.value)


def test_a_workflow_replaces_the_actions_rather_than_adding_to_them(docflow,
                                                                    stub_frappe,
                                                                    monkeypatch):
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "Invoice Approval")
	monkeypatch.setattr(docflow, "_shape", lambda doc, name: {"state": "Pending"})
	monkeypatch.setattr(docflow, "_transitions", lambda doc: [
		{"kind": "workflow", "action": "Approve", "next": "Approved", "cancels": False},
	])
	monkeypatch.setattr(docflow, "editable", lambda doc, meta=None: True)

	found = docflow.state(doc(docstatus=0), meta())
	assert [one["action"] for one in found["actions"]] == ["Approve"]
	assert found["workflow"]["state"] == "Pending"


def test_a_state_with_no_transitions_is_an_answer_rather_than_an_error(docflow,
                                                                       stub_frappe,
                                                                       monkeypatch):
	"""Frappe throws `WorkflowStateError` on a record with no state yet, which
	is ordinary for one created before the workflow existed."""
	import sys

	workflow = sys.modules["frappe.model.workflow"]

	def raise_it(doc, raise_exception=False):
		raise workflow.WorkflowStateError("no state")

	monkeypatch.setattr(workflow, "get_transitions", raise_it)
	assert docflow._transitions(doc()) == []


# --- the pipeline ----------------------------------------------------------
#
# Where the record stands is a badge; where it stands *among the states it can
# be in* is a different question and the one a person actually asks. "Approved"
# says nothing about how far along that is or what is left.


def workflow(*rows):
	"""A workflow, as thin as `_pipeline` asks of one.

	**A `Workflow Document State` row carries no `style`.** It has the state's
	name, its docstatus and who may edit in it, and that is all — the colour is
	on the `Workflow State` doctype, which is why `_shape` looks it up. The
	first version of this stub invented `row.style`, `_pipeline` read it, and
	every test passed against a shape the database does not have: the first
	real workflow threw `AttributeError` on the first record opened. A stub that
	is more generous than the thing it stands for is a test that proves nothing.
	"""
	return types.SimpleNamespace(
		workflow_state_field="workflow_state",
		states=[types.SimpleNamespace(**row) for row in rows],
	)


SCREENED = {"state": "Screened", "doc_status": "0"}
OFFERED = {"state": "Offered", "doc_status": "0"}
HIRED = {"state": "Hired", "doc_status": "1"}
REJECTED = {"state": "Rejected", "doc_status": "2"}


def test_the_pipeline_is_every_state_with_the_one_it_is_at_marked(docflow, monkeypatch):
	monkeypatch.setattr(docflow, "_workflow",
	                    lambda doctype: workflow(SCREENED, OFFERED, HIRED))

	found = docflow._pipeline(doc(workflow_state="Offered"), "Hiring")
	assert [one["state"] for one in found] == ["Screened", "Offered", "Hired"]
	assert [one["standing"] for one in found] == ["done", "now", "ahead"]


def test_a_state_on_two_rows_is_one_place_in_the_pipeline(docflow, monkeypatch):
	"""A state gets a row per role that may act in it, and a pipeline repeating
	it would say the document passes through the same place twice."""
	monkeypatch.setattr(docflow, "_workflow", lambda doctype: workflow(
		SCREENED, dict(SCREENED, doc_status="0"), OFFERED,
	))

	found = docflow._pipeline(doc(workflow_state="Screened"), "Hiring")
	assert [one["state"] for one in found] == ["Screened", "Offered"]


def test_a_record_with_no_state_yet_is_nowhere_rather_than_at_the_start(docflow,
                                                                        monkeypatch):
	"""A record made before the workflow existed is at none of its states, and
	saying it is at the first one would be the pipeline inventing a fact."""
	monkeypatch.setattr(docflow, "_workflow",
	                    lambda doctype: workflow(SCREENED, OFFERED))

	found = docflow._pipeline(doc(), "Hiring")
	assert [one["standing"] for one in found] == ["ahead", "ahead"]


def test_the_colour_comes_off_the_state_rather_than_the_workflows_row(docflow,
                                                                     stub_frappe,
                                                                     monkeypatch):
	"""A `Workflow Document State` has no `style`; `Workflow State` does.

	The witness for an `AttributeError` that reached a browser, because the stub
	this suite used to hand `_pipeline` had a field the real row does not.
	"""
	monkeypatch.setattr(docflow, "_workflow",
	                    lambda doctype: workflow(SCREENED, HIRED))
	monkeypatch.setattr(stub_frappe, "get_all",
	                    lambda *a, **k: [["Screened", "Info"], ["Hired", "Success"]])

	found = docflow._pipeline(doc(workflow_state="Screened"), "Hiring")
	assert [one["theme"] for one in found] == ["blue", "green"]


def test_a_cancelling_state_says_so(docflow, monkeypatch):
	"""So the sidebar can draw the way *out* differently from the way on."""
	monkeypatch.setattr(docflow, "_workflow",
	                    lambda doctype: workflow(SCREENED, REJECTED))

	found = docflow._pipeline(doc(workflow_state="Rejected"), "Hiring")
	assert [one["cancels"] for one in found] == [False, True]
	assert found[1]["standing"] == "now"


def test_a_submittable_doctype_gets_the_frameworks_own_three(docflow):
	found = docflow._plain_pipeline(1)
	assert [one["state"] for one in found] == ["Draft", "Submitted", "Cancelled"]
	assert [one["standing"] for one in found] == ["done", "now", "ahead"]


def test_a_doctype_that_neither_submits_nor_flows_has_no_pipeline(docflow,
                                                                  stub_frappe,
                                                                  monkeypatch):
	"""Nothing to draw, rather than a pipeline of one. A ToDo is not a document
	that goes anywhere."""
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "")
	monkeypatch.setattr(docflow, "editable", lambda doc, meta=None: True)

	found = docflow.state(doc(), meta(submittable=False))
	assert found["pipeline"] == []


# --- who may edit, and when -----------------------------------------------


def test_a_workflow_state_can_hand_the_record_to_one_role(docflow, stub_frappe,
                                                          monkeypatch):
	"""`allow_edit` on the state: a purchase order in Pending Approval is the
	approver's and nobody else's.

	The desk enforces this in the browser alone, so the API under it does not.
	Ours is the only surface there is, which is why `editable` decides on the
	way in as well as on the way out.
	"""
	state = types.SimpleNamespace(state="Pending", allow_edit="Approver", doc_status="0")
	workflow = types.SimpleNamespace(workflow_state_field="workflow_state", states=[state])
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "Invoice Approval")
	monkeypatch.setattr(docflow, "_workflow", lambda doctype: workflow)

	monkeypatch.setattr(stub_frappe, "get_roles", lambda *a: ["Sales"])
	assert docflow.editable(doc(workflow_state="Pending")) is False

	monkeypatch.setattr(stub_frappe, "get_roles", lambda *a: ["Approver"])
	assert docflow.editable(doc(workflow_state="Pending")) is True


def test_a_state_that_names_no_role_is_everybody_s(docflow, stub_frappe, monkeypatch):
	state = types.SimpleNamespace(state="Draft", allow_edit=None, doc_status="0")
	workflow = types.SimpleNamespace(workflow_state_field="workflow_state", states=[state])
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "Invoice Approval")
	monkeypatch.setattr(docflow, "_workflow", lambda doctype: workflow)
	monkeypatch.setattr(stub_frappe, "get_roles", lambda *a: [])

	assert docflow.editable(doc(workflow_state="Draft")) is True


def test_a_record_with_no_state_yet_is_editable(docflow, stub_frappe, monkeypatch):
	"""Frappe fills the first state on save, so refusing here would mean
	nothing could ever be saved into the workflow to begin with."""
	workflow = types.SimpleNamespace(workflow_state_field="workflow_state", states=[])
	monkeypatch.setattr(docflow, "workflow_name", lambda doctype: "Invoice Approval")
	monkeypatch.setattr(docflow, "_workflow", lambda doctype: workflow)

	assert docflow.editable(doc()) is True


# --- the two refusals Frappe does not make --------------------------------


def test_amending_checks_a_permission_frappe_never_looks_at(docflow, stub_frappe,
                                                            monkeypatch):
	"""An amendment is an ordinary insert of a new draft, so the framework asks
	for `create` and nothing else. Without this check `amend` would mean
	nothing on any doctype."""
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: False, raising=False)

	with pytest.raises(stub_frappe.PermissionError):
		docflow.amend(doc(docstatus=2))


def test_the_docstatus_has_to_be_the_right_one(docflow, stub_frappe, monkeypatch):
	no_workflow(docflow, monkeypatch)
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True, raising=False)

	with pytest.raises(stub_frappe.ValidationError):
		docflow.submit(doc(docstatus=1))
	with pytest.raises(stub_frappe.ValidationError):
		docflow.cancel(doc(docstatus=0))
	with pytest.raises(stub_frappe.ValidationError):
		docflow.amend(doc(docstatus=1))


def test_a_workflow_state_colour_is_frappes_own_six(docflow):
	"""Mapped onto the badge themes `lib/fields.js` draws, the same ones a
	Document State gets — a state is a state, and one product should not colour
	the two kinds differently."""
	assert set(docflow.STYLES) == {
		"Primary", "Info", "Success", "Warning", "Danger", "Inverse",
	}
	assert set(docflow.STYLES.values()) <= {"blue", "green", "orange", "red", "gray"}
