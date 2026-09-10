"""What the doctype makes of what has been typed, without saving it.

A quotation line is width × height × qty × rate. Frappe computes that twice —
a client script in the browser as you type, the controller's `validate` as the
truth on save — and this product has no client-script layer, so the grid edited
values and derived nothing.

The claim under test is that we did not write a second formula engine. The
values go up, the controller runs over a document built in memory, and what
came back different comes back. Which makes the two things worth pinning: that
nothing is written, and that a document too unfinished to validate is an
ordinary answer rather than an error.
"""

import importlib
import json
import sys
import types

import pytest


SCREEN = {
	"doctype": "Quotation",
	"all_columns": [
		{"fieldname": "party_name", "label": "Customer", "fieldtype": "Link"},
		{"fieldname": "grand_total", "label": "Total", "fieldtype": "Currency"},
		{"fieldname": "items", "label": "Items", "fieldtype": "Table",
		 "editable": 1, "child": {
			 "doctype": "Quotation Item", "editable": True,
			 "fields": [
				 {"fieldname": "qty", "fieldtype": "Float", "editable": 1},
				 {"fieldname": "rate", "fieldtype": "Currency", "editable": 1},
				 {"fieldname": "amount", "fieldtype": "Currency"},
			 ],
		 }},
	],
}


class Doc(dict):
	"""A document that computes its lines when `validate` is run over it."""

	def __init__(self, values=None, throws=False):
		super().__init__(values or {})
		self.throws = throws
		self.ran = []

	def get(self, key, default=None):
		return super().get(key, default)

	def update(self, values):
		super().update(values)

	def run_method(self, name):
		self.ran.append(name)
		if self.throws:
			raise ValueError("Customer is required")
		for at, row in enumerate(self.get("items") or []):
			# Frappe numbers a child table on every run; the browser lines its
			# rows up against that `idx` rather than against the order it sent.
			row["idx"] = at + 1
			row["amount"] = float(row.get("qty") or 0) * float(row.get("rate") or 0)
		self["grand_total"] = sum(r["amount"] for r in self.get("items") or [])


@pytest.fixture
def deriving(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	run = importlib.import_module("oneapp.onespace.spaceview.run")

	held = types.SimpleNamespace(doc=None, saves=[], rollbacks=[])

	monkeypatch.setattr(run, "_resolve", lambda space, screen=None, **k: SCREEN)
	stub_frappe.has_permission = lambda *a, **k: True
	stub_frappe.clear_last_message = lambda: None
	stub_frappe.db.savepoint = lambda point: held.saves.append(point)
	stub_frappe.db.rollback = lambda save_point=None: held.rollbacks.append(save_point)
	stub_frappe.get_doc = lambda *a, **k: held.doc
	stub_frappe.new_doc = lambda doctype: held.doc

	return types.SimpleNamespace(run=run, held=held, frappe=stub_frappe)


def ask(deriving, typed, doc=None, name="Q-1"):
	deriving.held.doc = doc if doc is not None else Doc(dict(typed))
	return deriving.run.derive(space_code="rua", screen="quotations",
	                           values=json.dumps(typed), name=name)


LINES = {
	"party_name": "Halloway",
	"items": [{"qty": 2, "rate": 100, "amount": 100},
	          {"qty": 1, "rate": 50, "amount": 50}],
}


# --------------------------------------------------------------------------- #
# What comes back
# --------------------------------------------------------------------------- #

def test_a_line_that_moved_comes_back(deriving):
	found = ask(deriving, LINES)
	rows = found["children"]["items"]
	assert rows[0]["amount"] == 200 and rows[0]["idx"] == 1
	# The second line's amount was already what the controller makes of it, so
	# it comes back as its `idx` and nothing else — see `test_only_what_moved`.
	assert rows[1] == {"idx": 2}


def test_a_total_the_lines_add_up_to_comes_back(deriving):
	assert ask(deriving, LINES)["values"]["grand_total"] == 250


def test_only_what_moved(deriving):
	"""A form patched whole is a form rewritten under a cursor still in it."""
	found = ask(deriving, LINES)
	assert "party_name" not in found["values"]
	# The second line's amount was already right, so its row carries nothing
	# but the `idx` it is matched on.
	assert found["children"]["items"][1] == {"idx": 2}


def test_a_number_that_only_changed_type_is_not_a_change(deriving):
	"""`100` out of a form, `100.0` out of the controller. Reporting that as a
	change is a form that rewrites itself on every keystroke."""
	settled = {"party_name": "Halloway",
	           "items": [{"qty": 2, "rate": 100, "amount": "200"}]}
	found = ask(deriving, settled)
	assert found["children"].get("items") is None


def test_a_screen_with_no_table_answers_nothing_about_one(deriving, monkeypatch):
	monkeypatch.setattr(deriving.run, "_resolve", lambda *a, **k: {
		"doctype": "ToDo",
		"all_columns": [{"fieldname": "description", "fieldtype": "Data"}],
	})
	assert ask(deriving, {"description": "x"})["children"] == {}


# --------------------------------------------------------------------------- #
# Nothing is written
# --------------------------------------------------------------------------- #

def test_the_savepoint_is_rolled_back_on_the_way_out(deriving):
	"""A controller's `validate` is allowed to touch other rows. Most do not;
	some do; "most" is not a guarantee to build a read-only endpoint on."""
	ask(deriving, LINES)
	assert deriving.held.saves == ["derive"]
	assert deriving.held.rollbacks == ["derive"]


def test_nothing_is_ever_saved(deriving):
	doc = Doc(dict(LINES))
	ask(deriving, LINES, doc=doc)
	assert doc.ran == ["validate"]
	assert not hasattr(doc, "saved")


def test_a_document_too_unfinished_to_validate_is_an_ordinary_answer(deriving):
	"""Half a line is not a line. The reader is still typing and the save is
	where they will be told."""
	found = ask(deriving, LINES, doc=Doc(dict(LINES), throws=True))
	assert found == {"values": {}, "children": {}}
	assert deriving.held.rollbacks == ["derive"]


# --------------------------------------------------------------------------- #
# The bounds
# --------------------------------------------------------------------------- #

def test_a_field_the_screen_cannot_write_never_reaches_the_document(deriving):
	doc = Doc()
	ask(deriving, {"party_name": "Halloway", "docstatus": 1, "owner": "someone"}, doc=doc)
	assert "docstatus" not in doc and "owner" not in doc


def test_more_rows_than_a_line_is_refused(deriving):
	with pytest.raises(Exception, match="more rows"):
		ask(deriving, {"items": [{"qty": 1} for _ in range(run_rows(deriving) + 1)]})


def run_rows(deriving):
	return deriving.run.MAX_DERIVE_ROWS


def test_changing_a_record_needs_permission_to_change_it(deriving):
	deriving.frappe.has_permission = lambda *a, **k: False
	with pytest.raises(Exception):
		ask(deriving, LINES)


def test_a_screen_with_no_records_answers_empty(deriving, monkeypatch):
	monkeypatch.setattr(deriving.run, "_resolve", lambda *a, **k: {})
	assert ask(deriving, LINES) == {"values": {}, "children": {}}
