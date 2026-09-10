"""A document and a workbook written about records.

A quotation's covering letter is prose with the quotation's numbers in it, and
an estimator's workbook is arithmetic over the job's. Typed out, both are a
second copy that goes stale, and the person who finds out is the customer.

Four claims are worth pinning and none is about rendering.

**The boundary.** A token and a `RECORD()` are both strings a person typed, so
the endpoint behind them takes a doctype and a fieldname from a browser.
Without `offer` narrowing it, that is a whitelisted read of any column of any
table on the site — permlevel, password fields and all.

**The stored text is never served.** A token carries its last answer so the
export reads as words, and that answer was written by whoever last had the
document open. Serving it would hand this reader a field they may not read.

**Freezing is total.** The body is stored twice — the HTML search and export
read, the JSON the editor loads — and freezing one brings the token back the
moment somebody opens it.

**A key outlives its record.** That is what makes a template work: fill the
slot, and every token that named the key keeps working without the prose being
touched.
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


def meta(fields, permissions=(("System Manager", 0),), title_field=None):
	return types.SimpleNamespace(
		# `file_sources` reads this to put the record's own name beside its
		# kind in the rail. None is the ordinary case and the one a doctype
		# without a title field really has.
		title_field=title_field,
		get_title_field=lambda: title_field,
		fields=[types.SimpleNamespace(**one) for one in fields],
		permissions=[
			types.SimpleNamespace(read=1, role=role, permlevel=level)
			for role, level in permissions
		],
	)


LINE = [
	{"fieldname": "item_code", "label": "Item", "fieldtype": "Data", "permlevel": 0},
	{"fieldname": "qty", "label": "Quantity", "fieldtype": "Float", "permlevel": 0},
	{"fieldname": "amount", "label": "Amount", "fieldtype": "Currency", "permlevel": 0},
	{"fieldname": "cost", "label": "Cost", "fieldtype": "Currency", "permlevel": 1},
]

QUOTATION = [
	{"fieldname": "party_name", "label": "Customer", "fieldtype": "Data", "permlevel": 0},
	{"fieldname": "grand_total", "label": "Total", "fieldtype": "Currency", "permlevel": 0},
	{"fieldname": "margin", "label": "Margin", "fieldtype": "Percent", "permlevel": 1},
	{"fieldname": "api_secret", "label": "Secret", "fieldtype": "Password", "permlevel": 0},
	{"fieldname": "items", "label": "Items", "fieldtype": "Table", "permlevel": 0,
	 "options": "Quotation Item"},
	{"fieldname": "sb_one", "label": None, "fieldtype": "Section Break", "permlevel": 0},
]


@pytest.fixture
def binding(stubbed):
	"""The module, with a `Bound Record` table it can actually read back.

	Sources are rows now, so a stub that answers `[]` to every `get_all`
	tests nothing: every question this module asks starts by reading them.
	"""
	mod = importlib.import_module("oneapp.shared.binding")
	stubbed._meta = {"Quotation": meta(QUOTATION), "Quotation Item": meta(LINE)}
	stubbed.get_roles = lambda *a: ["System Manager"]
	stubbed.db.exists = lambda doctype, name=None: True
	stubbed.has_permission = lambda *a, **k: True

	held = []
	stubbed._sources = held

	def get_all(doctype, filters=None, fields=None, **kw):
		if doctype != "Bound Record":
			return []
		where = (filters or {}).get("file")
		return [dict(row) for row in held if not where or row["file"] == where]

	def insert_row(spec):
		row = {"name": f"br{len(held)}", "label": "", "reference_name": None,
		       "idx_hint": 0, **spec}
		if row.get("doctype") == "Bound Record":
			held.append(row)
		return types.SimpleNamespace(**row)

	stubbed.get_all = get_all
	stubbed.get_doc = lambda *a, **k: (
		insert_doc(a[0]) if a and isinstance(a[0], dict)
		else types.SimpleNamespace(check_permission=lambda level="read": None)
	)

	def insert_doc(spec):
		made = insert_row(spec)
		made.insert = lambda **k: made
		# `frappe.get_doc({...}).insert()` is the shape the module writes in.
		return made

	return mod


def bind(stubbed, key, doctype, name=None, label=""):
	"""Put a source on the fixture's file, the way `add_source` would."""
	stubbed._sources.append({
		"name": f"br{len(stubbed._sources)}", "file": "f1", "key": key,
		"label": label or doctype, "reference_doctype": doctype,
		"reference_name": name, "idx_hint": len(stubbed._sources),
	})


