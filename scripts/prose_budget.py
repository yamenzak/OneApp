#!/usr/bin/env python3
"""Rewrite `tests/prose_budget.txt` from what the screens now say.

Run it after *cutting* prose, never after adding: the file is a ratchet, and
the guard that reads it exists to make the direction one-way. The header it
writes says why a flat cap would be the wrong instrument.
"""

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from copy_reader import visible  # noqa: E402

WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
#: Below this a string is a label, not prose.
PROSE_FROM = 9
#: A screen carrying less than this is not stacking anything.
FLOOR = 60

HEADER = """\
# How much prose each screen carries, and a ratchet on it.
#
# One line of orientation per screen and one line of help per control is the
# rule. The hard part is that every individual sentence on a stacked settings
# panel passes review and twelve of them is a manual — so the thing to hold is
# the total, not the sentence.
#
# A flat cap would be the wrong instrument: several of the files below hold
# mutually exclusive branches of one message, where no reader ever sees more
# than one, and a cap would push somebody to split the file rather than
# shorten the screen. So this is a ratchet instead — the number measured on
# the day the rule landed, which may only go down.
#
# Words, counted across visible strings of nine words or more, for every file
# over sixty. Regenerate with scripts/prose_budget.py after cutting, never
# after adding. tests/test_ui_copy.py reads it.
"""


def measured() -> dict[str, int]:
	per: collections.Counter = collections.Counter()
	for where, text in visible():
		words = len(WORD.findall(text))
		if words >= PROSE_FROM:
			per[where] += words
	return {where: words for where, words in per.items() if words > FLOOR}


def main() -> int:
	lines = [f"{words}\t{where}" for where, words in sorted(measured().items())]
	(ROOT / "tests/prose_budget.txt").write_text(HEADER + "\n".join(lines) + "\n")
	print(f"{len(lines)} screens over {FLOOR} words")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
