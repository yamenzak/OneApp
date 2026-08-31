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


# In Frappe's `no_value_fields` and placed in the map anyway, each for its own
# reason. Named one at a time so a fourth has to argue its case here.
NOT_LAYOUT = {
    # Both carry rows. The field holds nothing itself, but there is data behind
    # it and something to render.
    "Table",
    "Table MultiSelect",
    # Holds nothing and renders the *record's* attachments — Frappe's own
    # control reads the File rows and narrows them by the docfield's
    # `link_filters`. Layout renders nothing at all; this renders a gallery, so
    # treating it as layout meant it simply never appeared.
    "Attachment Gallery",
}


@needs_frappe
def test_layout_fields_are_the_ones_that_carry_no_value(spec):
    declared = frappe_tuple("no_value_fields")
    assert set(spec.LAYOUT_TYPES) == declared - NOT_LAYOUT


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


def barrel_exports() -> set[str]:
    """Every component name `@/ui` re-exports.

    Reads the export blocks rather than matching indented lines. The line-based
    version only saw the multi-line blocks, so a single-line
    `export { Editor } from 'frappe-ui/editor'` was invisible to it — and the
    guard below would then have reported a component that is exported as
    missing, or worse, passed a fieldtype whose control genuinely was not.
    """
    barrel = (ROOT / "apps/oneapp/frontend/src/ui.js").read_text()
    names = set()
    for block in re.findall(r"export\s*\{([^}]*)\}\s*from", barrel, re.S):
        # Comments first, and whole-line: the section headers sit *above* the
        # name they introduce, so splitting an entry on "//" and keeping the
        # left half throws away the name rather than the comment. That silently
        # hid every component under a header — which is most of them.
        block = re.sub(r"//[^\n]*", "", block)
        for entry in block.split(","):
            name = entry.strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                names.add(name)
    return names


def test_the_barrel_reader_finds_both_shapes():
    """If it stops finding one, the guard below passes by finding nothing."""
    exported = barrel_exports()
    assert "Button" in exported, "the multi-line blocks are no longer read"
    assert "Editor" in exported, "the single-line blocks are no longer read"


def test_a_named_control_is_in_the_barrel(spec):
    """A control that is not a FormControl type has to be a component we
    actually export, or the form renders nothing where a field should be."""
    exported = barrel_exports()

    # A control may also be one of ours. `AttachmentGallery` has no frappe-ui
    # counterpart — the library ships no carousel — so it lives beside the other
    # screen components, and the rule this guard exists for still holds: the
    # name has to resolve to something that actually renders.
    ours = {
        path.stem
        for path in (ROOT / "apps/oneapp/frontend/src/components/screen").glob("*.vue")
    }

    missing = [
        control for control, *_ in spec.FIELD_TYPES.values()
        if control and not control.startswith("FormControl:")
        # `Editor:html` and `Editor:markdown` are one component and a format.
        and control.split(":", 1)[0] not in exported | ours
    ]
    assert not missing, f"neither exported from @/ui nor a screen component: {missing}"


def test_every_editor_format_is_one_the_component_takes(spec):
    """`Editor` round-trips three formats and Frappe stores two of them. A
    format it does not declare is a prop that silently does nothing, which is
    the failure mode this whole table exists to prevent."""
    bad = [
        (fieldtype, control)
        for fieldtype, (control, *_rest) in spec.FIELD_TYPES.items()
        if control and control.startswith("Editor:")
        and control.split(":", 1)[1] not in spec.EDITOR_FORMATS
    ]
    assert not bad, f"not an Editor format: {bad}"


def test_the_editor_format_union_is_still_what_frappe_ui_declares(spec):
    """Read from the component rather than restated here, for the same reason
    the FormControl union is."""
    source = (
        ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src/molecules/editor/Editor.vue"
    )
    if not source.exists():
        pytest.skip("frappe-ui not installed")
    declared = set(
        re.findall(r"'(\w+)'", re.search(r"format\?\s*:\s*([^\n]+)", source.read_text()).group(1))
    )
    assert spec.EDITOR_FORMATS <= declared, (
        f"frappe-ui's Editor no longer takes {sorted(spec.EDITOR_FORMATS - declared)}"
    )


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
        "fields.controlComponent({ fieldtype: t }), "
        "fields.editorFormat({ fieldtype: t })]]))"
    )

    exported = barrel_exports()

    for fieldtype, (control_type, component, editor_format) in got.items():
        declared = spec.FIELD_TYPES[fieldtype][0]
        if declared is None:
            assert control_type is None and component is None, (
                f"{fieldtype} has no counterpart but the module offered one"
            )
            assert editor_format is None
        elif declared.startswith("FormControl:"):
            assert component is None
            assert control_type in spec.FORM_CONTROL_TYPES, (
                f"{fieldtype} resolves to type={control_type!r}, which FormControl "
                "does not know — it renders a plain text box and says nothing"
            )
            assert control_type == declared.split(":", 1)[1]
            assert editor_format is None
        elif declared.startswith("Editor:"):
            assert control_type is None
            assert component == "Editor", f"{fieldtype} resolves to {component!r}"
            assert component in exported
            assert editor_format == declared.split(":", 1)[1], (
                f"{fieldtype} would render the editor in {editor_format!r} and "
                "store something the field cannot hold"
            )
        else:
            assert control_type is None
            assert editor_format is None
            ours = {
                path.stem
                for path in (ROOT / "apps/oneapp/frontend/src/components/screen").glob("*.vue")
            }
            assert component in exported | ours, f"{fieldtype} resolves to {component!r}"


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


