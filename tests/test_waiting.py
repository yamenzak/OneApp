"""What is waiting on you, and the four ways an inbox gets this wrong.

`docs/FRAPPE.md` named the approvals inbox as the missing half of the workflow
gap: the engine has driven Frappe's workflow since the record shell was built,
the framework has been writing a `Workflow Action` per approver on every
transition, and nobody read them back.

An inbox over somebody else's permission model is the kind of surface that goes
wrong quietly, so the guards are about what it must *not* do:

  * it must not decide who may approve what — Frappe's own permission query
    conditions on `Workflow Action` are the whole of the scoping;
  * it must not be a second write path — acting is the endpoint the record
    header already calls;
  * it must not offer a verb it cannot deliver, which is what an unplaced row
    would be;
  * and it must not ask the same person twice about one document, which is
    exactly what the framework's one-row-per-role does.
"""

import ast
import pathlib
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onespace/waiting.py"
ONE = ROOT / "apps/oneapp/oneapp/onespace/one.py"
HOME = ROOT / "apps/oneapp/oneapp/onespace/home.py"
SCREEN = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/one/Waiting.vue"
REGISTRY = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
HOME_VUE = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/one/Home.vue"


@pytest.fixture
def waiting(stub_frappe):
	from oneapp.onespace import waiting as module

	return module


def _row(**over):
	return {
		"name": "wa-1", "reference_doctype": "zzApproval",
		"reference_name": "ZZA-00001", "workflow_state": "zzDraft",
		"creation": "2026-09-13 10:00:00", **over,
	}


def _target(**over):
	return {
		"doctype": "zzApproval", "space": "zzmock", "space_label": "MockSpace",
		"brand": "", "screen": "approvals", "label": "Approval",
		"icon": "lucide-shield", "fields": "title", "filters": "", **over,
	}


def _meta(fields: dict, title: str = ""):
	return types.SimpleNamespace(
		title_field=title, get_field=lambda name: fields.get(name), track_changes=0,
	)


# ------------------------------------------------------------------ the list

def test_one_document_is_one_line_however_many_roles_asked(waiting, stub_frappe):
	"""The framework writes a row per permitted *role*.

	Somebody holding two of them is asked twice about one expense claim, which
	is a true thing about the table and a wrong thing to put in front of a
	person.
	"""
	stub_frappe._meta["zzApproval"] = _meta({"title": types.SimpleNamespace(fieldtype="Data")})
	waiting._rows = lambda: [_row(name="wa-1"), _row(name="wa-2")]
	waiting.finding.placed = lambda: {"zzApproval": _target()}
	waiting.docflow._transitions = lambda doc: []
	assert waiting.mine()["count"] == 1


def test_the_badge_counts_what_the_list_would_show(waiting):
	waiting._rows = lambda: [_row(name="wa-1"), _row(name="wa-2")]
	assert waiting.how_many() == 1, (
		"a badge saying two over a list of one is a small lie about a number "
		"people are meant to trust"
	)


def test_a_row_is_placed_on_the_screen_that_shows_it(waiting, stub_frappe):
	stub_frappe._meta["zzApproval"] = _meta({}, "")
	waiting._rows = lambda: [_row()]
	waiting.finding.placed = lambda: {"zzApproval": _target()}
	waiting.docflow._transitions = lambda doc: [{"action": "zzSend", "cancels": False}]
	row = waiting.mine()["rows"][0]
	assert row["space"] == "zzmock" and row["screen"] == "approvals"
	assert row["placed"] is True
	assert [one["action"] for one in row["verbs"]] == ["zzSend"]


def test_a_document_no_screen_shows_is_listed_and_offers_nothing(waiting, stub_frappe):
	"""Being asked to approve something is not made untrue by the manifest.

	But `docstate.workflow_action` is reached through a space and a screen, so
	there is nowhere to send the action — a verb here would be a button that
	cannot work.
	"""
	stub_frappe._meta["zzApproval"] = _meta({}, "")
	waiting._rows = lambda: [_row()]
	waiting.finding.placed = lambda: {}
	row = waiting.mine()["rows"][0]
	assert row["placed"] is False
	assert row["verbs"] == []


def test_a_document_that_has_gone_does_not_take_the_inbox_down(waiting, stub_frappe):
	"""An inbox is read after the fact by definition."""
	stub_frappe._meta["zzApproval"] = _meta({}, "")

	def gone(*a, **k):
		raise RuntimeError("no such document")

	waiting.frappe.get_doc = gone
	assert waiting._verbs("zzApproval", "ZZA-00001") == []


