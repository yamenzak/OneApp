"""The one thing about check-ins a workspace decides rather than a place does.

A **Shift Location** carries where and how near — see `place.py`, and the record
page that fills both in without anybody typing. What is not a property of any
one place is whether this workspace records where check-ins happen *at all*,
and that is HRMS's own switch: with `allow_geolocation_tracking` on, every
`Employee Checkin` has to carry a position and the ones too far from their
shift's location are refused.

It is global rather than per-place on purpose and the reason is worth keeping:
with it off, a place's radius is a circle nothing reads. So the place page says
so where somebody setting one up will see it, and this is where they go to turn
it on.

Behind `when`, because a workspace without OnePeople has no check-ins to have an
opinion about — the same shape OneMobility's group uses and for the same reason:
the space's own role does not exist on a workspace that never had it, so roles
cannot answer this question.
"""

import frappe

from ..onespace.workspace import OWNER_ROLE, SUPPORT_ROLE, Setting

#: HRMS's own Single, and the field name it reads.
SETTINGS = "HR Settings"
TRACKING = "allow_geolocation_tracking"


def enabled() -> bool:
	"""Whether this workspace has OnePeople at all."""
	from ..onespace import sync

	if not frappe.db.exists("DocType", SETTINGS):
		return False
	for space in sync.state().get("spaces") or []:
		for said in (space.get("space_code"), space.get("module")):
			if (said or "").lower().replace(" ", "") == "onehr":
				return True
	return False


def groups() -> list[dict]:
	"""The settings group, for `onespace_settings_groups`."""
	return [
		{
			"key": "onehr-checkin",
			"label": "Check-ins",
			"icon": "lucide-map-pin",
			"section": "Workspace",
			"when": enabled,
			"roles": (OWNER_ROLE, SUPPORT_ROLE),
			"description": (
				"Whether a check-in records where it happened. With this on, "
				"people are asked for their location when they check in, and "
				"anyone whose shift is assigned to a place has to be within "
				"its distance of it. Which places those are, and the networks "
				"they accept, is set on the places themselves."
			),
			"settings": [
				Setting(
					TRACKING,
					"Record where check-ins happen",
					type="Check",
					targets=[(SETTINGS, TRACKING)],
					hint=(
						"Off unless you turn it on. With it off, a place's "
						"distance is not checked and nobody is asked for a "
						"location; its network list still is."
					),
				),
			],
		},
	]
