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
	from oneapp.onecalendar import diary as module
	return module


SPACES = [
	{
		"space_code": "zzmock",
		"space_label": "MockSpace",
		"screens": [
			{"screen": "events", "label": "Events", "view_types": "calendar,list",
			 "view_settings":
			 '{"calendar": {"start_field": "starts_on", "diary": true}}'},
			# A calendar of its own and not a place in the merge, which is the
			# shape most calendars are: a workspace with the three ERPNext
			# spaces declares twenty, and eight people's attendance is
			# sixty-three entries in a month that belong to nobody reading it.
			{"screen": "attendance", "label": "Attendance",
			 "view_types": "calendar,list",
			 "view_settings": '{"calendar": {"start_field": "attendance_date"}}'},
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
	"""A screen that offers no calendar is not a calendar, and one that offers
	a calendar without asking for the diary is not in the diary.

	And the reader's own row is there whether or not they have an event this
	month: a source that appears with its contents is a set of switches that
	moves under the cursor as you page.
	"""
	found = diary._sources(SPACES)

	# Not `zzmock/attendance`: it offers a calendar and does not ask to be in
	# this one, which is the default and has to be — see `views._calendar`.
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


# --------------------------------------------------------------------------- #
# What belongs in a diary at all
#
# The merge used to be every calendar-declaring screen in the workspace, which
# is the right rule while a workspace has one space with one calendar and the
# wrong one the moment it has three: OnePeople alone declares eleven — attendance,
# check-ins, shift requests — and eight people's attendance is sixty-three
# entries in a month that belong to nobody reading it. The fixture's own meeting
# ended up behind a "+7 more".
#
# So a screen asks. What earns a place is a record that happens *at* a time to
# somebody — a leave, an interview, a booked call, a milestone — and what does
# not is a record that merely carries a date.
# --------------------------------------------------------------------------- #

def test_a_calendar_is_not_in_the_diary_unless_it_says_so(diary, monkeypatch):
	asked = []
	monkeypatch.setattr(diary, "_screen_rows",
	                    lambda space, screen, *a: asked.append(screen["screen"]) or [])

	diary._from_screens(SPACES, "2026-09-01", "2026-09-30")

	assert asked == ["events"], (
		"attendance offers a calendar and does not ask for the diary; querying "
		"it is both the wrong rows and a query nobody wanted"
	)


def test_a_screen_with_no_settings_at_all_is_not_in_the_diary(diary):
	assert diary._in_diary({"screen": "x", "view_types": "calendar"}) is False
	assert diary._in_diary({"screen": "x", "view_types": "calendar",
	                        "view_settings": "not json"}) is False
	assert diary._in_diary({"screen": "x", "view_types": "list",
	                        "view_settings": '{"calendar": {"diary": true}}'}) is False


def test_a_screen_that_asks_is_in_it(diary):
	assert diary._in_diary({
		"screen": "x", "view_types": "calendar,list",
		"view_settings": '{"calendar": {"start_field": "on", "diary": true}}',
	}) is True


# --------------------------------------------------------------------------- #
# Whose days these are
#
# The merge answers two questions and the lens is which one was asked —
# `docs/WORK.md` §6. What is worth holding is that a source which cannot say
# whose a row is stays *out* of the personal answer rather than being guessed
# at: the failure mode of guessing is one person's week with the whole
# company's interviews on it.
# --------------------------------------------------------------------------- #

MINE_SPACES = [
	{
		"space_code": "onehr",
		"space_label": "OnePeople",
		"screens": [
			# Says whose it is.
			{"screen": "leave", "label": "Leave", "view_types": "calendar,list",
			 "view_settings":
			 '{"calendar": {"start_field": "from_date", "diary": true,'
			 ' "about": {"employee": "@me:employee"}}}'},
			# Says nothing, so it is the company's and not anybody's.
			{"screen": "holidays", "label": "Holidays",
			 "view_types": "calendar,list",
			 "view_settings":
			 '{"calendar": {"start_field": "holiday_date", "diary": true}}'},
			# Says nothing on its calendar, but the screen itself is a twin.
			{"screen": "my-goals", "label": "My goals",
			 "view_types": "calendar,list",
			 "filters": '{"employee": "@me:employee"}',
			 "view_settings":
			 '{"calendar": {"start_field": "start_date", "diary": true}}'},
		],
	},
]


def test_a_source_that_cannot_say_whose_a_row_is_stays_out_of_mine(diary):
	"""The whole safety property of the lens, in one assertion."""
	keys = [one["key"] for one in diary._sources(MINE_SPACES, diary.MINE)]

	assert "onehr/leave" in keys
	assert "onehr/holidays" not in keys
	# And the reader's own diary is in every lens.
	assert keys[0] == "event"


def test_everyone_is_every_source_as_it_always_was(diary):
	keys = [one["key"] for one in diary._sources(MINE_SPACES, diary.EVERYONE)]
	assert keys == ["event", "onehr/leave", "onehr/holidays", "onehr/my-goals"]


def test_a_twin_screen_is_personal_without_saying_so(diary):
	"""`My goals` carries `@me` in its own filters, so it is nothing *but*
	personal and needs no second declaration."""
	assert diary._personal(MINE_SPACES[0]["screens"][2])
	assert not diary._personal(MINE_SPACES[0]["screens"][1])


def test_about_is_read_as_the_clauses_a_query_takes(diary, monkeypatch):
	"""One spelling of "this row is theirs", resolved by one module."""
	monkeypatch.setattr(
		"oneapp.onespace.mine.subject", lambda value: "HR-EMP-0001",
	)
	assert diary._about_filters({"employee": "@me:employee"}) == [
		["employee", "=", "HR-EMP-0001"],
	]


def test_an_assignment_is_a_like_over_the_field_every_doctype_has(diary, monkeypatch):
	"""The one place the assignment system and the calendar meet — §2. A
	screen with no owner field of its own can still answer "mine"."""
	monkeypatch.setattr(
		"oneapp.onespace.mine.subject", lambda value: "hala@example.com",
	)
	assert diary._about_filters({"_assign": "@me"}) == [
		["_assign", "like", "%hala@example.com%"],
	]


def test_a_person_named_in_a_child_table_is_asked_about_there(diary, monkeypatch):
	"""An interviewer is a row under the interview, not a field on it."""
	monkeypatch.setattr(
		"oneapp.onespace.mine.subject", lambda value: "hala@example.com",
	)
	assert diary._about_filters({"Interview Detail.interviewer": "@me"}) == [
		["Interview Detail", "interviewer", "=", "hala@example.com"],
	]


def test_nothing_to_say_is_no_clauses(diary):
	assert diary._about_filters(None) == []
	assert diary._about_filters({}) == []


def test_an_unknown_lens_narrows_rather_than_raising(diary, monkeypatch):
	"""This runs on every month somebody pages through, so a typo in a query
	string should narrow rather than break."""
	monkeypatch.setattr(diary, "visible", lambda spaces: [])
	monkeypatch.setattr(diary, "_own_events", lambda since, until: [])
	monkeypatch.setattr(diary.sync, "state", lambda: {"spaces": []})

	for asked in ("whatever", "", None):
		assert diary.agenda("2026-09-01", "2026-09-30", lens=asked)["lens"] == diary.MINE
	assert diary.agenda(
		"2026-09-01", "2026-09-30", lens=diary.EVERYONE,
	)["lens"] == diary.EVERYONE


# --------------------------------------------------------------------------- #
# One record's own month
#
# Declared nowhere — `docs/WORK.md` §6(c). The record shell already says which
# screens are about one of these and which field points back, so a record's
# calendar is that list read as a calendar. What is worth holding is that it
# reads the *declaration* rather than a second one, and that it does not ask
# for `diary`: a timesheet does not belong in everybody's week and does belong
# in this project's month.
# --------------------------------------------------------------------------- #

ABOUT = {
	"doctype": "Project",
	"connections": [
		{"screen": "invoices", "field": "project", "label": "Invoices"},
	],
	"view_settings": {
		"showcase": {"tabs": [
			{"screen": "time", "field": "parent_project", "label": "Time"},
		]},
	},
}


def test_a_records_calendar_is_its_tabs_read_as_one(diary):
	"""Declared first in the manifest's own order, derived after — the order
	the record's tab strip draws them in."""
	assert [one["screen"] for one in diary._about_screens({}, ABOUT)] == [
		"time", "invoices",
	]


def test_a_tab_with_no_field_points_at_nothing_and_is_left_out(diary):
	resolved = {"view_settings": {"showcase": {"tabs": [{"screen": "time"}]}}}
	assert diary._about_screens({}, resolved) == []


def test_a_related_calendar_does_not_have_to_be_in_the_diary(diary, monkeypatch):
	"""The one difference from the merge, and the reason for it: the reader
	asked about this project rather than about their week."""
	monkeypatch.setattr(diary, "_resolve", lambda *a, **k: {
		"doctype": "Timesheet",
		# No `diary`: this screen is not in anybody's week.
		"calendar": {"start_field": "start_date", "end_field": "end_date"},
		"asked": [],
		"title_field": "name",
	})
	monkeypatch.setattr(diary, "_window", lambda *a: [["start_date", ">", "x"]])
	monkeypatch.setattr(diary, "_all_filters", lambda *a: [])

	sent = {}

	def get_list(doctype, **kwargs):
		sent.update(kwargs)
		return [diary.frappe._dict({"name": "TS-1", "start_date": "2026-09-10"})]

	monkeypatch.setattr(diary.frappe, "get_list", get_list, raising=False)

	screen = {"screen": "time", "label": "Time", "view_types": "calendar",
	          "view_settings": '{"calendar": {"start_field": "start_date"}}'}

	# Asked as the diary would: nothing, because it never said it wanted to be.
	assert diary._screen_rows(SPACES[0], screen, "a", "b") == []

	# Asked about one record: there, and narrowed to it.
	rows = diary._screen_rows(
		SPACES[0], screen, "a", "b", diary.EVERYONE,
		[["parent_project", "=", "PROJ-0001"]], False,
	)
	assert len(rows) == 1
	assert ["parent_project", "=", "PROJ-0001"] in sent["filters"]


def test_a_record_nobody_may_open_has_no_calendar(diary, monkeypatch):
	"""The parent's own screen decides, before any related screen is read."""
	monkeypatch.setattr(diary, "_resolve", lambda *a, **k: {"doctype": "Project"})
	monkeypatch.setattr(
		"oneapp.onespace.spaceview.records.record", lambda **kwargs: None,
	)
	answer = diary.about("oneproject", "projects", "PROJ-0001", "a", "b")
	assert answer == {"events": [], "sources": []}
