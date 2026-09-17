"""Every seat of every space, against every screen and every action.

`docs/CLEANUP.md` stage 13. The four seats decide what a person can reach —
which screens resolve, which records they may write, which buttons appear —
and until now nothing checked the *result*. Stage 2 was verified by opening the
dev site and counting roles, which is a thing somebody did once.

`scripts/seat_matrix.py` writes the answer to
`tests/fixtures/seat_matrix.json`, on a bench, because two of the action
providers import HRMS at the top of the module and the list of buttons cannot
be assembled without it. These are the rules over that file. Where a bench
exists the last rule recomputes and fails a stale matrix, which is the
arrangement `tests/fixtures/upstream_fields.json` already uses.

Six hundred and eighty-four cells, and the rules are the four sentences the
whole seat model rests on:

* an auditor writes nothing, anywhere;
* the ladder is a ladder — what a User may do, a Manager and an Admin may too;
* a button is on a page the person pressing it can open;
* and no button is unpressable by every seat, which is the "every role's every
  action" checkpoint read in the direction that can fail.
"""

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MATRIX = ROOT / "tests/fixtures/seat_matrix.json"

sys.path.insert(0, str(ROOT / "apps/oneapp_control"))

from oneapp_control.spaces import roles  # noqa: E402

CELLS = json.loads(MATRIX.read_text(encoding="utf-8"))
SPACES = sorted(CELLS)

#: Every (space, screen) pair, so a failure names the screen rather than the
#: space it is in.
SCREENS = [(code, screen) for code in SPACES for screen in CELLS[code]["screens"]]


def ids(case):
	return f"{case[0]}/{case[1]['screen']}"


def test_the_matrix_is_about_something():
	"""A fixture that came back empty turns every rule below into a pass."""
	assert len(SPACES) >= 5, SPACES
	assert len(SCREENS) >= 100, len(SCREENS)
	for code in SPACES:
		assert set(CELLS[code]["doctypes"]) == set(roles.LABELS), code


# --------------------------------------------------------------------------- #
# A. An auditor writes nothing
#
# The rule the seat set exists for. `registry.laddered` derives Audit at Read
# from every other grant, so the way this breaks is not somebody granting the
# auditor a write — it is the derivation changing under a manifest nobody
# looked at again.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("code", SPACES)
def test_an_auditor_writes_nothing(code):
	held = CELLS[code]["doctypes"][roles.AUDIT]
	writes = sorted(one for one, access in held.items() if access != "Read")
	assert not writes, f"{code}'s auditor may {writes}"


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_an_auditor_presses_nothing(case):
	code, screen = case
	seat = screen["seats"][roles.AUDIT]
	assert seat["press"] == [], f"{code}/{screen['screen']}: {seat['press']}"
	assert seat["new"] is False


@pytest.mark.parametrize("code", SPACES)
def test_an_auditor_sees_what_the_others_see(code):
	"""The other half, and the half that makes Audit a seat rather than a
	punishment: everything any seat can reach, at Read. A space cannot ship an
	auditor who can write, and cannot forget to let one look at something."""
	held = CELLS[code]["doctypes"]
	others = set()
	for key in (roles.USER, roles.MANAGER, roles.ADMIN):
		others |= set(held[key])
	missing = sorted(others - set(held[roles.AUDIT]))
	assert not missing, f"{code}'s auditor cannot see {missing}"


# --------------------------------------------------------------------------- #
# B. The ladder is a ladder
# --------------------------------------------------------------------------- #

RANK = {"": 0, "Read": 1, "Write": 2, "Manage": 3}

#: The three rungs, lowest first. Audit is not on them — it is derived.
RUNGS = (roles.USER, roles.MANAGER, roles.ADMIN)


@pytest.mark.parametrize("code", SPACES)
def test_each_rung_reaches_everything_below_it(code):
	held = CELLS[code]["doctypes"]
	for lower, upper in zip(RUNGS, RUNGS[1:]):
		for doctype, access in held[lower].items():
			above = held[upper].get(doctype, "")
			assert RANK[above] >= RANK[access], (
				f"{code}: {upper} holds {above or 'nothing'} on {doctype} and "
				f"{lower} holds {access}"
			)


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_a_screen_a_lower_seat_opens_a_higher_one_opens(case):
	code, screen = case
	for lower, upper in zip(RUNGS, RUNGS[1:]):
		if screen["seats"][lower]["open"]:
			assert screen["seats"][upper]["open"], (
				f"{code}/{screen['screen']} opens for {lower} and not {upper}"
			)


# --------------------------------------------------------------------------- #
# C. A button is on a page you can open
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_nobody_may_press_what_they_cannot_open(case):
	"""`run_action` asks for `write` on the screen's doctype and the rail asks
	for `read`, and nothing joins the two. A seat with write and no read is a
	manifest that granted at the wrong rung, and the symptom is a button in an
	API response for a screen the person has no way to reach."""
	code, screen = case
	for key, seat in screen["seats"].items():
		if seat["press"] or seat["new"]:
			assert seat["open"], (
				f"{code}/{screen['screen']}: {key} may act and cannot open it"
			)


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_every_action_is_pressable_by_somebody(case):
	"""The checkpoint, in the direction that can fail. An action declared on a
	screen no seat may write is a button nobody in the workspace can use, and
	nothing anywhere says so — it renders, it is in the payload, and it throws
	when pressed."""
	code, screen = case
	if not screen["actions"]:
		return
	pressers = [key for key, seat in screen["seats"].items() if seat["press"]]
	assert pressers, (
		f"{code}/{screen['screen']} declares {screen['actions']} and no seat "
		f"may press any of them"
	)


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_a_screen_that_offers_new_is_one_somebody_writes(case):
	"""`hide_new` is a declaration and the grant is the truth. A screen that
	offers New over a doctype every seat holds at Read is a form that fails on
	save — which is how a person finds out."""
	code, screen = case
	if screen["hide_new"]:
		assert not any(seat["new"] for seat in screen["seats"].values()), (
			f"{code}/{screen['screen']} hides New and a seat still has it"
		)


