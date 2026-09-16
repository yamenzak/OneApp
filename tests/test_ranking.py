"""Where a card sits in its column, as a string that sorts.

An integer order rewrites the whole column on every drag — two hundred rows,
two hundred `modified` bumps, two hundred version rows and two hundred
websocket messages, because somebody moved one card to the top. A fractional
rank rewrites one.

What has to hold is one property and three edges. The property: whatever is
minted between two ranks sorts between them. The edges: an empty column, the
top, the bottom, and a column dragged in so many times that the obvious
implementation runs out of alphabet.
"""

import pytest

from oneapp.onetask import ranking


def test_the_first_card_of_an_empty_column_gets_one():
	assert ranking.between("", "") == ranking.FIRST


def test_between_two_sorts_between_them():
	low, high = "a", "b"
	found = ranking.between(low, high)
	assert low < found < high


def test_after_sorts_after():
	assert ranking.after("n") > "n"


def test_before_sorts_before():
	assert ranking.before("n") < "n"


def test_a_column_filled_from_the_bottom_stays_in_order():
	"""Fifty drops at the end, which is what a backlog is."""
	ranks = [ranking.between("", "")]
	for _ in range(50):
		ranks.append(ranking.after(ranks[-1]))
	assert ranks == sorted(ranks)
	assert len(set(ranks)) == len(ranks)


def test_a_card_dropped_at_the_top_forty_times_stays_in_order():
	"""The pathological one: every drop goes above the last, which is what
	"this is next" looks like on a shared board."""
	ranks = ["n", "q"]
	for _ in range(40):
		ranks.insert(1, ranking.between(ranks[0], ranks[1]))
	assert ranks == sorted(ranks)
	assert len(set(ranks)) == len(ranks)


def test_the_same_rank_twice_is_not_an_error():
	"""Two people dragging at once. The list falls back to its own order for
	the tie rather than refusing the drop."""
	assert ranking.between("n", "n") > "n"


def test_ranks_out_of_order_land_after_the_lower_one():
	assert ranking.between("q", "b") > "q"


@pytest.mark.parametrize("junk", [None, "", "  ", "!!", "-", []])
def test_anything_that_is_not_a_rank_is_the_first_one(junk):
	"""A rank arrives from a browser, and a browser can send anything."""
	assert ranking.between(junk, junk) == ranking.FIRST


def test_a_number_is_a_rank_because_the_alphabet_holds_digits():
	"""Not junk: base-36 starts at 0, so `7` sorts and is kept rather than
	thrown away. Worth a test because the line above looks like it says the
	opposite."""
	assert ranking.between(7, 7) > "7"