# --------------------------------------------------------------------------- #
# Filter operators, read out of Frappe's own filter UI
#
# The same trick as the fieldtype list, and for the same reason: this table was
# ported from `frappe/public/js/frappe/ui/filters/filter.js`, and a port is a
# copy that stops being true quietly. Frappe writes it as a deny list per
# fieldtype; we invert it, so a change on their side has to show up as a failure
# here rather than as a filter that offers an operator their query layer will
# reject — or, worse, one it will accept and we never meant to expose.
# --------------------------------------------------------------------------- #

FRAPPE_FILTER_JS = next(
    (p for p in (
        Path("/home/frappe/bench1/apps/frappe/frappe/public/js/frappe/ui/filters/filter.js"),
        ROOT.parent / "frappe/frappe/public/js/frappe/ui/filters/filter.js",
    ) if p.exists()),
    None,
)

FRAPPE_OPERATOR_MAP = next(
    (p for p in (
        Path("/home/frappe/bench1/apps/frappe/frappe/database/operator_map.py"),
        ROOT.parent / "frappe/frappe/database/operator_map.py",
    ) if p.exists()),
    None,
)

needs_filter_js = pytest.mark.skipif(
    FRAPPE_FILTER_JS is None, reason="no frappe checkout to read the filter UI from"
)


def frappe_conditions() -> list[str]:
    """The operators Frappe's own filter offers, in its order.

    Lowercased: its UI writes "Between" and "Timespan" and its query layer
    lowercases them (`_operator.lower()`), so the two spellings are one
    operator and the lower one is what goes on the wire.
    """
    source = FRAPPE_FILTER_JS.read_text()
    body = re.search(r"this\.conditions = \[(.*?)\n\t\t\];", source, re.S)
    assert body, "frappe's filter.js no longer declares `this.conditions` as a list"
    return [m.group(1).lower() for m in re.finditer(r'\["([^"]+)", __\(', body.group(1))]


@needs_filter_js
def test_every_operator_we_offer_is_one_frappes_filter_offers(spec):
    """Not merely one its query layer accepts: `regex`, `ilike` and the
    arithmetic operators are all in OPERATOR_MAP and none of them belong in
    front of a customer."""
    theirs = set(frappe_conditions())
    extra = set(spec.OPERATORS) - theirs
    assert not extra, f"not in frappe's own filter: {sorted(extra)}"


@needs_filter_js
def test_the_operator_order_is_frappes(spec):
    """The list reads as an ordered menu, and reordering it silently reorders
    every filter dropdown in the product."""
    theirs = [op for op in frappe_conditions() if op in spec.OPERATORS]
    assert list(spec.OPERATORS) == theirs


@pytest.mark.skipif(FRAPPE_OPERATOR_MAP is None, reason="no frappe checkout")
def test_every_operator_survives_the_query_layer(spec):
    """The other half: an operator the filter UI offers but `OPERATOR_MAP` does
    not know raises rather than filtering, at the point a customer clicks
    Apply."""
    source = FRAPPE_OPERATOR_MAP.read_text()
    body = re.search(r"^OPERATOR_MAP: dict\[str, Callable\] = \{(.*?)^\}", source, re.S | re.M)
    assert body, "frappe no longer declares OPERATOR_MAP as a dict literal"
    known = set(re.findall(r'^\t"([^"]+)":', body.group(1), re.M))

    unknown = set(spec.OPERATORS) - known
    assert not unknown, f"frappe's query layer has no such operator: {sorted(unknown)}"


