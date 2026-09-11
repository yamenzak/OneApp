"""Something a model asked for, and the one place it can actually happen.

The claim under test is one sentence: **no path from a model reaches a write.**
A `propose_` tool writes a suggestion row; `apply` does the thing and is only
reachable from an endpoint a person calls. Everything here is either that
claim, one of the four ways the card in front of that person could lie — a
field the screen cannot write, a record that has moved since, a diff that is
not a diff, an Apply pressed twice — or the property the registry exists for:
that a second kind is a handler and changes nothing else.
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
	"""A stored suggestion, close enough to a Frappe Document to be written."""

	def __getattr__(self, name):
		return self.get(name)

	def insert(self, **kw):
		self.setdefault("name", f"sug-{len(STORED) + 1}")
		STORED[self["name"]] = self
		return self

	def db_set(self, values, **kw):
		self.update(values)


STORED: dict[str, Row] = {}


@pytest.fixture
def ai(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace") or name.startswith("oneapp.onecalendar"):
			del sys.modules[name]

	STORED.clear()
	saved, events, todos = [], [], []

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

	diary = types.ModuleType("oneapp.onecalendar.diary")
	diary.EVENT = "Event"
	diary.save_event = lambda values: (events.append(values) or {"name": "EV-1"})
	monkeypatch.setitem(sys.modules, "oneapp.onecalendar.diary", diary)
	# The package as well as the module: `oneapp/onecalendar/__init__.py` is a
	# façade that pulls names up out of the real `diary`, and importing it
	# would run that against this stub and fail on the first one missing.
	calendar = types.ModuleType("oneapp.onecalendar")
	calendar.diary = diary
	monkeypatch.setitem(sys.modules, "oneapp.onecalendar", calendar)

	# `get_doc` is one function in Frappe and four things here: a new
	# suggestion, a stored one being answered, a ToDo being inserted, and the
	# customer's own record `_editable` looks at.
	def get_doc(first, *a, **k):
		if isinstance(first, dict):
			if first.get("doctype") == "ToDo":
				row = Row(first)
				row["name"] = "TODO-1"
				todos.append(first)
				return row
			return Row(first)
		if first == "OneSpace Suggestion":
			return STORED.get(a[0])
		return Row(HELD.get(a[0]) or {"name": a[0]})

	stub_frappe.get_doc = get_doc
	stub_frappe.get_all = lambda *a, **k: []
	stub_frappe.db.savepoint = lambda *a, **k: None
	stub_frappe.db.release_savepoint = lambda *a, **k: None
	stub_frappe.db.rollback = lambda *a, **k: None
	stub_frappe.utils.now = lambda: "2026-09-10 08:00:00"
	stub_frappe.utils.format_datetime = lambda v, f=None: str(v)
	stub_frappe.utils.formatdate = lambda v, f=None: str(v)
	stub_frappe.utils.get_datetime = lambda v: _Stamp(v)
	stub_frappe.utils.getdate = lambda v: _Stamp(v)

	from oneapp.onespace.ai import actions, kinds, proposing
	from oneapp.onespace.chat import toolbox

	return types.SimpleNamespace(
		actions=actions, kinds=kinds, proposing=proposing, toolbox=toolbox,
		frappe=stub_frappe, monkeypatch=monkeypatch,
		saved=saved, events=events, todos=todos, stored=STORED,
	)


class _Stamp(str):
	"""`get_datetime` and `getdate` without a bench behind them."""

	def strftime(self, fmt):
		return str(self)

	def isoformat(self):
		return str(self)


def propose(ai, **kw):
	payload = dict(space="rua", screen="projects",
	               values={"status": "Closed"}, docname="PROJ-1")
	payload.update(kw.pop("payload", {}))
	return ai.actions.propose("record.save", payload, session="s1", **kw)


# --------------------------------------------------------------------------- #
# Nothing a model can call does anything
# --------------------------------------------------------------------------- #

def test_proposing_writes_a_suggestion_and_not_the_record(ai):
	answered = propose(ai)

	assert answered["proposed"] in ai.stored
	assert ai.saved == []
	# And the model is told so in words, because what it says next is built
	# out of what the tool handed back.
	assert "waiting" in answered["note"]
	assert "changed" not in answered


def test_the_tool_is_the_registry_and_adds_nothing(ai):
	"""`propose_update` is a wrapper. A second implementation is a second set
	of rules, and only one of them would be the one anybody tested."""
	answered = ai.proposing.propose_update(
		session="s1", about_doctype="", about_name="",
		space="rua", screen="projects", name="PROJ-1",
		values={"status": "Closed"},
	)
	assert answered["proposed"] in ai.stored
	assert ai.stored[answered["proposed"]]["kind"] == "record.save"


def test_no_tool_can_apply_one(ai):
	"""The whole safety argument, as a property of the toolbox.

	Apply is an endpoint a person's click reaches. If a tool ever calls it,
	the confirmation step is decoration and this file is describing something
	that is no longer true.
	"""
	import inspect

	for one in ai.toolbox.TOOLBOX:
		source = inspect.getsource(one.func)
		assert "actions.apply" not in source, one.name
		assert "records.save" not in source, one.name
		assert "save_event" not in source, one.name


def test_the_write_goes_through_the_screens_own_save(ai):
	"""Not `get_doc().save()`: `records.save` is where the field allowlist,
	the permission check and the workflow rule live."""
	name = propose(ai)["proposed"]
	answered = ai.actions.apply(name)

	assert answered["state"] == "Applied"
	assert ai.saved == [{"space": "rua", "screen": "projects",
	                     "values": {"status": "Closed"}, "name": "PROJ-1"}]


# --------------------------------------------------------------------------- #
# The card cannot lie about what it would do
# --------------------------------------------------------------------------- #

def test_a_field_the_screen_cannot_write_is_refused_on_the_turn_it_was_named(ai):
	"""Told to the model now rather than to a person after they agreed."""
	answered = propose(ai, payload={"values": {"invented": "x"}})
	assert "no field called invented" in answered["error"]
	assert not ai.stored


def test_a_record_the_screen_would_not_list_is_not_proposable(ai):
	answered = propose(ai, payload={"docname": "PROJ-NOPE"})
	assert "No record called PROJ-NOPE" in answered["error"]
	assert not ai.stored


def test_setting_a_field_to_what_it_already_says_is_not_a_change(ai):
	"""A card whose only row says Open → Open is a card asking for nothing."""
	answered = propose(ai, payload={"values": {"status": "Open"}})
	assert "already says that" in answered["error"]
	assert not ai.stored


def test_only_the_fields_that_move_reach_the_card(ai):
	answered = propose(ai, payload={
		"values": {"status": "Closed", "project_name": "Marina tower"},
	})
	stored = ai.stored[answered["proposed"]]
	assert json.loads(stored["payload"])["values"] == {"status": "Closed"}
	assert json.loads(stored["before"]) == {"status": "Open"}


def test_the_summary_is_written_by_the_handler_and_not_by_the_model(ai):
	"""The heading and the rows have to say the same thing, and only one of
	them can be the model's wording."""
	stored = ai.stored[propose(ai)["proposed"]]
	assert stored["summary"] == "Change Marina tower (PROJ-1) on Stage"


