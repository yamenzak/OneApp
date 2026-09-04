"""The model catalogue, the feature registry, and what tenants spent."""

import frappe
from frappe import _
from .guard import _require_manager


AI_MODEL_EDITABLE = ("status", "capability", "is_recommended", "markup_override",
                     "display_name", "description")


@frappe.whitelist(methods=["GET"])
def ai_models(capability: str | None = None, provider: str | None = None,
              status: str | None = None) -> list:
	_require_manager()

	filters = {}
	for field, value in (("capability", capability), ("provider", provider),
	                     ("status", status)):
		if value:
			filters[field] = value

	models = frappe.get_all(
		"AI Model",
		filters=filters,
		fields=[
			"name", "display_name", "provider", "model_id", "capability", "status",
			"input_modalities", "output_modalities", "context_window",
			"max_output_tokens", "supports_tools", "supports_reasoning",
			"is_recommended", "markup_override", "source", "last_synced",
			"deprecation_date", "sync_note", "description",
		],
		order_by="provider asc, capability asc, display_name asc",
	)

	# The rate matters more than any other field here: it is the number a markup
	# is applied to, and the one that moves without anyone being told.
	for model in models:
		model["prices"] = frappe.get_all(
			"AI Model Price",
			filters={"parent": model["name"]},
			fields=["kind", "modality", "unit", "cost_usd", "per_units", "tier",
			        "effective_from", "effective_to", "note"],
			order_by="tier asc, idx asc",
		)
	return models


@frappe.whitelist(methods=["POST"])
def sync_ai_models() -> dict:
	"""Refetch models and prices now, rather than waiting for the nightly run."""
	_require_manager()

	from oneapp_control.ai import catalogue

	return catalogue.sync()


@frappe.whitelist(methods=["POST"])
def update_ai_model(model: str, values: str | dict) -> dict:
	"""Change the commercial facts about a model. Not the technical ones.

	Prices, modalities and limits come from the provider and are overwritten on
	the next sync, so letting an operator edit them would be a control that
	silently stops working. What is genuinely ours — whether to sell it, what to
	charge on top, what to call it — is what this writes.
	"""
	_require_manager()

	if isinstance(values, str):
		values = frappe.parse_json(values)

	updates = {k: v for k, v in (values or {}).items() if k in AI_MODEL_EDITABLE}
	if not updates:
		frappe.throw(_("Nothing to change. Prices come from the provider."))

	doc = frappe.get_doc("AI Model", model)
	doc.update(updates)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "model": model, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def ai_features() -> list:
	"""Every feature the fleet's apps declare, as reported by tenant sites."""
	_require_manager()

	return frappe.get_all(
		"AI Feature",
		fields=[
			"name", "label", "app", "capability", "status", "tenant_can_disable",
			"allow_prompt_addendum", "default_model", "max_input_tokens",
			"max_output_tokens", "max_images", "max_outputs", "max_audio_seconds",
			"max_credits",
			"description", "last_seen",
		],
		order_by="app asc, label asc",
	)


AI_FEATURE_EDITABLE = ("status", "default_model", "max_input_tokens",
                       "max_output_tokens", "max_images", "max_outputs",
                       "max_audio_seconds", "max_credits")


@frappe.whitelist(methods=["POST"])
def update_ai_feature(feature: str, values: str | dict) -> dict:
	"""Pin a model, tighten a ceiling, or take a feature off the air.

	`tenant_can_disable` is absent from the editable set on purpose: whether a
	workflow can run without AI is a property of the code, declared by the app
	that has to keep working, and an operator flipping it here would be
	overruling the only thing that knows.
	"""
	_require_manager()

	if isinstance(values, str):
		values = frappe.parse_json(values)

	updates = {k: v for k, v in (values or {}).items() if k in AI_FEATURE_EDITABLE}
	if not updates:
		frappe.throw(_("Nothing to change."))

	doc = frappe.get_doc("AI Feature", feature)
	doc.update(updates)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "feature": feature, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def ai_usage(tenant: str | None = None, limit: int = 50) -> list:
	"""Recent calls, with the gateway's verdict where it has arrived."""
	_require_manager()

	return frappe.get_all(
		"AI Usage Record",
		filters={"tenant": tenant} if tenant else {},
		fields=["name", "tenant", "feature", "model", "provider", "credits_charged",
		        "cost_usd", "markup", "cached", "gateway_log_id",
		        "gateway_cost_usd", "reconciled_on", "recon_note", "creation"],
		order_by="creation desc",
		limit=min(int(limit or 50), 200),
	)


@frappe.whitelist(methods=["GET"])
def ai_settings() -> dict:
	"""The gateway's own configuration, and how fresh the catalogue is."""
	_require_manager()

	conf = frappe.get_single("OneSpace Control Settings")
	return {
		"cf_account_id": conf.cf_account_id,
		"ai_gateway": conf.ai_gateway,
		"markup": conf.ai_markup_multiplier,
		"synced_on": conf.ai_catalogue_synced_on,
		"note": conf.ai_catalogue_note,
		# Configured means a sync can run at all. Said plainly because the
		# alternative is an empty catalogue with no explanation.
		"has_cloudflare": bool(conf.cf_account_id
		                       and conf.get_password("cf_api_token", raise_exception=False)),
		"has_google": bool(conf.get_password("google_ai_key", raise_exception=False)),
		# Counted in Python rather than grouped in SQL: frappe.get_all rejects
		# an aggregate written as a string, and the catalogue is a few hundred
		# rows at most.
		"counts": _tally(frappe.get_all("AI Model", pluck="status")),
	}


def _tally(values) -> dict:
	counts: dict[str, int] = {}
	for value in values:
		counts[value] = counts.get(value, 0) + 1
	return counts


@frappe.whitelist(methods=["POST"])
def set_ai_markup(markup: float) -> dict:
	"""The multiplier applied to every model that does not override it."""
	_require_manager()

	markup = float(markup)
	if markup <= 0:
		frappe.throw(_("Markup must be greater than zero."))

	frappe.db.set_single_value("OneSpace Control Settings", "ai_markup_multiplier", markup)
	frappe.db.commit()
	return {"ok": True, "markup": markup}


@frappe.whitelist(methods=["POST"])
def reconcile_ai_usage() -> dict:
	"""Run the comparison against the gateway's logs now."""
	_require_manager()

	from oneapp_control.ai import reconcile

	return reconcile.run()