@needs_filter_js
def test_the_per_fieldtype_deny_lists_match_frappes(spec):
    """Read Frappe's `invalid_condition_map` back and compare it to ours for the
    fieldtypes it names explicitly."""
    source = FRAPPE_FILTER_JS.read_text()
    body = re.search(r"this\.invalid_condition_map = \{(.*?)\n\t\t\};", source, re.S)
    assert body, "frappe's filter.js no longer declares `invalid_condition_map`"

    groups = {
        "range_conditions": set(spec._RANGE),
        "comparison_conditions": set(spec._COMPARISON),
        "like_conditions": set(spec._LIKE),
        "in_conditions": set(spec._IN),
        "equality_conditions": set(spec._EQUALITY),
    }
    # Read frappe's own group members rather than trusting that ours are the
    # same set — the names could stay and the contents change.
    for name, ours in groups.items():
        declared = re.search(rf"this\.{name} = \[([^\]]*)\]", source)
        assert declared, f"frappe's filter.js no longer declares {name}"
        theirs = {v.lower() for v in re.findall(r'"([^"]+)"', declared.group(1))}
        assert ours == theirs, f"{name}: frappe has {sorted(theirs)}, we have {sorted(ours)}"

    for fieldtype, expression in re.findall(
        r"^\t\t\t(\w+): (this\.\w+|\[[^\]]*\]),$", body.group(1), re.M
    ):
        theirs = set()
        for name in re.findall(r"this\.(\w+)", expression):
            assert name in groups, f"frappe's filter.js grew a group we do not have: {name}"
            theirs |= groups[name]

        ours = set(spec.OPERATORS) - set(spec.operators_for(fieldtype))
        assert ours == theirs, (
            f"{fieldtype}: frappe forbids {sorted(theirs)}, we forbid {sorted(ours)}"
        )


@needs_filter_js
def test_the_timespan_vocabulary_is_frappes(spec):
    """These strings are handed to Frappe's `timespan` operator verbatim, so one
    it does not know is a filter that returns nothing and explains nothing."""
    source = FRAPPE_FILTER_JS.read_text()
    theirs = set(re.findall(r'value: "((?:last|this|next|yesterday|today|tomorrow)[^"]*)"', source))
    ours = {value for value, _label in spec.TIMESPANS}
    assert ours == theirs, (
        f"added {sorted(ours - theirs)}, missing {sorted(theirs - ours)}"
    )


def test_every_fieldtype_that_can_be_a_column_can_be_filtered(spec):
    """Including the ones with no control. A Colour cannot be edited through a
    screen and can still be asked about.

    A child table is the exception, and it is not one: it is rows rather than a
    value, so it is never a column and never a filter either."""
    # The two child-table types are the exception, and they are not really one:
    # rows rather than a value, so Frappe needs a four-part filter naming the
    # child doctype and a three-part one names a column that is not there.
    rows_not_a_value = ("Table", "Table MultiSelect")
    for fieldtype in spec.FIELD_TYPES:
        if fieldtype in rows_not_a_value:
            assert not spec.operators_for(fieldtype), (
                f"{fieldtype} is rows in a child table and cannot be filtered"
            )
        else:
            assert spec.operators_for(fieldtype), f"{fieldtype} has no operators at all"


def test_a_fieldtype_frappe_never_classified_does_not_get_everything(spec):
    """Frappe's deny list gives a Signature or a Duration every operator,
    because nothing names them. Timespan on a signature is not a question."""
    for fieldtype in ("Signature", "Geolocation", "Icon"):
        assert set(spec.operators_for(fieldtype)) == {"=", "!=", "is"}, fieldtype
    for fieldtype in ("Duration", "Long Int", "Slider"):
        assert "timespan" not in spec.operators_for(fieldtype), fieldtype
        assert "between" not in spec.operators_for(fieldtype), fieldtype


def test_only_a_date_gets_the_date_operators(spec):
    """Which is Frappe's own answer once `set_fieldtype` has run: a Phone or an
    Attach is a Data box by the time the operator menu is built."""
    for fieldtype in spec.FIELD_TYPES:
        if "between" in spec.operators_for(fieldtype):
            assert fieldtype in ("Date", "Datetime"), fieldtype


def test_an_unknown_fieldtype_gets_the_narrow_set(spec):
    """A deny list gives a fieldtype nobody thought about every operator. This
    is an allow list precisely so the answer is the other way round."""
    assert set(spec.operators_for("Something Frappe Added")) == {"=", "!=", "is"}


