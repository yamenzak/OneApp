"""What a migration does on a site that is not the one it was written for.

A patch is written against the site in front of whoever wrote it, which always
has the column the patch is about. The site it then runs on may not: `oneapp`
is installed fresh onto new sites all the time, and a fresh site's tables are
built from the doctype JSON *as it is now* — so a field the patch is migrating
*away from* was never created there at all.

`sources_become_folders` asked for `remote_folder` in a `SELECT` on every site,
and on a fresh one that is `Unknown column 'remote_folder' in 'SELECT'` — which
fails the whole `bench migrate`, not the one move that needed it. The column is
real on an old site, because the doctype sync does not drop columns; it is
absent on a new one for the same reason nothing else about the old shape is
there.
"""

import pytest


@pytest.fixture
def transit(stub_frappe, monkeypatch):
	"""A `Transit Source` table, with or without the column being migrated."""
	asked = {"fields": None}
	state = {"column": True, "rows": []}

	def get_all(doctype, fields=None, filters=None, **kwargs):
		asked["fields"] = list(fields or [])
		rows = []
		for row in state["rows"]:
			rows.append(stub_frappe._dict({
				key: row.get(key) for key in (fields or row.keys())
			}))
		return rows

	monkeypatch.setattr(stub_frappe, "get_all", get_all, raising=False)
	monkeypatch.setattr(stub_frappe.db, "table_exists", lambda name: True, raising=False)
	monkeypatch.setattr(
		stub_frappe.db, "has_column", lambda table, column: state["column"], raising=False,
	)
	monkeypatch.setattr(stub_frappe.db, "commit", lambda: None, raising=False)
	return stub_frappe, state, asked


def _run(frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.patches"):
			del sys.modules[name]
	from oneapp.patches import sources_become_folders

	sources_become_folders.execute()


def test_a_fresh_site_has_no_column_to_read(transit):
	"""And is not a crash. It is a site with nothing to move, which is not the
	same thing as a site that cannot be migrated."""
	frappe, state, asked = transit
	state["column"] = False
	state["rows"] = [{"name": "TS-1", "kind": "Socket", "folder": "", "format": "csv", "status": "Active"}]

	_run(frappe)

	assert "remote_folder" not in asked["fields"], (
		"asked for a column this site never had — which is the whole failure"
	)


def test_the_other_moves_still_happen_without_it(transit):
	"""The column is one of three moves, and the other two are about `kind`.
	Skipping the patch wholesale would leave a `Socket` source on a doctype
	whose `kind` no longer offers one."""
	frappe, state, asked = transit
	state["column"] = False
	state["rows"] = [
		{"name": "TS-1", "kind": "Socket", "folder": "", "format": "csv", "status": "Active"},
		{"name": "TS-2", "kind": "Upload", "folder": "", "format": "", "status": "Active"},
	]

	_run(frappe)

	written = {name: fresh for _dt, name, fresh, _v in frappe.db.writes}
	assert written["TS-1"]["kind"] == "Stream"
	assert written["TS-2"]["kind"] == "Folder"
	assert written["TS-2"]["status"] == "Paused"


def test_an_older_site_still_moves_the_mount(transit):
	"""The case the patch was written for, which has to go on working."""
	frappe, state, asked = transit
	state["column"] = True
	state["rows"] = [{
		"name": "TS-3", "kind": "Folder", "folder": "drop/here",
		"remote_folder": "RF-1", "format": "csv", "status": "Active",
	}]

	_run(frappe)

	assert "remote_folder" in asked["fields"]
	written = {name: fresh for _dt, name, fresh, _v in frappe.db.writes}
	assert written["TS-3"]["folder_type"] == "Remote Folder"
	assert written["TS-3"]["folder"] == "RF-1"
	assert written["TS-3"]["subfolder"] == "drop/here"


# --------------------------------------------------------------------------- #
# The work moves onto ERPNext's, and then the tables go
#
# `docs/WORK.md` §12. Two sites this never runs on and must not throw for:
# one installed fresh from this tree, where `One Task` was never created, and
# one without ERPNext, where there is nowhere to put the rows. Both are real
# — a new tenant is the first and a bench somebody is testing on is the second
# — and a patch that threw on either fails the whole `bench migrate`.
# --------------------------------------------------------------------------- #

@pytest.fixture
def moving(stub_frappe, monkeypatch):
	"""The patch, and a site that can be told what it has."""
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.patches"):
			del sys.modules[name]
	patch = importlib.import_module("oneapp.patches.the_work_becomes_erpnexts")

	state = {"tables": set(), "erpnext": True, "made": []}
	# `setattr` rather than `monkeypatch.setattr`: the stub's database has no
	# `table_exists` to replace, and the whole point of these three tests is
	# what the patch does when the answer is no.
	patch.frappe.db.table_exists = lambda name, cached=True: name in state["tables"]
	monkeypatch.setattr(patch.frappe.db, "exists",
	                    lambda *a, **k: state["erpnext"])
	patch.frappe.db.get_all = lambda *a, **k: state["made"].append(a) or []
	monkeypatch.setattr(patch.frappe.db, "commit", lambda: None)
	return patch, state


def test_a_fresh_site_has_nothing_to_move(moving):
	"""`One Task` was never created there, so the first read would be
	`Table 'tabOne Task' doesn't exist` — which fails the migration rather
	than the one move that needed it."""
	patch, state = moving
	state["tables"] = set()
	patch.execute()
	assert state["made"] == []


def test_a_bench_without_erpnext_is_left_alone(moving):
	"""There is nowhere to put the rows. Leaving them where they are beats
	throwing: they are still readable, and somebody has to look."""
	patch, state = moving
	state["tables"] = {"One Task", "One Project"}
	state["erpnext"] = False
	patch.execute()
	assert state["made"] == []


def test_the_site_it_was_written_for_reads_the_tables(moving):
	patch, state = moving
	state["tables"] = {"One Task", "One Project", "One Task Link"}
	patch.execute()
	assert [one[0] for one in state["made"]][:2] == ["One Project", "One Task"]
