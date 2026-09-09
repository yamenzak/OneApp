"""How long this workspace keeps its own history.

Two numbers, and they are the only two decisions in the tiering that are a
workspace's rather than ours. A fact table is declared with a default window in
`model.py`; these override it per workspace, through the same settings dialog
everything else is in.

**How much detail stays in the database.** Thirty days by default. Raw positions
are the expensive tier — five hundred vehicles reporting every fifteen seconds
is 2.2 million rows a day — and they are what the live map, the scrubber and the
ghosts read. Every chart reads the aggregates instead, which never expire, so
shortening this changes what the map can go back to and changes nothing about
Insights.

**How long the frozen copy is kept.** For ever by default, which is what this
did before anybody could say otherwise. A day that ages out of the database is
gzipped into the bucket first, and a workspace that will never read a March
Tuesday at full grain should be able to say so rather than pay for it for ever.

The group is offered only where OneMobility is enabled — `when` on the group,
which is the same shape as a settings tab's audience and exists for the same
reason: the space's own role does not exist on a workspace that never had it, so
roles cannot answer this question.
"""

import frappe

from ..onespace.workspace import OWNER_ROLE, SUPPORT_ROLE, Setting

#: The Single the two numbers live on, and the field names the platform reads.
#: `shared/facts` looks for `hot_days` and `frozen_days` by those exact names —
#: see `facts.Fact.settings` — so this doctype is the whole of the wiring.
SETTINGS = "OneMobility Settings"


def enabled() -> bool:
	"""Whether this workspace has OneMobility at all.

	Asked of the space manifest rather than of the roles, because the manifest
	is what the rail is built from and is therefore the same answer the person
	sees in front of them.
	"""
	from ..onespace import sync

	for space in sync.state().get("spaces") or []:
		for said in (space.get("space_code"), space.get("module")):
			if (said or "").lower().replace(" ", "") == "onemobility":
				return True
	return False


def groups() -> list[dict]:
	"""The settings group, for `onespace_settings_groups`."""
	return [
		{
			"key": "mobility",
			"label": "Transit history",
			"icon": "lucide-history",
			"section": "Workspace",
			"when": enabled,
			"roles": (OWNER_ROLE, SUPPORT_ROLE),
			"description": (
				"How far back this workspace keeps vehicle detail, and how long "
				"the frozen copy of it is kept afterwards. Charts and rankings "
				"are built from summaries that never expire, so neither number "
				"changes what Insights can answer."
			),
			"settings": [
				Setting(
					"hot_days",
					"Days of detail in the database",
					type="Int",
					targets=[(SETTINGS, "hot_days")],
					hint=(
						"What the live map and the scrubber can go back to. "
						"Thirty days unless you change it. Longer means a "
						"larger database, which your plan caps."
					),
				),
				Setting(
					"frozen_days",
					"Days to keep the frozen copy",
					type="Int",
					targets=[(SETTINGS, "frozen_days")],
					hint=(
						"A day that ages out of the database is compressed into "
						"storage first, and can be brought back from the map. "
						"Zero keeps it for ever."
					),
				),
			],
		}
	]


def window() -> dict:
	"""The two numbers as they stand, for anything that needs to say them."""
	from ..shared import facts
	from . import model

	return {
		"hot_days": facts.hot_days(model.OBSERVATION),
		"frozen_days": facts.frozen_days(model.OBSERVATION),
		"frozen_bytes": frappe.db.get_single_value(
			"OneSpace Site State", "frozen_bytes"
		) or 0,
	}