# --------------------------------------------------------------------------- #
# D. Every seat has something to do
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("code", SPACES)
def test_every_seat_can_open_something(code):
	"""A seat that opens no screen is a seat nobody should be sold, and the
	four are sold as a set."""
	for key in roles.LABELS:
		opens = [one["screen"] for one in CELLS[code]["screens"]
		         if one["seats"][key]["open"]]
		assert opens, f"{code}'s {key} can open nothing"


@pytest.mark.parametrize("code", SPACES)
def test_three_of_the_four_can_change_something(code):
	"""Audit is the exception by design; the other three each have a job, and
	a rung that can write nothing is a rung the manifest forgot."""
	for key in RUNGS:
		writes = [one for one, access in CELLS[code]["doctypes"][key].items()
		          if RANK[access] >= RANK["Write"]]
		assert writes, f"{code}'s {key} can change nothing"


#: Spaces whose Admin reaches exactly what their Manager does, and why that is
#: the right answer rather than a gap.
#:
#: The rule below found three, and only one of them was wrong. OneCRM's Admin
#: held nothing at all while its Manager held the answering dials — the target,
#: the working week, the levels and the rules — which is a sales manager with
#: the dial on the measure their own team is judged by. Those moved to Admin in
#: `docs/CLEANUP.md` stage 13 and OneCRM came off this list.
#:
#: The other two stay, with the reason, because inventing a difference is worse
#: than naming the absence of one.
FLAT = {
	"oneproject": (
		"The board's vocabulary — the columns, the labels, the cycles — is "
		"the manager's, and `spaces/oneproject.py` argues that out loud: "
		"renaming a column under a team mid-sprint is the job of whoever runs "
		"the team. Above that there is nothing this space owns. A project has "
		"no settings, no measure of the people in it and no confidential "
		"lane, so an Admin grant here would be a made-up one."
	),
	"rua": (
		"One company's own system delivered as a module, so its seats are "
		"that customer's decisions about their own data — the same exemption "
		"`test_space_wiring.py` §E makes, for the same reason."
	),
}


@pytest.mark.parametrize("code", SPACES)
def test_a_higher_rung_is_worth_holding(code):
	"""Two rungs that reach exactly the same things are one rung with two
	names, which is twelve words a customer has to learn for no reason —
	`spaces/roles.py` is the whole argument against that.

	`FLAT` is the exception and each entry says why. A space joining it is a
	decision somebody has to write down, which is the point of the list.
	"""
	held = CELLS[code]["doctypes"]
	for lower, upper in zip(RUNGS, RUNGS[1:]):
		if held[upper] == held[lower]:
			assert code in FLAT, (
				f"{code}: {upper} reaches exactly what {lower} does. Give it "
				f"something of its own, or add it to FLAT with the reason."
			)


def test_no_exemption_is_left_over():
	"""An exemption for a space that has since grown a rung of its own is a
	rule nobody is keeping."""
	flat = set()
	for code in SPACES:
		held = CELLS[code]["doctypes"]
		if any(held[up] == held[lo] for lo, up in zip(RUNGS, RUNGS[1:])):
			flat.add(code)
	assert set(FLAT) <= flat, f"these are not flat any more: {sorted(set(FLAT) - flat)}"


# --------------------------------------------------------------------------- #
# E. And the matrix is current
# --------------------------------------------------------------------------- #

def test_the_matrix_covers_every_screen_the_manifests_declare():
	"""The staleness check, and it is deliberately not a recompute.

	Recomputing needs the *actions*, and those need a bench — two of the
	providers import HRMS at the top of the module. The conftest here stubs
	`frappe` for every test in the suite, so a recompute inside pytest would
	assemble an empty action list and compare it to a full one, which fails
	for the wrong reason and teaches somebody to regenerate when nothing has
	changed.

	What *is* readable without a bench is the manifests, and that is where a
	drift actually starts: somebody adds a screen or moves a grant and does not
	rerun the script. So this reads the manifests and holds the fixture to them
	— every screen, its doctype and whether it hides New. The action lists are
	the bench's to keep current, and the script says so.
	"""
	from oneapp_control import spaces

	for code, module in spaces.shipped().items():
		declared = {
			one["screen"]: (one["document_type"], bool(one.get("hide_new")))
			for one in getattr(module, "SCREENS", [])
			if one.get("document_type")
		}
		held = {
			one["screen"]: (one["doctype"], one["hide_new"])
			for one in CELLS[code]["screens"]
		}
		assert held == declared, (
			f"{code}'s matrix is stale — run "
			f"`scripts/dev.sh run scripts/seat_matrix.py` and read the diff"
		)


def test_every_shipped_space_is_in_the_matrix():
	from oneapp_control import spaces

	assert set(CELLS) == set(spaces.shipped()), (
		"a space was added and the matrix was not regenerated"
	)
