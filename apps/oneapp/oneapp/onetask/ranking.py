"""Where a card sits in its column, as a string that sorts.

The obvious store is an integer, and it is the wrong one: dragging one card to
the top of a column of two hundred rewrites two hundred rows, every one of them
a `modified` bump, a version row and a websocket message. Every product that
does this well uses a fractional rank instead — a string with an ordering, where
a new value can always be minted *between* two existing ones without touching
either.

The alphabet is base-36 and the rule is the one LexoRank publishes: to sit
between `a0` and `a1` you find the first place they differ and take a character
between them, lengthening the string when there is no room. Two cards can end up
with the same rank — two people dragging at once — and that is deliberate: the
list falls back to its own order for the tie rather than refusing the drop.

On the record and not in the reader's own arrangement, unlike the generic
board's card order. A project's order is the team's: one person moving a task
to the top of Backlog is telling everybody it is next, which is the whole point
of a shared board.
"""

#: Base-36, in ASCII order, so a plain string comparison is the ordering.
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

#: What the first card in an empty column gets. Mid-alphabet, so there is as
#: much room to insert above it as below.
FIRST = "n"


def after(rank: str) -> str:
	"""A rank that sorts after this one, or the first one."""
	return between(rank, "")


def before(rank: str) -> str:
	"""A rank that sorts before this one, or the first one."""
	return between("", rank)


def between(lower: str, upper: str) -> str:
	"""A rank strictly between two, either of which may be missing.

	`lower` empty means the top of the column and `upper` empty the bottom, so
	`between("", "")` is the first card of an empty one.
	"""
	lower = _clean(lower)
	upper = _clean(upper)

	if not lower and not upper:
		return FIRST
	if not lower:
		return _before(upper)
	if not upper:
		return _after(lower)
	if lower >= upper:
		# Out of order, or the same: not an error worth throwing over a drag.
		# Sitting after the lower of the two is what the person meant.
		return _after(lower)
	return _mid(lower, upper)


def _clean(rank) -> str:
	said = str(rank or "").strip().lower()
	return "".join(one for one in said if one in DIGITS)


def _after(lower: str) -> str:
	"""The next rank down from one with nothing below it."""
	last = lower[-1]
	at = DIGITS.index(last)
	if at < len(DIGITS) - 1:
		# Halfway to the end of the alphabet rather than one step, so a column
		# filled from the bottom does not run out after 36 cards.
		return lower[:-1] + DIGITS[(at + len(DIGITS) - 1) // 2 + 1] \
			if at + 1 < len(DIGITS) else lower + FIRST
	return lower + FIRST


def _before(upper: str) -> str:
	"""The rank above one with nothing above it."""
	first = upper[0]
	at = DIGITS.index(first)
	if at > 0:
		return DIGITS[at // 2] if at > 1 else DIGITS[0] + FIRST
	return DIGITS[0] + _before(upper[1:]) if len(upper) > 1 else DIGITS[0] + FIRST


def _mid(lower: str, upper: str) -> str:
	"""A rank between two that are in order and not equal."""
	found = ""
	at = 0
	while True:
		low = DIGITS.index(lower[at]) if at < len(lower) else 0
		high = DIGITS.index(upper[at]) if at < len(upper) else len(DIGITS)
		if low + 1 < high:
			return found + DIGITS[(low + high) // 2]
		# No room at this place: keep the lower's character and look at the
		# next one, which is what lengthening the string means.
		found += lower[at] if at < len(lower) else DIGITS[0]
		at += 1