# --------------------------------------------------------------------------- #
# What a file reads
# --------------------------------------------------------------------------- #

def test_a_file_reads_nothing_until_something_says_so(binding):
	assert binding.sources("f1") == []
	assert binding.bound("f1") == {}


def test_the_first_source_is_what_a_bare_token_means(binding, stubbed):
	"""A token written before the file had two records names no source, and
	must go on meaning the one it was written about."""
	bind(stubbed, binding.FIRST, "Quotation", "Q-1")
	bind(stubbed, "project", "Project", "PROJ-1")
	assert binding.source("f1", "")["reference_name"] == "Q-1"
	assert binding.bound("f1") == {"doctype": "Quotation", "name": "Q-1"}


def test_a_named_source_is_found_by_its_key(binding, stubbed):
	bind(stubbed, binding.FIRST, "Quotation", "Q-1")
	bind(stubbed, "project", "Project", "PROJ-1")
	assert binding.source("f1", "project")["reference_doctype"] == "Project"


def test_a_template_slot_is_a_kind_with_no_record(binding, stubbed):
	bind(stubbed, binding.FIRST, "Quotation", None)
	assert binding.bound("f1") == {"doctype": "Quotation"}


def test_two_of_the_same_kind_get_keys_that_stay_apart(binding, stubbed):
	"""A letter about two projects. Without this the second token would name
	the first project and nobody would notice until the wrong site was on it."""
	bind(stubbed, binding.FIRST, "Quotation", "Q-1")
	assert binding._unused_key("f1", "Project") == "project"
	bind(stubbed, "project", "Project", "PROJ-1")
	assert binding._unused_key("f1", "Project") == "project_2"


def test_the_first_source_is_called_the_same_thing_whatever_it_is_of(binding):
	assert binding._unused_key("f1", "Sales Invoice") == binding.FIRST


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


def test_a_table_is_not_a_token(binding):
	"""It is a block. A picker that offered "Items" beside "Grand Total" would
	be offering two different kinds of insertion under one word."""
	assert "items" not in [one["fieldname"] for one in binding.offer("Quotation")]


def test_a_table_is_offered_as_a_block_with_its_columns(binding):
	found = binding.tables("Quotation")
	assert [one["fieldname"] for one in found] == ["items"]
	assert "item_code" in [one["fieldname"] for one in found[0]["columns"]]


def test_a_block_starts_with_the_columns_the_grid_shows(binding, stubbed):
	"""`in_list_view` is the doctype author saying what this table is about.
	Schema order on a real child table is an id and five checkboxes."""
	listed = [{**one, "in_list_view": 1 if one["fieldname"] in ("qty", "amount")
	           else 0} for one in LINE]
	stubbed._meta = {"Quotation": meta(QUOTATION), "Quotation Item": meta(listed)}
	assert binding.tables("Quotation")[0]["default"] == ["qty", "amount"]


def test_a_child_with_no_grid_columns_falls_back_to_the_first_few(binding):
	assert binding.tables("Quotation")[0]["default"] == \
		["item_code", "qty", "amount"]


def test_a_child_column_behind_a_permlevel_is_not_offered(binding, stubbed):
	# Both, and at level 0 only: a role that cannot read the parent at all
	# would be a different test, and would answer nothing for a duller reason.
	stubbed._meta = {"Quotation": meta(QUOTATION, (("Sales User", 0),)),
	                 "Quotation Item": meta(LINE, (("Sales User", 0),))}
	stubbed.get_roles = lambda *a: ["Sales User"]
	columns = binding.tables("Quotation")[0]["columns"]
	assert "cost" not in [one["fieldname"] for one in columns]


