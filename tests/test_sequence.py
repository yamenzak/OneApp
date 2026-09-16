"""The plan: what waits for what, and what moves when something slips.

Three claims, and the third is the one with teeth.

**One direction is stored.** A `One Task Link` row hangs off the task that is
waiting; "blocks" is the same edge read backwards. So the two can never
disagree, and the test for it is that both directions come out of one row.

**A loop is refused before it is saved.** A chart that renders nothing is a bad
way to find out that A waits for B waits for A.

**A plan slips forward and never backwards.** Moving a due date later moves
what waits on it; moving one earlier moves nothing, because finishing early is
not permission to promise somebody else's week.
"""

import types

import pytest


@pytest.fixture
def sequence(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onetask"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onetask.sequence")


def edges(sequence, monkeypatch, rows):
	"""`One Task Link` rows, as `get_all` would answer for them."""
	def get_all(doctype, filters=None, pluck=None, fields=None, **kw):
		filters = filters or {}
		found = [
			row for row in rows
			if all(row.get(key) == value for key, value in filters.items()
			       if key in row or key in ("parent", "task", "kind"))
		]
		if pluck:
			return [row.get(pluck) for row in found]
		return [dict(row) for row in found]

	monkeypatch.setattr(sequence.frappe, "get_all", get_all)


LINE = [
	{"parent": "B", "task": "A", "kind": "Blocked by", "parenttype": "One Task"},
	{"parent": "C", "task": "B", "kind": "Blocked by", "parenttype": "One Task"},
	{"parent": "D", "task": "C", "kind": "Blocked by", "parenttype": "One Task"},
	{"parent": "Z", "task": "A", "kind": "Relates to", "parenttype": "One Task"},
]


# --------------------------------------------------------------------------- #
# One row, both directions
# --------------------------------------------------------------------------- #

def test_one_row_answers_both_directions(sequence, monkeypatch):
	edges(sequence, monkeypatch, LINE)
	assert sequence.predecessors("B") == ["A"]
	assert sequence.dependents("A") == ["B"]


def test_a_pointer_is_not_a_sequence(sequence, monkeypatch):
	"""`Relates to` is something somebody left for somebody. A plan that
	treated it as an edge would push dates around for a note."""
	edges(sequence, monkeypatch, LINE)
	assert "Z" not in sequence.dependents("A")
	assert sequence.related("A") == ["Z"]
	assert sequence.related("Z") == ["A"]


def test_nothing_at_all_is_not_an_error(sequence, monkeypatch):
	edges(sequence, monkeypatch, [])
	assert sequence.predecessors("") == []
	assert sequence.dependents("A") == []
	assert sequence.related("") == []


# --------------------------------------------------------------------------- #
# A loop is refused
# --------------------------------------------------------------------------- #

def test_a_task_cannot_wait_for_itself(sequence, monkeypatch):
	edges(sequence, monkeypatch, [])
	doc = types.SimpleNamespace(
		name="A",
		get=lambda key: [types.SimpleNamespace(kind="Blocked by", task="A")],
	)
	with pytest.raises(Exception):
		sequence.refuse_a_cycle(doc)


def test_a_loop_is_refused_and_the_path_is_named(sequence, monkeypatch):
	"""A → B → C already stored; asking C to wait for A closes it."""
	edges(sequence, monkeypatch, LINE)
	said = []
	monkeypatch.setattr(sequence.frappe, "throw",
	                    lambda message, *a, **k: said.append(message) or (_ for _ in ()).throw(
	                        RuntimeError(message)))
	doc = types.SimpleNamespace(
		name="A",
		get=lambda key: [types.SimpleNamespace(kind="Blocked by", task="D")],
	)
	with pytest.raises(RuntimeError):
		sequence.refuse_a_cycle(doc)
	# Named rather than counted: this is something somebody can go and fix.
	assert "A" in said[0] and "D" in said[0]


def test_an_edge_that_closes_nothing_is_allowed(sequence, monkeypatch):
	edges(sequence, monkeypatch, LINE)
	doc = types.SimpleNamespace(
		name="E",
		get=lambda key: [types.SimpleNamespace(kind="Blocked by", task="D")],
	)
	sequence.refuse_a_cycle(doc)


# --------------------------------------------------------------------------- #
# The slip
# --------------------------------------------------------------------------- #

class Task:
	"""Just enough of a task for `push` to move it."""

	def __init__(self, name, starts_on, due_on, saved):
		self.name = name
		self.starts_on = starts_on
		self.due_on = due_on
		self.flags = types.SimpleNamespace()
		self._saved = saved

	def save(self, **kw):
		self._saved.append((self.name, self.starts_on, self.due_on))


def plan(sequence, monkeypatch, rows, tasks):
	edges(sequence, monkeypatch, rows)
	saved = []
	held = {name: Task(name, *dates, saved) for name, dates in tasks.items()}
	monkeypatch.setattr(sequence.frappe, "get_doc",
	                    lambda doctype, name: held[name])
	return held, saved


def test_a_later_date_moves_what_waits_on_it(sequence, monkeypatch):
	held, saved = plan(sequence, monkeypatch, LINE, {
		"B": ("2026-01-05", "2026-01-09"),
		"C": ("2026-01-12", "2026-01-14"),
		"D": ("2026-01-20", "2026-01-21"),
	})
	moved = sequence.push("A", "2026-01-08")

	# B started on the 5th and A now ends on the 8th, so B starts on the 9th —
	# and keeps its four days, ending on the 13th.
	assert str(held["B"].starts_on) == "2026-01-09"
	assert str(held["B"].due_on) == "2026-01-13"
	# Which pushes C, which was starting on the 12th.
	assert "C" in moved
	assert str(held["C"].starts_on) == "2026-01-14"
	# And not D, which was already starting after C's new end.
	assert "D" not in moved


def test_a_task_that_already_starts_late_enough_is_left_alone(sequence, monkeypatch):
	held, saved = plan(sequence, monkeypatch, LINE, {
		"B": ("2026-02-01", "2026-02-03"),
	})
	assert sequence.push("A", "2026-01-08") == []
	assert saved == []


def test_a_task_nobody_scheduled_is_not_late(sequence, monkeypatch):
	"""No start date is not a start date of today. A task nobody has put in the
	plan is not something the plan may move."""
	held, saved = plan(sequence, monkeypatch, LINE, {"B": (None, None)})
	assert sequence.push("A", "2026-01-08") == []


def test_a_diamond_moves_its_far_end_once(sequence, monkeypatch):
	"""Two tasks waiting on one, both feeding a third."""
	rows = [
		{"parent": "B", "task": "A", "kind": "Blocked by", "parenttype": "One Task"},
		{"parent": "C", "task": "A", "kind": "Blocked by", "parenttype": "One Task"},
		{"parent": "D", "task": "B", "kind": "Blocked by", "parenttype": "One Task"},
		{"parent": "D", "task": "C", "kind": "Blocked by", "parenttype": "One Task"},
	]
	held, saved = plan(sequence, monkeypatch, rows, {
		"B": ("2026-01-05", "2026-01-06"),
		"C": ("2026-01-05", "2026-01-07"),
		"D": ("2026-01-06", "2026-01-08"),
	})
	moved = sequence.push("A", "2026-01-08")
	assert sorted(moved) == ["B", "C", "D"]
	assert [name for name, *_ in saved].count("D") == 1
