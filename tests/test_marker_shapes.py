"""The map can only draw a silhouette it has a drawing for.

`Transit Marker Style.shape` is a Select, and a Select option is a promise: the
picker offers it, somebody chooses it, and the map then draws — nothing, or a
plain capsule, silently and for ever, because the lookup falls back rather than
throwing. That failure is invisible on the screen where it happens and
correct-looking everywhere else.

Four things have to agree and none of them can see the others: the SVG files,
the shapes the server will accept, the options the doctype offers, and the
glyph each one wears. This is where they are held to it.

The last two tests are about the drawings themselves. Every constraint they
check is one a well-meaning edit breaks silently: a second `#00FF00` and half
the vehicle stops carrying occupancy; a `<text>` element and the icon renders
differently on a machine without that font; a `width` on the root and the
rasteriser draws it at the wrong size.
"""

import json
import re
from pathlib import Path

import where

ROOT = Path(where.__file__).resolve().parent.parent
ART = ROOT / "apps/oneapp/frontend/src/modules/onemobility/art"
SERVER = ROOT / "apps/oneapp/oneapp/onemobility/markers.py"
STYLE = ROOT / (
    "apps/oneapp/oneapp/onemobility/doctype/transit_marker_style/transit_marker_style.json"
)

#: The only colours a drawing may use. `#00FF00` is the placeholder the body
#: wears until it is given an occupancy; the rest are the neutral greys that
#: have to read on top of any body colour from green to deep red.
INKS = {"#ffffff", "#e5e7eb", "#9ca3af", "#4b5563", "#1f2937", "#00ff00", "none"}

#: Things that make a drawing render differently somewhere else, or not at all.
BANNED = ("linearGradient", "radialGradient", "<filter", "<mask", "<text",
          "<style", "<image", "clipPath", "url(")


def drawn() -> set:
    """Every shape there is a file for."""
    return {one.stem for one in ART.glob("*.svg")}


def listed(name: str, source: str) -> set:
    """A python tuple of strings, read rather than imported.

    This suite runs without a bench, so importing the module would pull in
    frappe and the guard would be skipped exactly where it is needed.
    """
    block = re.search(rf"^{name} = \((.*?)\n\)", source, re.S | re.M)
    assert block, f"markers.py no longer declares {name} as one tuple"
    return set(re.findall(r'"([^"]+)"', block.group(1)))


def option(field: str) -> set:
    found = next(
        one for one in json.loads(STYLE.read_text())["fields"] if one["fieldname"] == field
    )
    return {one.strip() for one in found["options"].split("\n") if one.strip()}


def test_the_server_only_accepts_shapes_there_is_a_drawing_for():
    assert listed("SHAPES", SERVER.read_text()) == drawn()


def test_the_picker_only_offers_shapes_there_is_a_drawing_for():
    assert option("shape") == drawn()


def test_every_shape_has_a_glyph():
    """A shape and its emoji are the same vehicle, or the key lies about one."""
    source = SERVER.read_text()
    block = re.search(r"^DEFAULT_EMOJI = \{(.*?)\n\}", source, re.S | re.M)
    assert block, "markers.py no longer declares DEFAULT_EMOJI as one dict"
    assert {one for one in re.findall(r'"([^"]+)":', block.group(1))} == drawn()


def test_every_drawing_can_be_recoloured_and_rotated():
    for one in sorted(ART.glob("*.svg")):
        svg = one.read_text()
        # A 40x40 box with no intrinsic size: the rasteriser picks the size, and
        # a `width` on the root would win over it.
        assert 'viewBox="0 0 40 40"' in svg, one.name
        assert not re.search(r"<svg[^>]*\s(width|height)=", svg), one.name
        # Exactly one body, or only part of the vehicle carries occupancy.
        assert len(re.findall(r"#00FF00", svg, re.I)) == 1, one.name


def test_every_drawing_renders_the_same_everywhere():
    for one in sorted(ART.glob("*.svg")):
        svg = one.read_text()
        for banned in BANNED:
            assert banned not in svg, f"{one.name} uses {banned}"
        inks = {found.lower() for found in re.findall(r'(?:fill|stroke)="([^"]+)"', svg)}
        assert not inks - INKS, f"{one.name} uses {sorted(inks - INKS)}"
