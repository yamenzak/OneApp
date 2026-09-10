"""A write the assistant asked for, and the one place it can actually happen.

The claim under test is one sentence: **no path from a model reaches a save.**
`propose_update` writes a proposal row; `apply` writes the record and is only
reachable from an endpoint a person calls. Everything here is either that claim
or one of the four ways the card in front of that person could lie — a field
the screen cannot write, a record that has moved since, a diff that is not a
diff, or an Apply pressed twice.
"""

import json
import sys
import types

import pytest


RUA = {
	("rua", "projects"): {
		"space": "rua", "label": "RUA", "screen": "projects",
		"screen_label": "Projects", "singular": "Project",
		"doctype": "Project", "title_field": "project_name",
		"all_columns": [
			{"fieldname": "project_name", "label": "Name", "editable": 1},
			{"fieldname": "status", "label": "Stage", "editable": 1},
			{"fieldname": "modified", "label": "Last changed"},
		],
	},
}

HELD = {"PROJ-1": {"name": "PROJ-1", "project_name": "Marina tower", "status": "Open"}}


class Row(dict):
	"""A stored proposal, close enough to a Frappe Document to be written."""

	def __getattr__(self, name):
		return self.get(name)

	def insert(self, **kw):
		self.setdefault("name", f"chg-{len(STORED) + 1}")
		STORED[self["name"]] = self
		return self

	def db_set(self, values, **kw):
		self.update(values)


STORED: dict[str, Row] = {}