def test_a_child_table_with_no_permissions_of_its_own_still_has_columns(
		binding, stubbed):
	"""The bug this fixed showed up as a schedule with nothing in it.

	A child doctype carries no DocPerm rows — the framework reads the
	parent's — so asking it for its own readable permlevels answers the empty
	set, and every column is filtered out as unreadable.
	"""
	stubbed._meta = {"Quotation": meta(QUOTATION),
	                 "Quotation Item": meta(LINE, permissions=())}
	columns = binding.tables("Quotation")[0]["columns"]
	assert [one["fieldname"] for one in columns] == ["item_code", "qty", "amount"]


def test_a_permlevel_you_cannot_read_is_not_offered(binding, stubbed):
	"""Finding this out at render time would mean a document that looks
	complete to its author and blank to everybody else."""
	stubbed._meta = {"Quotation": meta(QUOTATION, (("Sales User", 0),))}
	stubbed.get_roles = lambda *a: ["Sales User"]
	assert "margin" not in [one["fieldname"] for one in binding.offer("Quotation")]


# --------------------------------------------------------------------------- #
# What the record says
# --------------------------------------------------------------------------- #

def held_doc(stubbed, values=None):
	rows = [{"item_code": "RUA-FAB", "qty": 4, "amount": 1200, "cost": 800},
	        {"item_code": "RUA-MAT", "qty": 2, "amount": 300, "cost": 150}]
	held = {"party_name": "Halloway", "grand_total": 144235.0, "margin": 12,
	        "api_secret": "hunter2", "name": "Q-1",
	        "items": [types.SimpleNamespace(get=row.get, **row) for row in rows]}
	held.update(values or {})
	stubbed.get_doc = lambda *a, **k: types.SimpleNamespace(get=held.get, **held)
	return held


def test_both_halves_come_back(binding, stubbed):
	"""A cell that says `AED 144,235.00` cannot be added up, and prose that
	says `144235.0` reads as a bug. One read answers both."""
	held_doc(stubbed)
	found = binding.resolve("Quotation", "Q-1", ["grand_total"])["fields"]
	assert found["grand_total"]["value"] == 144235.0
	assert found["grand_total"]["text"] == "AED 144,235.00"


def test_a_field_the_doctype_would_not_offer_is_not_answered(binding, stubbed):
	"""The guard. Without it this is a whitelisted read of any column of any
	doctype on the site."""
	held_doc(stubbed)
	assert binding.resolve("Quotation", "Q-1", ["api_secret"])["fields"] == {}


def test_reading_a_record_needs_permission_to_read_it(binding, stubbed):
	stubbed.has_permission = lambda *a, **k: False
	with pytest.raises(Exception):
		binding.resolve("Quotation", "Q-1", ["grand_total"])


def test_the_rows_of_a_child_table_come_back_as_text(binding, stubbed):
	held_doc(stubbed)
	found = binding.rows("Quotation", "Q-1", "items", ["item_code", "qty"])
	assert [one["label"] for one in found["columns"]] == ["Item", "Quantity"]
	assert found["rows"][0] == ["RUA-FAB", "4"]


def test_a_schedule_comes_back_as_text_and_as_numbers(binding, stubbed):
	"""Both halves, and for the reason `resolve` sends both: a schedule in a
	letter is read, so it wants `AED 1,200.00`; the same schedule in a
	workbook is added up, so it wants `1200`."""
	held_doc(stubbed)
	found = binding.rows("Quotation", "Q-1", "items", ["item_code", "amount"])
	assert found["rows"] == [["RUA-FAB", "AED 1,200.00"], ["RUA-MAT", "AED 300.00"]]
	assert found["values"] == [["RUA-FAB", 1200], ["RUA-MAT", 300]]


