"""One stretch of somebody's time.

Everything derived is derived here and on one path: the length from the two
ends, the project from the task, and the task's own total from all of its
entries. `onetask/timing.py` has the argument for why a running entry is a row
with no end rather than a flag.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_seconds

from oneapp.onetask import timing


class OneTimeEntry(Document):
	def validate(self):
		if self.ends_at and get_datetime(self.ends_at) < get_datetime(self.starts_at):
			frappe.throw(_("That stretch ends before it starts."))

		# The project is the task's, always. Not asked for and not editable:
		# moving a task to another project moves its time with it, and a row
		# that remembered the old one would be an invoice against the wrong
		# client.
		self.project = frappe.db.get_value("One Task", self.task, "project") or None
		self.minutes = _length(self.starts_at, self.ends_at)

	def on_update(self):
		timing.recount(self.task)
		was = (self.get_doc_before_save() or {}).get("task") if not self.is_new() else None
		if was and was != self.task:
			timing.recount(was)

	def after_delete(self):
		# And not `on_trash`, which runs before the row goes — the same
		# correction `One Task.after_delete` needed for the project's counts.
		timing.recount(self.task)


def _length(starts_at, ends_at) -> int:
	"""Whole minutes between the two ends, or nothing while it is running."""
	if not (starts_at and ends_at):
		return 0
	seconds = time_diff_in_seconds(get_datetime(ends_at), get_datetime(starts_at))
	return max(0, int(seconds // 60))
