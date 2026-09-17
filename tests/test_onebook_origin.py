"""Which space raised a document, and the four ways of getting that wrong.

`oneapp/onebook/origin.py` writes `custom_origin` on save. It is a cache of a
join and every way of breaking it is silent: a stamp that runs before the field
exists throws on every save of a half-built site; a stamp that reads the wrong
child table writes nothing and the column is quietly always blank; a stamp that
writes a word the catalogue does not know gives the Invoices dashboard a slice
nothing else in the product calls by that name.

So this checks the derivation against documents, the declaration against the
manifest, and the vocabulary against `oneapp/catalogue.py`.
"""

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "apps/oneapp_control/oneapp_control/spaces/onebook.py"
HOOKS = ROOT / "apps/oneapp/oneapp/hooks.py"


def declared():
	"""The manifest, loaded off its path — it imports nothing but `json`."""
	spec = importlib.util.spec_from_file_location("onebook_manifest", MANIFEST)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


@pytest.fixture
def origin(stub_frappe):
	from oneapp.onebook import origin as module

	return module


class Meta:
	def __init__(self, wears: bool):
		self.wears = wears

	def has_field(self, name):
		return self.wears


class Doc:
	"""Enough of a Frappe document for a `validate` handler."""

	def __init__(self, doctype, wears=True, **values):
		self.doctype = doctype
		self.meta = Meta(wears)
		self.values = dict(values)

	def get(self, key, default=None):
		return self.values.get(key, default)

	def set(self, key, value):
		self.values[key] = value


# --------------------------------------------------------------------------- #
# A. The derivation
# --------------------------------------------------------------------------- #

def test_an_invoice_against_a_project_is_the_projects(origin):
	doc = Doc("Sales Invoice", project="PROJ-0001")
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "oneproject"


def test_a_project_on_one_line_is_enough(origin):
	"""ERPNext allows the project per row, and an invoice mixing two jobs sets
	it there and not on the header. Reading only the header would call that
	invoice ours."""
	doc = Doc("Sales Invoice", items=[{"item_code": "A"},
	                                  {"project": "PROJ-0002"}])
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "oneproject"


def test_an_ordinary_invoice_is_blank_rather_than_named(origin):
	"""Blank means "raised here", and is deliberately not spelt `onebook` —
	the README says why. A blank cell reads as ours and a filled one as
	theirs."""
	doc = Doc("Sales Invoice", customer="Ada")
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == ""


def test_a_payroll_bank_entry_is_onepeoples(origin):
	"""The shape HRMS writes: a Journal Entry whose account rows reference the
	Payroll Entry — `payroll_entry.make_bank_entry`."""
	doc = Doc("Journal Entry", voucher_type="Bank Entry", accounts=[
		{"account": "Payroll Payable", "reference_type": "Payroll Entry",
		 "reference_name": "HR-PRUN-2026-00001"},
		{"account": "Bank"},
	])
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "onehr"


def test_an_ordinary_journal_entry_is_blank(origin):
	doc = Doc("Journal Entry", voucher_type="Journal Entry",
	          accounts=[{"account": "Bank"}, {"account": "Suspense"}])
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == ""


def test_a_payment_settling_a_claim_is_onepeoples(origin):
	doc = Doc("Payment Entry", references=[
		{"reference_doctype": "Expense Claim", "reference_name": "HR-EXP-0001"},
	])
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "onehr"


def test_a_payment_against_a_project_is_the_projects(origin):
	doc = Doc("Payment Entry", project="PROJ-0001", references=[
		{"reference_doctype": "Sales Invoice", "reference_name": "SI-0001"},
	])
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "oneproject"


def test_people_win_over_projects(origin):
	"""Both can be true — a payment clearing a staff advance can carry the
	project the work was for. The useful answer names the document somebody
	else approved, because that is the one with a person at the end of it."""
	doc = Doc("Payment Entry", project="PROJ-0001", references=[
		{"reference_doctype": "Employee Advance", "reference_name": "HR-ADV-1"},
	])
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "onehr"


def test_a_stamp_rewrites_rather_than_fills(origin):
	"""Set once would mean an invoice whose project was cleared keeps saying it
	belongs to one. What it is derived from is editable until submit."""
	doc = Doc("Sales Invoice", project="PROJ-0001")
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == "oneproject"

	doc.values["project"] = ""
	origin.stamp(doc)
	assert doc.get(origin.FIELD) == ""


def test_a_document_without_the_field_is_left_alone(origin):
	"""Custom fields are applied by the tenant seeder and not by migrate, so
	between installing the app and seeding the space every one of these
	doctypes exists without the column. A handler that assumed otherwise would
	fail every save on a half-built site."""
	doc = Doc("Sales Invoice", wears=False, project="PROJ-0001")
	origin.stamp(doc)
	assert origin.FIELD not in doc.values


# --------------------------------------------------------------------------- #
# B. The vocabulary
# --------------------------------------------------------------------------- #

