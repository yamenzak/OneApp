"""A document that expires, and the warning before it does.

The register is worth keeping for one reason: it tells somebody a licence
lapses in three weeks. Everything else on the doctype is bookkeeping around
that, and this file is the two halves of it — a status that cannot disagree
with the date beside it, and a job that says so once.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate

# What the status means, and it is worked out rather than typed. A status
# somebody can set is a status that eventually says Valid over a date in 2019.
VALID = "Valid"
EXPIRING = "Expiring"
EXPIRED = "Expired"
NONE = "No expiry"


def standing(expiry, remind_days: int, today=None) -> str:
	"""Where one document stands, from its date and its warning window.

	A function rather than a method so the daily job can ask about a thousand
	rows without loading a thousand documents — and so this is testable without
	a database, which is what the rule deserves.
	"""
	if not expiry:
		# Not the same as unknown. A deed does not expire, and a register that
		# called that "Expired" would cry wolf on every one of them.
		return NONE

	expiry = getdate(expiry)
	today = getdate(today or nowdate())

	if expiry < today:
		return EXPIRED
	if expiry <= getdate(add_days(today, max(int(remind_days or 0), 0))):
		return EXPIRING
	return VALID


class ComplianceDocument(Document):
	def validate(self):
		self.status = standing(self.expiry_date, self.remind_days)

		if self.renews and self.renews == self.name:
			frappe.throw(_("A document cannot renew itself."))

	def on_update(self):
		"""Point the old document at the new one.

		Written from this side because this is the side that knows: somebody
		files the renewal and names what it replaces, and nobody goes back to
		the expired one to say it was replaced. Doing it here is what makes the
		chain readable from either end.
		"""
		if not self.renews:
			return
		if frappe.db.get_value("Compliance Document", self.renews, "renewed_by") != self.name:
			frappe.db.set_value("Compliance Document", self.renews, "renewed_by", self.name,
			                    update_modified=False)
