"""Bringing the platform's mail up, from a token.

One endpoint that runs every step Cloudflare exposes an API for, in order and
idempotently, and answers with what each one did. Meant to be pressed whenever
somebody is unsure rather than once at the beginning: every step finds what is
already there and leaves it alone.

    1. a KV namespace for the tenant map          Workers KV
    2. the inbound worker, with its bindings      Workers Scripts
    3. Email Routing on the zone                  adds and locks MX and SPF
    4. the catch-all, pointed at the worker       one rule, for ever

Step five is not here because Cloudflare has no API for it: onboarding the
domain for **Email Sending** is a dashboard action. `bring_up` says so in its
answer rather than quietly succeeding, and `readiness` keeps saying so until it
is done.
"""

import frappe
from frappe import _

from oneapp_control.cloudflare import api as cf
from oneapp_control.cloudflare import email as routing
from oneapp_control.cloudflare import workers

from .guard import _require_manager


@frappe.whitelist(methods=["POST"])
def bring_up() -> dict:
	"""Run every step of the mail bring-up. Safe to run again.

	Each step answers `ok` and a line saying what happened, so a half-finished
	bring-up reads as a list with a cross partway down rather than as one
	exception naming whichever call failed.
	"""
	_require_manager()

	steps = []
	namespace = None

	try:
		namespace = workers.ensure_namespace()
		steps.append(_step("KV namespace", True, namespace))
	except Exception as e:
		steps.append(_step("KV namespace", False, str(e)))
		return _answer(steps)

	try:
		deployed = workers.deploy()
		steps.append(
			_step("Inbound worker", True,
			      _("{0}, routing {1}").format(deployed["script"], deployed["mail_domain"]))
		)
	except Exception as e:
		steps.append(_step("Inbound worker", False, str(e)))
		return _answer(steps)

	try:
		routing.enable()
		steps.append(_step("Email Routing", True, _("Enabled; MX and SPF written and locked.")))
	except Exception as e:
		steps.append(_step("Email Routing", False, str(e)))
		return _answer(steps)

	try:
		routing.point_catch_all()
		steps.append(
			_step("Catch-all", True,
			      _("Everything on the zone goes to {0}.").format(workers.SCRIPT_NAME))
		)
	except Exception as e:
		steps.append(_step("Catch-all", False, str(e)))

	sending = routing.sending_ready()
	steps.append(
		_step("Email Sending", sending["ok"], f"{sending['detail']} {sending['where']}"
		      if not sending["ok"] else sending["detail"])
	)

	return _answer(steps)


@frappe.whitelist(methods=["GET"])
def readiness() -> dict:
	"""What the mail platform looks like right now, without changing anything."""
	_require_manager()

	s = cf.settings()
	zone = routing.status()
	script = workers.deployed()
	sending = routing.sending_ready()

	return {
		"mail_domain": s.mail_domain,
		"checks": [
			_check("Account token", bool(cf.token("admin")),
			       _("Account-wide token, control plane only.")),
			_check("KV namespace", bool(s.cf_kv_namespace_id), s.cf_kv_namespace_id or
			       _("Not created. Run the bring-up.")),
			_check("Inbound worker", bool(script),
			       workers.SCRIPT_NAME if script else _("Not deployed.")),
			_check("Email Routing", bool(zone.get("enabled")),
			       zone.get("status") or zone.get("reason") or _("Not enabled.")),
			_check("Catch-all", routing.points_at_worker(),
			       _("Pointed at the worker.") if routing.points_at_worker()
			       else _("Not pointed at the worker.")),
			_check("Email Sending", sending["ok"],
			       sending["detail"] if sending["ok"]
			       else f"{sending['detail']} {sending['where']}"),
		],
	}


def _step(label: str, ok: bool, detail: str) -> dict:
	return {"label": label, "ok": bool(ok), "detail": detail}


_check = _step


def _answer(steps: list[dict]) -> dict:
	return {"ok": all(one["ok"] for one in steps), "steps": steps}
