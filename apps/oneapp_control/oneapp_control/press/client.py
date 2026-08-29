"""Thin client over the Frappe Cloud (press) HTTP API.

We are a press *customer*, not its operator — we never reach the per-server
`agent` daemon directly. Press's whitelisted API is the entire provisioning
boundary.

Errors are classified rather than raised uniformly, because the retry decision
depends on it: a 503 should be retried, a 400 never should. Retrying a permanent
failure forever is how a provisioning queue quietly stops working.
"""

import json

import frappe
import requests

TIMEOUT = 30


class PressError(Exception):
	def __init__(self, message, status_code=None, payload=None):
		super().__init__(message)
		self.status_code = status_code
		self.payload = payload


class PressTransientError(PressError):
	"""Worth retrying: network failure, rate limit, or a 5xx."""


class PressPermanentError(PressError):
	"""Not worth retrying: bad request, auth failure, or a rejected argument."""


def settings():
	return frappe.get_single("OneApp Control Settings")


class PressClient:
	def __init__(self, url=None, api_key=None, api_secret=None):
		s = settings()
		self.url = (url or s.press_api_url or "https://frappecloud.com").rstrip("/")
		self.api_key = api_key or s.press_api_key
		self.api_secret = api_secret or s.get_password("press_api_secret", raise_exception=False)

		if not (self.api_key and self.api_secret):
			raise PressPermanentError(
				"Press API credentials are not configured in OneApp Control Settings."
			)

	# ------------------------------------------------------------------ #

	def _headers(self):
		return {
			"Authorization": f"token {self.api_key}:{self.api_secret}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

	def call(self, method: str, **params):
		"""Invoke a whitelisted press method and return its `message` payload."""
		endpoint = f"{self.url}/api/method/{method}"

		try:
			response = requests.post(
				endpoint,
				headers=self._headers(),
				data=json.dumps(params),
				timeout=TIMEOUT,
			)
		except requests.Timeout as e:
			raise PressTransientError(f"Timeout calling {method}") from e
		except requests.RequestException as e:
			raise PressTransientError(f"Network error calling {method}: {e}") from e

		return self._handle(method, response)

	def _handle(self, method, response):
		status = response.status_code

		if status == 200:
			try:
				return response.json().get("message")
			except ValueError as e:
				raise PressPermanentError(
					f"{method} returned non-JSON body", status, response.text[:500]
				) from e

		detail = self._error_detail(response)

		# 429 and 5xx are worth another attempt. Everything else in 4xx is our
		# fault and will fail identically forever.
		if status == 429 or status >= 500:
			raise PressTransientError(f"{method} failed: {detail}", status, detail)

		raise PressPermanentError(f"{method} failed: {detail}", status, detail)

	@staticmethod
	def _error_detail(response):
		try:
			body = response.json()
		except ValueError:
			return response.text[:500]

		for key in ("exception", "_server_messages", "message", "exc"):
			if body.get(key):
				return str(body[key])[:500]

		return str(body)[:500]

	# ------------------------------------------------------------------ #
	# Sites
	# ------------------------------------------------------------------ #

	def site_exists(self, subdomain: str, domain: str) -> bool:
		return bool(self.call("press.api.site.exists", subdomain=subdomain, domain=domain))

	def create_site(
		self,
		subdomain: str,
		domain: str,
		release_group: str,
		apps: list[str],
		plan: str | None = None,
		server: str | None = None,
		cluster: str | None = None,
	) -> dict:
		"""Returns {"site": <name>, "job": <agent job id>}."""
		payload = {
			"name": subdomain,
			"domain": domain,
			"group": release_group,
			"apps": apps,
		}
		if plan:
			payload["plan"] = plan
		if server:
			payload["server"] = server
		if cluster:
			payload["cluster"] = cluster

		return self.call("press.api.site.new", site=payload)

	def job(self, job_id) -> dict:
		return self.call("press.api.site.job", job=job_id) or {}

	def update_config(self, site: str, config: dict):
		"""Inject keys into the site's site_config.json.

		Press rejects blacklisted and internal keys but accepts our own, typing
		them from the value. Note these land as plain String config visible in the
		Frappe Cloud dashboard — fine for our own account, but it is why the
		per-tenant secret is scoped to that tenant and nothing else.
		"""
		return self.call("press.api.site.update_config", name=site, config=json.dumps(config))

	def deactivate(self, site: str):
		return self.call("press.api.site.deactivate", name=site)

	def activate(self, site: str):
		return self.call("press.api.site.activate", name=site)

	def backup(self, site: str, with_files: bool = True):
		return self.call("press.api.site.backup", name=site, with_files=with_files)

	def archive(self, site: str, force: bool = False):
		return self.call("press.api.site.archive", name=site, force=force)

	def migrate(self, site: str, skip_failing_patches: bool = False):
		return self.call(
			"press.api.site.migrate", name=site, skip_failing_patches=skip_failing_patches
		)

	def change_plan(self, site: str, plan: str):
		return self.call("press.api.site.change_plan", name=site, plan=plan)

	def login_link(self, site: str, reason: str = "support"):
		"""One-shot admin login for support. Every use should be audited."""
		return self.call("press.api.site.login", name=site, reason=reason)

	def get_site(self, site: str) -> dict:
		return self.call("press.api.site.get", name=site) or {}

	# ------------------------------------------------------------------ #
	# Domains — no dedicated API, so go through the generic doc-method gateway
	# ------------------------------------------------------------------ #

	def run_doc_method(self, doctype: str, name: str, method: str, args: dict | None = None):
		return self.call(
			"press.api.client.run_doc_method",
			dt=doctype,
			dn=name,
			method=method,
			args=json.dumps(args or {}),
		)

	def add_domain(self, site: str, domain: str):
		return self.run_doc_method("Site", site, "add_domain", {"domain": domain})

	def set_primary_domain(self, site: str, domain: str):
		return self.run_doc_method("Site", site, "set_host_name", {"domain": domain})

	def remove_domain(self, site: str, domain: str):
		return self.run_doc_method("Site", site, "remove_domain", {"domain": domain})


def get_client() -> PressClient:
	return PressClient()
