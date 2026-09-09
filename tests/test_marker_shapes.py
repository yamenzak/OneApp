"""The map can only draw a silhouette it has a drawing for.

`Transit Marker Style.shape` is a Select, and a Select option is a promise: the
picker offers it, somebody chooses it, and the map then draws — a plain capsule,
silently, for ever, because `markers.js` has no such body and `bodyFor` falls
back rather than throwing. That failure is invisible on the screen where it
happens and correct-looking everywhere else.

Three lists have to agree and none of them can see the others: the outlines
drawn in the browser, the shapes the server will accept, and the options the
doctype offers. This is where they are held to it.
"""

import json
import re
from pathlib import Path

import where

ROOT = Path(where.__file__).resolve().parent.parent
STYLE = ROOT / (
    "apps/oneapp/oneapp/onemobility/doctype/transit_marker_style/transit_marker_style.json"
)


def drawn() -> set:
    """The keys of `BODIES` — every outline the browser can actually draw."""
    source = where.module_source("markers.js")
    block = re.search(r"const BODIES = \{(.*?)\n\}", source, re.S)
    assert block, "markers.js no longer declares BODIES as one object"
    return set(re.findall(r"^  (\w+):", block.group(1), re.M))


def test_the_server_only_accepts_shapes_the_browser_can_draw():
    # Read rather than imported: this suite runs without a bench, so importing
    # the module would pull in frappe and the guard would be skipped exactly
    # where it is needed.
    source = (ROOT / "apps/oneapp/oneapp/onemobility/markers.py").read_text()
    listed = re.search(r"^SHAPES = \((.*?)\)", source, re.S | re.M)
    assert listed, "markers.py no longer declares SHAPES as one tuple"
    assert set(re.findall(r'"(\w+)"', listed.group(1))) == drawn()


def test_the_picker_only_offers_shapes_the_browser_can_draw():
    field = next(
        one
        for one in json.loads(STYLE.read_text())["fields"]
        if one["fieldname"] == "shape"
    )
    offered = {one.strip().lower() for one in field["options"].split("\n") if one.strip()}
    assert offered == drawn()
