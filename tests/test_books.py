"""Our own revenue, in our own books — including the cash.

A Sales Invoice says what somebody owes. Every invoice we raise is already
paid, so a book of nothing but invoices shows every customer permanently
outstanding and gives a Stripe payout nothing to land against. What was missing
was the other half: a Payment Entry per invoice, into a clearing account that
stands for the Stripe balance.

The fee is the reason that account reconciles. Stripe pays out the net of a
batch of charges, so booking the gross leaves the clearing balance and the
payout differing by exactly the fees — and the fee is not on the invoice or on
the charge, it is on the charge's balance transaction.
"""

import pytest


@pytest.fixture
def books(stub_frappe):
	from oneapp_control.billing import books as module

	return module


class FakeDoc:
	"""Enough of a Frappe document to be inserted, appended to and submitted."""

	def __init__(self, values):
		self.__dict__.update(values)
		self.name = values.get("name") or "PE-0001"
		self.submitted = False

	def append(self, field, row):
		self.__dict__.setdefault(field, []).append(row)
		return row

	def insert(self, **kwargs):
		return self

	def submit(self):
		self.submitted = True

	def get(self, field, default=None):
		return getattr(self, field, default)


@pytest.fixture
def made(books, stub_frappe):
	"""Every document the module makes, in order."""
	docs = []

	def get_doc(*args, **kwargs):
		values = args[0] if args and isinstance(args[0], dict) else {}
		doc = FakeDoc(values)
		docs.append(doc)
		return doc

	stub_frappe.get_doc = get_doc
	return docs


@pytest.fixture
def accounts(books, stub_frappe):
	"""Both accounts named, which is the configured case."""
	settings = stub_frappe._dict({
		"stripe_clearing_account": "Stripe - OS",
		"stripe_fee_account": "Payment Fees - OS",
		"books_company": "OneSpace",
	})
	stub_frappe.get_single = lambda *a, **k: settings
	return settings


@pytest.fixture
def invoice(stub_frappe):
	"""A submitted, unpaid Sales Invoice of a hundred dollars."""
	stub_frappe.db.values[(
		"Sales Invoice",
		("customer", "company", "currency", "outstanding_amount", "docstatus"),
	)] = stub_frappe._dict({
		"customer": "Acme", "company": "OneSpace", "currency": "USD",
		"outstanding_amount": 100.0, "docstatus": 1,
	})
	stub_frappe.db.values[("Company", "default_currency")] = "USD"
	stub_frappe.db.values[("Company", "cost_center")] = "Main - OS"


@pytest.fixture
def stripe(books, monkeypatch):
	"""Stripe, answering with a charge whose fee is $3.20."""
	monkeypatch.setattr(books.stripe_client, "get_charge", lambda charge_id: {
		"id": charge_id,
		"balance_transaction": {"currency": "usd", "fee": 320},
	})
	monkeypatch.setattr(books.stripe_client, "get_payment_intent", lambda intent: {
		"id": intent, "latest_charge": "ch_from_intent",
	})


PAID = {"id": "in_123", "charge": "ch_123"}


# --------------------------------------------------------------------------- #
# The entry itself
# --------------------------------------------------------------------------- #

def test_an_invoice_is_paid_off_the_moment_it_is_raised(
	books, accounts, invoice, stripe, made
):
	books.settle("SI-0001", PAID)

	entry = made[0]
	assert entry.doctype == "Payment Entry"
	assert entry.payment_type == "Receive"
	assert entry.party == "Acme"
	assert entry.references[0]["reference_name"] == "SI-0001"
	assert entry.submitted


def test_the_customer_pays_the_gross_and_the_account_receives_the_net(
	books, accounts, invoice, stripe, made
):
	"""The three numbers ERPNext insists agree, and the whole point of the
	exercise: the clearing account holds what the payout will be worth."""
	books.settle("SI-0001", PAID)

	entry = made[0]
	assert entry.references[0]["allocated_amount"] == 100.0
	assert entry.paid_amount == pytest.approx(96.80)
	assert entry.received_amount == pytest.approx(96.80)
	assert entry.deductions[0]["amount"] == pytest.approx(3.20)
	assert entry.deductions[0]["account"] == "Payment Fees - OS"


def test_the_stripe_id_is_the_reference_somebody_searches_on(
	books, accounts, invoice, stripe, made
):
	books.settle("SI-0001", PAID)

	assert made[0].reference_no == "in_123"


def test_the_clearing_account_is_the_one_named(books, accounts, invoice, stripe, made):
	books.settle("SI-0001", PAID)

	assert made[0].paid_to == "Stripe - OS"
	# `paid_from` is the customer's receivable account, which ERPNext fills in
	# from the party. Naming it here would be guessing at a chart of accounts.
	assert made[0].get("paid_from") is None


# --------------------------------------------------------------------------- #
# When nothing should be posted
# --------------------------------------------------------------------------- #

