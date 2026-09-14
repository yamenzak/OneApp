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


# --------------------------------------------------------------------------- #
# What a record view may be told
#
# One thing, and it is a list of words: the order a record moves through. A
# candidate page draws where somebody is in hiring, and that order is neither
# the doctype's — Job Applicant's Select puts Rejected between Shortlisted and
# Hold — nor anything the engine can work out.
# --------------------------------------------------------------------------- #

def test_a_record_view_carries_the_stages_it_was_given(recordviews):
	assert recordviews.shape({"as": "candidate", "stages": ["Open", "Hired"]}, {}) == {
		"as": "candidate", "stages": ["Open", "Hired"],
	}


def test_a_screen_that_names_no_stages_carries_none(recordviews):
	"""Absent rather than empty. A page reading `stages` draws nothing for a
	missing key and nothing for an empty list, and the second one is a key the
	browser has to check the length of anyway."""
	assert recordviews.shape({"as": "candidate"}, {}) == {"as": "candidate"}
	assert recordviews.shape({"as": "candidate", "stages": []}, {}) == {"as": "candidate"}


def test_stages_that_are_not_words_are_dropped(recordviews):
	"""The rule every shaper here follows: a settings blob somebody mistyped
	costs the drawing it describes and not the screen."""
	asked = {"as": "candidate", "stages": ["Open", "", None, 7, "  Hired  "]}
	assert recordviews.shape(asked, {})["stages"] == ["Open", "Hired"]

	for wrong in ("Open,Hired", {"first": "Open"}, 7):
		assert "stages" not in recordviews.shape({"as": "candidate", "stages": wrong}, {})


def test_a_strip_of_stages_is_capped(recordviews):
	"""Past a dozen it is a list, and a list of stages is a report."""
	asked = {"as": "candidate", "stages": [f"S{n}" for n in range(40)]}
	assert len(recordviews.shape(asked, {})["stages"]) == recordviews.MOST_STAGES


def test_the_candidate_page_and_the_board_read_one_list():
	"""OneHR's applicants screen declares the hiring order three times — the
	board's arrangement, the Where-they-are widget, and now the record — and a
	manifest is a Python file, so all three name one constant. This is the
	guard against somebody later typing the second one out by hand.
	"""
	module = _onehr()
	settings = _settings(module, "applicants")

	stages = module.APPLICANT_STAGES
	assert settings["record"]["stages"] == stages
	assert settings["board"]["arrangement"]["order"] == stages
	widget = next(one for one in settings["dashboard"]["widgets"]
	              if one.get("group_by") == "status")
	assert widget["order"] == stages


def _onehr():
	"""OneHR's manifest, loaded from source.

	By path rather than by import: the control plane is a second app and these
	tests run without a bench, which is the same reason `test_space_screens`
	reads it this way.
	"""
	import importlib.util
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	path = root / "apps/oneapp_control/oneapp_control/spaces/onehr.py"
	spec = importlib.util.spec_from_file_location("recordviews_onehr", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _settings(module, screen: str) -> dict:
	import json

	found = next(one for one in module.SCREENS if one["screen"] == screen)
	return json.loads(found["view_settings"])


def test_the_opening_page_counts_the_same_stages_the_board_arranges():
	"""A funnel for one role, in the order the board puts its columns in.

	The fourth place `APPLICANT_STAGES` is read and the fourth reason it is a
	constant: a hiring order typed out by hand in a fourth file is a page that
	agrees with hiring until somebody inserts a stage.
	"""
	module = _onehr()
	settings = _settings(module, "openings")
	assert settings["record"]["as"] == "opening"
	assert settings["record"]["stages"] == module.APPLICANT_STAGES


def test_the_opening_page_still_reads_the_declaration_it_replaced():
	"""The eyebrow, the badge, the facts and the Applicants tab are the same
	words in a different layout — which is the argument for a library of record
	views rather than a component per screen. A migration here is one word."""
	settings = _settings(_onehr(), "openings")
	showcase = settings["showcase"]
	assert showcase["eyebrow_field"] and showcase["badge_field"]
	assert any(tab["screen"] == "applicants" for tab in showcase["tabs"])


def test_a_cell_of_the_attendance_grid_opens_a_day():
	"""The matrix and the record it opens are one screen, and the page behind a
	cell has to answer why the verdict is the verdict — which the form does in
	twenty fields across four sections."""
	settings = _settings(_onehr(), "attendance")
	assert settings["record"] == {"as": "day"}
	assert settings["matrix"]["date_field"] == "attendance_date"


def test_every_record_view_onehr_names_is_one_the_engine_has(recordviews):
	"""The manifest ran ahead of the engine once — `matrix` was declared before
	`viewtypes.py` had it — and the fallback is silent by design. Silent is
	right on a customer's site and wrong in this repository, where a screen that
	quietly drew a form instead of the page it asked for is a regression nobody
	would see."""
	import json

	module = _onehr()
	for screen in module.SCREENS:
		asked = json.loads(screen.get("view_settings") or "{}").get("record")
		if not asked:
			continue
		assert asked["as"] in recordviews.BUILT_RECORD_VIEWS, (
			f"{screen['screen']} names {asked['as']}, which nothing draws"
		)
