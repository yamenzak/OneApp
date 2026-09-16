"""ERPNext's Task, with the five things a board needs and one better name.

`docs/WORK.md` §12. OneProject is ERPNext's Projects module the way OnePeople
is Frappe HR: their `Task` is the unit of work and nothing here replaces it.
What this class does is the part a custom field cannot — run on save — and it
is three small things.

**A task is named after its project.** `REEM-14` is what people say to each
other and `TASK-00042` is not. Frappe runs `autoname` before the doctype's own
`naming_series` rule, so a project with no key falls straight through to
ERPNext's series with nothing to configure.

**The state decides the status.** `custom_state` is a row a team named and
`status` is ERPNext's own Select, which its controller, its Gantt and its
project rollups all read. One is written from the other's category, on one
path, so "is this finished" has an answer in both vocabularies and they cannot
disagree.

**Where a card sits is a string.** `custom_rank` is minted on the way in, so
dragging one card rewrites one row rather than a column of two hundred.

Everything else — dependencies, the nested set, milestones, dates, progress,
costing — is ERPNext's and stays ERPNext's.
"""

import frappe
import frappe.model.naming
from erpnext.projects.doctype.task.task import Task as ERPNextTask

from oneapp.onetask import ranking, states

#: The field a project's key lives on — `oneproject.CUSTOM_FIELDS`.
KEY = "custom_key"

#: Ours, on their Task.
STATE = "custom_state"
RANK = "custom_rank"


class ProjectTask(ERPNextTask):
	def autoname(self):
		"""`REEM-14` where the project has a key, ERPNext's series where not.

		The counter is per prefix, which makes it per project for free: two
		projects with different keys never collide, and one that changes its
		key leaves its existing tasks named after the old one — which is
		right. A task's id is what somebody wrote on a whiteboard, and
		renaming a hundred of them because the project was renamed is worse
		than a hundred ids that are still correct about where they came from.
		"""
		key = (frappe.db.get_value("Project", self.project, KEY) or "").strip()
		if key:
			self.name = frappe.model.naming.make_autoname(f"{key.upper()}-.####")

		# And nothing where there is no key. Not a call to `super()`: neither
		# ERPNext's Task nor `Document` defines one, because the name comes
		# from the doctype's own `TASK-.YYYY.-.#####` rule — which Frappe
		# applies exactly when this leaves `self.name` unset.

	def validate(self):
		"""ERPNext's whole validation, plus the two fields it does not know.

		Before `super()` rather than after: their `validate` reads `status` —
		for the dependency check, for `completed_on`, for the project rollup —
		so a status written afterwards would be a status their own rules never
		saw.
		"""
		self._status_from_state()
		self._rank_if_missing()
		super().validate()

	def _status_from_state(self) -> None:
		"""Their word for ours, where a team has chosen one.

		A task with no state keeps whatever status it was given, because a
		workspace that never opened the board should not have its tasks
		rewritten by a field it has not used.
		"""
		if not self.get(STATE):
			return
		status = states.status_of(self.get(STATE))
		if status:
			self.status = status

	def _rank_if_missing(self) -> None:
		if self.get(RANK):
			return
		self.set(RANK, ranking.after(_last_rank(self.get(STATE), self.project)))


def _last_rank(state: str, project: str | None) -> str:
	"""The rank at the bottom of the column this task is joining."""
	found = frappe.get_all(
		"Task",
		filters={STATE: state or "", "project": project or ""},
		fields=[RANK],
		order_by=f"{RANK} desc",
		limit_page_length=1,
	)
	return (found[0].get(RANK) if found else "") or ""
