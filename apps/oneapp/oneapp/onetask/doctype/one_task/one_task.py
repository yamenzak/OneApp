"""One piece of work.

Three things happen on save and none of them is a second source of truth.

**The category is copied down.** `state` is a Link, because that is the whole
of "a board has its own columns" — and the engine's badge, its filters and
every "is it finished" want a Select, which a Link cannot be. So the state's
own `category` lands on the task as `status`. Derived, on one path, from one
place: `docs/WORK.md` §5.

**The rank is minted where there is none.** Where a card sits in its column is
a string that sorts, so dragging one card rewrites one row rather than the
whole column — `onetask/ranking.py` has the argument.

**And the project's counts are kept.** A portfolio of forty projects should be
one query rather than forty, so `open_tasks` and `done_tasks` are rolled up
here rather than counted on every read.
"""

import frappe
from frappe.model.document import Document

from oneapp.onetask import ranking, states


class OneTask(Document):
	def before_save(self):
		self.status = states.category_of(self.state)
		if not self.rank:
			self.rank = ranking.after(_last_rank(self.state, self.project))

		# Who finished it, and when — written here rather than asked for,
		# because "who moved this to Done" is a fact the row already has and a
		# field somebody has to fill in is a field that is wrong by Friday.
		if self.status == "Done" and not self.completed_on:
			self.completed_on = frappe.utils.now_datetime()
			self.completed_by = frappe.session.user
		elif self.status != "Done":
			self.completed_on = None
			self.completed_by = None

	def on_update(self):
		_recount(self.project)
		# The project it *left*, which is the half a rollup forgets: moving the
		# last open task off a project leaves that project saying one is open
		# for ever.
		was = (self.get_doc_before_save() or {}).get("project") if not self.is_new() else None
		if was and was != self.project:
			_recount(was)

	def on_trash(self):
		_recount(self.project)


def _last_rank(state: str, project: str | None) -> str:
	"""The rank at the bottom of the column this task is joining."""
	found = frappe.get_all(
		"One Task",
		filters={"state": state or "", "project": project or ""},
		fields=["rank"],
		order_by="rank desc",
		limit_page_length=1,
	)
	return (found[0].rank if found else "") or ""


def _recount(project: str | None) -> None:
	"""How many of a project's tasks are open and how many are done."""
	if not project:
		return
	# Two counts rather than a grouped one: Frappe v17 refuses a SQL function
	# written as a string in `fields`, and the dict form it wants back is
	# harder to read than asking twice for something this small.
	total = frappe.db.count("One Task", {"project": project})
	done = frappe.db.count("One Task", {
		"project": project, "status": ["in", ("Done", "Cancelled")],
	})
	frappe.db.set_value("One Project", project, {
		"open_tasks": total - done, "done_tasks": done,
	}, update_modified=False)
