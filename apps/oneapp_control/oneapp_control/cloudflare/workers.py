"""The inbound email worker: its KV namespace, and getting it deployed.

The script itself is `cloudflare/worker/email-inbound.js`, a bundle built from
`workers/email-inbound/` and checked in — Cloudflare's upload API takes one file
and the worker imports a MIME parser, and a deployed control plane has no
`workers/` directory to build from. `tests/test_worker_bundle.py` is what keeps
the bundle and its source in step.

Everything here is idempotent. Uploading the same script twice replaces it,
creating a namespace that exists finds it instead, and the whole thing is meant
to be run again whenever an operator wonders whether it is still right.
"""

import json
from pathlib import Path

import frappe
from frappe import _

from . import api

SCRIPT_NAME = "oneapp-email-inbound"
NAMESPACE_TITLE = "oneapp-tenants"
BINDING = "TENANTS"

#: Pinned rather than "today": a compatibility date is the runtime's behaviour,
#: and one that moves on every deploy is a runtime that changes under a worker
#: nobody edited. Matches `workers/email-inbound/wrangler.toml`.
COMPATIBILITY_DATE = "2026-01-01"
COMPATIBILITY_FLAGS = ["nodejs_compat"]

BUNDLE = Path(__file__).resolve().parent / "worker" / "email-inbound.js"


def bundle() -> str:
	if not BUNDLE.exists():
		frappe.throw(
			_("The email worker has not been built. Run `npm run build` in "
			  "workers/email-inbound.")
		)
	return BUNDLE.read_text()


# --------------------------------------------------------------------------- #
# KV
# --------------------------------------------------------------------------- #

def ensure_namespace() -> str:
	"""The namespace the worker reads tenants out of. Its id, created if new.

	Found by title rather than remembered blindly, so an operator who deleted
	the id from settings does not get a second namespace and a worker reading
	the empty one.
	"""
	s = api.settings()
	if s.cf_kv_namespace_id:
		return s.cf_kv_namespace_id

	# Deliberately the whole list: an account has a handful of namespaces and
	# paging through them is cheaper than getting the wrong one.
	found = api.call(
		"GET",
		f"accounts/{api.account_id()}/storage/kv/namespaces",
		purpose="kv",
		params={"per_page": 100},
	)
	for one in found or []:
		if one.get("title") == NAMESPACE_TITLE:
			return _remember(one["id"])

	made = api.call(
		"POST",
		f"accounts/{api.account_id()}/storage/kv/namespaces",
		purpose="kv",
		json={"title": NAMESPACE_TITLE},
	)
	return _remember(made["id"])


def _remember(namespace: str) -> str:
	frappe.db.set_single_value("OneSpace Control Settings", "cf_kv_namespace_id", namespace)
	return namespace


# --------------------------------------------------------------------------- #
# The script
# --------------------------------------------------------------------------- #

def deploy(mail_domain: str = "") -> dict:
	"""Upload the worker with its bindings. Replaces whatever is there.

	Multipart, because that is the only shape the script API takes: a
	`metadata` part that is the `wrangler.toml` in JSON, and the module itself
	as a part named by `main_module`.
	"""
	namespace = ensure_namespace()
	domain = mail_domain or api.settings().mail_domain or ""
	if not domain:
		frappe.throw(_("Set the mail domain before deploying the worker."))

	metadata = {
		"main_module": "email-inbound.js",
		"compatibility_date": COMPATIBILITY_DATE,
		"compatibility_flags": COMPATIBILITY_FLAGS,
		"bindings": [
			{"type": "kv_namespace", "name": BINDING, "namespace_id": namespace},
			{"type": "plain_text", "name": "MAIL_DOMAIN", "text": domain},
			# Cloudflare's own inbound ceiling. Bigger than this and the message
			# still arrives; the attachment is what is left behind.
			{"type": "plain_text", "name": "MAX_ATTACHMENT_BYTES", "text": "25000000"},
		],
	}

	api.call(
		"PUT",
		f"accounts/{api.account_id()}/workers/scripts/{SCRIPT_NAME}",
		files={
			"metadata": (None, json.dumps(metadata), "application/json"),
			# The part's *name* is what `main_module` points at, which is why it
			# is the filename and not something descriptive.
			"email-inbound.js": (
				"email-inbound.js", bundle(), "application/javascript+module",
			),
		},
	)

	return {"script": SCRIPT_NAME, "namespace": namespace, "mail_domain": domain}


def deployed() -> dict | None:
	"""What Cloudflare has, or None if it has never heard of this worker."""
	try:
		return api.call(
			"GET", f"accounts/{api.account_id()}/workers/scripts/{SCRIPT_NAME}/settings"
		)
	except api.CloudflareError:
		return None