def test_a_record_that_moved_since_is_refused_rather_than_overwritten(ai):
	"""The person agreed to a diff. It is no longer that diff."""
	name = propose(ai)["proposed"]
	HELD["PROJ-1"]["status"] = "Won"
	try:
		answered = ai.actions.apply(name)
	finally:
		HELD["PROJ-1"]["status"] = "Open"

	assert answered["ok"] is False
	assert answered["state"] == "Failed"
	assert "status changed since" in answered["error"]
	assert ai.saved == []


def test_a_suggestion_is_answered_once(ai):
	name = propose(ai)["proposed"]
	ai.actions.apply(name)
	with pytest.raises(Exception, match="already been answered"):
		ai.actions.apply(name)


def test_discarding_keeps_the_row(ai):
	"""Gone from the card and still in the thread: the thread is the record of
	what was asked, including what was said no to."""
	name = propose(ai)["proposed"]
	assert ai.actions.discard(name)["state"] == "Discarded"
	assert ai.stored[name]["state"] == "Discarded"
	assert ai.saved == []


def test_a_save_that_fails_says_so_on_the_card(ai):
	"""And stays Failed rather than reverting to Proposed, which would invite
	the same press again."""
	records = sys.modules["oneapp.onespace.spaceview.records"]

	def refuse(**kw):
		raise ValueError("nope")

	ai.monkeypatch.setattr(records, "save", refuse)

	name = propose(ai)["proposed"]
	answered = ai.actions.apply(name)
	assert answered["state"] == "Failed"
	assert ai.stored[name]["state"] == "Failed"
	assert "could not be done" in ai.stored[name]["error"]


def test_a_create_carries_no_record_and_no_before(ai):
	answered = ai.actions.propose("record.save", {
		"space": "rua", "screen": "projects", "values": {"project_name": "Pier 9"},
	}, session="s1")
	stored = ai.stored[answered["proposed"]]
	assert json.loads(stored["payload"])["docname"] == ""
	assert json.loads(stored["before"]) == {}
	assert stored["summary"] == "Create a Project on Projects"


