"""A field that is a whole application opens the application.

`docs/CLEANUP.md` stage 12: the code editor is OneCode, prose is OneWriter,
a child table is OneWorkbook. **All three were already built when the stage
came up**, and this file is what was actually missing — a rule that keeps them
that way.

The thing being prevented is small and happens by itself. A field type whose
editor is an embedded application has two halves: the inline control, which has
to be small enough to sit in a form, and the door to the product that does the
job properly. The inline half is where every feature request lands, and the
door is one button that nothing fails without. So doors rot: they get renamed,
they lose their `data-slot`, they get dropped in a refactor of the row they sit
in, and the field quietly becomes its own editor again.

Four families, and the fourth is the one the plan did not name:

    Code, JSON, HTML Editor      CodeEditor      → OneCode
    Text Editor, Markdown Editor Editor          → OneWriter
    Table                        ChildTable      → OneWorkbook
    Attach, Attach Image,        FilePicker      → OneCloud
    Attachment Gallery

The attach family is different in kind and is the reason it was missed:
the other three *embed* a foreign editor and offer a door out, and this one has
no inline editor at all — the control **is** OneCloud's picker. That is the end
state the other three are heading for, so it is here as the example rather than
as an exception.
"""

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPA = ROOT / "apps/oneapp/frontend/src"
FIELDS_JS = SPA / "modules/onespace/lib/screen/fields.js"
CONTROL = SPA / "modules/onespace/components/screen/fields/FieldControl.vue"
CHILD_TABLE = SPA / "modules/onespace/components/screen/record/ChildTable.vue"
GALLERY = SPA / "modules/onespace/components/screen/record/AttachmentGallery.vue"


def _controls() -> dict[str, str]:
	"""Fieldtype to the control that draws it, off `fields.js`'s own table.

	Parsed out of the JSON-ish literal rather than imported, because this is a
	Python test reading a JS module — and the table is written as a plain
	object precisely so it can be read this way.
	"""
	source = FIELDS_JS.read_text()
	found = {}
	for match in re.finditer(
			r'^\s{2}"([^"]+)":\s*\{(.*?)^\s{2}\},', source, re.S | re.M):
		control = re.search(r'"control":\s*"([^"]*)"', match.group(2))
		if control:
			# `Editor:html` and `Editor:markdown` are one component storing
			# two formats — `fields.js` says so in its own comment.
			found[match.group(1)] = control.group(1).split(":")[0]
	return found


CONTROLS = _controls()

OPEN_IN_SHEET = SPA / "modules/onesheet/components/OpenInSheet.vue"

#: The control, the module that owns the product behind it, the `data-slot` of
#: the door, where the control is drawn, and where the door itself lives.
#:
#: A slot rather than a label because the slot is what a browser spec selects
#: on, so renaming it is the change this catches.
#:
#: The last two are the same file for two of the three and not for the child
#: table, whose door is a component of OneWorkbook's own — which is the better
#: shape and the reason this rule is two assertions rather than one: the
#: control has to reach the door, and the door has to be the door.
SERVED = {
	"CodeEditor": ("onecode", "open-in-code", CONTROL, CONTROL),
	"Editor": ("onedoc", "open-in-doc", CONTROL, CONTROL),
	"ChildTable": ("onesheet", "open-in-sheet", CHILD_TABLE, OPEN_IN_SHEET),
}

#: The fourth family. No door because there is no inline editor to leave — the
#: control is the service's own picker, and the record's Files tab is the one
#: door, on the record rather than on each field. A second door per attach
#: field would be `docs/UNIFICATION.md` F1 in miniature: the same sentence in
#: three places, drifting.
PICKED = {
	"FileUploader": ("onestorage", CONTROL),
	"AttachmentGallery": ("onestorage", GALLERY),
}


def test_the_reader_found_the_table():
	"""A regex that matches nothing turns every rule below into a pass."""
	assert len(CONTROLS) >= 25, len(CONTROLS)
	assert CONTROLS.get("Code") == "CodeEditor"
	assert CONTROLS.get("Text Editor") == "Editor"
	assert CONTROLS.get("Markdown Editor") == "Editor"
	assert CONTROLS.get("Table") is None or CONTROLS.get("Table") == "ChildTable"


