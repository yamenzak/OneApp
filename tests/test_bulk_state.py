"""What a selection can be moved through, and what it adds up to.

Three things the list could not do that the desk has always done: submit or
cancel a batch, print one, and read a subtotal under each group of a report.
Each is small; each was the difference between a screen somebody works in and
one they leave for the desk.

The bookkeeping is what these pin. A batch that half-succeeds is the normal
case — a submitted document will not submit again, a mandatory field is empty
on one row of forty — so what matters is that the ones that took it stayed, the
ones that refused were rolled back and named, and the response is not a failure
because one record had something to say.
"""

import types

import pytest


@pytest.fixture
def bulk(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	import importlib

	module = importlib.import_module("oneapp.oneapp_core.spaceview.bulk")
	# `_quietly` puts the response back the way `frappe.throw` found it, and
	# the stub has no request to put back. Real enough to be written into.
	module.frappe.local = types.SimpleNamespace(message_log=[], response={})
	return module


def submittable(monkeypatch, module, is_submittable=1):
	monkeypatch.setattr(
		module.frappe, "get_meta",
		lambda name: types.SimpleNamespace(name=name, is_submittable=is_submittable),
	)


def docs(monkeypatch, module, refuse=()):
	"""`get_doc` handing back a stub per name, and a mover that refuses some."""
	made = {}

	def get_doc(doctype, name):
		made.setdefault(name, types.SimpleNamespace(doctype=doctype, name=name, moved=False))
		return made[name]

	monkeypatch.setattr(module.frappe, "get_doc", get_doc)

	def move(doc):
		if doc.name in refuse:
			module.frappe.throw("Only a draft can be submitted.")
		doc.moved = True

	return made, move


def test_a_docstatus_move_is_not_a_save(bulk):
	"""`_each` saves, and a `save()` after a `submit()` is a second write that
	Frappe refuses on the document that has just become submitted. So the two
	share their bookkeeping and not their body."""
	import inspect

	body = inspect.getsource(bulk._stated)
	assert "doc.save()" not in body
	assert "savepoint" in body


def test_every_record_that_took_it_is_named(bulk, monkeypatch):
	submittable(monkeypatch, bulk)
	_made, move = docs(monkeypatch, bulk)

	found = bulk._stated({"doctype": "Sales Invoice"}, ["A", "B", "C"], move)

	assert found == {"ok": True, "done": ["A", "B", "C"], "refused": []}


def test_one_refusal_is_a_fact_about_one_record(bulk, monkeypatch):
	"""Not a failed request. Forty purchase orders where one is already
	submitted is thirty-nine that went through, and a batch that came back as
	one opaque error is the swallowing this exists to prevent."""
	submittable(monkeypatch, bulk)
	made, move = docs(monkeypatch, bulk, refuse={"B"})

	found = bulk._stated({"doctype": "Sales Invoice"}, ["A", "B", "C"], move)

	assert found["done"] == ["A", "C"]
	assert found["refused"] == [{"name": "B", "reason": "Only a draft can be submitted."}]
	assert found["ok"] is False
	assert made["A"].moved and made["C"].moved


def test_a_refusal_is_rolled_back_to_its_own_mark(bulk, monkeypatch):
	"""The request commits at the end whatever happened, so a record that
	raised halfway through would otherwise leave half of itself behind in the
	same transaction as the ones that succeeded."""
	submittable(monkeypatch, bulk)
	docs(monkeypatch, bulk, refuse={"B"})

	_made, move = docs(monkeypatch, bulk, refuse={"B"})
	bulk._stated({"doctype": "Sales Invoice"}, ["A", "B"], move)

	assert bulk.frappe.db.rollbacks == ["oneapp_bulk"]


def test_a_doctype_with_no_docstatus_is_refused_outright(bulk, monkeypatch):
	"""Rather than per record: it is a fact about the screen, and forty
	identical refusals is a worse way of saying it."""
	submittable(monkeypatch, bulk, is_submittable=0)

	with pytest.raises(Exception) as raised:
		bulk._stated({"doctype": "Note"}, ["A"], lambda doc: None)

	assert "Note" in str(raised.value)


def test_the_two_endpoints_resolve_the_screen_themselves(bulk):
	"""`test_every_endpoint_establishes_which_space_it_is_in` reads the calls a
	whitelisted function makes directly and does not follow helpers — which is
	the right side to be strict on, and is why `_stated` takes a resolved
	screen rather than resolving one."""
	import inspect

	for endpoint in (bulk.bulk_submit, bulk.bulk_cancel):
		assert "_resolve(space_code, screen)" in inspect.getsource(endpoint)


# --------------------------------------------------------------------------- #
# Printing a selection
# --------------------------------------------------------------------------- #

def test_a_bundle_is_bounded(stub_frappe):
	"""A PDF is built inside the request and every record in it is a full
	render. Fifty invoices is a few seconds; two hundred is a request that
	times out and leaves nobody with anything."""
	from oneapp.oneapp_core import printing

	assert printing.MAX_BUNDLE == 50


def test_a_bundle_asks_per_record(stub_frappe):
	"""A selection is a list of ids, and the reader may have been shown some of
	them and not others — so the print permission is checked per document
	rather than once for the doctype."""
	import inspect

	from oneapp.oneapp_core import printing

	body = inspect.getsource(printing.bundle)
	# Once as a call, per record, inside the loop — the import above it is the
	# other occurrence of the name.
	assert body.count("validate_print_permission(document)") == 1
	assert "for at, name in enumerate" in body
	# One page break per record after the first, on a block: wkhtmltopdf and
	# Chrome disagree about almost everything else and both honour this.
	assert "page-break-before" in body


# --------------------------------------------------------------------------- #
# What a group adds up to
# --------------------------------------------------------------------------- #

@pytest.fixture
def records(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	module = importlib.import_module("oneapp.oneapp_core.spaceview.records")
	module.frappe.get_list = lambda *a, **k: []
	return module


def test_nothing_is_grouped_by_default(records):
	assert records._group_totals({"doctype": "Sales Invoice"}, ["amount"], []) == {}


def test_a_subtotal_per_group_comes_back_keyed_by_value(records, monkeypatch):
	asked = {}

	def get_list(doctype, **kw):
		asked.update(kw)
		return [
			{"customer": "Halloway", "amount": 88_000},
			{"customer": "Al-Ittihad", "amount": 412_500},
			# A row with no value in the group column is still a group: those
			# records exist and their money is real.
			{"customer": None, "amount": 1_200},
		]

	monkeypatch.setattr(records.frappe, "get_list", get_list)

	found = records._group_totals(
		{"doctype": "Sales Invoice", "group_by": "customer"}, ["amount"], [["docstatus", "=", 1]],
	)

	assert found == {
		"Halloway": {"amount": 88_000.0},
		"Al-Ittihad": {"amount": 412_500.0},
		"": {"amount": 1_200.0},
	}
	# The same filters the rows and the total went through, not a second
	# opinion about which rows count.
	assert asked["filters"] == [["docstatus", "=", 1]]
	assert asked["group_by"] == "customer"
	assert asked["limit_page_length"] == records.GROUP_TOTALS
