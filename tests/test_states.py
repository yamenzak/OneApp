"""The columns a board is made of, and what each means in ERPNext's words.

`docs/WORK.md` §12. A team names a column — `One Task State` is a row, which
is the whole of "each board has its own columns" — and the engine needs a
category, because "is it finished" has to have an answer without reading the
word somebody chose. What §12 added is that the category writes ERPNext's own
`Task.status`, which their controller, their Gantt and their project rollups
all read.

This file used to be `tests/test_sequence.py` and mostly tested a plan of our
own. That went with `One Task Link`: ERPNext already stores what a task waits
for and already slips a plan forward, so `sequence.py` was deleted rather than
ported. What was worth keeping is below.
"""

import pytest


@pytest.fixture
def states(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onetask"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onetask.states")


def test_a_category_has_a_word_in_erpnexts_vocabulary(states, monkeypatch):
	"""`docs/WORK.md` §12. A team names a column; ERPNext's `Task.status` is
	what their controller, their Gantt and their project rollups read. A task
	in a column called "Signed off" has to be `Completed` over there or the
	project's percent complete is wrong."""
	monkeypatch.setattr(states.frappe.db, "get_value",
	                    lambda doctype, name, field: {
	                        "Signed off": "Done", "Doing": "Started",
	                    }.get(name, "Backlog"))
	assert states.status_of("Signed off") == "Completed"
	assert states.status_of("Doing") == "Working"
	assert states.status_of("Anything else") == "Open"


def test_the_three_statuses_we_never_write_are_theirs(states):
	"""`Overdue` is computed from a date, `Template` marks a task that is not
	work, and `Pending Review` is a word no category means."""
	assert set(states.STATUS_OF.values()) == {"Open", "Working", "Completed", "Cancelled"}