def test_a_child_column_nobody_may_read_cannot_be_asked_for(binding, stubbed):
	stubbed._meta = {"Quotation": meta(QUOTATION, (("Sales User", 0),)),
	                 "Quotation Item": meta(LINE, (("Sales User", 0),))}
	stubbed.get_roles = lambda *a: ["Sales User"]
	held_doc(stubbed)
	found = binding.rows("Quotation", "Q-1", "items", ["item_code", "cost"])
	assert [one["fieldname"] for one in found["columns"]] == ["item_code"]


def test_a_table_the_doctype_does_not_have_answers_nothing(binding, stubbed):
	held_doc(stubbed)
	assert binding.rows("Quotation", "Q-1", "taxes", ["rate"])["rows"] == []


# --------------------------------------------------------------------------- #
# The token in a document
# --------------------------------------------------------------------------- #

@pytest.fixture
def fields(binding, stubbed):
	return importlib.import_module("oneapp.onedoc.fields")


def body_with(*names, table=None, source=""):
	nodes = [{"type": "text", "text": "Total: "}]
	nodes += [{"type": "recordField",
	           "attrs": {"source": source, "field": one, "text": "-"}}
	          for one in names]
	content = [{"type": "paragraph", "content": nodes}]
	if table:
		content.append({"type": "recordTable",
		                "attrs": {"source": source, "table": table,
		                          "columns": ["item_code", "qty"]}})
	return json.dumps({"type": "doc", "content": content})


def test_every_field_and_table_the_prose_names(fields):
	found = fields.named(body_with("grand_total", "party_name", table="items"))
	assert [one["field"] for one in found["fields"]] == ["grand_total", "party_name"]
	assert found["tables"][0]["table"] == "items"


def test_the_same_field_from_two_sources_is_two_questions(fields):
	"""A letter about two projects asks each of them for its own name."""
	one = json.loads(body_with("project_name", source="project"))
	two = json.loads(body_with("project_name", source="project_2"))
	both = json.dumps({"type": "doc",
	                   "content": one["content"] + two["content"]})
	assert len(fields.named(both)["fields"]) == 2


def test_a_body_that_is_not_json_names_nothing(fields):
	assert fields.named("not json at all") == {"fields": [], "tables": []}


HTML = ('<p>Total: <span data-record-source="record" data-record-field="grand_total">'
        'old</span> and <span data-record-source="project" '
        'data-record-field="project_name">Marina</span></p>')


def test_the_current_text_goes_inside_the_token(fields):
	filled = fields.fill(HTML, {"record.grand_total": "AED 144,235.00"})
	assert ">AED 144,235.00</span>" in filled


def test_a_token_that_did_not_resolve_is_emptied_and_not_left(fields):
	"""The permission rule, in the export. What was stored was written by
	somebody who could read it; this reader may not be that person."""
	filled = fields.fill(HTML, {"record.grand_total": "AED 1.00"})
	assert "Marina" not in filled


def test_a_value_with_markup_in_it_is_escaped(fields):
	"""A record field is data. A customer called `<script>` is a customer,
	not a document that runs."""
	filled = fields.fill(HTML, {"record.grand_total": "<b>x</b>"})
	assert "<b>x</b>" not in filled and "&lt;b&gt;" in filled


def test_the_body_served_is_never_the_body_stored(fields):
	"""`sanitise`. The bug this exists for: a permlevel field one person
	resolved became readable by everyone who could open the document."""
	stored = json.dumps({"type": "doc", "content": [{"type": "paragraph", "content": [
		{"type": "recordField",
		 "attrs": {"source": "record", "field": "margin", "text": "12%"}},
	]}]})
	served = json.loads(fields.sanitise(stored, {}))
	assert served["content"][0]["content"][0]["attrs"]["text"] == ""


def test_a_block_rows_never_travel_in_the_body(fields):
	stored = json.dumps({"type": "doc", "content": [
		{"type": "recordTable",
		 "attrs": {"source": "record", "table": "items", "rows": [["leaked"]]}},
	]})
	served = json.loads(fields.sanitise(stored, {}))
	assert served["content"][0]["attrs"]["rows"] == []


