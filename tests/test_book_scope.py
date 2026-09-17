"""What OneBook is, and what it is deliberately not.

`docs/ONEBOOK.md` stage 5. The arc's last structural question was the hole in
the middle of the selling chain — a Quotation and a Sales Invoice with nothing
between them — and the list of things that stay out until somebody asks.

The first half is the order. The second half is this file: a paragraph in a
document is a paragraph, and a reason nothing checks is a reason that survives
being wrong. Each family below is absent on purpose, and the day one of them
turns up in the manifest the argument for it has to be written here first.
"""

import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "apps/oneapp_control/oneapp_control/spaces/onebook.py"
CRM = ROOT / "apps/oneapp_control/oneapp_control/spaces/onecrm.py"
SOURCE = ROOT / "apps/oneapp/oneapp/onebook/orders.py"
HOOKS = ROOT / "apps/oneapp/oneapp/hooks.py"
BOOKS = ROOT / "apps/oneapp/oneapp/onespace/books.py"
PLAN = ROOT / "docs/ONEBOOK.md"


def manifest(path: pathlib.Path):
	spec = importlib.util.spec_from_file_location(f"{path.stem}_manifest", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def granted(path: pathlib.Path) -> set[str]:
	return {row[0] for row in manifest(path).DOCTYPES}


@pytest.fixture
def orders(stub_frappe):
	from oneapp.onebook import orders as module

	return module


# --------------------------------------------------------------------------- #
# A. The middle of the chain
# --------------------------------------------------------------------------- #

def test_the_order_is_granted_by_both_spaces_that_touch_it():
	"""Accepting a quote is a selling act and billing one is a books act, and
	the two spaces read the same doctype for different reasons."""
	assert "Sales Order" in granted(MANIFEST)
	assert "Sales Order" in granted(CRM)


def test_the_order_sits_on_the_same_rung_as_the_invoice():
	"""Whoever raises the invoice raises the order it is against. A row with no
	seat named is the User rung — `spaces/roles.py`."""
	rows = {row[0]: row for row in manifest(MANIFEST).DOCTYPES}
	assert len(rows["Sales Order"]) == 3, "no seat named: everybody in the space"
	assert len(rows["Sales Invoice"]) == 3


def test_each_space_has_a_screen_for_it():
	for path in (MANIFEST, CRM):
		named = {one.get("document_type") for one in manifest(path).SCREENS}
		assert "Sales Order" in named, path.name


def test_only_the_books_screen_carries_what_is_left_to_bill():
	"""`per_billed` is a books question. A rep asking it is a rep chasing the
	wrong department, and a column they cannot act on is noise on their list."""
	def fields(path):
		found = next(one for one in manifest(path).SCREENS
		             if one.get("document_type") == "Sales Order")
		return (found.get("fields") or "")

	assert "per_billed" in fields(MANIFEST)
	assert "per_billed" not in fields(CRM)


def test_both_mappers_are_erpnexts(orders):
	"""What carries forward from a quote to an order has twenty answers in it
	and no interesting ones."""
	assert orders.FROM_QUOTATION.startswith("erpnext.selling.doctype.quotation")
	assert orders.FROM_ORDER.startswith("erpnext.selling.doctype.sales_order")


def test_a_conversion_only_ever_makes_a_draft():
	"""Converting is clerical and submitting is a ledger act, and the second is
	a decision somebody makes while looking at the document."""
	tree = ast.parse(SOURCE.read_text())
	calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
	named = {getattr(one.func, "attr", "") for one in calls}
	assert "insert" in named
	assert "submit" not in named, "nothing here posts"
	# Read from the tree rather than grepped, because the module's own
	# docstring promises it does not pass this — the same trap
	# `test_mail_concerns` fell into over `frappe.share`.
	for one in calls:
		assert not any(kw.arg == "ignore_permissions" for kw in one.keywords), (
			"the reader's own permission decides what they may create"
		)


def test_the_verbs_are_registered_and_land_where_they_are_pressed(orders):
	"""`run_action`'s `_next` resolves a screen against the space the action
	was pressed in, so a verb cannot open somebody else's."""
	declared = orders.actions()
	assert set(declared) == {"onebook/orders", "onecrm/quotations"}
	assert '"oneapp.onebook.orders.actions"' in HOOKS.read_text()

	screens = {path.stem: {one["screen"] for one in manifest(path).SCREENS}
	           for path in (MANIFEST, CRM)}
	# Where each verb sends the reader, read out of the module's own constants.
	assert orders.ORDERS in screens["onecrm"], "the quote verb lands in OneCRM"
	assert orders.INVOICES in screens["onebook"]
	assert orders.ORDERS in screens["onebook"]


def test_the_project_rollup_is_live():
	"""ERPNext defers it to a scheduled job by default, which on a workspace
	with a few hundred projects means a margin that is a month stale — and a
	margin nobody trusts is a margin nobody reads."""
	source = BOOKS.read_text()
	assert 'SALES_UPDATE = "Each Transaction"' in source
	assert "roll_up_each_transaction()" in source


# --------------------------------------------------------------------------- #
# B. And what stays out
# --------------------------------------------------------------------------- #

#: Absent on purpose, and why. The doctype is the tripwire; the sentence is the
#: argument, and it is here rather than only in the plan so that adding one
#: means writing its case in the same commit.
#:
#: None of these is a judgement about ERPNext. Each is a judgement about *this*
#: space: a books space that grows a module nobody asked for is a books space
#: that takes twice as long to learn.
OUT = {
	"Asset": "a depreciation schedule is its own product — a life, a method, "
	         "a salvage value and a disposal, none of which the rest of this "
	         "space would ever read",
	"Asset Category": "the shape of a thing this space does not carry, which "
	                  "makes it a table maintained for nobody",
	"Budget": "a control nobody has asked for, and one that is only worth "
	          "having where somebody enforces it",
	"Dunning": "a letter, and OneWriter is where a letter belongs",
	"Exchange Rate Revaluation": "one company and one currency until a "
	                             "customer says otherwise",
	"Accounting Dimension": "a second cost centre with more words",
	"Accounting Dimension Detail": "the child table of the same idea, which "
	                               "cannot be worth more than its parent",
	# The goods half of the chain, which the order deliberately stops short of.
	"Delivery Note": "the order says what was agreed and the invoice says what "
	                 "was billed; what was *delivered* is a stock question, and "
	                 "this space has no stock",
	"Stock Entry": "the same question one level down, and a workspace that "
	               "wanted it would want a warehouse first",
	"Material Request": "the same question before it, and the same answer",
}


def test_nothing_on_the_out_list_is_granted():
	found = granted(MANIFEST) & set(OUT)
	assert not found, (
		"OneBook now grants " + ", ".join(sorted(found)) + ", which "
		+ "`docs/ONEBOOK.md` §5 says stays out. Either the grant is wrong or "
		+ "the argument has changed — and if it has changed, it is the "
		+ "argument that needs editing first, here and in the plan."
	)


def test_every_reason_is_a_reason():
	"""A list of doctype names with no reasons is a list somebody could have
	grepped. `test_adapters` holds the adapters to the same rule."""
	for doctype, why in OUT.items():
		assert len(why.split()) >= 6, f"{doctype} says {why!r}"


def test_the_plan_carries_the_same_list():
	"""So that the reader who finds the tripwire finds the argument, and the
	reader who finds the argument finds the tripwire."""
	plan = PLAN.read_text()
	for doctype in ("Asset", "Budget", "Dunning", "Exchange Rate Revaluation",
	                "Accounting Dimension", "Delivery Note"):
		assert doctype.lower() in plan.lower(), doctype


def test_the_out_list_names_nothing_that_is_not_a_doctype():
	"""A tripwire on a name nothing ships is a tripwire that can never fire.

	Read off the manifests of every space rather than off a running site, so
	this holds without Frappe: a doctype no space grants anywhere *and* that
	ERPNext does not ship would be a typo, and the check that catches the
	second case lives on the dev site — `scripts/check_screens.py`.
	"""
	spelled = {one for one in OUT if one[:1].isupper()}
	assert spelled == set(OUT), "these are doctype names, capitalised as such"


def _table(source: str, name: str):
	return ast.literal_eval(
		next(ast.unparse(node.value) for node in ast.walk(ast.parse(source))
		     if isinstance(node, ast.Assign)
		     and getattr(node.targets[0], "id", "") == name)
	)


def test_the_fixture_has_a_part_billed_order():
	"""The number this stage exists for. An order with one line is either
	nought or a hundred per cent, and neither says anything."""
	seeder = (ROOT / "scripts/seed_erp_spaces.py").read_text()
	order = _table(seeder, "ORDER")
	assert len(order[2]) == 2, "two stages, so `per_billed` is a fraction"
	assert "_ordered(company, made)" in seeder
