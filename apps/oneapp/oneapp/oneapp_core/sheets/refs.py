"""A1 notation, and nothing else.

Pure functions over strings and integers: no Frappe, no database, no document.
That is deliberate. Reference arithmetic is where a spreadsheet is most easily
and most quietly wrong — `Z` to `AA`, a range whose corners arrive the wrong way
round, a row zero — and a module with no dependencies is one a test can hammer.

Columns are 1-based, like rows and like every spreadsheet anybody has used.
`A` is 1. The temptation to make them 0-based dies the first time a stack trace
has to be read next to a screenshot of the grid.
"""

import re

# `A1`, `AA10`, and the `$` an absolute reference carries. The dollars are
# parsed and dropped: what a cell is *called* does not change when a formula
# freezes it, and the freezing matters only when a formula is copied — which is
# the browser's problem, in `formula-adjust`, not the store's.
CELL = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]{0,6})$")

# The bounds a grid is allowed to have. Not the spreadsheet's limits — ours.
# See `docs/SHEETS.md` §7: a row per cell is the right shape for the read-back
# and the wrong shape for a million of them, so the cap is a number picked on
# purpose rather than discovered when somebody pastes a CSV.
MAX_COLUMN = 702      # ZZ
MAX_ROW = 100_000
MAX_CELLS = 20_000    # per sheet, counted across every tab


class BadRef(ValueError):
    """A reference that is not one. Caught at the edge and shown on the cell."""


def column_number(letters: str) -> int:
    """`A` → 1, `Z` → 26, `AA` → 27.

    Base-26 with no zero, which is the whole trick and the reason this is not
    `int(letters, 26)`: there is no digit worth nothing, so `AA` is 1×26 + 1
    rather than 0×26 + 1.
    """
    if not letters:
        raise BadRef("a column needs a letter")
    total = 0
    for char in letters.upper():
        if not "A" <= char <= "Z":
            raise BadRef(f"{letters!r} is not a column")
        total = total * 26 + (ord(char) - 64)
    return total


def column_letters(number: int) -> str:
    """1 → `A`, 27 → `AA`. The inverse, and tested as one."""
    if number < 1:
        raise BadRef(f"there is no column {number}")
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def parse(ref: str) -> tuple[int, int]:
    """`B3` → `(3, 2)`, as `(row, column)`.

    Row first, because every loop over a grid is rows-then-columns and a tuple
    that reads the other way round is a transposition waiting to happen.
    """
    matched = CELL.match((ref or "").strip())
    if not matched:
        raise BadRef(f"{ref!r} is not a cell reference")
    column = column_number(matched.group(1))
    row = int(matched.group(2))
    if column > MAX_COLUMN or row > MAX_ROW:
        raise BadRef(f"{ref!r} is outside the grid")
    return row, column


def format(row: int, column: int) -> str:
    """`(3, 2)` → `B3`."""
    if row < 1:
        raise BadRef(f"there is no row {row}")
    return f"{column_letters(column)}{row}"


def parse_range(ref: str) -> tuple[int, int, int, int]:
    """`A1:C10` → `(top, left, bottom, right)`.

    A single cell is a range of one, so a caller never has to ask which it was
    given. And the corners are sorted: `C10:A1` is the same rectangle as
    `A1:C10`, which is what a person who dragged upwards means and what a
    stored range that was edited by hand often says.
    """
    text = (ref or "").strip()
    if ":" not in text:
        row, column = parse(text)
        return row, column, row, column

    start, _, end = text.partition(":")
    top, left = parse(start)
    bottom, right = parse(end)
    return min(top, bottom), min(left, right), max(top, bottom), max(left, right)


def format_range(top: int, left: int, bottom: int, right: int) -> str:
    return f"{format(top, left)}:{format(bottom, right)}"


def cells_in(ref: str) -> list[str]:
    """Every cell of a range, reading order.

    Bounded by `MAX_CELLS`, because `A1:ZZ100000` is a valid-looking string and
    an unbounded list comprehension is how one of those becomes an outage.
    """
    top, left, bottom, right = parse_range(ref)
    size = (bottom - top + 1) * (right - left + 1)
    if size > MAX_CELLS:
        raise BadRef(f"{ref} is {size:,} cells, and the limit is {MAX_CELLS:,}")
    return [
        format(row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
    ]


def within(ref: str, area: str) -> bool:
    """Whether one cell falls inside a rectangle. What a named range is for."""
    try:
        row, column = parse(ref)
    except BadRef:
        return False
    top, left, bottom, right = parse_range(area)
    return top <= row <= bottom and left <= column <= right


def grid(rows: dict[str, object], area: str) -> list[list[object]]:
    """A `{ref: value}` map, shaped into the rectangle `area` names.

    Absent cells are `None` rather than missing, so every row is the same
    length and the caller can index without checking. That is what makes the
    read-back's "first row is the headers" a safe sentence.
    """
    top, left, bottom, right = parse_range(area)
    return [
        [rows.get(format(row, column)) for column in range(left, right + 1)]
        for row in range(top, bottom + 1)
    ]
