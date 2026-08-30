"""Every Frappe fieldtype has somewhere to go.

Read out of Frappe's own `frappe/model/__init__.py` rather than copied, because
a copy is a list that stops being true quietly. The failure this prevents is
specific: a fieldtype nobody placed renders as a plain text box, and a text box
over a Currency column saves a string into it.

Skipped when there is no frappe checkout to read — CI has one, a laptop may not.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FRAPPE_MODEL = next(
    (p for p in (
        Path("/home/frappe/bench1/apps/frappe/frappe/model/__init__.py"),
        ROOT.parent / "frappe/frappe/model/__init__.py",
    ) if p.exists()),
    None,
)


@pytest.fixture
def spec():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import field_types

    return field_types


def frappe_tuple(name: str) -> set[str]:
    """Read one tuple literal out of frappe's model module."""
    source = FRAPPE_MODEL.read_text()
    # Some are written across lines, some on one. Match to the closing paren
    # either way rather than assuming the formatting holds.
    body = re.search(rf"^{name} = \((.*?)\)", source, re.S | re.M)
    assert body, f"{name} is no longer a tuple literal in frappe/model/__init__.py"
    return set(re.findall(r'"([^"]+)"', body.group(1)))


needs_frappe = pytest.mark.skipif(
    FRAPPE_MODEL is None, reason="no frappe checkout to read fieldtypes from"
)


@needs_frappe
def test_every_data_fieldtype_is_placed(spec):
    """The one that matters. A fieldtype we have not placed is a field that
    renders as text and writes the wrong shape."""
    declared = frappe_tuple("data_fieldtypes")
    missing = declared - set(spec.FIELD_TYPES)

    assert not missing, (
        "Frappe has fieldtypes this does not handle, so they would render as "
        "plain text boxes: " + ", ".join(sorted(missing)) +
        "\nAdd them to scripts/field_types.py."
    )


@needs_frappe
def test_nothing_is_placed_that_frappe_does_not_have(spec):
    """The converse: an entry for a fieldtype that no longer exists is a rule
    nobody will ever hit, and reads as though it is doing something."""
    declared = frappe_tuple("data_fieldtypes") | frappe_tuple("no_value_fields")
    # Slider is ours: frappe-ui has the component and a Percent or Int field can
    # opt into it, but Frappe has no such fieldtype.
    invented = set(spec.FIELD_TYPES) - declared - {"Slider"}

    assert not invented, f"these are not Frappe fieldtypes: {sorted(invented)}"


@needs_frappe
def test_layout_fields_are_the_ones_that_carry_no_value(spec):
    declared = frappe_tuple("no_value_fields")
    # Table and Table MultiSelect are in frappe's no_value_fields but do carry
    # rows, so they are placed in the map rather than treated as layout.
    assert set(spec.LAYOUT_TYPES) == declared - {"Table", "Table MultiSelect"}


@needs_frappe
def test_the_data_field_options_match_frappes(spec):
    assert set(spec.DATA_OPTIONS) == frappe_tuple("data_field_options")


# --------------------------------------------------------------------------- #
# Against frappe-ui rather than against Frappe
# --------------------------------------------------------------------------- #

def test_every_control_is_a_real_form_control_type(spec):
    """`FormControl` falls through to a TextInput for a type it does not know,
    with nothing logged. A date field silently becoming a text box is exactly
    the kind of thing that survives a review."""
    wrong = [
        (fieldtype, control)
        for fieldtype, (control, *_rest) in spec.FIELD_TYPES.items()
        if control and control.startswith("FormControl:")
        and control.split(":", 1)[1] not in spec.FORM_CONTROL_TYPES
    ]
    assert not wrong, f"not in frappe-ui's FormControl type union: {wrong}"


def test_the_form_control_union_is_still_what_frappe_ui_declares(spec):
    """Pinned against the library rather than remembered. When frappe-ui adds
    or drops a type, this is what says so."""
    types_file = (ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src"
                  / "components/FormControl/types.ts")
    text_input = (ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src"
                  / "components/types/TextInput.ts")
    if not types_file.exists():
        pytest.skip("frappe-ui is not installed")

    declared = set(re.findall(r"'([a-z-]+)'", types_file.read_text()))
    declared |= set(re.findall(r"'([a-z-]+)'", text_input.read_text()))
    # `sm`/`md`/`subtle`/`outline` are the size and variant unions in the same file.
    declared -= {"sm", "md", "subtle", "outline"}

    assert spec.FORM_CONTROL_TYPES == declared, (
        "frappe-ui's FormControl types changed: "
        f"added {sorted(declared - spec.FORM_CONTROL_TYPES)}, "
        f"removed {sorted(spec.FORM_CONTROL_TYPES - declared)}"
    )


def test_a_named_control_is_in_the_barrel(spec):
    """A control that is not a FormControl type has to be a component we
    actually export, or the form renders nothing where a field should be."""
    barrel = (ROOT / "apps/oneapp/frontend/src/ui.js").read_text()
    exported = set(re.findall(r"^  ([A-Z]\w+),", barrel, re.M))

    missing = [
        control for control, *_ in spec.FIELD_TYPES.values()
        if control and not control.startswith("FormControl:") and control not in exported
    ]
    assert not missing, f"not exported from @/ui: {missing}"