def test_no_account_means_no_entry_rather_than_a_guessed_one(
	books, stub_frappe, invoice, stripe, made
):
	"""A wrong entry in a submitted ledger is far more work to undo than one
	that was never made. The console's readiness list is what says so."""
	stub_frappe.get_single = lambda *a, **k: stub_frappe._dict({})

	assert books.settle("SI-0001", PAID) is None
	assert made == []


def test_a_second_delivery_of_the_same_event_pays_nothing_twice(
	books, accounts, stub_frappe, stripe, made
):
	"""Stripe delivers `invoice.paid` more than once. An invoice with nothing
	outstanding has already been settled — no marker of our own needed."""
	stub_frappe.db.values[(
		"Sales Invoice",
		("customer", "company", "currency", "outstanding_amount", "docstatus"),
	)] = stub_frappe._dict({
		"customer": "Acme", "company": "OneSpace", "currency": "USD",
		"outstanding_amount": 0.0, "docstatus": 1,
	})

	assert books.settle("SI-0001", PAID) is None
	assert made == []


def test_a_draft_or_cancelled_invoice_is_left_alone(
	books, accounts, stub_frappe, stripe, made
):
	stub_frappe.db.values[(
		"Sales Invoice",
		("customer", "company", "currency", "outstanding_amount", "docstatus"),
	)] = stub_frappe._dict({
		"customer": "Acme", "company": "OneSpace", "currency": "USD",
		"outstanding_amount": 100.0, "docstatus": 2,
	})

	assert books.settle("SI-0001", PAID) is None
	assert made == []


def test_stripe_being_unreachable_does_not_stop_the_settlement(
	books, accounts, invoice, monkeypatch, made
):
	"""The fee is a nicety; the invoice being paid is not. Booking the gross
	leaves the clearing account drifting by the fees, which is a visible number
	an operator can chase — an unpaid invoice is not."""
	def refuse(charge_id):
		raise RuntimeError("stripe is having a day")

	monkeypatch.setattr(books.stripe_client, "get_charge", refuse)

	books.settle("SI-0001", PAID)

	assert made[0].paid_amount == 100.0
	assert made[0].get("deductions") is None


# --------------------------------------------------------------------------- #
# The fee, and every reason it is not booked
# --------------------------------------------------------------------------- #

def test_a_fee_in_another_settlement_currency_is_not_converted(
	books, accounts, invoice, monkeypatch, made
):
	"""Stripe denominates the fee in the *account's* settlement currency, not
	the charge's. Booking 320 of those as dollars would be inventing a rate."""
	monkeypatch.setattr(books.stripe_client, "get_charge", lambda charge_id: {
		"balance_transaction": {"currency": "eur", "fee": 320},
	})

	books.settle("SI-0001", PAID)

	assert made[0].paid_amount == 100.0


def test_a_fee_at_or_above_the_sale_is_not_a_fee(
	books, accounts, invoice, monkeypatch, made
):
	monkeypatch.setattr(books.stripe_client, "get_charge", lambda charge_id: {
		"balance_transaction": {"currency": "usd", "fee": 20000},
	})

	books.settle("SI-0001", PAID)

	assert made[0].paid_amount == 100.0


def test_a_sale_in_another_currency_books_the_gross(
	books, accounts, stub_frappe, stripe, made
):
	"""A deduction posts in the company's currency. Where the sale was not in
	it, the fee would have to be converted at a rate nobody chose."""
	stub_frappe.db.values[(
		"Sales Invoice",
		("customer", "company", "currency", "outstanding_amount", "docstatus"),
	)] = stub_frappe._dict({
		"customer": "Acme", "company": "OneSpace", "currency": "EUR",
		"outstanding_amount": 100.0, "docstatus": 1,
	})
	stub_frappe.db.values[("Company", "default_currency")] = "USD"

	books.settle("SI-0001", PAID)

	assert made[0].paid_amount == 100.0


def test_no_fee_account_means_the_gross(books, stub_frappe, invoice, stripe, made):
	stub_frappe.get_single = lambda *a, **k: stub_frappe._dict({
		"stripe_clearing_account": "Stripe - OS",
	})

	books.settle("SI-0001", PAID)

	assert made[0].paid_amount == 100.0


# --------------------------------------------------------------------------- #
# Finding the charge
# --------------------------------------------------------------------------- #

def test_a_checkout_session_names_an_intent_and_the_intent_names_the_charge(
	books, accounts, invoice, stripe, made
):
	"""A credit pack arrives as `checkout.session.completed`, which carries a
	payment intent rather than a charge."""
	books.settle("SI-0001", {"id": "cs_1", "payment_intent": "pi_1"})

	assert made[0].deductions[0]["amount"] == pytest.approx(3.20)