def test_a_block_is_drawn_into_the_export(fields):
	"""The rows are not in the body, so the export builds the table from what
	this reader just resolved — `fields.draw`, the other half of `fill`."""
	html = '<p>Schedule</p><div data-record-table="items" data-record-source=""></div>'
	made = fields.draw(html, {"record.items": {
		"columns": [{"fieldname": "item_code", "label": "Item"}],
		"rows": [["Fabrication"]],
	}})
	assert "<th>Item</th>" in made
	assert "<td>Fabrication</td>" in made


def test_a_block_that_did_not_resolve_is_left_empty(fields):
	html = '<div data-record-table="items" data-record-source="">old rows</div>'
	assert fields.draw(html, {}) == \
		'<div data-record-table="items" data-record-source=""></div>'


def test_a_block_from_one_source_is_not_drawn_from_another(fields):
	html = '<div data-record-source="customer" data-record-table="items"></div>'
	made = fields.draw(html, {"record.items": {
		"columns": [{"fieldname": "item_code", "label": "Item"}],
		"rows": [["Fabrication"]],
	}})
	assert "Fabrication" not in made


def test_a_cell_with_markup_in_it_is_escaped(fields):
	made = fields.draw(
		'<div data-record-table="items"></div>',
		{"record.items": {"columns": [{"fieldname": "item_code", "label": "Item"}],
		                  "rows": [["<script>alert(1)</script>"]]}},
	)
	assert "<script>" not in made


def test_freezing_leaves_the_words_and_takes_the_token(fields):
	frozen = fields.freeze(fields.fill(HTML, {"record.grand_total": "AED 1.00"}))
	assert "data-record-field" not in frozen and "AED 1.00" in frozen


def test_freezing_the_json_too(fields):
	"""Both halves together or the document contradicts itself: freeze the
	HTML alone and the token comes back the moment somebody opens it."""
	frozen = json.loads(fields.frozen_content(
		body_with("grand_total", source="record"), {"record.grand_total": "AED 1.00"}))
	nodes = frozen["content"][0]["content"]
	assert all(one["type"] == "text" for one in nodes)
	assert nodes[-1]["text"] == "AED 1.00"


def test_a_frozen_token_with_nothing_to_say_is_dropped(fields):
	"""ProseMirror refuses a text node with no text, and a document that fails
	to load is worse than one missing a number."""
	frozen = json.loads(fields.frozen_content(body_with("grand_total"),
	                                          {"record.grand_total": ""}))
	assert [one["type"] for one in frozen["content"][0]["content"]] == ["text"]


def test_a_document_reading_nothing_asks_nothing(fields):
	assert fields.values("f1", body_with("grand_total")) == {"fields": {}, "tables": {}}


def test_a_slot_nobody_has_filled_in_asks_nothing(fields, stubbed, binding):
	"""A template. The doctype is known and the record is not, so there is
	nothing to read and a blank is the right answer."""
	bind(stubbed, binding.FIRST, "Quotation", None)
	assert fields.values("f1", body_with("grand_total"))["fields"] == {}


def test_each_source_is_read_once_however_many_fields_it_answers(
		fields, stubbed, binding, monkeypatch):
	bind(stubbed, binding.FIRST, "Quotation", "Q-1")
	held_doc(stubbed)
	asked = []
	real = binding.resolve
	monkeypatch.setattr(fields.binding, "resolve",
	                    lambda d, n, w: asked.append(w) or real(d, n, w))
	fields.values("f1", body_with("grand_total", "party_name"))
	assert asked == [["grand_total", "party_name"]]


def readable(monkeypatch, doctypes):
	"""Stand in for `frappe.permissions.get_doctypes_with_read`.

	A module rather than an attribute, because the stub `frappe` is a module
	and not a package — so `from frappe.permissions import ...` needs one to
	exist in `sys.modules` before it will resolve at all.
	"""
	made = types.ModuleType("frappe.permissions")
	made.get_doctypes_with_read = lambda user=None: list(doctypes)
	monkeypatch.setitem(sys.modules, "frappe.permissions", made)


