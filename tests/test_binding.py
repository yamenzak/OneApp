"""A document and a workbook written about a record.

A quotation's covering letter is prose with the quotation's numbers in it, and
an estimator's workbook is arithmetic over the job's. Typed out, both are a
second copy that goes stale, and the person who finds out is the customer.

Two claims are worth pinning here and neither is about rendering.

The first is the boundary. A token in a document and a `RECORD()` in a cell
are both strings a person typed, so the endpoint behind them is one that takes
a doctype and a fieldname from a browser. Without `offer` narrowing it, that
is a whitelisted read of any column of any table on the site — permlevel,
password fields and all.

The second is that freezing is total. A document that has been sent must not
change afterwards, and it is stored twice — the HTML search and export read,
the JSON the editor loads. Freezing one and not the other means the token
comes back the moment somebody opens it.
"""

import importlib
import json
import sys
import types

import pytest


@pytest.fixture
def stubbed(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]

	# `format_value` is the framework's own formatter, and is why a bound
	# document and a printed one agree about what a currency looks like.
	stub_frappe.format_value = lambda value, column=None, doc=None: (
		f"AED {value:,.2f}" if (column or {}).get("fieldtype") == "Currency"
		and isinstance(value, (int, float)) else str("" if value is None else value)
	)
	stub_frappe.clear_last_message = lambda: None
	return stub_frappe


def meta(fields, permissions=(("System Manager", 0),)):
	return types.SimpleNamespace(
		fields=[types.SimpleNamespace(**one) for one in fields],
		permissions=[
			types.SimpleNamespace(read=1, role=role, permlevel=level)
			for role, level in permissions
		],
	)


QUOTATION = [
	{"fieldname": "party_name", "label": "Customer", "fieldtype": "Data", "permlevel": 0},
	{"fieldname": "grand_total", "label": "Total", "fieldtype": "Currency", "permlevel": 0},
	{"fieldname": "margin", "label": "Margin", "fieldtype": "Percent", "permlevel": 1},
	{"fieldname": "api_secret", "label": "Secret", "fieldtype": "Password", "permlevel": 0},
	{"fieldname": "items", "label": "Items", "fieldtype": "Table", "permlevel": 0},
	{"fieldname": "sb_one", "label": None, "fieldtype": "Section Break", "permlevel": 0},
]


@pytest.fixture
def binding(stubbed):
	mod = importlib.import_module("oneapp.shared.binding")
	stubbed._meta = {"Quotation": meta(QUOTATION)}
	stubbed.get_roles = lambda *a: ["System Manager"]
	stubbed.db.exists = lambda doctype, name=None: True
	stubbed.has_permission = lambda *a, **k: True
	return mod


# --------------------------------------------------------------------------- #
# What is bound to what
# --------------------------------------------------------------------------- #

def test_a_document_about_a_record_is_a_document_attached_to_it(binding, stubbed):
	"""One concept, not two. `File` already carries the attachment and the
	record's Attachments panel is where somebody looks for the letter."""
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            binding.BOUND_FIELD))] = {
		"attached_to_doctype": "Quotation", "attached_to_name": "Q-1",
		binding.BOUND_FIELD: None,
	}
	assert binding.bound("f1") == {"doctype": "Quotation", "name": "Q-1"}


def test_a_template_is_bound_to_a_doctype_and_no_record(binding, stubbed):
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            binding.BOUND_FIELD))] = {
		"attached_to_doctype": None, "attached_to_name": None,
		binding.BOUND_FIELD: "Quotation",
	}
	assert binding.bound("t1") == {"doctype": "Quotation"}


def test_a_file_bound_to_nothing_says_so(binding, stubbed):
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            binding.BOUND_FIELD))] = {}
	assert binding.bound("f2") == {}


# --------------------------------------------------------------------------- #
# What a record will offer
# --------------------------------------------------------------------------- #

def test_the_id_is_offered_first(binding):
	"""What most templates want before anything else — a covering letter says
	which quotation it is about before it says anything."""
	assert binding.offer("Quotation")[0]["fieldname"] == "name"


def test_a_password_is_never_offered(binding):
	"""The one that matters. Everything else on the deny list would render as
	nonsense; this one would render as a secret, in a document somebody prints."""
	assert "api_secret" not in [one["fieldname"] for one in binding.offer("Quotation")]


def test_layout_and_tables_are_not_fields_anybody_can_name(binding):
	offered = [one["fieldname"] for one in binding.offer("Quotation")]
	assert "sb_one" not in offered and "items" not in offered


