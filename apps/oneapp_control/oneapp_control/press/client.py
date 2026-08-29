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
		self.url = (url or s.press_api_url or "https://cloud.frappe.io").rstrip("/")
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

	def call(self, endpoint: str, **params):
		"""Invoke a whitelisted press method and return its `message` payload.

		The positional is named `endpoint`, not `method`: press.api.client.run_doc_method
		takes a parameter called `method`, and a matching positional name makes
		that call raise TypeError before it ever leaves the process.
		"""
		url = f"{self.url}/api/method/{endpoint}"

		try:
			response = requests.post(
				url,
				headers=self._headers(),
				data=json.dumps(params),
				timeout=TIMEOUT,
			)
		except requests.Timeout as e:
			raise PressTransientError(f"Timeout calling {endpoint}") from e
		except requests.RequestException as e:
			raise PressTransientError(f"Network error calling {endpoint}: {e}") from e

		return self._handle(endpoint, response)

	def _handle(self, endpoint, response):
		status = response.status_code

		if status == 200:
			try:
				return response.json().get("message")
			except ValueError as e:
				raise PressPermanentError(
					f"{endpoint} returned non-JSON body", status, response.text[:500]
				) from e

		detail = self._error_detail(response)

		# 429 and 5xx are worth another attempt. Everything else in 4xx is our
		# fault and will fail identically forever.
		if status == 429 or status >= 500:
			raise PressTransientError(f"{endpoint} failed: {detail}", status, detail)

		raise PressPermanentError(f"{endpoint} failed: {detail}", status, detail)

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
		version: str | None = None,
	) -> dict:
		"""Returns {"site": <name>, "job": <agent job id>}.

		On a dedicated server press ignores `group` and re-derives the bench from
		(server, version, apps) — and returns None if `version` is missing, then
		silently falls back to its public marketplace path, which cannot resolve
		our private app sources. So version is effectively required, and the app
		list must be a subset of the bench group's apps.
		"""
		payload = {
			"name": subdomain,
			"domain": domain,
			"group": release_group,
			"apps": apps,
		}
		if version:
			payload["version"] = version
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
		# The API takes a list of {key, value, type}, unlike Site.update_config the
		# doc method, which takes a plain mapping. Passing a dict makes press
		# iterate its keys as strings and fail with a bare ValueError.
		payload = [{"key": k, "value": v, "type": _config_type(v)} for k, v in config.items()]
		return self.call("press.api.site.update_config", name=site, config=json.dumps(payload))

	def update_bench_config(self, release_group: str, config: dict):
		"""Set common site config for a whole bench group.

		Keys that are the same for every tenant — R2 credentials, the Cloudflare
		email token, AI keys — belong here rather than on each site. Frappe merges
		common_site_config into frappe.conf, so every site on the bench inherits
		them and a rotation is one call instead of one per tenant.
		"""
		payload = [{"key": k, "value": v, "type": _config_type(v)} for k, v in config.items()]
		return self.call(
			"press.api.bench.update_config", name=release_group, config=json.dumps(payload)
		)

	# ------------------------------------------------------------------ #
	# Bench deploys — the mechanism behind deploy rings
	# ------------------------------------------------------------------ #

	def deploy_information(self, release_group: str) -> dict:
		return self.call("press.api.bench.deploy_information", name=release_group) or {}

	def deploy_bench(self, release_group: str, only_apps: list[str] | None = None) -> str:
		"""Build and deploy a bench group, returning the build name.

		Press requires both a release and its commit hash per app, and refuses
		the whole deploy if either is missing — so the hash is resolved from each
		app's own releases list rather than assumed.
		"""
		info = self.deploy_information(release_group)

		if info.get("deploy_in_progress"):
			raise PressPermanentError(
				f"A deploy is already running on {release_group}."
			)

		payload = []
		for app in info.get("apps") or []:
			if only_apps and app.get("app") not in only_apps:
				continue
			if not app.get("update_available"):
				continue

			release = app.get("next_release")
			commit = _hash_for_release(app, release)
			if not (release and commit):
				raise PressPermanentError(
					f"No release or commit hash available for {app.get('app')}."
				)

			payload.append(
				{
					"app": app["app"],
					"source": app.get("source"),
					"release": release,
					"hash": commit,
				}
			)

		if not payload:
			raise PressPermanentError("Nothing to deploy — no app has an update.")

		# Sent as a real array, not a JSON string: unlike update_config, this
		# endpoint does not parse its argument. A string gets iterated as
		# characters and fails with a bare AttributeError.
		return self.call("press.api.bench.deploy", name=release_group, apps=payload)

	def deactivate(self, site: str):
		return self.call("press.api.site.deactivate", name=site)

	def activate(self, site: str):
		return self.call("press.api.site.activate", name=site)

	def backup(self, site: str, with_files: bool = True):
		return self.call("press.api.site.backup", name=site, with_files=with_files)

	def archive(self, site: str, force: bool = False):
		return self.call("press.api.site.archive", name=site, force=force)

	def update_site(self, site: str, skip_failing_patches: bool = False):
		"""Move a site onto its bench group's newest bench.

		This is what actually deploys new app code to a site. A successful build
		only produces a new bench — existing sites stay on the old one until they
		are updated, which is what makes staged rollouts possible and what makes
		"the build went green but nothing changed" a confusing first experience.

		Distinct from `migrate`, which runs patches on the site's *current* bench.
		"""
		return self.call(
			"press.api.site.update", name=site, skip_failing_patches=skip_failing_patches
		)

	def migrate(self, site: str, skip_failing_patches: bool = False):
		return self.call(
			"press.api.site.migrate", name=site, skip_failing_patches=skip_failing_patches
		)

	def change_plan(self, site: str, plan: str):
		return self.call("press.api.site.change_plan", name=site, plan=plan)

	def login_link(self, site: str, reason: str = "support"):
		"""One-shot admin login for support. Every use should be audited."""
		return self.call("press.api.site.login", name=site, reason=reason)

	# ------------------------------------------------------------------ #
	# Capacity — what exists on the account to build a shard from
	# ------------------------------------------------------------------ #

	def servers(self) -> list[dict]:
		"""Every server on the account, with the cluster each sits in."""
		return self.call("press.api.server.all") or []

	def release_groups(self) -> list[dict]:
		"""Bench groups. A shard is a (server, group) pair, so both are needed."""
		return self.call("press.api.bench.all") or []

	def group_regions(self, release_group: str) -> list[dict]:
		"""Clusters a bench group can deploy into."""
		return self.call("press.api.bench.regions", name=release_group) or []

	def get_site(self, site: str) -> dict:
		return self.call("press.api.site.get", name=site) or {}

	# ------------------------------------------------------------------ #
	# Fast iteration
	#
	# A normal deploy builds a new image and then moves sites onto it: minutes,
	# and every site restarts. These two skip the image entirely — the agent
	# works on the running bench.
	#
	# Both write code that is not in any image. **The next deploy silently
	# reverts them**, because images are built from git. That makes them right
	# for chasing a bug on a live bench and wrong as a way to ship: a fix that
	# exists only as a patch disappears the next time anything else deploys.
	# ------------------------------------------------------------------ #

	def apply_patch(
		self,
		release_group: str,
		app: str,
		patch: str,
		filename: str = "oneapp.patch",
		build_assets: bool = False,
		bench: str | None = None,
		all_benches: bool = False,
		latest_deploy: bool = True,
	) -> list:
		"""`git apply` a diff to a running bench, without rebuilding the image.

		The agent writes the patch into the container and runs `git apply` in the
		app directory, optionally `bench build`, then restarts. Seconds rather
		than minutes.

		`build_assets` is only needed when the diff touches something the asset
		bundler compiles. Our SPAs are built by Vite into the app's public/
		directory, so a patch that carries the built bundle needs no rebuild —
		but one that changes only frontend source does nothing without it.
		"""
		config = {
			"patch": patch,
			"filename": filename,
			"build_assets": build_assets,
			"patch_all_benches": all_benches,
			"patch_latest_deploy": latest_deploy,
		}
		if bench:
			config["patch_bench"] = bench

		# patch_config goes as a nested object, NOT json.dumps'd. Press does not
		# parse this one — it calls .get() on whatever arrives, so a JSON string
		# raises AttributeError server-side and comes back as a bare HTTP 500
		# with {"exc_type": "AttributeError"} and nothing naming the parameter.
		# (bench.update_config does parse its string, which is exactly why this
		# is easy to get wrong.) Verified against the live API.
		return self.call(
			"press.api.bench.apply_patch",
			release_group=release_group,
			app=app,
			patch_config=config,
		) or []

	def update_inplace(self, release_group: str, apps: list[dict], sites: list[str]):
		"""Pull new app code onto a running bench without building an image.

		`apps` are {"app": ..., "hash": ..., "release": ...} entries as
		`deploy_information` returns them — press validates the hashes, so they
		have to be real releases rather than arbitrary commits.

		Returns the Agent Job name, which `job()` can then be polled with.
		"""
		return self.call(
			"press.api.bench.update_inplace",
			name=release_group,
			apps=json.dumps(apps),
			sites=json.dumps(sites),
		)

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

	def site_domains(self, site: str) -> list:
		"""Domains on a site with their certificate status."""
		return self.call("press.api.site.domains", name=site) or []

	def add_domain(self, site: str, domain: str):
		return self.run_doc_method("Site", site, "add_domain", {"domain": domain})

	def set_primary_domain(self, site: str, domain: str):
		return self.run_doc_method("Site", site, "set_host_name", {"domain": domain})

	def remove_domain(self, site: str, domain: str):
		return self.run_doc_method("Site", site, "remove_domain", {"domain": domain})


def _hash_for_release(app: dict, release: str) -> str | None:
	"""Press returns the hash inside the app's releases list, not beside it."""
	for candidate in app.get("releases") or []:
		if candidate.get("name") == release:
			return candidate.get("hash")
	return None


def _config_type(value) -> str:
	if isinstance(value, bool):
		return "Boolean"
	if isinstance(value, (int, float)):
		return "Number"
	if isinstance(value, (dict, list)):
		return "JSON"
	return "String"


def get_client() -> PressClient:
	return PressClient()