def test_only_kinds_this_person_may_read_are_offered(binding, stubbed, monkeypatch):
	"""The sidebar's first step. Frappe's own answer to "what can this person
	read", so a doctype somebody has no business seeing is not in the list."""
	readable(monkeypatch, ["Quotation"])
	asked = {}

	def get_all(doctype, filters=None, fields=None, **kw):
		if doctype != "DocType":
			return []
		asked["filters"] = filters
		return [{"name": "Quotation", "module": "Selling"}]

	held = stubbed.get_all
	stubbed.get_all = lambda dt, **kw: (get_all(dt, **kw) if dt == "DocType"
	                                    else held(dt, **kw))

	found = binding.kinds("quo")
	assert [one["name"] for one in found] == ["Quotation"]
	# The readable set and the search both, which a dict of filters cannot
	# hold — they are both about `name`.
	assert ["name", "in", ["Quotation"]] in asked["filters"]
	assert ["name", "like", "%quo%"] in asked["filters"]
	assert ["istable", "=", 0] in asked["filters"]


def test_nothing_readable_is_an_empty_list_and_not_a_query(binding, monkeypatch):
	readable(monkeypatch, [])
	assert binding.kinds("") == []


# --------------------------------------------------------------------------- #
# `RECORD()` in a cell
# --------------------------------------------------------------------------- #

@pytest.fixture
def records(binding, stubbed):
	mod = importlib.import_module("oneapp.onesheet.records")
	held = stubbed.get_doc
	stubbed.get_doc = lambda *a, **k: (
		types.SimpleNamespace(
			get=lambda key, default=None: "Sheet" if key == "custom_kind" else default,
			check_permission=lambda level="read": None,
			db_set=lambda *x, **y: None,
		) if a and a[0] == "File" else held(*a, **k)
	)
	return mod


def test_the_one_argument_form_means_the_sheet_own_record(records, stubbed, binding):
	"""`RECORD("grand_total")` names no record, so the sheet's first source is
	the record — which is what makes an estimator's template reusable."""
	stubbed._sources.append({
		"name": "br0", "file": "s1", "key": binding.FIRST, "label": "Quotation",
		"reference_doctype": "Quotation", "reference_name": "Q-9", "idx_hint": 0,
	})
	assert records._asked("s1", {"fields": ["grand_total"]}) == \
		("Quotation", "Q-9", ["grand_total"])


def test_a_sheet_reading_nothing_resolves_nothing(records):
	assert records._asked("s1", {"fields": ["grand_total"]}) is None


def test_a_keyed_ask_resolves_through_the_source(records, stubbed, binding):
	"""`RECORD("customer", "credit_limit")`. The two-argument form: a workbook
	reading two records says which one without naming an id that can change."""
	stubbed._sources.append({
		"name": "br0", "file": "s1", "key": binding.FIRST, "label": "Quotation",
		"reference_doctype": "Quotation", "reference_name": "Q-9", "idx_hint": 0,
	})
	stubbed._sources.append({
		"name": "br1", "file": "s1", "key": "customer", "label": "Customer",
		"reference_doctype": "Customer", "reference_name": "Halloway", "idx_hint": 1,
	})
	assert records._asked("s1", {"source": "customer", "fields": ["credit_limit"]}) == \
		("Customer", "Halloway", ["credit_limit"])


def test_a_key_nothing_answers_to_resolves_nothing(records, stubbed, binding):
	# A formula naming a source somebody removed. `#N/A`, not an error.
	stubbed._sources.append({
		"name": "br0", "file": "s1", "key": binding.FIRST, "label": "Quotation",
		"reference_doctype": "Quotation", "reference_name": "Q-9", "idx_hint": 0,
	})
	assert records._asked("s1", {"source": "project", "fields": ["title"]}) is None


