"""What waits for what, and what happens when something slips.

`docs/WORK.md` stage 5. Three things, and the third is the only one that is
not bookkeeping.

**One direction is stored.** A `One Task Link` row hangs off the task that is
*waiting* and names the one it waits for. "Blocks" is that same edge read
backwards — a query, never a second row — because two rows for one fact is two
rows that disagree by Thursday. A person may still say it from either end; the
verb writes the edge where it belongs.

**A cycle is refused, with the path.** A plan where A waits for B and B waits
for A is not a plan and cannot be drawn; the check is a walk of the edges
already stored, done before the row is saved rather than discovered by a chart
that renders nothing.

**A plan slips forward and never backwards.** When a task's due date moves
later, everything waiting on it that would now start too early moves with it,
keeping its own duration. The other direction is deliberately not symmetric:
finishing early does not mean the next person is free to start, and a schedule
that quietly pulled their dates forward would be promising somebody else's
week on their behalf.
"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate

#: The kind that is a sequence. The other — `Relates to` — is a pointer
#: somebody left for somebody, and moves nothing.
BLOCKED_BY = "Blocked by"
RELATES_TO = "Relates to"

#: How far a slip is allowed to travel.
#:
#: A cascade is a write per task, and a plan where one date moves four hundred
#: rows is one somebody should look at rather than one to apply silently. Past
#: this the save is refused and says so — which has never happened on a real
#: project and would be worth knowing about if it did.
MOST = 200


def predecessors(name: str) -> list[str]:
	"""What this task is waiting for."""
	if not name:
		return []
	return frappe.get_all(
		"One Task Link",
		filters={"parent": name, "parenttype": "One Task", "kind": BLOCKED_BY},
		pluck="task",
	)


def dependents(name: str) -> list[str]:
	"""What is waiting for this task — the same edges, read backwards."""
	if not name:
		return []
	return frappe.get_all(
		"One Task Link",
		filters={"task": name, "parenttype": "One Task", "kind": BLOCKED_BY},
		pluck="parent",
	)


def related(name: str) -> list[str]:
	"""What points at this one without waiting for it, either way round."""
	if not name:
		return []
	mine = frappe.get_all(
		"One Task Link",
		filters={"parent": name, "parenttype": "One Task", "kind": RELATES_TO},
		pluck="task",
	)
	theirs = frappe.get_all(
		"One Task Link",
		filters={"task": name, "parenttype": "One Task", "kind": RELATES_TO},
		pluck="parent",
	)
	return sorted(set(mine) | set(theirs))


def refuse_a_cycle(doc) -> None:
	"""Refuse a task whose dependencies close a loop.

	Walked from each thing this task now waits for, over what is *stored* —
	the row being added is the only new edge, and it is the one we are asking
	about. A loop is named rather than counted: "REEM-3 → REEM-9 → REEM-3" is
	something somebody can go and fix.
	"""
	wanted = [row.task for row in (doc.get("links") or [])
	          if row.kind == BLOCKED_BY and row.task]
	if not wanted:
		return

	for start in wanted:
		if start == doc.name:
			frappe.throw(_("A task cannot wait for itself."))
		path = _walk_to(start, doc.name)
		if path:
			frappe.throw(_("That would make a loop: {0}.").format(
				" → ".join([doc.name or _("this task"), *path])
			))


def _walk_to(start: str, wanted: str) -> list[str] | None:
	"""The path from `start` to `wanted` through blocking edges, if there is one."""
	seen, stack = set(), [(start, [start])]
	while stack:
		here, path = stack.pop()
		if here == wanted:
			return path
		if here in seen or len(seen) > MOST:
			continue
		seen.add(here)
		for further in predecessors(here):
			stack.append((further, [*path, further]))
	return None


def push(name: str, moved_to) -> list[str]:
	"""Move what is waiting on this task, where it now starts too early.

	Returns what moved, so the caller can say so. Breadth-first over the edges
	with a seen set, which is what keeps a diamond — two tasks waiting on one,
	both feeding a third — from moving the far end twice.

	Each task keeps its own duration: a two-week job pushed by three days is
	still a two-week job. A dependent with no start date is left alone rather
	than given one, because a task nobody has scheduled is not late.
	"""
	moved, seen = [], set()
	queue = [(name, getdate(moved_to))]
	while queue:
		after, ends = queue.pop(0)
		if not ends:
			continue
		for waiting in dependents(after):
			if waiting in seen:
				continue
			seen.add(waiting)
			if len(moved) >= MOST:
				frappe.throw(_("That date moves more than {0} tasks. Move them "
				               "in smaller pieces, or take the link off.")
				             .format(MOST))
			task = frappe.get_doc("One Task", waiting)
			if not task.starts_on or getdate(task.starts_on) > ends:
				continue
			shift = date_diff(add_days(ends, 1), task.starts_on)
			task.starts_on = add_days(task.starts_on, shift)
			if task.due_on:
				task.due_on = add_days(task.due_on, shift)
			# `flags` rather than a parameter: the save runs the controller,
			# which calls this again for whatever *that* task blocks, and the
			# queue here is what bounds the whole cascade instead.
			task.flags.pushed_by = after
			task.save(ignore_permissions=True)
			moved.append(waiting)
			queue.append((waiting, getdate(task.due_on) if task.due_on else None))
	return moved


@frappe.whitelist(methods=["GET"])
def around(name: str) -> dict:
	"""One task's edges, for a surface that draws them.

	Three lists and the subject of each, because a record showing `REEM-0007`
	is a record showing an id. Permissions are the framework's: this reads
	`One Task`, and a person who may not read one gets nothing for it.
	"""
	frappe.has_permission("One Task", "read", doc=name, throw=True)
	return {
		"blocked_by": _titles(predecessors(name)),
		"blocks": _titles(dependents(name)),
		"relates_to": _titles(related(name)),
	}


def _titles(names: list[str]) -> list[dict]:
	if not names:
		return []
	found = frappe.get_all(
		"One Task",
		filters={"name": ["in", names]},
		fields=["name", "subject", "status", "due_on"],
	)
	return [dict(row) for row in found]
