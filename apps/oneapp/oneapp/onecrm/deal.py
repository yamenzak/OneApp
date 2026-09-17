"""ERPNext's Opportunity, drawn by a column a team named.

`docs/ONECRM.md`. OneCRM is ERPNext's CRM module the way OnePeople is Frappe
HR: their Opportunity is the deal and nothing here replaces it. What this class
does is the part a custom field cannot — run on save — and it is two things.

**The stage decides the status.** `custom_stage` is a row a team named and
`status` is ERPNext's own Select, which their controller, their prospect
rollup and every report over the module read. One is written from the other's
category, on one path, so "did we win it" has an answer in both vocabularies
and they cannot disagree.

**A stage carries a probability, and a deal may disagree.** The stage's number
is what the desk assumes; the number on the deal is what the person selling it
says. So it is written when the deal *arrives* at a stage and never again — a
rep who typed 80% on a deal sitting in Proposal keeps it, and moving the card
is what asks the question again.

**And where it has been is kept.** `docs/ONECRM.md` stage 2: a pipeline review
is not held to ask what is in Negotiation, it is held to ask what has been in
Negotiation for forty days. Each arrival appends a `One Stage Change` row and
closes the one before it, and the *current* arrival is mirrored onto
`custom_stage_since` — because a child table cannot be sorted on and "longest
stuck first" is a sort. A Datetime rather than a day count, which would be
wrong by one every midnight.

Everything else — the party, the items, the totals, the quotation, the lost
reasons — is ERPNext's and stays ERPNext's.
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from erpnext.crm.doctype.opportunity.opportunity import Opportunity as ERPNextOpportunity

from oneapp.onecrm import stages

#: Ours, on their Opportunity — `onecrm.CUSTOM_FIELDS`.
STAGE = "custom_stage"
LOG = "custom_stage_log"
SINCE = "custom_stage_since"

#: How many arrivals one deal keeps.
#:
#: A deal that has moved two hundred times is a deal somebody is dragging
#: around a board, and the oldest rows are the least interesting: what a
#: review asks is where it is *now* and how long it has been there. Past this
#: the earliest row is dropped, which keeps the record openable.
MOST = 100


class Deal(ERPNextOpportunity):
	def validate(self):
		"""ERPNext's whole validation, plus the field it does not know.

		Before `super()` rather than after: their `validate` reads `status` —
		`map_fields` and the prospect rollup both do — so a status written
		afterwards would be one their own rules never saw.
		"""
		self._from_stage()
		self._log_the_move()
		super().validate()

	def _from_stage(self) -> None:
		"""Their word for ours, and the probability the column assumes.

		A deal with no stage keeps whatever status it was given, because a
		workspace that has not opened the pipeline should not have its deals
		rewritten by a field it has not used.
		"""
		stage = self.get(STAGE)
		if not stage:
			return

		status = stages.status_of(stage)
		if status:
			self.status = status

		# Only on arrival. `get_doc_before_save` is None on an insert, which is
		# an arrival too — a deal made straight into Negotiation should carry
		# that column's number rather than nothing.
		was = (self.get_doc_before_save() or {}).get(STAGE) if not self.is_new() else None
		if was == stage:
			return
		assumed = stages.probability_of(stage)
		if assumed is not None:
			self.probability = assumed

	def _log_the_move(self) -> None:
		"""Close the row for where it was, and open one for where it is.

		Driven off the child table rather than off `custom_stage_since`: the
		last open row *is* where the deal was, so the log cannot drift from the
		field even if somebody writes one of them by hand. The field is the
		copy, because a sort needs a column.

		A deal with no stage logs nothing, and a deal saved without moving
		touches neither — this runs on every save of every deal on the site.
		"""
		stage = self.get(STAGE)
		if not stage:
			return

		rows = self.get(LOG) or []
		open_row = rows[-1] if rows and not rows[-1].left_on else None
		if open_row and open_row.stage == stage:
			return

		now = now_datetime()
		if open_row:
			open_row.left_on = now
			open_row.days = round(
				time_diff_in_hours(now, open_row.entered_on) / 24.0, 2)

		self.append(LOG, {
			"stage": stage, "entered_on": now, "moved_by": frappe.session.user,
		})
		if len(self.get(LOG)) > MOST:
			self.set(LOG, self.get(LOG)[-MOST:])
		self.set(SINCE, now)