def test_a_screen_with_no_records_has_nothing_to_change(ai):
	answered = propose(ai, payload={"screen": "dashboard"})
	assert "no records to change" in answered["error"]


def test_one_change_cannot_rewrite_a_whole_record(ai):
	"""Not a performance limit — a card with forty rows is one nobody reads."""
	answered = propose(ai, payload={"values": {f"f{n}": n for n in range(50)}})
	assert "more fields than one change may set" in answered["error"]


# --------------------------------------------------------------------------- #
# A second kind is a handler and nothing else
# --------------------------------------------------------------------------- #

def test_the_three_kinds_the_spine_ships_are_registered(ai):
	assert set(ai.actions.REGISTRY) >= {"record.save", "calendar.event", "task"}


def test_a_kind_nothing_registered_is_refused(ai):
	assert "no such suggestion" in ai.actions.propose("delete.everything", {})["error"]


def test_an_event_goes_through_the_diary_rather_than_writing_one(ai):
	"""`diary.save_event` is the endpoint the calendar itself posts to, and is
	where "yours, and private" is decided."""
	answered = ai.actions.propose("calendar.event", {
		"subject": "Site visit", "starts_on": "2026-09-15 09:00:00",
	}, about=("Communication", "MSG-1"))

	assert ai.events == []
	ai.actions.apply(answered["proposed"])
	assert ai.events[0]["subject"] == "Site visit"


def test_an_event_with_no_date_is_refused_rather_than_guessed(ai):
	answered = ai.actions.propose("calendar.event", {"subject": "Sometime"})
	assert "when it starts" in answered["error"]


def test_an_event_with_no_name_is_refused(ai):
	answered = ai.actions.propose("calendar.event", {"starts_on": "2026-09-15 09:00:00"})
	assert "what the event is called" in answered["error"]


def test_a_task_is_the_askers_own(ai):
	"""A task made for a colleague is a notification they did not agree to."""
	answered = ai.actions.propose("task", {"what": "Send the schedule"})
	ai.actions.apply(answered["proposed"])

	assert ai.todos[0]["allocated_to"] == ai.frappe.session.user
	assert ai.todos[0]["description"] == "Send the schedule"


def test_a_task_with_nothing_in_it_is_refused(ai):
	assert "what the task is" in ai.actions.propose("task", {"what": "  "})["error"]


def test_a_card_is_found_by_what_it_is_about(ai):
	"""How a surface with no chat session — a mail thread, a document — finds
	the suggestions that belong on it."""
	ai.actions.propose("task", {"what": "Book the survey"},
	                   about=("Communication", "MSG-1"))
	stored = list(ai.stored.values())[0]
	assert stored["about_doctype"] == "Communication"
	assert stored["about_name"] == "MSG-1"
	assert stored["session"] == ""


def test_a_handler_that_cannot_read_its_own_screen_still_draws_a_card(ai):
	"""A screen an app took with it must not take the card with it: a summary
	that still reads is a card somebody can still discard."""
	name = propose(ai)["proposed"]
	ai.frappe.get_list = lambda *a, **k: [dict(ai.stored[name])]

	handler = ai.actions.get("record.save")
	ai.monkeypatch.setattr(
		type(handler), "rows",
		lambda self, payload, before: (_ for _ in ()).throw(RuntimeError("gone")),
	)

	[card] = ai.actions.for_session("s1")
	assert card["summary"] == "Change Marina tower (PROJ-1) on Stage"
	assert card["rows"] == []


# --------------------------------------------------------------------------- #
# Where the card appears, and what the model may not reach
# --------------------------------------------------------------------------- #

@pytest.fixture
def surface(ai):
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


def test_where_a_card_belongs_is_bound_out_of_the_schema(ai):
	"""A session id is all a suggestion is filed under, so an argument the
	model can still name is one it can be talked into filing elsewhere."""
	usable = ai.proposing.where(ai.toolbox.TOOLBOX, session="s1")

	asking = [one for one in usable if one.name.startswith("propose_")]
	assert len(asking) == 4
	for one in asking:
		for gone in ("session", "about_doctype", "about_name"):
			assert gone not in one.parameters["properties"], one.name
		assert one.bound["session"] == "s1"


def test_binding_leaves_alone_a_tool_that_takes_none_of_it(ai):
	"""Binding an argument a tool never declared is a TypeError a turn later,
	which is the wrong place to find out."""
	usable = ai.proposing.where(ai.toolbox.TOOLBOX, session="s1")
	reading = next(one for one in usable if one.name == "search_files")
	assert reading.bound == {}