def test_a_named_record_beats_the_binding(records, stubbed, binding):
	stubbed._sources.append({
		"name": "br0", "file": "s1", "key": binding.FIRST, "label": "Quotation",
		"reference_doctype": "Quotation", "reference_name": "Q-9", "idx_hint": 0,
	})
	assert records._asked("s1", {"doctype": "Item", "name": "RUA-FAB",
	                             "fields": ["rate"]}) == ("Item", "RUA-FAB", ["rate"])


def _bound_sheet(stubbed, binding):
	stubbed._sources.append({
		"name": "br0", "file": "s1", "key": binding.FIRST, "label": "Quotation",
		"reference_doctype": "Quotation", "reference_name": "Q-1", "idx_hint": 0,
	})


def test_a_table_ask_answers_a_schedule(records, stubbed, binding, monkeypatch):
	"""What a block of `RECORDROW()` fetches: one ask per table, keyed so a
	cell can find it without knowing which request brought it."""
	_bound_sheet(stubbed, binding)
	seen = {}

	def drawn(doctype, name, table, columns=None):
		seen.update({"doctype": doctype, "name": name, "table": table,
		             "columns": columns})
		return {"columns": [], "rows": [], "values": [["RUA-FAB", 1200]]}

	monkeypatch.setattr(records.binding, "rows", drawn)
	found = records.record_fields("s1", [
		{"source": "record", "table": "items", "fields": ["item_code", "amount"]},
	])

	# A table ask is not a field ask, and must not be resolved as one.
	assert found["records"] == {}
	assert seen == {"doctype": "Quotation", "name": "Q-1", "table": "items",
	                "columns": ["item_code", "amount"]}
	assert found["tables"]["Quotation\x1fQ-1\x1fitems"]["values"] == \
		[["RUA-FAB", 1200]]


def test_a_table_ask_may_name_no_columns(records, stubbed, binding, monkeypatch):
	"""Which is how the rail asks before anybody has chosen any — `rows`
	then draws the ones the child's own grid shows."""
	_bound_sheet(stubbed, binding)
	monkeypatch.setattr(records.binding, "rows",
	                    lambda d, n, t, c=None: {"columns": [], "rows": [],
	                                             "values": [], "asked": c})
	found = records.record_fields("s1", [{"source": "record", "table": "items",
	                                      "fields": []}])
	assert found["tables"]["Quotation\x1fQ-1\x1fitems"]["asked"] == []


def test_a_record_this_person_cannot_read_is_missing_and_not_a_refusal(
		records, monkeypatch):
	"""Nineteen answers and one `#N/A`, rather than a workbook that will not
	open because one cell names a salary."""
	def refuse(doctype, name, wanted=None):
		raise PermissionError("no")

	monkeypatch.setattr(records.binding, "resolve", refuse)
	found = records.record_fields("s1", [{"doctype": "Quotation", "name": "Q-1",
	                                      "fields": ["grand_total"]}])
	assert found["records"] == {}


def test_more_records_than_a_workbook_is_cut(records, monkeypatch):
	seen = []
	monkeypatch.setattr(records.binding, "resolve",
	                    lambda d, n, w: seen.append(n) or {"fields": {}})
	records.record_fields("s1", [{"doctype": "Quotation", "name": f"Q-{n}",
	                              "fields": ["grand_total"]}
	                             for n in range(records.MAX_RECORDS + 20)])
	assert len(seen) == records.MAX_RECORDS


# --------------------------------------------------------------------------- #
# One glyph per field
# --------------------------------------------------------------------------- #

def test_a_field_carries_the_glyph_its_type_earns(binding):
	"""The rail draws the same mark the record's own label does, from the
	same call — a picker that invented its own would be the fifth answer to
	one question."""
	found = {one["fieldname"]: one["icon"] for one in binding.offer("Quotation")}
	assert found["grand_total"] == "lucide-wallet"
	assert found["party_name"] == "lucide-type"
	assert found["name"] == "lucide-type"


def test_a_child_table_and_its_columns_carry_one_too(binding):
	table = binding.tables("Quotation")[0]
	assert table["icon"] == "lucide-table"
	assert {one["fieldname"]: one["icon"] for one in table["columns"]}["qty"] == \
		"lucide-hash"
