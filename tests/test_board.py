"""How a board is arranged, as opposed to what it is made of.

`column_field` says the board is columns of `status`; the doctype says what the
statuses are and what colour each is. Neither says that this workspace puts
Blocked last, never wants to see Cancelled, and keeps the two urgent jobs at the
top of Open — and until this there was nowhere to put any of it, so a board
redrew itself in the doctype's order every morning.

Frappe keeps the same four facts on a Kanban Board doctype. Here they are a
*view*, in `view_settings.board.arrangement`, which is why the checking is
bounds rather than validation: everything is keyed by a column's **value** —
`Open`, `HR-EMP-00042` — and there is nothing on the server to check a value
against.
"""

import pytest


@pytest.fixture
def board(stub_frappe):
	from oneapp.onespace import board as module

	return module


@pytest.fixture
def views(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	from oneapp.onespace.spaceview import views as module

	return module


def test_nothing_is_a_shape(board):
	assert board.shape(None) == {}
	assert board.shape("Open,Closed") == {}
	assert board.shape([]) == {}


def test_the_four_answers_are_independent(board):
	"""A colour somebody set and an order they did not are not halves of one
	thing — unlike a showcase, where half a hero is worse than none."""
	assert board.shape({"colours": {"Open": "blue"}}) == {"colours": {"Open": "blue"}}
	assert board.shape({"order": ["Closed", "Open"]}) == {"order": ["Closed", "Open"]}


def test_a_colour_outside_the_badge_set_is_dropped(board):
	"""The nine frappe-ui themes and no others. A value that reaches a class
	name has to come from a closed set or it reaches no CSS at all."""
	found = board.shape({"colours": {"Open": "blue", "Closed": "chartreuse", "Done": 3}})
	assert found["colours"] == {"Open": "blue"}


def test_every_theme_the_browser_draws_is_one_the_server_admits(board):
	"""Read off the component rather than restated: a colour the browser offers
	and the server refuses is one that cannot be chosen, and nothing would say
	why."""
	from pathlib import Path

	source = (
		Path(__file__).resolve().parent.parent
		/ "apps" / "oneapp" / "frontend" / "src" / "components" / "screen" / "bodies"
		/ "BoardBody.vue"
	).read_text()
	block = source[source.index("const INK = {"):]
	block = block[: block.index("}")]
	drawn = {line.split(":")[0].strip() for line in block.splitlines() if ":" in line}

	assert drawn == set(board.THEMES)


def test_a_column_named_twice_is_named_once(board):
	assert board.shape({"order": ["Open", "Open", "Closed"]})["order"] == ["Open", "Closed"]


def test_the_lists_are_bounded(board):
	"""A board with sixty columns is not a board, and the arrangement of it is
	not the reason — but a payload is a payload."""
	found = board.shape({
		"order": [f"c{n}" for n in range(200)],
		"cards": {"Open": [f"T{n}" for n in range(1000)]},
	})
	assert len(found["order"]) == board.COLUMNS
	assert len(found["cards"]["Open"]) == board.CARDS


def test_a_card_order_is_ids_and_nothing_else(board):
	found = board.shape({"cards": {
		"Open": ["TASK-1", "", None, {"name": "TASK-2"}, "x" * 200, "TASK-3"],
		"": ["TASK-9"],
		"Closed": "TASK-4",
	}})
	assert found["cards"] == {"Open": ["TASK-1", "TASK-3"]}


def test_an_arrangement_reaches_the_board_through_the_settings(views, monkeypatch):
	"""`_view_settings` drops any key that is not a fieldname or a fieldname
	list — which is right, and is what silently dropped this the first time.
	`arrangement` is the second exception after a dashboard's widgets."""
	resolved = {
		"all_columns": [
			{"fieldname": "status", "label": "Status", "fieldtype": "Select",
			 "options": "Open\nClosed", "list_ok": True},
		],
	}
	kept = views._view_settings(resolved, {
		"board": {
			"column_field": "status",
			"arrangement": {"order": ["Closed", "Open"], "colours": {"Open": "green"}},
		},
	})
	assert kept["board"]["column_field"] == "status"
	assert kept["board"]["arrangement"] == {
		"order": ["Closed", "Open"], "colours": {"Open": "green"},
	}


def test_an_arrangement_on_anything_but_a_board_is_dropped(views):
	"""It is keyed by column value, and only a board has columns with values."""
	resolved = {"all_columns": [
		{"fieldname": "status", "label": "Status", "fieldtype": "Select", "list_ok": True},
	]}
	kept = views._view_settings(resolved, {
		"calendar": {"arrangement": {"order": ["Open"]}},
	})
	assert "calendar" not in kept


def test_an_arrangement_can_be_cleared(views):
	"""Unarchiving the last hidden column sends an empty list, and a truthiness
	check would leave the saved arrangement standing — so the column would come
	back on screen and be gone again on the next load, with nothing saying why.
	The same rule filters follow: kept whenever the payload mentions it."""
	resolved = {"all_columns": [
		{"fieldname": "status", "label": "Status", "fieldtype": "Select", "list_ok": True},
	]}
	kept = views._view_settings(resolved, {"board": {"arrangement": {"hidden": []}}})
	assert kept["board"]["arrangement"] == {}


def test_an_arrangement_that_is_not_an_arrangement_is_dropped(views):
	resolved = {"all_columns": [
		{"fieldname": "status", "label": "Status", "fieldtype": "Select", "list_ok": True},
	]}
	assert views._view_settings(resolved, {"board": {"arrangement": "hidden"}}) == {}
