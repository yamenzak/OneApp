"""Frappe Cloud's records, read live, with no table behind them.

We used to copy press's answers onto rows of our own and a copy of somebody
else's truth has exactly one behaviour: it drifts. A bench upgraded in the
Frappe Cloud dashboard left `Shard.press_version` saying what it used to be, and
nothing anywhere could tell.

These are about the machinery that replaced it — the filtering and paging a
virtual `get_list` has to do for itself, the refusal to write, and the one thing
no table of ours could ever have shown: a site on the account that no workspace
claims.
"""

import pytest


@pytest.fixture
def records(stub_frappe):
	from oneapp_control.press import records as module

	return module


SITES = [
	{"name": "acme.4dl.app", "status": "Active", "group": "canary",
	 "server": "f1", "cluster": "Frankfurt", "plan": "USD 10"},
	{"name": "zeta.4dl.app", "status": "Suspended", "group": "canary",
	 "server": "f1", "cluster": "Frankfurt", "plan": "USD 10"},
	{"name": "ghost.4dl.app", "status": "Active", "group": "wave-1",
	 "server": "f2", "cluster": "Mumbai", "plan": "USD 25"},
]


# --------------------------------------------------------------------------- #
# Standing in for the database
# --------------------------------------------------------------------------- #

def test_a_filter_narrows_the_way_the_desk_expects(records):
	rows = [{"name": "a", "status": "Active"}, {"name": "b", "status": "Broken"}]

	assert records.narrow(rows, [["status", "=", "Active"]]) == [rows[0]]
	assert records.narrow(rows, {"status": "Broken"}) == [rows[1]]
	assert records.narrow(rows, [["status", "!=", "Active"]]) == [rows[1]]
	assert records.narrow(rows, [["status", "in", ["Active", "Broken"]]]) == rows


def test_frappe_may_name_the_doctype_in_front_of_the_field(records):
	"""`get_list` passes [doctype, field, operator, value] once it has resolved
	one, and [field, operator, value] before that. Both are the same filter."""
	rows = [{"name": "a", "status": "Active"}]

	assert records.narrow(rows, [["Press Site", "status", "=", "Active"]]) == rows


def test_an_operator_this_cannot_answer_is_refused_rather_than_ignored(records):
	"""A vocabulary that quietly drops what it does not understand shows the
	wrong rows, which on a console is worse than showing none."""
	with pytest.raises(Exception):
		records.narrow([{"name": "a", "status": "Active"}], [["status", "between", [1, 2]]])


def test_a_page_is_sorted_and_sliced(records):
	rows = [{"name": one} for one in ("c", "a", "b")]

	found = records.page(rows, {"order_by": "name asc", "limit_start": 0,
	                            "limit_page_length": 2})

	assert [row["name"] for row in found] == ["a", "b"]


def test_sorting_descending_is_the_same_question_backwards(records):
	rows = [{"name": one} for one in ("c", "a", "b")]

	found = records.page(rows, {"order_by": "`tabPress Site`.name desc",
	                            "limit_page_length": 0})

	assert [row["name"] for row in found] == ["c", "b", "a"]


def test_the_count_is_of_what_the_filter_left(records):
	rows = [{"name": "a", "status": "Active"}, {"name": "b", "status": "Broken"}]

	assert records.counted(rows, {"filters": [["status", "=", "Active"]]}) == 1
	assert records.counted(rows, {"filters": None}) == 2


# --------------------------------------------------------------------------- #
# The sites, and the orphans among them
# --------------------------------------------------------------------------- #

@pytest.fixture
def sites(records, stub_frappe, monkeypatch):
	monkeypatch.setattr(records, "sites", lambda: list(SITES))
	monkeypatch.setattr(
		records, "tenants_by_site",
		lambda: {"acme.4dl.app": "TEN-0001", "zeta.4dl.app": "TEN-0002"},
	)
	from oneapp_control.control_plane.doctype.press_site import press_site

	return press_site


def test_every_site_press_has_is_a_row(sites):
	assert len(sites._rows()) == 3


def test_a_site_no_workspace_claims_is_an_orphan_with_a_name(sites):
	"""The whole reason this doctype exists. A mirror only ever holds what we
	remembered to put in it, so a site we are being charged for and nobody is
	using cannot appear in one — here it is a row with an empty tenant and a
	filter an operator can save."""
	orphans = [row for row in sites._rows() if not row["tenant"]]

	assert [row["name"] for row in orphans] == ["ghost.4dl.app"]


def test_the_workspace_comes_across_where_there_is_one(sites):
	found = {row["name"]: row["tenant"] for row in sites._rows()}

	assert found["acme.4dl.app"] == "TEN-0001"


def test_a_field_press_stops_sending_reads_as_empty(records, stub_frappe, monkeypatch):
	"""Press's own field names, so a reader comparing this with the Frappe Cloud
	dashboard compares like with like — and a rename there is a quiet column
	rather than an exception on a console screen."""
	monkeypatch.setattr(records, "sites", lambda: [{"name": "acme.4dl.app"}])
	monkeypatch.setattr(records, "tenants_by_site", dict)
	from oneapp_control.control_plane.doctype.press_site import press_site

	row = press_site._rows()[0]

	assert row["name"] == "acme.4dl.app"
	assert row["status"] == "" and row["cluster"] == ""


def test_a_row_press_did_not_name_is_skipped(records, stub_frappe, monkeypatch):
	monkeypatch.setattr(records, "sites", lambda: [{"status": "Active"}])
	monkeypatch.setattr(records, "tenants_by_site", dict)
	from oneapp_control.control_plane.doctype.press_site import press_site

	assert press_site._rows() == []


# --------------------------------------------------------------------------- #
# Nothing here is written
# --------------------------------------------------------------------------- #

def test_press_is_not_edited_through_a_form(records, stub_frappe):
	"""A form that saves and changes nothing is worse than one that refuses.
	Changing a site is an operation with a job behind it."""
	with pytest.raises(Exception):
		records.read_only("Press Site")


@pytest.mark.parametrize("module,cls", [
	("press_site", "PressSite"),
	("press_server", "PressServer"),
	("press_bench_group", "PressBenchGroup"),
])
def test_every_controller_implements_the_virtual_contract(stub_frappe, module, cls):
	"""Frappe checks this itself and answers with a message box on a desk
	nobody here has. The four instance methods must be overridden and the three
	list methods must be static — a missing one is a doctype that reads as
	empty rather than one that errors.
	"""
	import importlib
	import inspect

	loaded = importlib.import_module(
		f"oneapp_control.control_plane.doctype.{module}.{module}"
	)
	controller = getattr(loaded, cls)

	for name in ("get_list", "get_count", "get_stats"):
		assert isinstance(inspect.getattr_static(controller, name), staticmethod), name

	parent = controller.mro()[1]
	for name in ("db_insert", "db_update", "load_from_db", "delete"):
		assert getattr(controller, name) is not getattr(parent, name, None), name
