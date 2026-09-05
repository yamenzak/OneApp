"""Print formats: the shaping, the bounds and the two doors.

The rendering is Frappe's — `PrintFormatGenerator` walks a layout and
`frappe.get_print` makes the PDF — so nothing here tests that. What is pinned
is everything between the browser and that generator: the layout shape, which
is Frappe's own `format_data` contract and has to stay it; the bounds on what
reaches a PDF engine's command line; and the refusal to write a field the
doctype does not have, whose symptom would otherwise be a blank space on a
printed invoice. See `docs/PRINTING.md`.
"""

import types

import pytest


@pytest.fixture
def printing(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import printing as module

	return module


def declare(frappe, doctype, fields, autoname=""):
	"""A doctype, as thin as what this module asks of one."""
	made = [types.SimpleNamespace(fieldname=f[0], fieldtype=f[1], label=f[2],
	                              options=f[3] if len(f) > 3 else None)
	        for f in fields]
	frappe._meta[doctype] = types.SimpleNamespace(
		name=doctype,
		fields=made,
		autoname=autoname,
		get_field=lambda name, made=made: next(
			(one for one in made if one.fieldname == name), None
		),
	)


# --- the layout ------------------------------------------------------------


def test_a_layout_keeps_frappes_own_shape(printing, stub_frappe):
	"""`sections`, `header` and `footer`, each a list of columns of fields.

	This is the one thing in the module that is not ours to design. Frappe's
	generator reads exactly these keys; a layout of our own shape would need a
	renderer of our own, and a second renderer is a second set of decisions
	about margins and letter heads, drifting.
	"""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	found = printing._layout({"sections": [{"columns": [{"fields": [
		{"fieldname": "total", "label": "Total"},
	]}]}]}, "Invoice")

	assert set(found) == {"sections", "header", "footer"}
	assert found["header"] == {"columns": []}
	assert found["sections"][0]["columns"][0]["fields"][0] == {
		"fieldname": "total", "fieldtype": "Currency", "label": "Total",
	}


def test_the_fieldtype_comes_from_the_doctype_not_the_browser(printing, stub_frappe):
	"""The generator branches on `fieldtype` to pick a renderer, so a browser
	that said `Data` for a Currency field would print an unformatted number."""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	found = printing._layout({"sections": [{"columns": [{"fields": [
		{"fieldname": "total", "fieldtype": "Data", "label": "Total"},
	]}]}]}, "Invoice")

	assert found["sections"][0]["columns"][0]["fields"][0]["fieldtype"] == "Currency"


def test_a_field_the_doctype_does_not_have_is_refused_by_name(printing, stub_frappe):
	"""The one mistake that is not dropped quietly.

	Everything else the browser can get wrong shows up as a missing box on a
	canvas somebody is looking at. A fieldname that does not resolve shows up
	as a blank space on a printed invoice, weeks later.
	"""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	with pytest.raises(stub_frappe.ValidationError) as raised:
		printing._layout({"sections": [{"columns": [{"fields": [
			{"fieldname": "grand_total"},
		]}]}]}, "Invoice")
	assert "grand_total" in str(raised.value)


def test_only_the_four_justify_modes_survive(printing, stub_frappe):
	"""`justify` names a CSS class in the generator's own template. Anything
	else would reach the markup as a class that does not exist."""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	kept = printing._layout(
		{"sections": [{"columns": [], "justify": "space-between"}]}, "Invoice")
	assert kept["sections"][0]["justify"] == "space-between"

	dropped = printing._layout(
		{"sections": [{"columns": [], "justify": "onto-the-floor"}]}, "Invoice")
	assert "justify" not in dropped["sections"][0]


def test_a_layout_stops_somewhere(printing, stub_frappe):
	"""A page is a page. Past these it is a report, and a browser sending
	twelve thousand sections is a browser that has gone wrong."""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	found = printing._layout({
		"sections": [{"columns": [{"fields": [{"fieldname": "total"}]
		                           * (printing.FIELDS + 5)}]
		              * (printing.COLUMNS + 3)}] * (printing.SECTIONS + 10),
	}, "Invoice")

	assert len(found["sections"]) == printing.SECTIONS
	assert len(found["sections"][0]["columns"]) == printing.COLUMNS
	assert len(found["sections"][0]["columns"][0]["fields"]) == printing.FIELDS


def test_an_element_is_one_of_the_five_the_generator_draws(printing, stub_frappe):
	"""HTML, Spacer, Divider, Image, Barcode. The generator's template branches
	on each by name and falls through to "render the docfield" for anything
	else — which is why an invented sixth must not reach it as an element."""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	assert printing.ELEMENTS == ("HTML", "Spacer", "Divider", "Image", "Barcode")

	# Dropped rather than refused: it names no field, so there is nothing whose
	# absence anybody would go looking for later.
	found = printing._layout({"sections": [{"columns": [{"fields": [
		{"fieldtype": "Carousel"},
	]}]}]}, "Invoice")
	assert found["sections"][0]["columns"][0]["fields"] == []


def test_a_spacer_carries_a_height_and_nothing_else(printing, stub_frappe):
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])

	found = printing._layout({"sections": [{"columns": [{"fields": [
		{"fieldtype": "Spacer", "height": 40, "html": "<script>x</script>"},
	]}]}]}, "Invoice")

	assert found["sections"][0]["columns"][0]["fields"][0] == {
		"fieldtype": "Spacer", "height": 40,
	}