def test_a_permlevel_you_cannot_read_is_not_offered(binding, stubbed):
	"""Finding this out at render time would mean a document that looks
	complete to its author and blank to everybody else."""
	stubbed._meta = {"Quotation": meta(QUOTATION, (("Sales User", 0),))}
	stubbed.get_roles = lambda *a: ["Sales User"]
	assert "margin" not in [one["fieldname"] for one in binding.offer("Quotation")]


def test_a_permlevel_you_can_read_is_offered(binding, stubbed):
	stubbed._meta = {"Quotation": meta(QUOTATION, (("Sales User", 0), ("Sales User", 1)))}
	stubbed.get_roles = lambda *a: ["Sales User"]
	assert "margin" in [one["fieldname"] for one in binding.offer("Quotation")]


# --------------------------------------------------------------------------- #
# What the record says
# --------------------------------------------------------------------------- #

def resolving(binding, stubbed, values=None):
	held = {"party_name": "Halloway", "grand_total": 144235.0,
	        "margin": 12, "api_secret": "hunter2", "name": "Q-1"}
	held.update(values or {})
	stubbed.get_doc = lambda *a, **k: types.SimpleNamespace(get=held.get, **held)
	return binding.resolve("Quotation", "Q-1", ["grand_total", "party_name"])


def test_both_halves_come_back(binding, stubbed):
	"""A cell that says `AED 144,235.00` cannot be added up, and prose that
	says `144235.0` reads as a bug. One read answers both."""
	found = resolving(binding, stubbed)["fields"]
	assert found["grand_total"]["value"] == 144235.0
	assert found["grand_total"]["text"] == "AED 144,235.00"


def test_a_field_the_doctype_would_not_offer_is_not_answered(binding, stubbed):
	"""The guard. Without it this is a whitelisted read of any column of any
	doctype on the site."""
	stubbed.get_doc = lambda *a, **k: types.SimpleNamespace(
		get=lambda one, d=None: "hunter2")
	found = binding.resolve("Quotation", "Q-1", ["api_secret"])
	assert found["fields"] == {}


def test_reading_a_record_needs_permission_to_read_it(binding, stubbed):
	stubbed.has_permission = lambda *a, **k: False
	with pytest.raises(Exception):
		binding.resolve("Quotation", "Q-1", ["grand_total"])


def test_more_fields_than_a_document_is_cut(binding, stubbed):
	stubbed.get_doc = lambda *a, **k: types.SimpleNamespace(get=lambda one, d=None: 1)
	stubbed._meta = {"Quotation": meta(
		[{"fieldname": f"f{n}", "label": f"F{n}", "fieldtype": "Data", "permlevel": 0}
		 for n in range(binding.MAX_FIELDS + 20)])}
	asked = [f"f{n}" for n in range(binding.MAX_FIELDS + 20)]
	assert len(binding.resolve("Quotation", "Q-1", asked)["fields"]) == binding.MAX_FIELDS


# --------------------------------------------------------------------------- #
# The token in a document
# --------------------------------------------------------------------------- #

@pytest.fixture
def fields(binding, stubbed):
	return importlib.import_module("oneapp.onedoc.fields")


def body_with(*names):
	return json.dumps({"type": "doc", "content": [
		{"type": "paragraph", "content": [
			{"type": "text", "text": "Total: "},
			*[{"type": "recordField", "attrs": {"field": one, "text": "—"}}
			  for one in names],
		]},
	]})


def test_every_field_the_prose_names(fields):
	assert fields.named(body_with("grand_total", "party_name")) == \
		["grand_total", "party_name"]


def test_a_field_named_twice_is_asked_for_once(fields):
	assert fields.named(body_with("grand_total", "grand_total")) == ["grand_total"]


def test_a_body_that_is_not_json_names_nothing(fields):
	assert fields.named("not json at all") == []


HTML = ('<p>Total: <span data-record-field="grand_total">old</span> and '
        '<span data-record-field="party_name">Halloway</span></p>')


def test_the_current_text_goes_inside_the_token(fields):
	filled = fields.fill(HTML, {"grand_total": "AED 144,235.00"})
	assert '>AED 144,235.00</span>' in filled
	# Untouched, because nothing resolved it — which is the whole reason the
	# last answer lives in the markup.
	assert '>Halloway</span>' in filled


