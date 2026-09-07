"""The marks a Space may name, read back from what the generator wrote.

Read rather than listed, so a mark added to `scripts/brand/marks.source.html`
is selectable the moment `scripts/gen_brand.py` has run — and so a mark taken
out cannot go on being selectable after the drawing it named is gone.
"""

import json
from pathlib import Path

MARKS_JSON = Path(__file__).resolve().parent / "brand" / "marks.json"

BRAND_MARKS = tuple(
	mark["id"] for mark in json.loads(MARKS_JSON.read_text(encoding="utf-8"))
)
