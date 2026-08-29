"""AI calls, routed through Cloudflare AI Gateway and metered against credits.

The gateway is the gateway, not the model provider: Gemini and Workers AI both
sit behind it. What we get from that is caching, rate limiting, retries and —
the part that matters commercially — per-request logs tagged with tenant id, so
AI spend can be reconciled against what we charged for it.

Every call is wrapped in reserve -> execute -> commit/release. Reading a balance
and then spending it is a race two concurrent requests will lose.
"""

import json

import frappe
import requests

from oneapp.oneapp_core import control_client
from oneapp.oneapp_core.ai import pricing

TIMEOUT = 120


class AIError(Exception):
	pass


class OutOfCredits(AIError):
	pass


def config() -> dict:
	conf = frappe.conf
	return {
		"account_id": conf.get("oneapp_cf_account_id"),
		"gateway": conf.get("oneapp_ai_gateway") or "oneapp",
		"gateway_token": conf.get("oneapp_ai_gateway_token"),
		"google_key": conf.get("oneapp_google_ai_key"),
		"cf_token": conf.get("oneapp_cf_api_token"),
		"tenant": conf.get("oneapp_tenant"),
		"markup": float(conf.get("oneapp_ai_markup") or pricing.DEFAULT_MARKUP),
	}


def is_configured() -> bool:
	c = config()
	return bool(c["account_id"] and c["gateway"])


def gateway_url(provider: str, path: str) -> str:
	c = config()
	base = f"https://gateway.ai.cloudflare.com/v1/{c['account_id']}/{c['gateway']}/{provider}"
	return f"{base}/{path.lstrip('/')}"


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #

def _google_request(model: str, prompt: str, max_output_tokens: int, system: str | None):
	c = config()
	body = {
		"contents": [{"role": "user", "parts": [{"text": prompt}]}],
		"generationConfig": {"maxOutputTokens": max_output_tokens},
	}
	if system:
		body["systemInstruction"] = {"parts": [{"text": system}]}

	return (
		gateway_url("google-ai-studio", f"v1beta/models/{model}:generateContent"),
		{"x-goog-api-key": c["google_key"], "Content-Type": "application/json"},
		body,
	)


def _google_parse(payload: dict) -> dict:
	candidates = payload.get("candidates") or []
	text = ""
	if candidates:
		for part in (candidates[0].get("content") or {}).get("parts") or []:
			text += part.get("text") or ""

	usage = payload.get("usageMetadata") or {}
	return {
		"text": text,
		"input_tokens": int(usage.get("promptTokenCount") or 0),
		"output_tokens": int(usage.get("candidatesTokenCount") or 0),
	}


def _workers_request(model: str, prompt: str, max_output_tokens: int, system: str | None):
	c = config()
	messages = ([{"role": "system", "content": system}] if system else []) + [
		{"role": "user", "content": prompt}
	]
	return (
		gateway_url("workers-ai", model),
		{"Authorization": f"Bearer {c['cf_token']}", "Content-Type": "application/json"},
		{"messages": messages, "max_tokens": max_output_tokens},
	)


def _workers_parse(payload: dict) -> dict:
	result = payload.get("result") or {}
	usage = result.get("usage") or {}
	return {
		"text": result.get("response") or "",
		"input_tokens": int(usage.get("prompt_tokens") or 0),
		"output_tokens": int(usage.get("completion_tokens") or 0),
	}


PROVIDERS = {
	"google-ai-studio": (_google_request, _google_parse),
	"workers-ai": (_workers_request, _workers_parse),
}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def complete(
	prompt: str,
	model: str = "gemini-2.5-flash",
	provider: str = "google-ai-studio",
	system: str | None = None,
	max_output_tokens: int = 1024,
	purpose: str = "ai:complete",
) -> dict:
	"""Run a completion, charging the tenant for what it actually used."""
	if not is_configured():
		raise AIError("AI gateway is not configured in site_config.json.")

	if provider not in PROVIDERS:
		raise AIError(f"Unknown provider '{provider}'.")

	c = config()
	estimate = pricing.estimate_credits(
		provider, model, len(prompt or "") + len(system or ""), max_output_tokens, c["markup"]
	)

	reservation = _reserve(estimate, purpose)

	try:
		result = _execute(provider, model, prompt, max_output_tokens, system)
	except Exception:
		# Nothing was used, so nothing is charged.
		_release(reservation, "provider call failed")
		raise

	charged = pricing.credits_for(
		provider, model, result["input_tokens"], result["output_tokens"], c["markup"]
	)
	_commit(reservation, charged, f"{provider}/{model} {purpose}")

	result.update({"credits": charged, "model": model, "provider": provider})
	return result


def _execute(provider, model, prompt, max_output_tokens, system) -> dict:
	build, parse = PROVIDERS[provider]
	url, headers, body = build(model, prompt, max_output_tokens, system)

	c = config()
	if c["gateway_token"]:
		headers["cf-aig-authorization"] = f"Bearer {c['gateway_token']}"
	# Tags the gateway log so spend can be attributed per tenant.
	if c["tenant"]:
		headers["cf-aig-metadata"] = json.dumps({"tenant": c["tenant"]})

	try:
		response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
	except requests.RequestException as e:
		raise AIError(f"AI gateway unreachable: {e}") from e

	if response.status_code != 200:
		raise AIError(f"AI gateway {response.status_code}: {response.text[:300]}")

	return parse(response.json())


# --------------------------------------------------------------------------- #
# Credit plumbing
# --------------------------------------------------------------------------- #

def _reserve(credits: float, purpose: str) -> str | None:
	if credits <= 0:
		return None

	result = control_client.reserve_credits(credits, purpose)
	if not result.get("ok"):
		raise OutOfCredits(
			f"Not enough credits: {result.get('available', 0)} available, "
			f"{credits} needed."
		)
	return result["reservation"]


def _commit(reservation: str | None, credits: float, remarks: str):
	if not reservation:
		return
	try:
		control_client.commit_credits(reservation, credits, remarks)
	except control_client.ControlPlaneError:
		# The work is done and the customer has their answer. A stuck reservation
		# is swept and released by the control plane rather than failing here.
		frappe.log_error(
			title="AI credit commit failed", message=frappe.get_traceback()
		)


def _release(reservation: str | None, reason: str):
	if not reservation:
		return
	try:
		control_client.release_credits(reservation, reason)
	except control_client.ControlPlaneError:
		frappe.log_error(
			title="AI credit release failed", message=frappe.get_traceback()
		)


@frappe.whitelist()
def ask(prompt: str, model: str = "gemini-2.5-flash", purpose: str = "ai:ask") -> dict:
	"""SPA entry point."""
	try:
		return complete(prompt, model=model, purpose=purpose)
	except OutOfCredits as e:
		return {"ok": False, "reason": "insufficient_credits", "message": str(e)}