def test_every_word_it_writes_is_a_space_the_catalogue_knows(origin):
	"""A stamp holding a word nothing else uses gives the Invoices dashboard a
	slice with no space behind it. Read off `catalogue.py` rather than typed,
	so a space that is renamed cannot leave this behind."""
	from oneapp import catalogue

	for word in (origin.PEOPLE, origin.PROJECTS):
		assert word in catalogue.BY_ID, word
		assert catalogue.kind_of(word) == catalogue.SPACE, word


def test_the_doctypes_it_reads_are_ones_hrms_actually_has():
	"""`FROM_PEOPLE` is proof a row came from OnePeople, so a name in it that
	HRMS does not ship is a rule that matches nothing."""
	import upstream

	known = upstream.snapshot()
	source = (ROOT / "apps/oneapp/oneapp/onebook/origin.py").read_text()

	# Three of the six, because only the ones a manifest already names are in
	# the snapshot. The other three — `Employee Advance`, `Gratuity`,
	# `Employee Benefit Claim` — are real HRMS doctypes that no screen of ours
	# shows, so there is nothing checked-in to read them back against.
	for name in ("Payroll Entry", "Salary Slip", "Expense Claim"):
		assert f'"{name}"' in source, name
		assert name in known, f"{name} is not in the upstream snapshot"


# --------------------------------------------------------------------------- #
# C. The declaration, held to the code
# --------------------------------------------------------------------------- #

def test_the_manifest_and_the_module_agree_on_which_documents_wear_it(origin):
	"""Two lists of four in two files. One growing without the other is either
	a field nothing writes or a handler on a doctype with no column."""
	assert tuple(declared().POSTED_INTO) == tuple(origin.POSTED_INTO)


def test_the_field_is_declared_on_exactly_those_four():
	module = declared()
	assert {row["dt"] for row in module.CUSTOM_FIELDS} == set(module.POSTED_INTO)
	assert len(module.CUSTOM_FIELDS) == len(module.POSTED_INTO)


def test_the_field_is_read_only_everywhere():
	"""A provenance somebody can edit is not a provenance."""
	for row in declared().CUSTOM_FIELDS:
		assert row.get("read_only") == 1, row["dt"]


def test_every_one_of_the_four_is_hooked():
	"""A declared column with no handler is a column that is always blank, and
	nothing anywhere says so."""
	body = HOOKS.read_text()
	for name in declared().POSTED_INTO:
		at = body.index(f'\t"{name}": {{')
		block = body[at:body.index("\n\t},", at)]
		assert "oneapp.onebook.origin.stamp" in block, name


def origin_named(screen) -> bool:
	if "custom_origin" in (screen.get("fields") or ""):
		return True
	return "custom_origin" in (screen.get("view_settings") or "")


def test_a_screen_that_shows_the_column_is_one_of_the_four():
	"""The other direction: a screen naming `custom_origin` over a doctype that
	does not wear it draws an empty column, which `_columns` does silently."""
	module = declared()
	for screen in module.SCREENS:
		if origin_named(screen):
			assert screen["document_type"] in module.POSTED_INTO, screen["screen"]


def test_the_reader_found_the_screens():
	"""A reader that matched nothing would turn the rule above into a pass."""
	found = [s["screen"] for s in declared().SCREENS if origin_named(s)]
	assert len(found) >= 4, found


# --------------------------------------------------------------------------- #
# D. And the space itself
# --------------------------------------------------------------------------- #

def test_the_space_code_is_the_one_the_catalogue_uses():
	"""It was `books` against a catalogue row saying `onebook` — the last
	shipped space whose code disagreed with its id, which is the sort of thing
	`docs/CLEANUP.md` stage 3 exists to stop."""
	from oneapp import catalogue

	code = declared().SPACE["space_code"]
	assert code in catalogue.BY_ID
	assert catalogue.kind_of(code) == catalogue.SPACE
	assert declared().SPACE["brand"] == code


def test_the_payroll_screen_reads_and_does_not_write():
	"""A bookkeeper pays the payroll and does not approve it. Both halves: the
	grant is Read, and the screen says so before the click."""
	module = declared()
	rows = [row for row in module.DOCTYPES if row[0] == "Salary Slip"]
	assert rows and all(row[1] == "Read" for row in rows), rows

	screen = next(s for s in module.SCREENS if s["screen"] == "payroll")
	assert screen["document_type"] == "Salary Slip"
	assert screen.get("hide_new") == 1


def test_the_payslip_record_view_is_the_one_onepeople_already_has():
	"""Stage 6's argument landing: a payslip is a payslip whichever rail it was
	opened from, and the alternative was a ninth bespoke page."""
	screen = next(s for s in declared().SCREENS if s["screen"] == "payroll")
	assert json.loads(screen["view_settings"])["record"]["as"] == "payslip"


def test_the_ledger_cannot_be_written_by_hand():
	"""ERPNext has no way to make a `GL Entry` either. The screen says so
	rather than letting somebody find out from a traceback."""
	module = declared()
	rows = [row for row in module.DOCTYPES if row[0] == "GL Entry"]
	assert rows and all(row[1] == "Read" for row in rows), rows

	screen = next(s for s in module.SCREENS if s["screen"] == "ledger")
	assert screen.get("hide_new") == 1
