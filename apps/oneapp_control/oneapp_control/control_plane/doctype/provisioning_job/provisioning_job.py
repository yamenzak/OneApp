import json

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime


class ProvisioningJob(Document):
	def parsed_payload(self) -> dict:
		if not self.payload:
			return {}
		try:
			return json.loads(self.payload) or {}
		except (json.JSONDecodeError, TypeError):
			return {}

	# ------------------------------------------------------------------ #
	# State transitions. All use db_set so a crash mid-step still records
	# where we got to.
	# ------------------------------------------------------------------ #

	def wait_for_agent(self):
		from oneapp_control.provisioning.runner import backoff_for

		attempts = (self.attempts or 0) + 1
		self.db_set("attempts", attempts)
		self.db_set("state", "Awaiting Agent")
		self.db_set(
			"next_retry_at", add_to_date(now_datetime(), seconds=backoff_for(attempts))
		)

	def retry_later(self, error: str):
		from oneapp_control.provisioning.runner import MAX_ATTEMPTS, backoff_for

		attempts = (self.attempts or 0) + 1
		self.db_set("attempts", attempts)
		self.db_set("last_error", error)

		if attempts >= MAX_ATTEMPTS:
			return self.fail(f"Giving up after {attempts} attempts. Last error: {error}")

		self.db_set("state", "Running")
		self.db_set(
			"next_retry_at", add_to_date(now_datetime(), seconds=backoff_for(attempts))
		)

	def fail(self, error: str):
		self.db_set("state", "Failed")
		self.db_set("last_error", error)
		self.db_set("finished_at", now_datetime())

		# A failed Create Site leaves the tenant unusable; say so plainly rather
		# than leaving it stuck on Provisioning forever.
		if self.action == "Create Site":
			frappe.get_doc("Tenant", self.tenant).mark_failed(error)

	def succeed(self):
		self.db_set("state", "Succeeded")
		self.db_set("finished_at", now_datetime())
		self.db_set("last_error", None)

	def reset(self):
		"""Re-run a failed job from the beginning of its pipeline."""
		self.db_set("state", "Requested")
		self.db_set("step", None)
		self.db_set("attempts", 0)
		self.db_set("last_error", None)
		self.db_set("finished_at", None)
		self.db_set("next_retry_at", now_datetime())

	@frappe.whitelist()
	def retry(self):
		"""Operator action from the desk UI."""
		self.reset()
		return self.name