def test_a_table_prints_only_columns_its_child_declares(printing, stub_frappe):
	"""A `table_columns` entry names a field of the *child* doctype. One that
	does not exist there would render as a column of nothing."""
	declare(stub_frappe, "Invoice", [("items", "Table", "Items", "Invoice Item")])
	declare(stub_frappe, "Invoice Item", [
		("item", "Data", "Item"), ("qty", "Float", "Quantity"),
	])

	found = printing._layout({"sections": [{"columns": [{"fields": [
		{"fieldname": "items", "table_columns": [
			{"fieldname": "qty"}, {"fieldname": "smuggled"},
		]},
	]}]}]}, "Invoice")

	columns = found["sections"][0]["columns"][0]["fields"][0]["table_columns"]
	assert [one["fieldname"] for one in columns] == ["qty"]
	assert columns[0]["label"] == "Quantity"


def test_the_row_number_is_a_column_a_table_may_print(printing, stub_frappe):
	"""`idx` is not a docfield and is on almost every printed table there is."""
	declare(stub_frappe, "Invoice", [("items", "Table", "Items", "Invoice Item")])
	declare(stub_frappe, "Invoice Item", [("item", "Data", "Item")])

	found = printing._layout({"sections": [{"columns": [{"fields": [
		{"fieldname": "items", "table_columns": [{"fieldname": "idx"}]},
	]}]}]}, "Invoice")

	columns = found["sections"][0]["columns"][0]["fields"][0]["table_columns"]
	assert columns[0]["fieldname"] == "idx"


# --- the page --------------------------------------------------------------


def test_a_margin_is_bounded_because_it_reaches_a_command_line(printing):
	"""`margin_left` becomes `--margin-left 900mm` on the PDF engine's own
	invocation. A number with a bound is one the engine can be given."""
	found = printing._setup({"margin_left": 9000, "margin_top": -40})
	assert found["margin_left"] == 100
	assert found["margin_top"] == 0


def test_a_page_number_position_is_one_of_frappes_seven(printing):
	assert printing._setup({"page_number": "Bottom Center"})["page_number"] == "Bottom Center"
	assert "page_number" not in printing._setup({"page_number": "Somewhere Nice"})


def test_a_font_size_that_is_not_a_number_falls_back(printing):
	"""It reaches a stylesheet as `font-size: {n}pt`, so `14pt` beats nothing."""
	assert printing._setup({"font_size": "enormous"})["font_size"] == 14
	assert printing._setup({})["font_size"] == 14


# --- the palette -----------------------------------------------------------


def test_the_palette_leaves_out_what_has_nothing_to_print(printing, stub_frappe,
                                                          monkeypatch):
	"""A Section Break is layout in the form and an empty labelled div on the
	page. So is a Column Break, a Tab Break and a Button."""
	declare(stub_frappe, "Invoice", [
		("sec", "Section Break", None),
		("total", "Currency", "Total"),
		("go", "Button", "Recalculate"),
	])
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True,
	                    raising=False)

	found = printing.palette("Invoice")
	assert [one["fieldname"] for one in found["fields"]] == ["name", "total"]


