"""What the workspace assistant may ask this module.

Two tools, and the reason there are any is that the engine's eight are about
*records*. `find_records` and `count_records` are the right shape for almost
every question anybody asks a workspace — and the wrong shape for the two the
employee's own page exists to answer, because neither answer is a row.

"How much leave have I got left" is an allocation minus what has been taken
against it, which `history.py` computes and no filter can express. "Am I checked
in" is the last punch of the day read against a shift, which `presence.py` works
out and which is not a field on anything. A model given only the generic tools
answers both by listing Leave Applications and guessing.

**Nothing here is a new way to read.** Both go through `me.py`, which goes
through `own.may_read` — `if_owner` covers what you filed and that covers what
was filed about you — so the assistant sees exactly what the person asking would
see if they opened the page themselves. A tool that called `get_all` would be
the assistant reading past a permission, and `chat/toolbox.py` opens with the
paragraph saying why that is the one thing it may not do.

**Nothing here writes.** Asking for leave is a proposal like any other:
`propose_create` on the `leave` screen, which is the engine's own card and the
person's own Apply. There is no HR verb here that a model may perform.
"""

from typing import Annotated

from oneapp.onespace.ai.tools import Tool, tool


def tools() -> list[Tool]:
	"""The hook. See `onespace/chat/toolbox.TOOLS_HOOK`."""
	return [my_hr_standing, who_is_in]


#: How many of somebody's own open requests are worth carrying into a turn.
#: The page shows what fits; a model wants the ones that are still moving.
REQUESTS = 8


@tool
def my_hr_standing() -> dict:
	"""Where the person asking stands at work: their job, whether they are in
	today, how much leave they have left, what they have asked for and what is
	coming up. Use this for any question about *their own* employment, leave
	balance, attendance or requests — the record tools cannot compute a leave
	balance."""
	from oneapp.onehr import me

	found = me.home()
	mine = found.get("employee")
	if not mine:
		# The two ordinary states of a real site, said rather than raised: a
		# workspace without HRMS, and a login nobody linked to a record.
		return {"employee": None, "reason": found.get("reason") or "not-linked"}

	presence = found.get("presence") or {}
	return {
		"employee": {
			"name": mine.get("employee_name"),
			"designation": mine.get("designation"),
			"department": mine.get("department_name") or mine.get("department"),
			"reports_to": mine.get("reports_to_name"),
			"joined": str(mine.get("date_of_joining") or ""),
			"status": mine.get("status"),
		},
		"today": {
			"state": presence.get("state"),
			"said": presence.get("label"),
			"since": str(presence.get("since") or ""),
			"late": bool(presence.get("late")),
		},
		# The whole reason this tool exists. Each entry is one leave type with
		# what is left of it and what it started as.
		"leave_left": [
			{"type": one.get("leave_type"), "left": one.get("left"),
			 "allocated": one.get("allocated"), "taken": one.get("taken")}
			for one in (found.get("history") or {}).get("balance") or []
		],
		"asked_for": [
			{"what": one.get("subject"), "kind": one.get("doctype"),
			 "state": one.get("state"), "id": one.get("name")}
			for one in (found.get("requests") or [])[:REQUESTS]
		],
		"coming_up": [
			{"what": one.get("label"), "kind": one.get("kind"),
			 "from": one.get("date"), "until": one.get("until")}
			for one in found.get("upcoming") or []
		],
	}


@tool
def who_is_in(
	about: Annotated[
		str | None,
		"A colleague's name, to ask about one person rather than the whole team.",
	] = None,
) -> dict:
	"""Who around the person asking is at work today — their manager, the people
	alongside them and anybody who reports to them, each with whether they are
	in, on leave, absent or not known. Use this for "is X in today" and "who is
	off this week"."""
	from oneapp.onehr import me

	found = me.home()
	if not found.get("employee"):
		return {"team": [], "reason": found.get("reason") or "not-linked"}

	team = [
		{
			"name": one.get("employee_name"),
			"designation": one.get("designation"),
			# `manager`, `peer` or `report` — how they stand to the asker.
			"relation": one.get("how"),
			"state": (one.get("presence") or {}).get("state"),
			"said": (one.get("presence") or {}).get("label"),
		}
		for one in found.get("team") or []
	]
	if about:
		# Matched loosely on purpose: a model asking about "Hala" should not be
		# refused for not knowing she is filed as "zzHala Zayed".
		wanted = str(about).strip().casefold()
		team = [one for one in team if wanted in str(one["name"]).casefold()]
	return {"team": team}
