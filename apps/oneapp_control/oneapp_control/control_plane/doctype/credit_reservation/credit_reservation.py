import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class CreditReservation(Document):
	def validate(self):
		if self.credits_reserved <= 0:
			frappe.throw(_("Reserved credits must be positive."))

	def commit_usage(self, actual_credits: float, remarks: str | None = None):
		"""Convert a reservation into a real Spend for what was actually used."""
		from oneapp_control.credits.ledger import post_entry

		if self.status != "Open":
			frappe.throw(
				_("Reservation {0} is {1}, not Open.").format(self.name, self.status)
			)

		actual = min(float(actual_credits), float(self.credits_reserved))

		if actual > 0:
			post_entry(
				tenant=self.tenant,
				entry_type="Spend",
				credits=-actual,
				reservation=self.name,
				remarks=remarks or self.purpose,
			)

		self.db_set("credits_committed", actual)
		self.db_set("status", "Committed")
		self.db_set("committed_on", now_datetime())

	def release(self, reason: str = "released"):
		"""Give back an unused reservation. Never posts a ledger entry —
		nothing was spent."""
		if self.status != "Open":
			return

		self.db_set("status", "Released")
		self.db_set("released_on", now_datetime())
		self.db_set("purpose", f"{self.purpose or ''} ({reason})".strip())


def sweep_expired_reservations():
	"""Scheduled. A crashed worker must not strand a tenant's credits forever."""
	stale = frappe.get_all(
		"Credit Reservation",
		filters={"status": "Open", "expires_at": ("<", now_datetime())},
		pluck="name",
	)

	for name in stale:
		doc = frappe.get_doc("Credit Reservation", name)
		doc.db_set("status", "Expired")
		doc.db_set("released_on", now_datetime())

	if stale:
		frappe.db.commit()

	return len(stale)