def test_a_value_with_markup_in_it_is_escaped(fields):
	"""A record field is data. A customer called `<script>` is a customer,
	not a document that runs."""
	filled = fields.fill(HTML, {"grand_total": "<b>x</b>"})
	assert "<b>x</b>" not in filled and "&lt;b&gt;" in filled


def test_freezing_leaves_the_words_and_takes_the_token(fields):
	frozen = fields.freeze(fields.fill(HTML, {"grand_total": "AED 1.00"}))
	assert "data-record-field" not in frozen
	assert "AED 1.00" in frozen and "Halloway" in frozen


def test_freezing_the_json_too(fields):
	"""Both halves together or the document contradicts itself: freeze the
	HTML alone and the token comes back the moment somebody opens it."""
	frozen = json.loads(fields.frozen_content(body_with("grand_total"),
	                                          {"grand_total": "AED 1.00"}))
	nodes = frozen["content"][0]["content"]
	assert all(one["type"] == "text" for one in nodes)
	assert nodes[-1]["text"] == "AED 1.00"


def test_a_frozen_token_with_nothing_to_say_is_dropped(fields):
	"""ProseMirror refuses a text node with no text, and a document that fails
	to load is worse than one missing a number."""
	frozen = json.loads(fields.frozen_content(body_with("grand_total"),
	                                          {"grand_total": ""}))
	assert [one["type"] for one in frozen["content"][0]["content"]] == ["text"]


def test_a_document_bound_to_nothing_asks_nothing(fields, stubbed):
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            "custom_bound_doctype"))] = {}
	assert fields.values("f1", body_with("grand_total")) == {}


# --------------------------------------------------------------------------- #
# `RECORD()` in a cell
# --------------------------------------------------------------------------- #

@pytest.fixture
def records(binding, stubbed):
	mod = importlib.import_module("oneapp.onesheet.records")
	# `_mine` reads the File and asks whether it is a sheet at all.
	stubbed.get_doc = lambda *a, **k: types.SimpleNamespace(
		get=lambda key, default=None: "Sheet" if key == "custom_kind" else default,
		check_permission=lambda level="read": None,
		db_set=lambda *a, **k: None,
	)
	return mod


def test_the_one_argument_form_means_the_sheet_own_record(records, stubbed):
	"""`RECORD("grand_total")` names no record, so the sheet's binding is the
	record — which is what makes an estimator's template reusable."""
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            "custom_bound_doctype"))] = {
		"attached_to_doctype": "Quotation", "attached_to_name": "Q-9",
	}
	assert records._asked("s1", {"fields": ["grand_total"]}) == \
		("Quotation", "Q-9", ["grand_total"])


def test_a_sheet_bound_to_nothing_resolves_nothing(records, stubbed):
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            "custom_bound_doctype"))] = {}
	assert records._asked("s1", {"fields": ["grand_total"]}) is None


def test_a_named_record_beats_the_binding(records, stubbed):
	stubbed.db.values[("File", ("attached_to_doctype", "attached_to_name",
	                            "custom_bound_doctype"))] = {
		"attached_to_doctype": "Quotation", "attached_to_name": "Q-9",
	}
	assert records._asked("s1", {"doctype": "Item", "name": "RUA-FAB",
	                             "fields": ["rate"]}) == ("Item", "RUA-FAB", ["rate"])


def test_a_record_this_person_cannot_read_is_missing_and_not_a_refusal(
		records, stubbed, monkeypatch):
	"""Nineteen answers and one `#N/A`, rather than a workbook that will not
	open because one cell names a salary."""
	from oneapp.shared import binding as shared

	def refuse(doctype, name, wanted=None):
		raise PermissionError("no")

	monkeypatch.setattr(shared, "resolve", refuse)
	monkeypatch.setattr(records.binding, "resolve", refuse)
	found = records.record_fields("s1", [{"doctype": "Quotation", "name": "Q-1",
	                                      "fields": ["grand_total"]}])
	assert found["records"] == {}


def test_more_records_than_a_workbook_is_cut(records, stubbed, monkeypatch):
	seen = []
	monkeypatch.setattr(records.binding, "resolve",
	                    lambda d, n, w: seen.append(n) or {"fields": {}})
	records.record_fields("s1", [{"doctype": "Quotation", "name": f"Q-{n}",
	                              "fields": ["grand_total"]}
	                             for n in range(records.MAX_RECORDS + 20)])
	assert len(seen) == records.MAX_RECORDS
