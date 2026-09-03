"""Retention — the part of an invoice a construction customer keeps.

The arithmetic is one line. Everything worth testing is around it: that an
invoice which does not use retention is left completely alone, that a second
save does not leave two rows, and that the deduction is negative — because a
retention row with a positive rate is an invoice for money nobody owes.

See `oneapp_core/retention.py` for why a subcontractor's books are wrong
without this at all.
"""

import types

import pytest


@pytest.fixture
def retention(stub_frappe):
	from oneapp.oneapp_core import retention as module

	return module


class Row(dict):
	"""A taxes-and-charges row, which is read by attribute and written as a
	dict — which is exactly how Frappe's child rows behave."""

	def __getattr__(self, key):
		return self.get(key)


class Invoice:
	def __init__(self, held=None, has_field=True, taxes=None, company="RUA Contracting"):
		self.company = company
		self.taxes = [Row(one) for one in (taxes or [])]
		self.meta = types.SimpleNamespace(has_field=lambda name: has_field)
		self._values = {"custom_retention_percentage": held}

	def get(self, key, default=None):
		if key == "taxes":
			return self.taxes
		return self._values.get(key, default)

	def set(self, key, value):
		setattr(self, key, value)

	def append(self, key, values):
		row = Row(values)
		getattr(self, key).append(row)
		return row


@pytest.fixture
def books(retention, stub_frappe, monkeypatch):
	"""A company with a chart of accounts, and a note of what got made."""
	made = []
	monkeypatch.setattr(stub_frappe, "get_cached_value",
	                    lambda dt, name, field: {"abbr": "RUA",
	                                             "default_currency": "AED",
	                                             "default_receivable_account":
	                                                 "1310 - Debtors - RUA"}[field])
	monkeypatch.setattr(stub_frappe.db, "get_value",
	                    lambda *a, **k: "1300 - Accounts Receivable - RUA")
	monkeypatch.setattr(stub_frappe, "get_doc",
	                    lambda values: made.append(values) or types.SimpleNamespace(
	                        insert=lambda **k: None))
	return made


def test_an_invoice_with_no_retention_field_is_untouched(retention):
	"""Every workspace that is not a contractor. The field is what turns this
	on, and without it nothing here runs at all."""
	invoice = Invoice(has_field=False, taxes=[{"account_head": "VAT 5% - RUA"}])

	retention.apply(invoice)

	assert [row.account_head for row in invoice.taxes] == ["VAT 5% - RUA"]


def test_zero_retention_adds_nothing(retention, books, stub_frappe, monkeypatch):
	"""Which is every invoice their old system ever issued: the field was there
	for four years and held zero on all sixty-three of them."""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)
	invoice = Invoice(held=0, taxes=[{"account_head": "VAT 5% - RUA"}])

	retention.apply(invoice)

	assert [row.account_head for row in invoice.taxes] == ["VAT 5% - RUA"]
	assert books == []


def test_retention_is_a_negative_charge_against_its_own_account(retention, books,
                                                               stub_frappe, monkeypatch):
	"""The whole mechanism. A charge that takes away, so what lands in Debtors
	is what the customer owes now — and the rest waits somewhere it can still
	be seen."""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)
	invoice = Invoice(held=10, taxes=[{"account_head": "VAT 5% - RUA"}])

	retention.apply(invoice)

	held = invoice.taxes[-1]
	assert held.rate == -10
	assert held.charge_type == "On Net Total"
	assert held.account_head == "Retention Receivable - RUA"
	assert "10%" in held.description
	# And the VAT row is still above it, untouched: the tax is on the whole
	# supply, because retention is when the customer pays and not what they buy.
	assert invoice.taxes[0].account_head == "VAT 5% - RUA"


def test_the_invoice_is_totalled_again_after_the_row_goes_on(retention, books,
                                                            stub_frappe, monkeypatch):
	"""A document hook runs after the controller's own `validate`.

	So the invoice has already been totalled by the time the row exists, and
	without this it sits there with an amount of zero and a grand total that
	still says the customer owes the retention — a wrong invoice that looks
	right, which is what the first run against a real ERPNext produced.
	"""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)
	invoice = Invoice(held=10)
	invoice.totalled = 0
	invoice.calculate_taxes_and_totals = lambda: setattr(
		invoice, "totalled", invoice.totalled + 1)

	retention.apply(invoice)

	assert invoice.totalled == 1


def test_saving_twice_does_not_leave_two_rows(retention, books, stub_frappe, monkeypatch):
	"""`validate` runs on every save, so this is written as "make the row match
	the field" rather than "add a row"."""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)
	invoice = Invoice(held=10)

	retention.apply(invoice)
	retention.apply(invoice)

	assert len(invoice.taxes) == 1


def test_lowering_the_percentage_replaces_the_row(retention, books, stub_frappe,
                                                  monkeypatch):
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)
	invoice = Invoice(held=10)
	retention.apply(invoice)

	invoice._values["custom_retention_percentage"] = 5
	retention.apply(invoice)

	assert [row.rate for row in invoice.taxes] == [-5]


def test_taking_the_retention_off_takes_the_row_off(retention, books, stub_frappe,
                                                    monkeypatch):
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)
	invoice = Invoice(held=10)
	retention.apply(invoice)

	invoice._values["custom_retention_percentage"] = 0
	retention.apply(invoice)

	assert invoice.taxes == []


def test_a_percentage_that_is_not_one_is_refused(retention, books, stub_frappe,
                                                 monkeypatch):
	"""A hundred per cent retention is an invoice for nothing, and a negative
	one is a charge. Both are somebody's typo."""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)

	with pytest.raises(stub_frappe.ValidationError):
		retention.apply(Invoice(held=100))
	with pytest.raises(stub_frappe.ValidationError):
		retention.apply(Invoice(held=-5))


def test_the_account_is_made_once_beside_the_receivables(retention, books, stub_frappe,
                                                         monkeypatch):
	"""Read off the company's own receivable account rather than matched by
	name: "Accounts Receivable" is called four things across the charts ERPNext
	ships, and every company has a default receivable account."""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: False)

	retention.apply(Invoice(held=10))

	assert books == [{
		"doctype": "Account",
		"account_name": "Retention Receivable",
		"parent_account": "1300 - Accounts Receivable - RUA",
		"company": "RUA Contracting",
		"root_type": "Asset",
		"is_group": 0,
		"account_currency": "AED",
	}]
	# Not `Receivable`: ERPNext demands a party on every entry against one of
	# those, and a taxes-and-charges row has none.
	assert "account_type" not in books[0]