def test_the_default_operator_is_always_one_of_the_offered(spec):
    """Otherwise a new filter opens on an operator its own dropdown does not
    contain, and the first change resets the value."""
    for fieldtype in spec.FIELD_TYPES:
        allowed = spec.operators_for(fieldtype)
        default = spec.default_operator(fieldtype)
        if not allowed:
            assert default == "", f"{fieldtype} cannot be filtered but has a default operator"
        else:
            assert default in allowed, fieldtype


def test_every_operator_has_a_value_shape(spec):
    for fieldtype in spec.FIELD_TYPES:
        for operator in spec.operators_for(fieldtype):
            shape = spec.value_shape(fieldtype, operator)
            assert shape in ("choice", "set", "timespan", "range", "multi", "link", "value"), (
                f"{fieldtype} {operator} -> {shape}"
            )


@needs_filter_js
def test_the_text_and_numeric_groups_match_frappes(spec):
    """These reach `invalid_condition_map` through a spread rather than a line
    of their own, so the scan above cannot see them."""
    source = FRAPPE_FILTER_JS.read_text()
    for name, ours in (("text_fields", spec._TEXT_FIELDS),
                       ("numeric_fields", spec._NUMERIC_FIELDS)):
        declared = re.search(rf"const {name} = \[(.*?)\];", source, re.S)
        assert declared, f"frappe's filter.js no longer declares {name}"
        theirs = set(re.findall(r'"([^"]+)"', declared.group(1)))
        assert set(ours) == theirs, (
            f"{name}: frappe has {sorted(theirs)}, we have {sorted(ours)}"
        )


@needs_filter_js
def test_the_fieldtype_rewrite_is_frappes(spec):
    """`set_fieldtype` turns a Phone, an Attach and a Barcode into a Data box
    before the operator menu is built, and that rewrite is what decides which
    operators they get. Ported, so read it back."""
    source = FRAPPE_FILTER_JS.read_text()
    body = re.search(r'\t\t\t\[\n((?:\t+"[A-Za-z ]+",\n)+)\t\t\t\]\.indexOf\(df\.fieldtype\)', source)
    assert body, "frappe's filter.js no longer scrubs a list of fieldtypes to Data"
    theirs = set(re.findall(r'"([^"]+)"', body.group(1)))

    # Frappe scrubs a few fieldtypes we do not have at all (Tag, Comments,
    # Assign are desk-only) and a few it names in the deny list anyway, where
    # the original type wins and the rewrite never applies.
    ours = {f for f, stand_in in spec._AS_IF.items() if stand_in == "Data"}
    unhandled = (theirs & set(spec.FIELD_TYPES)) - ours - set(spec._INVALID)
    assert not unhandled, (
        f"frappe rewrites these to Data before choosing operators and we do not: "
        f"{sorted(unhandled)}"
    )


# --------------------------------------------------------------------------- #
# Prose and source are different questions
# --------------------------------------------------------------------------- #

def test_prose_goes_to_the_editor_and_source_goes_to_the_code_editor(spec):
    """The distinction most easily got backwards.

    Frappe's `Text Editor` and `Markdown Editor` hold prose somebody wrote in a
    formatting UI. `HTML Editor` holds markup somebody wrote *as* markup — it is
    Frappe's source editor, and putting it in a rich editor would silently
    rewrite the markup it exists to let people control. `Code` and `JSON` are
    the same kind of thing.
    """
    control = {t: spec.FIELD_TYPES[t][0] for t in (
        "Text Editor", "Markdown Editor", "HTML Editor", "Code", "JSON",
    )}
    assert control["Text Editor"] == "Editor:html"
    assert control["Markdown Editor"] == "Editor:markdown"
    assert control["HTML Editor"] == "CodeEditor"
    assert control["Code"] == "CodeEditor"
    assert control["JSON"] == "CodeEditor"


def test_no_prose_or_source_type_is_a_textarea_any_more(spec):
    """The regression this batch existed to fix: five fieldtypes rendered as
    plain textareas, so a paragraph typed into a Text Editor field saved as
    text into a column the rest of Frappe renders as HTML."""
    plain = [
        fieldtype for fieldtype in
        ("Text Editor", "Markdown Editor", "HTML Editor", "Code", "JSON")
        if (spec.FIELD_TYPES[fieldtype][0] or "").startswith("FormControl:")
    ]
    assert not plain, f"still a textarea: {plain}"


def test_the_plain_text_types_are_still_textareas(spec):
    """And the ones that should be. Small Text and Long Text hold text with no
    formatting at all; an editor over one would invent markup nobody asked
    for."""
    for fieldtype in ("Small Text", "Text", "Long Text"):
        assert spec.FIELD_TYPES[fieldtype][0] == "FormControl:textarea"