@pytest.fixture
def chat(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	STORED.clear()
	saved = []

	resolve = types.ModuleType("oneapp.onespace.spaceview.resolve")
	resolve._resolve = lambda space, screen=None, view_type=None: RUA.get((space, screen), {})
	monkeypatch.setitem(sys.modules, "oneapp.onespace.spaceview.resolve", resolve)

	records = types.ModuleType("oneapp.onespace.spaceview.records")
	records.record = lambda space_code, screen, name: dict(HELD.get(name) or {}) or None
	records._writable = lambda resolved: {"project_name", "status"}
	records.save = lambda space_code, screen, values, name=None: (
		saved.append({"space": space_code, "screen": screen,
		              "values": values, "name": name})
		or {"name": name or "PROJ-9"}
	)
	monkeypatch.setitem(sys.modules, "oneapp.onespace.spaceview.records", records)

	docflow = types.ModuleType("oneapp.onespace.docflow")
	docflow.editable = lambda doc, meta=None: True
	monkeypatch.setitem(sys.modules, "oneapp.onespace.docflow", docflow)

	# `get_doc` is one function in Frappe and three things here: a new
	# proposal, a stored one being answered, and the customer's own record
	# `_editable` looks at.
	stub_frappe.get_doc = lambda first, *a, **k: (
		Row(first) if isinstance(first, dict)
		else STORED.get(a[0]) if first == "OneSpace Chat Change"
		else Row(HELD.get(a[0]) or {"name": a[0]})
	)
	stub_frappe.get_all = lambda *a, **k: []
	stub_frappe.db.savepoint = lambda *a, **k: None
	stub_frappe.db.release_savepoint = lambda *a, **k: None
	stub_frappe.db.rollback = lambda *a, **k: None
	stub_frappe.utils.now = lambda: "2026-09-10 08:00:00"

	from oneapp.onespace.chat import changes, toolbox

	return types.SimpleNamespace(
		changes=changes, toolbox=toolbox, frappe=stub_frappe,
		monkeypatch=monkeypatch, saved=saved, stored=STORED,
	)


def propose(chat, **kw):
	asked = dict(session="s1", space="rua", screen="projects",
	             values={"status": "Closed"}, docname="PROJ-1")
	asked.update(kw)
	return chat.changes.propose(**asked)


# --------------------------------------------------------------------------- #
# Nothing a model can call writes a record
# --------------------------------------------------------------------------- #

def test_proposing_writes_a_proposal_and_not_the_record(chat):
	answered = propose(chat)

	assert answered["proposed"] in chat.stored
	assert chat.saved == []
	# And the model is told so in words, because what it says next is built out
	# of what the tool handed back.
	assert "waiting" in answered["note"]
	assert "changed" not in answered


def test_the_tool_is_the_module_and_adds_nothing(chat):
	"""`propose_update` is a wrapper. A second implementation is a second set
	of rules, and only one of them would be the one anybody tested."""
	answered = chat.toolbox.propose_update(
		session="s1", space="rua", screen="projects", name="PROJ-1",
		values={"status": "Closed"},
	)
	assert answered["proposed"] in chat.stored
	assert chat.stored[answered["proposed"]]["kind"] == "Update"


def test_no_tool_can_apply_one(chat):
	"""The whole safety argument, as a property of the toolbox.

	Apply is an endpoint a person's click reaches. If a tool ever calls it, the
	confirmation step is decoration and this file is describing something that
	is no longer true.
	"""
	import inspect

	for one in chat.toolbox.TOOLBOX:
		source = inspect.getsource(one.func)
		assert "changes.apply" not in source, one.name
		assert "records.save" not in source, one.name


def test_the_write_goes_through_the_screens_own_save(chat):
	"""Not `get_doc().save()`: `records.save` is where the field allowlist, the
	permission check and the workflow rule live."""
	name = propose(chat)["proposed"]
	answered = chat.changes.apply(name)

	assert answered["state"] == "Applied"
	assert chat.saved == [{"space": "rua", "screen": "projects",
	                       "values": {"status": "Closed"}, "name": "PROJ-1"}]


# --------------------------------------------------------------------------- #
# The card cannot lie about what it would do
# --------------------------------------------------------------------------- #

def test_a_field_the_screen_cannot_write_is_refused_on_the_turn_it_was_named(chat):
	"""Told to the model now rather than to a person after they agreed."""
	answered = propose(chat, values={"invented": "x"})
	assert "no field called invented" in answered["error"]
	assert not chat.stored


def test_a_record_the_screen_would_not_list_is_not_proposable(chat):
	answered = propose(chat, docname="PROJ-NOPE")
	assert "No record called PROJ-NOPE" in answered["error"]
	assert not chat.stored


def test_setting_a_field_to_what_it_already_says_is_not_a_change(chat):
	"""A card whose only row says Open → Open is a card asking for nothing."""
	answered = propose(chat, values={"status": "Open"})
	assert "already says that" in answered["answer"]
	assert not chat.stored


def test_only_the_fields_that_move_reach_the_card(chat):
	answered = propose(chat, values={"status": "Closed", "project_name": "Marina tower"})
	stored = chat.stored[answered["proposed"]]
	assert json.loads(stored["changes"]) == {"status": "Closed"}
	assert json.loads(stored["before"]) == {"status": "Open"}


def test_the_summary_is_written_here_and_not_by_the_model(chat):
	"""The heading and the rows have to say the same thing, and only one of
	them can be the model's wording."""
	stored = chat.stored[propose(chat)["proposed"]]
	assert stored["summary"] == "Change Marina tower (PROJ-1) on Stage"


def test_a_record_that_moved_since_is_refused_rather_than_overwritten(chat):
	"""The person agreed to a diff. It is no longer that diff."""
	name = propose(chat)["proposed"]
	HELD["PROJ-1"]["status"] = "Won"
	try:
		answered = chat.changes.apply(name)
	finally:
		HELD["PROJ-1"]["status"] = "Open"

	assert answered["ok"] is False
	assert answered["state"] == "Failed"
	assert "status changed since" in answered["error"]
	assert chat.saved == []


def test_a_change_is_answered_once(chat):
	name = propose(chat)["proposed"]
	chat.changes.apply(name)
	with pytest.raises(Exception, match="already been answered"):
		chat.changes.apply(name)


def test_discarding_keeps_the_row(chat):
	"""Gone from the card and still in the thread: the thread is the record of
	what was asked, including what was said no to."""
	name = propose(chat)["proposed"]
	assert chat.changes.discard(name)["state"] == "Discarded"
	assert chat.stored[name]["state"] == "Discarded"
	assert chat.saved == []


def test_a_save_that_fails_says_so_on_the_card(chat):
	"""And stays Failed rather than reverting to Proposed, which would invite
	the same press again."""
	records = sys.modules["oneapp.onespace.spaceview.records"]
	def refuse(**kw):
		raise ValueError("nope")
	chat.monkeypatch.setattr(records, "save", refuse)

	name = propose(chat)["proposed"]
	answered = chat.changes.apply(name)
	assert answered["state"] == "Failed"
	assert chat.stored[name]["state"] == "Failed"
	assert "could not be saved" in chat.stored[name]["error"]


def test_a_create_carries_no_record_and_no_before(chat):
	answered = chat.changes.propose(
		session="s1", space="rua", screen="projects",
		values={"project_name": "Pier 9"},
	)
	stored = chat.stored[answered["proposed"]]
	assert stored["kind"] == "Create"
	assert stored["docname"] == ""
	assert json.loads(stored["before"]) == {}
	assert stored["summary"] == "Create a Project on Projects"


def test_a_screen_with_no_records_has_nothing_to_change(chat):
	answered = propose(chat, screen="dashboard")
	assert "no records to change" in answered["error"]


def test_one_change_cannot_rewrite_a_whole_record(chat):
	"""Not a performance limit — a card with forty rows is one nobody reads."""
	answered = propose(chat, values={f"f{n}": n for n in range(50)})
	assert "more fields than one change may set" in answered["error"]


# --------------------------------------------------------------------------- #
# Where the card appears, and what the model may not reach
# --------------------------------------------------------------------------- #

@pytest.fixture
def surface(chat):
	"""The endpoints, which need the feature registry the decorator fills."""
	from oneapp.onespace.chat import assistant

	return assistant


def test_a_change_hangs_under_the_answer_that_asked_for_it(surface):
	"""A run proposes before it answers, so the card belongs to the answer.

	Anchored on the last turn stored when the tool ran — the previous answer,
	or nothing at all on the first question — and the card lands on the first
	assistant turn after it.
	"""
	shown = [
		{"name": "m1", "role": "user", "changes": []},
		{"name": "m2", "role": "assistant", "changes": []},
		{"name": "m3", "role": "user", "changes": []},
		{"name": "m4", "role": "assistant", "changes": []},
	]
	surface._hang(shown, [
		{"name": "c1", "after_message": ""},
		{"name": "c2", "after_message": "m2"},
	])

	assert [one["name"] for one in shown[1]["changes"]] == ["c1"]
	assert [one["name"] for one in shown[3]["changes"]] == ["c2"]


def test_a_change_with_no_answer_after_it_still_has_somewhere_to_go(surface):
	"""The case that actually happens: a run that proposed and then ran out of
	turns. A card with nowhere to hang is one nobody can answer."""
	shown = [{"name": "m1", "role": "user", "changes": []}]
	surface._hang(shown, [{"name": "c1", "after_message": "m1"}])
	assert [one["name"] for one in shown[0]["changes"]] == ["c1"]


def test_the_session_is_bound_out_of_the_schema(chat):
	"""A session id is all a proposal is filed under, so an argument the model
	can still name is one it can be talked into filing elsewhere."""
	usable = [one.bind(session="s1") if one.takes("session") else one
	          for one in chat.toolbox.TOOLBOX]

	asking = [one for one in usable if one.name.startswith("propose_")]
	assert len(asking) == 2
	for one in asking:
		assert "session" not in one.parameters["properties"]
		assert one.bound["session"] == "s1"
