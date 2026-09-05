"""The merged calendar: everything with a date on it, for one person.

Three things are worth holding here, and all three are about a merge rather
than about a calendar.

The **de-duplication**, because two sources reaching the same record is the
normal case rather than the edge one: a workspace with an events screen puts
Tuesday's review in front of the same person twice, and a diary that draws it
twice is one nobody trusts about Wednesday.

The **range**, because a diary that answers a request with no dates in it by
returning everything is a request that fetches a doctype's whole history.

The **source list**, because it is what the rail draws and what the colours are
keyed on, and it has to hold still while somebody pages through months.
"""

import pytest


@pytest.fixture
def diary(monkeypatch):
	from oneapp.oneapp_core import diary as module
	return module


SPACES = [
	{
		"space_code": "zzmock",
		"space_label": "MockSpace",
		"screens": [
			{"screen": "events", "label": "Events", "view_types": "calendar,list",
			 "view_settings": '{"calendar": {"start_field": "starts_on"}}'},
			{"screen": "tasks", "label": "Tasks", "view_types": "list,board",
			 "status_field": "status"},
		],
	},
	{
		"space_code": "rua",
		"space_label": "RUA",
		"screens": [
			{"screen": "projects", "label": "Projects", "view_types": "list"},
		],
	},
]


# --------------------------------------------------------------------------- #
# One record, one entry


def test_a_record_reached_twice_is_drawn_once(diary):
	"""The same meeting from a screen and from somebody's own diary.

	The screen's copy wins, and that is the whole point of the ordering rather
	than a tie-break: a screen entry knows where the record lives and can open
	it, and the personal one knows only that it exists.
	"""
	found = diary._once([
		{"doctype": "Event", "record": "EV1", "kind": "record", "screen": "events"},
		{"doctype": "Event", "record": "EV1", "kind": "event", "screen": ""},
		{"doctype": "Event", "record": "EV2", "kind": "event", "screen": ""},
	])

	assert [one["record"] for one in found] == ["EV1", "EV2"]
	assert found[0]["kind"] == "record"
	assert found[0]["screen"] == "events"


def test_two_doctypes_may_share_an_id(diary):
	"""`EV00001` is a Sales Invoice somewhere and an Event somewhere else.

	De-duplicating on the id alone would silently drop one of them, and the one
	dropped would depend on which space happened to be first.
	"""
	found = diary._once([
		{"doctype": "Event", "record": "EV00001"},
		{"doctype": "Sales Invoice", "record": "EV00001"},
	])
	assert len(found) == 2


# --------------------------------------------------------------------------- #
# The range is the request


def test_a_diary_with_no_range_asks_for_nothing(diary, monkeypatch):
	"""Not "everything": that is a doctype's whole history, per screen.

	`_window` already refuses a range that is not two dates; this is the other
	half — a screen whose window came back empty is skipped rather than queried
	without one.
	"""
	monkeypatch.setattr(diary, "_resolve", lambda *a, **k: {
		"doctype": "Event",
		"calendar": {"start_field": "starts_on", "end_field": ""},
		"asked": [],
	})
	monkeypatch.setattr(diary, "_window", lambda *a: [])

	asked = []
	monkeypatch.setattr(diary.frappe, "get_list",
	                    lambda *a, **k: asked.append(a) or [], raising=False)

	assert diary._screen_rows(SPACES[0], SPACES[0]["screens"][0], "", "") == []
	assert not asked, "a screen was queried with no range"


def test_own_events_need_a_range_too(diary, monkeypatch):
	asked = []
	monkeypatch.setattr(diary.frappe, "get_list",
	                    lambda *a, **k: asked.append(a) or [], raising=False)
	assert diary._own_events("", "") == []
	assert diary._own_events("2026-09-01", "") == []
	assert not asked


# --------------------------------------------------------------------------- #
# What the rail draws


def test_the_sources_are_every_calendar_and_always_your_own(diary):
	"""A screen that offers no calendar is not a calendar.

	And the reader's own row is there whether or not they have an event this
	month: a source that appears with its contents is a set of switches that
	moves under the cursor as you page.
	"""
	found = diary._sources(SPACES)

	assert [one["key"] for one in found] == ["event", "zzmock/events"]
	assert found[0]["label"]
	assert found[1]["label"] == "Events"
	assert found[1]["space_label"] == "MockSpace"


def test_a_screen_that_cannot_be_read_costs_that_screen_and_no_more(diary, monkeypatch):
	"""One revoked doctype is not an error page over somebody's whole week."""
	def refuse(space_code, screen, **kwargs):
		raise RuntimeError("no permission")

	monkeypatch.setattr(diary, "_resolve", refuse)
	logged = []
	monkeypatch.setattr(diary.frappe, "log_error", lambda **kw: logged.append(kw),
	                    raising=False)

	assert diary._from_screens(SPACES, "2026-09-01", "2026-09-30") == []
	# Logged rather than swallowed: this is where a manifest typo shows up.
	assert logged


def test_the_merge_is_in_time_order(diary, monkeypatch):
	"""One diary, not its sources laid end to end."""
	monkeypatch.setattr(diary, "visible", lambda spaces: [])
	monkeypatch.setattr(diary.sync, "state", lambda: {"spaces": []})
	monkeypatch.setattr(diary, "_own_events", lambda *a: [
		{"start": "2026-09-12 09:00:00", "title": "Later", "doctype": "Event", "record": "B"},
		{"start": "2026-09-10 10:00:00", "title": "Earlier", "doctype": "Event", "record": "A"},
	])

	found = diary.agenda("2026-09-01", "2026-09-30")["events"]
	assert [one["title"] for one in found] == ["Earlier", "Later"]