def test_the_palette_offers_the_id(printing, stub_frappe, monkeypatch):
	"""`name` is not a docfield and is on every format anybody has drawn."""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True,
	                    raising=False)

	assert printing.palette("Invoice")["fields"][0]["fieldname"] == "name"


# --- what a manifest ships -------------------------------------------------


@pytest.fixture
def sync(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import sync as module

	return module


def screen(**kw):
	return {"space_code": "zz", "module": "Zed", "screens": [{"document_type": "Invoice", **kw}]}


def test_a_shipped_format_is_created_once_and_then_left_alone(sync, stub_frappe,
                                                              monkeypatch):
	"""The opposite of everything else in this module.

	Roles, permissions and members are reconciled every sync, because the
	control plane owns them. A print format it does not: an app gives a
	workspace somewhere to start and the workspace owns what it does with it.
	Rewriting these every quarter hour would silently undo an afternoon's work
	and nothing would say why.
	"""
	made = []
	held = set()

	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: doctype == "DocType" or name in held)

	from oneapp.oneapp_core import printing

	monkeypatch.setattr(printing, "save_format",
	                    lambda dt, label, layout, page: (held.add(label), made.append(label)))
	monkeypatch.setattr(printing, "set_default", lambda dt, name: None)

	rows = '[{"name": "ACME Invoice", "layout": {"sections": []}}]'

	assert sync.sync_screen_fixtures([screen(print_formats=rows)])["formats"] == 1
	assert sync.sync_screen_fixtures([screen(print_formats=rows)])["formats"] == 0
	assert made == ["ACME Invoice"]


def test_a_bad_fixture_row_costs_one_row_rather_than_the_sync(sync, stub_frappe,
                                                              monkeypatch):
	"""A space naming a doctype this site does not have is a space whose app is
	not installed yet, which is ordinary. Nothing here may fail a sync that
	also carries roles, members and quotas."""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda *a, **k: True)

	from oneapp.oneapp_core import printing

	def boom(*a, **k):
		raise ValueError("that layout will not parse")

	monkeypatch.setattr(printing, "save_format", boom)

	found = sync.sync_screen_fixtures(
		[screen(print_formats='[{"name": "Broken", "layout": "nonsense"}]')]
	)
	assert found == {"series": 0, "formats": 0, "fields": 0}


def test_a_series_a_workspace_has_already_set_is_never_replaced(sync, stub_frappe,
                                                               monkeypatch):
	""""Already set" is read off the Property Setter Frappe writes when anybody
	changes the options — so a workspace that has chosen its own prefixes keeps
	them, and one that has not gets the app's."""
	declare(stub_frappe, "Invoice", [("naming_series", "Select", "Series")])

	written = []

	class Settings:
		transaction_type = None
		naming_series_options = None

		def update_series(self):
			written.append(self.naming_series_options)

	monkeypatch.setattr(stub_frappe, "get_doc", lambda *a, **k: Settings())

	# Nothing set yet: the app's prefixes are applied.
	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: doctype == "DocType")
	assert sync.sync_screen_fixtures([screen(naming_series="ACME-.#####")])["series"] == 1
	assert written == ["ACME-.#####"]

	# A Property Setter says somebody has chosen since. Left alone.
	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: doctype in ("DocType", "Property Setter"))
	assert sync.sync_screen_fixtures([screen(naming_series="OTHER-.#####")])["series"] == 0
	assert written == ["ACME-.#####"]


def test_a_doctype_with_no_series_field_is_skipped(sync, stub_frappe, monkeypatch):
	"""A manifest may name prefixes for a doctype whose app does not offer any;
	writing them would be a Property Setter on a field that is not there."""
	declare(stub_frappe, "Invoice", [("total", "Currency", "Total")])
	monkeypatch.setattr(stub_frappe.db, "exists",
	                    lambda doctype, name=None: doctype == "DocType")

	assert sync.sync_screen_fixtures([screen(naming_series="ACME-.#####")])["series"] == 0
