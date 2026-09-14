"""The ways a screen draws one record, and the two halves that have to agree.

A screen already says how a *page* of records is looked at. This is the same
question one level down — a record has more than one right shape, and which one
is a name in the manifest rather than a fork of the record component. The
vocabulary lives in `onespace/recordviews.py` and in `lib/screen/recordViews.js`,
and a name in one and not the other is a screen that draws nothing.
"""

import re as _re
from pathlib import Path as _Path

import pytest

from test_screens import spaceview  # noqa: F401


@pytest.fixture
def recordviews(stub_frappe):
	from oneapp.onespace import recordviews

	return recordviews


RECORD_VIEWS_JS = (
	_Path(__file__).resolve().parents[1]
	/ "apps/oneapp/frontend/src/modules/onespace/lib/screen/recordViews.js"
)


def _declared() -> dict:
	"""The browser's table, read back: `{name: {"built": bool, "whole": bool}}`."""
	source = RECORD_VIEWS_JS.read_text()
	block = _re.search(r"export const RECORD_VIEWS = \{(.*?)\n\}", source, _re.S).group(1)
	entries = _re.split(r"^  (\w+): \{", block, flags=_re.M)[1:]
	return {
		name: {"built": "built: true" in body}
		for name, body in zip(entries[::2], entries[1::2])
	}


def test_the_two_halves_agree_on_what_a_record_view_is(recordviews):
	"""The server narrows the name a screen asked for; the SPA mounts what it
	narrowed to. A name in one and not the other is a screen that resolves to a
	page nothing draws."""
	declared = _declared()
	assert set(declared) == set(recordviews.RECORD_VIEWS), (
		f"lib/recordViews.js has {sorted(declared)}, recordviews has "
		f"{sorted(recordviews.RECORD_VIEWS)}"
	)

	for name, one in declared.items():
		assert one["built"] == recordviews.RECORD_VIEWS[name]["built"], name


def test_the_guard_would_notice_a_name_only_one_half_has(recordviews, monkeypatch):
	"""The witness. `docs/UNIFICATION.md` F1: every guard that failed, failed at
	the edge of its own scan, and the fix that keeps the rest honest is a test
	that the guard catches a known offender."""
	monkeypatch.setitem(recordviews.RECORD_VIEWS, "zzghost", {"built": True})
	with pytest.raises(AssertionError):
		test_the_two_halves_agree_on_what_a_record_view_is(recordviews)


def test_the_default_is_the_form_and_the_tabs(recordviews):
	"""A screen that says nothing keeps what every screen drew before this
	existed. Silence is the commonest declaration there is."""
	assert recordviews.named(None) == "record"
	assert recordviews.named({}) == "record"
	assert recordviews.named("person") == "record", "a string is not a declaration"
	assert recordviews.named({"as": ""}) == "record"


def test_a_name_nothing_draws_falls_back_rather_than_failing(recordviews):
	"""The same rule an unknown view type follows: a manifest may name one
	before the engine has it, and until then the screen keeps the page it had.
	A screen that refused to open over a word in a settings blob would be a
	deployment order nobody can keep."""
	assert recordviews.named({"as": "hologram"}) == "record"
	assert recordviews.named({"as": "person"}) == "person"


def test_a_screen_that_declared_a_showcase_is_a_showcase_screen(recordviews):
	"""The back-compatible rule, and the whole reason nothing in a manifest had
	to change. It reads the *shaped* settings rather than the asked-for ones, so
	a showcase that was dropped for being structurally wrong does not quietly
	select a record view either."""
	assert recordviews.shape(None, {"showcase": {"images": True}}) == {"as": "showcase"}
	assert recordviews.shape(None, {}) == {"as": "record"}

	# And an explicit name wins over the inference, which is how one of these
	# screens is migrated later: by saying so.
	assert recordviews.shape({"as": "person"}, {"showcase": {"images": True}}) == {
		"as": "person",
	}


def test_every_screen_carries_one(spaceview):  # noqa: F811
	"""Present on every screen, including one whose settings are missing or are
	not settings at all — a key the browser has to check for before reading is a
	key half its callers will forget to check for."""
	resolved = {"all_columns": []}
	for asked in (None, "", "not json at all", {}, {"board": {"colour": "red"}}):
		kept = spaceview._view_settings(resolved, asked)
		assert kept["record"] == {"as": "record"}, asked
