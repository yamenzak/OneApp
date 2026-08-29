import frappe
from frappe import _
from frappe.model.document import Document

# Hosts that 308-redirect to the canonical one. `requests` follows the redirect
# and drops the Authorization header on the way — the second request arrives
# unauthenticated, and press answers "Function … is not whitelisted", which
# reads as a permissions problem with the API key rather than a wrong hostname.
#
# Refused rather than warned about: every press call fails, and the error names
# the wrong cause. Half an hour of looking at API key scopes is the usual price.
REDIRECTING_PRESS_HOSTS = ("frappecloud.com", "www.frappecloud.com")

CANONICAL_PRESS_URL = "https://cloud.frappe.io"


class OneAppControlSettings(Document):
	def validate(self):
		self.validate_press_url()

	def validate_press_url(self):
		url = (self.press_api_url or "").strip().rstrip("/")
		if not url:
			return

		host = url.split("://", 1)[-1].split("/", 1)[0].lower()
		if host in REDIRECTING_PRESS_HOSTS:
			frappe.throw(
				_(
					"{0} redirects to {1}, and the redirect drops the API "
					"credential — every call would fail as though the key were "
					"wrong. Use {1}."
				).format(host, CANONICAL_PRESS_URL)
			)

		self.press_api_url = url