def test_a_field_with_no_control_is_not_editable(spec):
    """Colour, signature, geolocation. Shown, never offered — a control that
    cannot produce the right shape is worse than no control."""
    for fieldtype, (control, _cell, _icon, editable) in spec.FIELD_TYPES.items():
        if control is None:
            assert not editable, f"{fieldtype} has no control but claims to be editable"


def test_every_field_has_an_icon(spec):
    """List headers and the record dialog both render one, and a blank where an
    icon belongs is worse than a generic one."""
    for fieldtype, (_control, _cell, icon, _editable) in spec.FIELD_TYPES.items():
        assert icon and icon.startswith("lucide-"), f"{fieldtype} has no icon"


def test_state_colours_are_frappe_ui_badge_themes(spec):
    """DocType State's palette is Frappe's; Badge's is frappe-ui's. This is the
    join, and a theme Badge does not know renders uncoloured."""
    themes = {"gray", "blue", "green", "orange", "red", "amber", "violet",
              "teal", "pink", "black"}
    unknown = set(spec.STATE_COLORS.values()) - themes
    assert not unknown, f"not Badge themes: {sorted(unknown)}"

    for theme, _words in spec.WORD_COLORS:
        assert theme in themes, f"{theme} is not a Badge theme"


# --------------------------------------------------------------------------- #
# The generated module, not the table it was generated from
#
# Everything above checks scripts/field_types.py. The bug that got through was
# not in the table: the generated helper stripped the "FormControl:" prefix with
# a hand-counted offset that was one too many, so every type lost its first
# letter — "date" became "ate". FormControl answers a type it does not know with
# a plain TextInput and logs nothing, so the whole record dialog rendered as
# text boxes and every check above still passed. So run the real module.
# --------------------------------------------------------------------------- #

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

NODE = shutil.which("node") or next(
    (p for p in ("/opt/node24/bin/node", "/opt/node22/bin/node") if Path(p).exists()), None
)

needs_node = pytest.mark.skipif(NODE is None, reason="no node to run the generated module")


def run_fields_js(body: str):
    """Evaluate an expression against the generated fields.js and read it back."""
    module = ROOT / "apps/oneapp/frontend/src/lib/fields.js"
    script = (
        f"import * as fields from {json.dumps(str(module))}\n"
        f"console.log(JSON.stringify({body}))\n"
    )
    out = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


@needs_node
def test_the_generated_helpers_return_real_control_types(spec):
    """Every fieldtype, through the module the SPA actually imports."""
    got = run_fields_js(
        "Object.fromEntries(Object.keys(fields.FIELD_TYPES).map((t) => "
        "[t, [fields.formControlType({ fieldtype: t }), "
        "fields.controlComponent({ fieldtype: t })]]))"
    )

    barrel = (ROOT / "apps/oneapp/frontend/src/ui.js").read_text()
    exported = set(re.findall(r"^  ([A-Z]\w+),", barrel, re.M))

    for fieldtype, (control_type, component) in got.items():
        declared = spec.FIELD_TYPES[fieldtype][0]
        if declared is None:
            assert control_type is None and component is None, (
                f"{fieldtype} has no counterpart but the module offered one"
            )
        elif declared.startswith("FormControl:"):
            assert component is None
            assert control_type in spec.FORM_CONTROL_TYPES, (
                f"{fieldtype} resolves to type={control_type!r}, which FormControl "
                "does not know — it renders a plain text box and says nothing"
            )
            assert control_type == declared.split(":", 1)[1]
        else:
            assert control_type is None
            assert component in exported, f"{fieldtype} resolves to {component!r}"


@needs_node
def test_a_data_field_is_refined_by_its_options(spec):
    """Email, Phone, URL. The browser has a better keyboard for each, and the
    refinement runs through the same prefix-stripping the bug lived in."""
    got = run_fields_js(
        "Object.fromEntries(Object.keys(fields.DATA_OPTIONS).map((o) => "
        "[o, fields.formControlType({ fieldtype: 'Data', options: o })]))"
    )
    assert got == dict(spec.DATA_OPTIONS), got
    for control_type in got.values():
        assert control_type in spec.FORM_CONTROL_TYPES


@needs_node
def test_an_unknown_fieldtype_falls_back_to_something_real():
    """Frappe adds a fieldtype; this site has it before we do. It must not
    become an editable control of a shape we cannot write."""
    got = run_fields_js(
        "[fields.fieldSpec({ fieldtype: 'Something New' }), "
        "fields.formControlType({ fieldtype: 'Something New' })]"
    )
    spec_out, control_type = got
    assert spec_out["editable"] is False
    assert control_type == "text"


@needs_frappe
def test_frappes_bookkeeping_is_all_reserved():
    """`RESERVED` is written out by hand, so it drifts the moment Frappe adds a
    field to `default_fields` — and the field it adds becomes a column a
    customer can see and a control they can write."""
    import sys

    sys.path.insert(0, str(ROOT / "apps/oneapp"))
    from oneapp.oneapp_core import fieldtypes

    declared = frappe_tuple("default_fields") | frappe_tuple("optional_fields")
    missing = declared - set(fieldtypes.RESERVED)
    assert not missing, (
        "Frappe keeps these on every document and a customer reading one is "
        f"always an accident: {sorted(missing)}"
    )