@pytest.mark.parametrize("control", sorted(SERVED))
def test_an_embedded_editor_has_a_door(control):
	"""One button, and nothing fails without it — which is why it needs this."""
	brand, slot, drawn, door = SERVED[control]
	source = door.read_text()
	assert f'slot-name="{slot}"' in source, (
		f"{door.name} no longer opens {control} in {brand}: the "
		f"{slot!r} door is gone"
	)
	assert f'brand="{brand}"' in source, (
		f"{door.name}'s door no longer names {brand}"
	)
	if door is not drawn:
		assert door.stem in drawn.read_text(), (
			f"{drawn.name} no longer reaches {door.name}, so the door exists "
			f"and nothing opens it"
		)


@pytest.mark.parametrize("control", sorted(SERVED))
def test_the_door_leads_where_it_says(control):
	"""A door wearing OneCode's mark and opening somebody else's dialog is
	worse than no door. The dialog has to come out of that module."""
	brand, _slot, drawn, _door = SERVED[control]
	source = drawn.read_text()
	assert f"@/modules/{brand}/" in source, (
		f"{drawn.name} wears {brand}'s mark and imports nothing from it"
	)


@pytest.mark.parametrize("control", sorted(PICKED))
def test_a_picked_field_is_the_services_own_control(control):
	"""No door, because there is nothing to leave: the control *is* OneCloud's
	picker. `attached-to` is what makes the file belong to the record rather
	than land loose in the drive, and a field that dropped it would look
	identical and orphan every attachment."""
	brand, where = PICKED[control]
	source = where.read_text()
	assert f"@/modules/{brand}/components/FilePicker.vue" in source, (
		f"{where.name} no longer attaches through {brand}'s picker"
	)
	assert "attached-to" in source or ":attached-to" in source, (
		f"{where.name} picks a file without saying what it belongs to"
	)


def test_no_field_type_has_an_editor_with_nowhere_to_go():
	"""The completeness direction, and the whole point of the file.

	Every control named in `fields.js` is either a widget — a switch, a rating,
	a duration — or an application. The applications are `SERVED` and `PICKED`.
	A new one is a field type that has quietly grown its own editor, and it
	fails here rather than being noticed by somebody wondering why a code field
	in one space opens OneCode and one in another does not.
	"""
	#: Controls that are a widget rather than an application: one input, no
	#: product behind it, nothing for a service to own.
	WIDGETS = {
		"Combobox", "Duration", "MultiSelect", "Password", "Rating", "Switch",
		"Slider", "LinkPicker", "IconPicker", "TagControl", "AssignControl",
		"ShareControl", "StateBadge",
		# frappe-ui's own, which is what most of the table resolves to: a text
		# box, a number, a date. `fields.js` names it where a `FormControl`
		# `type` is not enough on its own.
		"FormControl",
	}
	known = set(SERVED) | set(PICKED) | WIDGETS
	found = {one for one in CONTROLS.values() if one}
	assert found <= known, (
		f"these field types draw a control nothing owns: {sorted(found - known)}"
	)


def test_the_five_with_no_editor_are_still_five():
	"""Colour, signature, geolocation, barcode and icon are shown and never
	offered — `FieldControl.vue` says why, and it is the honest answer while
	frappe-ui has no picker for any of them.

	Pinned because two of the five have an owner waiting: a geolocation is a
	map and OneMobility draws maps, and a signature is OneSignature, which is
	drawn in `marks.json` and not built. A sixth joining this list is a field
	type somebody gave up on; a fourth leaving it is this stage continuing.
	"""
	source = CONTROL.read_text()
	block = source[source.index("v-else-if=\"!controlType\""):]
	block = block[:block.index("</div>", block.index("</div>") + 1)]
	for fieldtype in ("Color", "Signature", "Geolocation", "Barcode"):
		assert f"'{fieldtype}'" in block, f"{fieldtype} left the unoffered set"
	assert CONTROLS.get("Color") in (None, ""), (
		"Color now has a control, which is stage 12 continuing — move it out "
		"of this rule and say which service owns it"
	)


def test_the_doors_all_use_the_one_button():
	"""Three copies of one sentence is three places for the wording, the mark
	or the weight to drift, and they had already drifted once —
	`OpenIn.vue` says so. This is that argument kept."""
	for _control, (_brand, _slot, _drawn, door) in SERVED.items():
		source = door.read_text()
		assert "shared/components/brand/OpenIn.vue" in source, (
			f"{door.name} hand-rolls its own door"
		)