def test_an_expanded_object_is_read_as_an_id(books, accounts, invoice, stripe, made):
	"""Stripe sends a related object bare or expanded depending on the event
	and the API version. Both are an id."""
	books.settle("SI-0001", {"id": "in_1", "charge": {"id": "ch_9"}})

	assert made[0].deductions[0]["amount"] == pytest.approx(3.20)


def test_the_older_name_for_the_charge_still_works(
	books, accounts, invoice, stripe, made
):
	"""`charge` became `latest_charge` across API versions, and an account
	pinned to an older one still sends the first."""
	books.settle("SI-0001", {"id": "in_1", "latest_charge": "ch_9"})

	assert made[0].deductions[0]["amount"] == pytest.approx(3.20)


def test_a_payment_with_no_charge_anywhere_books_the_gross(
	books, accounts, invoice, stripe, made
):
	books.settle("SI-0001", {"id": "in_1"})

	assert made[0].paid_amount == 100.0


# --------------------------------------------------------------------------- #
# The invoice half calls it, and a redelivery retries it
# --------------------------------------------------------------------------- #

def test_raising_an_invoice_settles_it(books, monkeypatch):
	import inspect

	assert "settle(invoice.name" in inspect.getsource(books.record_invoice)
	assert "settle(invoice.name" in inspect.getsource(books._record_one_off)


def test_a_redelivered_event_retries_a_settlement_that_failed(
	books, stub_frappe, monkeypatch
):
	"""The way to end up with an unpaid invoice here is the invoice landing and
	the Payment Entry failing — and `_safe` makes that failure quiet. So the
	duplicate delivery, which used to return early, tries the cash again."""
	stub_frappe.db.values[("Sales Invoice", "name")] = "SI-0001"
	tried = []
	monkeypatch.setattr(books, "settle", lambda name, paid: tried.append(name))

	books.record_invoice(stub_frappe._dict({"tenant": "acme"}), PAID)

	assert tried == ["SI-0001"]


def test_a_settlement_that_throws_does_not_lose_the_invoice(
	books, accounts, invoice, stub_frappe, monkeypatch
):
	"""`settle` is `@_safe` in its own right, so a broken chart of accounts
	costs the cash entry and not the record of the sale."""
	def refuse(*a, **k):
		raise RuntimeError("no such account")

	stub_frappe.get_doc = refuse

	assert books.settle("SI-0001", PAID) is None


# --------------------------------------------------------------------------- #
# The key that let the payments app go
# --------------------------------------------------------------------------- #

def test_our_own_settings_hold_the_stripe_key(stub_frappe):
	"""The payments app was carried on the control bench for one Password
	field, and none of what it exists for — Payment Requests, gateway portals,
	redirect flows — is how anything here charges."""
	from oneapp_control.billing import stripe_client

	settings = stub_frappe._dict({})
	settings.get_password = lambda field, raise_exception=False: (
		"sk_test_ours" if field == "stripe_secret_key" else None
	)
	stub_frappe.get_single = lambda *a, **k: settings

	assert stripe_client.secret_key() == "sk_test_ours"


def test_an_existing_stripe_settings_still_wins_over_nothing(stub_frappe):
	"""So a deployment that has the key in the old place keeps working until
	somebody moves it, rather than failing every charge on deploy."""
	from oneapp_control.billing import stripe_client

	settings = stub_frappe._dict({})
	settings.get_password = lambda field, raise_exception=False: None
	stub_frappe.get_single = lambda *a, **k: settings
	stub_frappe.db.records[("DocType", "Stripe Settings")] = 1
	stub_frappe.db.values[("Stripe Settings", "name")] = "Stripe"

	old = stub_frappe._dict({})
	old.get_password = lambda field, raise_exception=False: "sk_test_old"
	stub_frappe.get_doc = lambda *a, **k: old

	assert stripe_client.secret_key() == "sk_test_old"


def test_no_key_anywhere_says_where_to_put_one(stub_frappe):
	from oneapp_control.billing import stripe_client

	settings = stub_frappe._dict({})
	settings.get_password = lambda field, raise_exception=False: None
	stub_frappe.get_single = lambda *a, **k: settings

	with pytest.raises(stripe_client.StripeError) as caught:
		stripe_client.secret_key()

	assert "Billing" in str(caught.value)


def test_a_control_site_without_erpnext_yet_does_not_raise(books, stub_frappe):
	"""Bring-up order reaches here: the control app installs, the readiness
	list is answered, and the books arrive after. Asking `tabCompany` a
	question before it exists took the screen asking it down."""
	stub_frappe.get_single = lambda *a, **k: stub_frappe._dict({})

	assert books._company() is None


def test_the_console_says_when_cash_is_not_being_booked(stub_frappe):
	"""The one visible consequence of leaving the account blank. Without this
	row nothing anywhere says why every customer reads as outstanding."""
	from oneapp_control.api import setup

	assert '"key": "books_clearing"' in __import__("inspect").getsource(setup)
