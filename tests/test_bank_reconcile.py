"""The bank feed, turned into a reconciliation.

`docs/ONEBOOK.md` stage 3. OneBook listed its `Bank Transaction` rows and had
no way to say which document in these books each of them was — which is the
whole of what a bank account is *for* in a set of books, and the thing an
auditor asks about first.

ERPNext's matcher is called rather than copied, so what is ours and what these
check is the four things around it: an allowlist of what a bank line may be
matched against, a date window without which their queries match nothing, a
payload that cannot name a doctype this space does not carry, and the party
side, which is a verb on a payment rather than a fourth screen.

Building this found the fixture banking into a **Cash** account. It posted, it
looked right on every screen, and it could not be reconciled at all: ERPNext
finds a voucher's bank leg with `account_type = "Bank"`, so money in a Cash
account has, as far as a reconciliation is concerned, never touched the bank.
A year of that is invisible until the day somebody tries to tie a statement to
it.
"""

import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onebook/reconcile.py"
SCREEN = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/onebook/Reconcile.vue"
REGISTRY = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
MANIFEST = ROOT / "apps/oneapp_control/oneapp_control/spaces/onebook.py"
HOOKS = ROOT / "apps/oneapp/oneapp/hooks.py"
SEEDER = ROOT / "scripts/seed_erp_spaces.py"
ADAPTER = ROOT / "apps/oneapp/oneapp/adapters/erpnext.py"


@pytest.fixture
def reconcile(stub_frappe):
	from oneapp.onebook import reconcile as module

	return module


def manifest():
	spec = importlib.util.spec_from_file_location("books_manifest", MANIFEST)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


# --------------------------------------------------------------------------- #
# A. What a bank line may be matched against
# --------------------------------------------------------------------------- #

def test_the_document_types_are_ours_and_not_the_requests(reconcile):
	"""ERPNext's tool takes this list from its own dialog's checkboxes, which
	is also how another app's `get_matching_queries` hook joins in. A
	whitelisted endpoint taking it from the request is an endpoint that decides
	what to query from the request."""
	assert set(reconcile.MATCHABLE) == {
		"payment_entry", "journal_entry", "sales_invoice", "purchase_invoice"}
	source = SOURCE.read_text()
	assert "document_types" not in _signatures(source), (
		"no endpoint here takes a document type list from its caller"
	)


def test_every_matchable_type_is_granted_by_the_space():
	"""A match against a doctype this space does not carry would be a write
	nobody in it can see afterwards."""
	granted = {row[0] for row in manifest().DOCTYPES}
	for kind in ("payment_entry", "journal_entry", "sales_invoice",
	             "purchase_invoice"):
		assert kind.replace("_", " ").title() in granted, kind


def test_a_bank_line_is_not_matched_against_another(reconcile):
	"""`bank_transaction` is ERPNext's way of settling an internal transfer
	between two accounts of one company, and this workspace has one bank
	account until somebody says otherwise — `docs/ONEBOOK.md` §5."""
	assert "bank_transaction" not in reconcile.MATCHABLE


# --------------------------------------------------------------------------- #
# B. The window their queries need
# --------------------------------------------------------------------------- #

def test_there_is_always_a_date_range(reconcile):
	"""The measured one. ERPNext's matching queries end in `posting_date
	BETWEEN from AND to`, so passing nothing is `BETWEEN NULL AND NULL`, which
	matches no rows — a screen that silently finds nothing for every line."""
	assert reconcile.LOOK_BACK > 0 and reconcile.LOOK_AHEAD > 0
	source = SOURCE.read_text()
	assert "from_date=since or" in source and "to_date=until or" in source


def test_the_window_is_longer_behind_than_ahead(reconcile):
	"""A payment is entered after the money moves and sometimes long after; one
	entered a year before it moved is somebody's mistake rather than this
	line."""
	assert reconcile.LOOK_BACK > reconcile.LOOK_AHEAD


# --------------------------------------------------------------------------- #
# C. What the payload may say
# --------------------------------------------------------------------------- #

def test_the_allocation_is_not_the_browsers(reconcile):
	"""How much of a line each voucher takes is `allocate_payment_entries`' to
	work out from what the voucher is worth and what it has already been
	allocated elsewhere. A number from the browser would disagree with the
	ledger the first time somebody reconciles one payment twice."""
	source = SOURCE.read_text()
	assert '{"payment_doctype": doctype, "payment_name": name}' in source


def test_matching_checks_the_reader_may_read_what_they_ticked():
	source = SOURCE.read_text()
	assert 'frappe.has_permission(doctype, "read", doc=name, throw=True)' in source


def test_every_verb_asks_for_write_and_every_read_asks_for_read():
	"""Matching sets a clearance date on a voucher and an allocation on the
	transaction; unmatching takes both off. Reading the feed does neither."""
	source = SOURCE.read_text()
	tree = ast.parse(source)
	asked = {}
	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef):
			continue
		for inner in ast.walk(node):
			if (isinstance(inner, ast.Call)
					and getattr(inner.func, "id", "") == "_allowed"):
				asked[node.name] = any(
					kw.arg == "write" for kw in inner.keywords)
	assert asked.get("feed") is False
	assert asked.get("matches") is False
	assert asked.get("match") is True
	assert asked.get("unmatch") is True
	assert asked.get("settle") is True


