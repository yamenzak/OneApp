"""A form that collects a document and its lines.

`docs/ONEFORMS.md` §15, stage 16. `Table` was in `NEVER` from stage 1 with a
reason that was true and stopped being enough — a grid on a page a stranger
fills in is a different control — and what it left out was every form whose
subject has parts. An order has lines. A claim has expenses. "Fill the header in
here and mail us a spreadsheet for the rest" is not a product.

The write needed nothing: `accept` does `doc.set(fieldname, value)` and
`Document.set` on a table field with a list of dicts is how Frappe has always
filled a child table. So everything here is about what may be in that list.
"""

import pathlib
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/oneforms/lines.py"
PUBLIC = ROOT / "apps/oneapp/oneapp/oneforms/public.py"
SERVICE = ROOT / "apps/oneapp/oneapp/oneforms/service.py"
PAGE = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue"
ROWS = ROOT / "apps/oneapp/frontend/src/modules/oneforms/components/RowsField.vue"
BUILDER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/FormBuilder.vue"
LAYOUT = ROOT / "apps/oneapp/frontend/src/modules/oneforms/lib/layout.js"


class Row(dict):
	def __getattr__(self, name):
		return self.get(name)


class Form:
	def __init__(self, *fields):
		self.web_form_fields = list(fields)


def table(fieldname="items", child="Opportunity Item", asks=""):
	from oneapp.oneforms.lines import COLUMNS

	return Row(fieldname=fieldname, fieldtype="Table", options=child,
	           label="What you need", **{COLUMNS: asks})


@pytest.fixture
def lines(stub_frappe, monkeypatch):
	from oneapp.oneforms import lines, service

	monkeypatch.setattr(service, "available", lambda doctype: [
		{"fieldname": "item_name", "label": "Item", "fieldtype": "Data",
		 "reqd": 0, "options": ""},
		{"fieldname": "qty", "label": "Quantity", "fieldtype": "Float",
		 "reqd": 0, "options": ""},
		{"fieldname": "rate", "label": "Rate", "fieldtype": "Currency",
		 "reqd": 0, "options": ""},
	])
	return lines


# ------------------------------------------------------------ what a row holds

def test_a_row_may_only_carry_the_columns_the_form_asked_for(lines):
	"""Not the child doctype's own fields — the *form's*, which is a subset
	somebody chose. A payload naming `rate` on a form that asks for a name and
	a quantity is a payload setting a price."""
	doc = Form(table(asks="item_name, qty"))
	values = {"items": [{"item_name": "Cable", "qty": "3", "rate": "0.01"}]}

	lines.clean(doc, values)

	assert values["items"] == [{"item_name": "Cable", "qty": "3"}]


def test_nothing_about_the_parent_is_settable_from_a_row(lines):
	"""A row that could name its own `parent` is a row that files itself
	against somebody else's document."""
	doc = Form(table(asks="item_name"))
	values = {"items": [{"item_name": "Cable", "parent": "OPP-9999",
	                     "parenttype": "Opportunity", "name": "x",
	                     "owner": "them@example.com", "docstatus": 1}]}

	lines.clean(doc, values)

	assert values["items"] == [{"item_name": "Cable"}]
	assert {"parent", "parenttype", "name", "owner", "docstatus"} <= lines.NEVER


def test_a_form_that_named_no_columns_takes_all_of_them(lines):
	"""What a form made before stage 16 says. A fallback that widens rather
	than breaks, because the alternative is a table that silently collects
	nothing."""
	doc = Form(table(asks=""))
	values = {"items": [{"item_name": "Cable", "qty": "3", "rate": "2"}]}

	lines.clean(doc, values)

	assert values["items"] == [{"item_name": "Cable", "qty": "3", "rate": "2"}]


def test_a_column_that_is_no_longer_on_the_child_falls_out(lines):
	doc = Form(table(asks="item_name, gone"))
	assert lines.asked(doc, "items") == ["item_name"]


# ------------------------------------------------------------------ the rows

def test_a_row_nobody_filled_in_is_dropped(lines):
	"""A child table of blanks is what a grid with an Add button produces by
	accident."""
	doc = Form(table(asks="item_name, qty"))
	values = {"items": [{"item_name": "Cable", "qty": "3"},
	                    {"item_name": "", "qty": ""},
	                    {"item_name": "  ", "qty": None}]}

	lines.clean(doc, values)

	assert values["items"] == [{"item_name": "Cable", "qty": "3"}]


def test_nothing_sent_is_an_empty_list_rather_than_missing(lines):
	"""So `accept` clears a table somebody emptied, instead of leaving what
	was there."""
	doc = Form(table())
	for sent in ({}, {"items": None}, {"items": ""}):
		values = dict(sent)
		lines.clean(doc, values)
		assert values["items"] == []


def test_there_is_a_ceiling_and_it_is_said_rather_than_silent(lines):
	"""A hundred lines is a big order and a thousand is somebody finding out
	what happens. Loud, because a person filled this in and needs to know why
	it bounced — unlike a dropped column, which nobody typed."""
	doc = Form(table(asks="item_name"))
	values = {"items": [{"item_name": f"row {n}"} for n in range(lines.MOST + 1)]}

	with pytest.raises(Exception) as refused:
		lines.clean(doc, values)
	assert str(lines.MOST) in str(refused.value)


