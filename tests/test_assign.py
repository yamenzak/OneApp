"""Who a record is assigned to, and which half of that is the truth.

An assignment is a ToDo. `_assign` on the document is Frappe's own cache of
them, written by `ToDo.update_in_reference`, read by every list row and every
row of faces. Two stores for one fact, and the whole of this file is what
happens when they disagree — which they do, in the wild and in the fixture.
"""

import json
import sys
import types

import pytest


@pytest.fixture
def assigning(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	added, removed, todos = [], [], []
	frappe_assign = types.ModuleType("frappe.desk.form.assign_to")
	frappe_assign.add = lambda args: (
		added.append(args["assign_to"][0])
		or todos.append({"allocated_to": args["assign_to"][0], "status": "Open"})
		or stub_frappe.db.set_value(
			"ToDo", args["name"], "_assign",
			json.dumps([t["allocated_to"] for t in todos]), update_modified=False)
	)
	frappe_assign.remove = lambda doctype, name, who: (
		removed.append(who)
		or todos.remove(next(t for t in todos if t["allocated_to"] == who))
		or stub_frappe.db.set_value(
			"ToDo", name, "_assign",
			json.dumps([t["allocated_to"] for t in todos]), update_modified=False)
	)
	monkeypatch.setitem(sys.modules, "frappe.desk.form.assign_to", frappe_assign)

	# The stub records writes and does not apply them, which would make every
	# assertion here a transcription of the call rather than a statement about
	# what the record ends up saying.
	def set_value(doctype, name, field, value=None, **k):
		stub_frappe.db.writes.append((doctype, name, field, value))
		stub_frappe.db.values[(doctype, field)] = value

	stub_frappe.db.set_value = set_value

	stub_frappe.get_all = lambda doctype, **kw: (
		[t["allocated_to"] for t in todos if t["status"] == "Open"]
		if kw.get("pluck") == "allocated_to" else []
	)
	stub_frappe.get_doc = lambda *a, **k: types.SimpleNamespace(
		check_permission=lambda level: None)

	# `import_module`, because the package re-exports the `assign` *function*
	# under the module's own name and a plain `from ... import assign` hands
	# back the callable.
	import importlib

	module = importlib.import_module("oneapp.onespace.spaceview.assign")

	# Patched onto the module rather than stubbed as one: `assign.py` imports
	# these by name, and a fake `resolve` module would have to carry the six
	# other things the package's `__init__` imports from the real one.
	monkeypatch.setattr(module, "_resolve", lambda space, screen=None, view_type=None: {
		"doctype": "ToDo", "screen": screen, "space": space})
	monkeypatch.setattr(module, "_people", lambda raw: json.loads(raw or "[]"))

	return types.SimpleNamespace(
		module=module, frappe=stub_frappe, added=added, removed=removed, todos=todos,
	)


def said(assigning) -> list:
	return json.loads(assigning.frappe.db.values.get(("ToDo", "_assign")) or "[]")


def hold(assigning, named, real=()):
	"""`_assign` says `named`; the ToDos say `real`."""
	assigning.frappe.db.values[("ToDo", "_assign")] = json.dumps(list(named))
	assigning.todos[:] = [{"allocated_to": one, "status": "Open"} for one in real]


def call(assigning, users):
	return assigning.module.assign(
		space_code="zzmock", screen="tasks", name="zzmock-q3", users=users)


def test_somebody_with_a_todo_is_not_assigned_twice(assigning):
	hold(assigning, ["robin@x"], ["robin@x"])
	call(assigning, ["robin@x"])
	assert assigning.added == []


def test_dropping_somebody_closes_their_todo(assigning):
	hold(assigning, ["robin@x"], ["robin@x"])
	call(assigning, [])
	assert assigning.removed == ["robin@x"]
	assert said(assigning) == []


def test_a_name_no_todo_backs_is_dropped_rather_than_believed(assigning):
	"""The bug, in one line.

	`_assign` naming somebody with no ToDo behind them made `assign_add` skip
	them — already assigned, it thought — so the control did nothing and said
	it had worked. Nobody got a task, nobody got a notification, and the same
	click did nothing again tomorrow.
	"""
	hold(assigning, ["robin@x"], [])
	call(assigning, ["robin@x"])
	assert assigning.added == ["robin@x"]
	assert said(assigning) == ["robin@x"]


def test_a_ghost_goes_even_when_nobody_is_being_assigned(assigning):
	"""And unassigning was broken the same way from the other side:
	`assign_remove` looks for the ToDo first and returns when there is none, so
	the name survived every edit."""
	hold(assigning, ["ghost@x"], [])
	call(assigning, [])
	assert assigning.removed == []
	assert said(assigning) == []


def test_a_real_holder_survives_the_sweep(assigning):
	hold(assigning, ["ghost@x", "robin@x"], ["robin@x"])
	call(assigning, ["robin@x"])
	assert assigning.added == []
	assert assigning.removed == []
	assert said(assigning) == ["robin@x"]


def test_an_untouched_record_is_not_rewritten(assigning):
	"""`_assign` and the ToDos agreeing is the ordinary case, and it must not
	cost a write — the age on a list row is something people read."""
	hold(assigning, ["robin@x"], ["robin@x"])
	before = dict(assigning.frappe.db.values)
	call(assigning, ["robin@x"])
	assert assigning.frappe.db.values == before
