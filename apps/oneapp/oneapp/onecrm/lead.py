"""ERPNext's Lead, keeping the same history a deal keeps.

`docs/ONECRM.md` stage 2 said the stage log belongs on Lead and Opportunity
both, and the first cut put it only on the deal — so "how long has this sat
unqualified" was unanswerable on exactly the record where it is most often
asked. A lead that goes quiet is lost, and the column that would have said so
was not there.

The field is ERPNext's own `qualification_status` rather than a stage of ours.
A deal's columns are a workspace's to name — `One Deal Stage` — and a lead's
three are not: Unqualified, In Process, Qualified is the question a lead sits
inside, the Leads board is already drawn by it, and inventing a second
vocabulary here would be two words for one fact.

Everything else about a lead is ERPNext's and stays ERPNext's.
"""

from erpnext.crm.doctype.lead.lead import Lead as ERPNextLead

from oneapp.onecrm import progress

#: Theirs, and ours beside it — `onecrm.CUSTOM_FIELDS`.
STATE = "qualification_status"
LOG = "custom_stage_log"
SINCE = "custom_stage_since"


class Lead(ERPNextLead):
	def validate(self):
		"""Their whole validation, plus where this has been."""
		progress.log_the_move(self, STATE, LOG, SINCE)
		super().validate()