def test_something_that_is_not_a_list_is_refused(lines):
	doc = Form(table())
	with pytest.raises(Exception):
		lines.clean(doc, {"items": {"item_name": "Cable"}})


# ------------------------------------------------------------ what is drawn

def test_the_page_is_told_what_one_row_is_made_of(lines):
	"""`service.available` on the *child*, so the same rule decides what can be
	on a form and what can be in one of its rows — a read-only or hidden column
	is out of both."""
	doc = Form(table(asks="qty, item_name"))
	drawn = lines.shown(doc, "items")

	# In the order the form asked for them, not the child's own order.
	assert [one["fieldname"] for one in drawn] == ["qty", "item_name"]
	assert drawn[0]["label"] == "Quantity"


def test_the_public_endpoint_sends_the_columns_and_the_ceiling():
	source = PUBLIC.read_text()
	assert 'field["rows"] = lines.shown' in source
	assert 'field["most"] = lines.MOST' in source


def test_the_submit_path_cleans_every_table():
	sending = PUBLIC.read_text().split("def send")[1]
	assert "lines.clean(doc, asked)" in sending


def test_table_multiselect_stays_out(lines):
	"""It looks like this and is not: every row is a Link, and resolving a Link
	against Guest is the one thing `LINKISH` says a public page cannot do."""
	from oneapp.oneforms import service

	assert "Table" not in service.NEVER
	assert "Table MultiSelect" in service.NEVER


def test_the_control_is_the_record_pages_own_grid():
	"""One table in this product. `ListBody` draws a screen's records with
	`RecordTable`, `ChildTable` draws the rows inside one record with it, and a
	public form is the third — so the tracks, the header, the scroller, the
	edges, the selection and the reordering are not written twice."""
	drawn = ROWS.read_text()
	assert "components/screen/bodies/RecordTable.vue" in drawn
	assert "lucide-plus" in drawn


def test_typing_an_answer_does_not_tick_the_row():
	"""A row in a selectable list toggles when it is clicked, and
	`RecordTable` lets a click on a control through rather than stopping it —
	so typing into a cell ticked its row, and the next press of Remove would
	have taken it out."""
	drawn = ROWS.read_text()
	# The element lines, not the comment above them explaining why.
	stops = [one.strip() for one in drawn.splitlines()
	         if one.strip() in ("@click.stop", "@click.stop>")
	         or one.strip().endswith('justify-end" @click.stop>')]
	assert len(stops) == 2


def test_a_row_hook_does_not_replace_the_one_frappe_ui_put_there():
	"""`rowProps` lands on `ListRowBase`'s root, which already carries
	`data-slot="list-row"` — and that is what `frappe-ui/list`'s structural CSS
	matches to make a row a grid. Writing `data-slot` there drew every row as
	one column with its cells stacked, silently."""
	drawn = ROWS.read_text()
	rows = drawn.split("const rowProps")[1]
	assert "'data-row'" in rows and "'data-slot'" not in rows


def test_a_new_row_carries_every_column_empty():
	"""`v-model` on a key that does not exist yet makes the row reactive only
	after the first keystroke, which loses that keystroke."""
	drawn = ROWS.read_text()
	assert "Object.fromEntries(props.field.rows.map" in drawn


def test_the_builder_chooses_which_columns_a_row_asks_for():
	"""A child doctype has columns for the staff who work it, and a page a
	stranger fills in is not that."""
	assert "builder-column-" in BUILDER.read_text()
	assert '"tables"' in SERVICE.read_text()


# --------------------------------------------------- a step skipped by an answer

def test_a_page_break_may_carry_a_condition():
	"""Stage 16's other half. One field watching another was stage 10; skipping
	a whole step is what makes a long form short."""
	layout = LAYOUT.read_text()
	assert "shown_when: when || null" in layout
	assert "export const walk" in layout

	saving = SERVICE.read_text().split("def layout")[1]
	assert 'fieldtype == "Page Break"' in saving


def test_only_a_page_break_carries_one():
	"""A heading that comes and goes while the fields under it stay is a
	heading that belongs to nothing."""
	saving = SERVICE.read_text().split("def layout")[1].split("\n@")[0]
	block = saving.split("if fieldtype in BREAKS:")[1].split("continue")[0]
	assert 'else ""' in block


def test_the_progress_bar_counts_the_steps_that_will_be_asked():
	"""A bar that counted steps nobody will see is a bar that never fills."""
	page = PAGE.read_text()
	assert "walk(pagesOf(shown.value), values, holds)" in page



def test_the_chosen_columns_are_not_kept_where_a_reader_sees_them(lines):
	"""`description` was the first home and the browser printed it: "item_name,
	qty, description" under the label, on the page somebody was filling in."""
	assert lines.COLUMNS == "custom_onespace_columns"
	assert "custom_onespace_columns" in (
		ROOT / "apps/oneapp/oneapp/install.py").read_text()

	saving = SERVICE.read_text().split("def layout")[1].split("\n@")[0]
	assert '"description"' not in saving


def test_the_child_doctype_comes_from_the_meta_and_never_the_browser():
	"""Same rule as `fieldtype` one line up: `options` on a Table names the
	child doctype, which is schema rather than presentation. It was read off
	the payload at first and arrived as `None`, so the page drew a row with no
	cells in it."""
	saving = SERVICE.read_text().split("def layout")[1].split("\n@")[0]
	assert '"options": field.get("options")' in saving
