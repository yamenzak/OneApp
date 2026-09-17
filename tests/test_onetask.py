"""OneTask, which is a door rather than a space.

`docs/WORK.md` §12. Three claims, and the first is the one everything else
hangs off.

**It owns no table.** Every row is an ERPNext `Task` and every verb is
something a person could have done by going to OneProject — so the test for
the service is that it writes *their* doctype and nothing of ours.

**Capture costs one line.** A task with no project is the inbox, because
ERPNext's Task has an optional project; nothing here is a staging table.

**A tick writes the state, not the status.** `custom_state` is the column a
team named and `status` is derived from its category — writing the derived
half is how a tick survives until the next save and then undoes itself.
"""

import pytest


@pytest.fixture
def service(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onetask"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onetask.service")


class Doc:
	"""Just enough of a Task for the service to make one and tick one."""

	def __init__(self, values, made):
		self.__dict__.update(values)
		self.name = values.get("name") or "TASK-0001"
		self.status = values.get("status", "Open")
		self._made = made

	def insert(self):
		self._made.append(self)
		return self

	def save(self):
		self._made.append(self)
		return self

	def check_permission(self, what):
		return True


def site(service, monkeypatch, rows=(), states=()):
	"""A site with these tasks on it and these columns declared."""
	made = []

	def get_all(doctype, filters=None, fields=None, pluck=None, order_by=None,
	            as_list=False, **kw):
		if doctype == "One Task State":
			wanted = (filters or {}).get("category", ["in", ()])[1]
			return [one["name"] for one in states if one["category"] in wanted]
		if doctype == "Project":
			return [(one["name"], one["project_name"]) for one in
			        ({"name": "PROJ-1", "project_name": "zzHarbour Point"},)]
		filters = filters or {}
		found = list(rows)
		if "_assign" in filters:
			found = [one for one in found if one.get("mine")]
		if "project" in filters:
			found = [one for one in found if not one.get("project")]
		# A `_dict`, as `get_all` answers: the service reads `.project` off a
		# row and a plain dict would only look right.
		return [service.frappe._dict(
			{key: value for key, value in one.items() if key != "mine"})
			for one in found]

	monkeypatch.setattr(service.frappe, "get_all", get_all)
	monkeypatch.setattr(service.frappe, "has_permission", lambda *a, **k: True)
	monkeypatch.setattr(service.frappe, "get_doc",
	                    lambda values, *rest: Doc(values, made)
	                    if isinstance(values, dict)
	                    else Doc({"name": rest[0] if rest else values}, made))
	monkeypatch.setattr(service.frappe.db, "exists", lambda *a, **k: True)
	monkeypatch.setattr(service.frappe.session, "user", "somebody@example.com")
	monkeypatch.setattr(service.timing, "running", lambda: {})
	return made


COLUMNS = (
	{"name": "Backlog", "category": "Backlog"},
	{"name": "In progress", "category": "Started"},
	{"name": "Done", "category": "Done"},
)

MINE = {"name": "TASK-1", "subject": "zzChase the quote", "project": "PROJ-1",
        "custom_state": "Backlog", "priority": "Medium", "exp_end_date": None,
        "status": "Open", "mine": True}
LOOSE = {"name": "TASK-2", "subject": "zzRing the landlord", "project": None,
         "custom_state": "Backlog", "priority": "Low", "exp_end_date": None,
         "status": "Open"}


def test_the_two_lists_are_mine_and_what_nobody_placed(service, monkeypatch):
	site(service, monkeypatch, rows=(MINE, LOOSE), states=COLUMNS)
	found = service.now()
	assert [one["name"] for one in found["mine"]] == ["TASK-1"]
	assert [one["name"] for one in found["inbox"]] == ["TASK-2"]


def test_a_row_says_the_project_s_name_rather_than_its_id(service, monkeypatch):
	"""`PROJ-0003` beside a task is the database's answer to a question nobody
	asked."""
	site(service, monkeypatch, rows=(MINE,), states=COLUMNS)
	assert service.now()["mine"][0]["project_name"] == "zzHarbour Point"


def test_capture_writes_their_task_and_places_it_nowhere(service, monkeypatch):
	made = site(service, monkeypatch, states=COLUMNS)
	monkeypatch.setitem(
		__import__("sys").modules,
		"frappe.desk.form",
		type("m", (), {"assign_to": type("a", (), {"add": staticmethod(lambda *a, **k: None)})})(),
	)
	service.capture("  zzBook the van service  ")
	assert len(made) == 1
	# Theirs, and unplaced — which on ERPNext's Task is free.
	assert made[0].doctype == "Task"
	assert made[0].subject == "zzBook the van service"
	assert not getattr(made[0], "project", None)
	# And it lands in the first column that is not finished.
	assert made[0].custom_state == "Backlog"


def test_a_blank_line_is_refused(service, monkeypatch):
	site(service, monkeypatch, states=COLUMNS)
	with pytest.raises(Exception):
		service.capture("   ")


def test_a_tick_writes_the_state_and_never_the_status(service, monkeypatch):
	"""`status` is derived from the state's category — `onetask/task.py` — so
	writing it here would be writing the half the next save recomputes."""
	made = site(service, monkeypatch, states=COLUMNS)
	service.tick("TASK-1", 1)
	assert made[0].custom_state == "Done"
	assert made[0].status == "Open"


def test_untick_puts_it_back_at_the_start(service, monkeypatch):
	made = site(service, monkeypatch, states=COLUMNS)
	service.tick("TASK-1", 0)
	assert made[0].custom_state == "Backlog"


def test_a_workspace_with_no_columns_does_not_throw(service, monkeypatch):
	"""A state is a row a workspace can rename or delete, so "there is no Done
	column" is a real state of the world and not a bug to crash on."""
	made = site(service, monkeypatch, states=())
	service.tick("TASK-1", 1)
	assert made[0].custom_state == ""