def test_only_a_submitted_line_is_reconciled():
	"""A draft statement line is a row somebody is still importing, and
	allocating against it would tie a payment to something that may never
	exist."""
	source = SOURCE.read_text()
	assert "if line.docstatus != 1:" in source


def test_a_bank_account_of_a_customers_is_refused():
	"""`Bank Account` holds a payee's details as well as a workspace's own —
	that is what `is_company_account` is for. Reconciling against one of those
	would be reconciling a statement nobody has."""
	source = SOURCE.read_text()
	assert 'not found.get("is_company_account")' in source


# --------------------------------------------------------------------------- #
# D. The party side
# --------------------------------------------------------------------------- #

def test_the_party_side_is_a_verb_and_not_a_screen(reconcile):
	"""`Payment Reconciliation` is three grids of results, a Link to `DocType`
	and three buttons pressed in order against a document that is never saved.
	What a bookkeeper does with it nine times in ten is one sentence, and
	`spaceview/actions.py` is where a sentence about a record lives."""
	declared = reconcile.actions()
	assert set(declared) == {"onebook/payments"}
	verb = declared["onebook/payments"][0]
	assert verb["method"] == "oneapp.onebook.reconcile.settle"
	assert verb["scope"] == "one"
	assert verb["confirm"], "ledger surgery on a submitted document asks first"


def test_the_verb_is_registered_as_a_provider():
	assert '"oneapp.onebook.reconcile.actions"' in HOOKS.read_text()


def test_the_screen_the_verb_sits_on_exists():
	screens = {one["screen"] for one in manifest().SCREENS}
	assert "payments" in screens


def test_only_a_customer_or_a_supplier_is_settled_this_way(reconcile):
	"""ERPNext's tool also takes an Employee and a Shareholder, which are
	advances rather than invoices — an advance is settled by an expense claim,
	which is OnePeople's to approve and this space's to read."""
	assert set(reconcile.SETTLEABLE) == {"Customer", "Supplier"}


def test_the_tool_behind_it_is_granted_and_has_no_screen():
	"""The one grant in this space with no door, deliberately: a doctype whose
	`db_update` is a no-op is a question rather than a record."""
	book = manifest()
	granted = {row[0] for row in book.DOCTYPES}
	assert "Payment Reconciliation" in granted
	named = {one.get("document_type") for one in book.SCREENS}
	assert "Payment Reconciliation" not in named


# --------------------------------------------------------------------------- #
# E. The screen, and the fixture behind it
# --------------------------------------------------------------------------- #

def test_the_screen_is_declared_and_registered():
	book = manifest()
	found = next(one for one in book.SCREENS if one["screen"] == "reconcile")
	assert found["component"] == "onebook/reconcile"
	assert found["document_type"] == "Bank Transaction"
	registry = REGISTRY.read_text()
	assert "'onebook/reconcile':" in registry
	assert SCREEN.exists()


def test_the_seam_is_declared():
	"""Four functions of ERPNext's reached by import, plus the party account
	lookup. `docs/CLEANUP.md` stage 10: a call into somebody else's app that no
	adapter explains is the thing that breaks silently on an upgrade."""
	adapter = ADAPTER.read_text()
	for name in ("get_bank_transactions", "get_account_balance",
	             "get_linked_payments", "reconcile_vouchers",
	             "erpnext.accounts.party.get_party_account"):
		assert name in adapter, name


def test_the_fixture_banks_into_a_bank_account():
	"""The error this stage was built on top of. A Cash account posts and looks
	right everywhere and cannot be reconciled, because ERPNext finds a
	voucher's bank leg with `account_type = "Bank"`."""
	seeder = SEEDER.read_text()
	assert 'def _bank_ledger(' in seeder
	assert '"account_type": "Bank"' in seeder
	assert "_bank_ledger(company)" in seeder


def test_the_statement_mirrors_what_the_books_say():
	"""Two of the five lines carry a payment's own amount and reference, read
	back rather than repeated. A fixture whose best match is no match is a
	screen that looks broken when it is working."""
	seeder = SEEDER.read_text()
	table = _table(seeder, "STATEMENT")
	assert len(table) == 5
	mirrors = _table(seeder, "MIRRORS")
	assert set(mirrors) == {0, 1, 4}, "two exact, and one on the amount alone"
	# The fifth deliberately repeats the first's amount under no reference.
	assert mirrors[4] == 0
	assert table[4][3] == ""


def test_two_lines_deliberately_match_nothing():
	"""A supplier paid by transfer with no payment entry, and a bank charge.
	They are the reason the screen exists — a feed where everything matches is
	a feed nobody needed a screen for."""
	table = _table(SEEDER.read_text(), "STATEMENT")
	unmirrored = [row for at, row in enumerate(table)
	              if at not in _table(SEEDER.read_text(), "MIRRORS")]
	assert len(unmirrored) == 2
	assert all(row[1] is not None for row in unmirrored)


def _table(source: str, name: str):
	return ast.literal_eval(
		next(ast.unparse(node.value) for node in ast.walk(ast.parse(source))
		     if isinstance(node, ast.Assign)
		     and getattr(node.targets[0], "id", "") == name)
	)


def _signatures(source: str) -> str:
	"""Every argument name of every whitelisted function in the module."""
	names = []
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.FunctionDef):
			names += [one.arg for one in node.args.args]
	return " ".join(names)