def test_markup_in_a_title_is_not_shown_as_markup(waiting, stub_frappe):
	stub_frappe._meta["zzApproval"] = _meta({}, "title")
	waiting.frappe.db.get_value = lambda *a, **k: "<p>Office chairs</p>"
	assert waiting._title("zzApproval", "ZZA-00001") == "Office chairs"


def test_a_doctype_with_no_title_field_says_its_id(waiting, stub_frappe):
	stub_frappe._meta["zzApproval"] = _meta({}, "")
	assert waiting._title("zzApproval", "ZZA-00001") == "ZZA-00001"


# ----------------------------------------------------------------- the rules

def _tree():
	return ast.parse(SOURCE.read_text())


def test_nothing_here_ignores_permissions():
	"""Read off the tree, not grepped for: the docstring argues about it."""
	offenders = [
		node.arg for node in ast.walk(_tree())
		if isinstance(node, ast.keyword) and node.arg == "ignore_permissions"
	]
	assert not offenders, (
		"Frappe's own permission query conditions on Workflow Action are the "
		"whole of the scoping, and they only apply through `get_list`"
	)


def test_the_rows_come_through_get_list():
	calls = {
		ast.unparse(node.func) for node in ast.walk(_tree())
		if isinstance(node, ast.Call)
	}
	assert "frappe.get_list" in calls
	assert "frappe.db.count" not in calls, (
		"`db.count` does not apply this doctype's permission query conditions, "
		"so it would count the whole workspace's approvals for everybody"
	)


def test_the_inbox_is_not_a_second_write_path():
	"""Acting is `spaceview/docstate.workflow_action`, which already exists.

	A second door onto one transition is a second idea of who may open it.

	Read off the tree and not the text, for the third time in this repository:
	the module's own docstring explains at length that `apply_workflow` is what
	drives a transition *elsewhere*, so a grep finds the paragraph arguing for
	the rule and fails the rule.
	"""
	forbidden = {"apply_workflow", "docstate", "submit", "cancel", "save"}
	named = set()
	for node in ast.walk(_tree()):
		if isinstance(node, ast.Name):
			named.add(node.id)
		elif isinstance(node, ast.Attribute):
			named.add(node.attr)
		elif isinstance(node, ast.alias):
			named.add(node.name.split(".")[-1])
	assert not (named & forbidden), (
		f"{sorted(named & forbidden)} here would make this an inbox that writes"
	)


def test_both_endpoints_only_read():
	for node in ast.walk(_tree()):
		if not isinstance(node, ast.FunctionDef):
			continue
		for one in node.decorator_list:
			if not isinstance(one, ast.Call) or "whitelist" not in ast.unparse(one.func):
				continue
			methods = next(
				(ast.literal_eval(kw.value) for kw in one.keywords if kw.arg == "methods"),
				None,
			)
			assert methods == ["GET"], f"{node.name} must not accept a write"


def test_the_screen_is_declared_only_where_there_is_a_workflow():
	"""Most workspaces ship none, and a door onto nothing is worse than absence."""
	source = ONE.read_text()
	assert 'frappe.db.exists("Workflow", {"is_active": 1})' in source
	assert '"screen": "waiting"' in source


# ------------------------------------------------------------- the front end

def test_the_screen_is_registered():
	assert "'one/waiting'" in REGISTRY.read_text()


def test_the_screen_acts_through_the_endpoint_the_header_uses():
	source = SCREEN.read_text()
	assert "workspace.workflowAction(" in source
	assert "apply" not in source.split("<script")[0], (
		"the template must not name a transition of its own"
	)


def test_a_transition_that_cancels_asks_first():
	source = SCREEN.read_text()
	assert "verb.cancels" in source and "<Dialog" in source, (
		"'Reject' and 'Return to draft' read the same and one of them unwrites "
		"a ledger — the question is the state's own doc_status"
	)


def test_the_home_page_stopped_pretending_it_answered_this():
	"""**What needs you** said notifications and meant them."""
	assert '"approvals": _try(_approvals)' in HOME.read_text()
	source = HOME_VUE.read_text()
	assert "fromApproval" in source
	assert "  4: " in source, (
		"a fourth block needs a fourth column count, or the grid keeps a hole "
		"where the card is"
	)
