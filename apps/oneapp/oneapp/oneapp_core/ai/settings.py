"""What a workspace gets to decide about AI, and what it does not.

The settings page is not written anywhere. It is the feature registry rendered:
every declared feature becomes a row, its model picker is filtered to models
that match the capability it declared, and a feature declared as critical shows
without a switch. Adding a feature to an app adds it here; nothing to configure,
which is the point.

Two things stay ours:

  * **The system prompt.** A workspace can add to it and can read back what it
    added. It cannot read ours, and no endpoint here returns it — the prompt is
    business logic, and the model receives ours followed by theirs.

  * **Whether a critical feature runs.** `tenant_can_disable=False` is declared
    in code by the app that has to keep working afterwards. Turning AI off for
    the workspace leaves those running.
"""

import json

import frappe
from frappe import _

from oneapp.oneapp_core.ai import features


def doc():
	return frappe.get_single("OneSpace AI Settings")


def _cached(field: str):
	raw = frappe.db.get_single_value("OneSpace AI Settings", field)
	try:
		return json.loads(raw) if raw else {}
	except (TypeError, ValueError):
		return {}


def catalogue() -> list[dict]:
	"""Models the control plane says this workspace may choose from."""
	return _cached("catalogue_json") or []


def policy() -> dict[str, dict]:
	"""Platform policy per feature, keyed by feature key."""
	rows = _cached("registry_json") or []
	return {row["key"]: row for row in rows if row.get("key")}


def _row(settings, key: str):
	for row in settings.features or []:
		if row.feature_key == key:
			return row
	return None


def is_enabled(feature) -> bool:
	"""Whether this feature may run right now.

	Order matters. A feature the operator suspended is off for everyone; a
	feature declared critical is on for everyone; only then does the workspace's
	own answer count.
	"""
	rules = policy().get(feature.key) or {}
	if rules.get("status") in ("Withdrawn", "Suspended"):
		return False

	# Declared in code. A workspace switching AI off does not stop the features
	# that *are* the process — they would fail with nothing to say instead.
	if not feature.tenant_can_disable:
		return True

	settings = doc()
	if not settings.ai_enabled:
		return False

	row = _row(settings, feature.key)
	return bool(row.enabled) if row else True


def model_for(feature) -> str:
	"""Which model this feature runs on: the code's, the workspace's, ours.

	A feature that pins a model in code wins — it pinned one because it only
	works with that one. Otherwise the workspace's choice, then the operator's
	default, then whatever the catalogue recommends for the capability.
	"""
	if feature.model:
		return feature.model

	row = _row(doc(), feature.key)
	chosen = (row.model_key if row else "") or ""
	available = {m["model_key"]: m for m in catalogue()}

	# A workspace's choice can go stale — a model is retired, or the operator
	# takes it off sale. Falling through beats failing the call.
	if chosen in available:
		return chosen

	rules = policy().get(feature.key) or {}
	if rules.get("default_model") in available:
		return rules["default_model"]

	matching = [m for m in catalogue() if m["capability"] == feature.capability]
	if not matching:
		raise features.AIError(
			f"No model in the catalogue can do {feature.capability}."
		)
	recommended = [m for m in matching if m.get("is_recommended")]
	return (recommended or matching)[0]["model_key"]


def system_prompt(feature) -> str:
	"""Ours, then theirs.

	Concatenated in that order deliberately: instructions later in a system
	prompt qualify what came before rather than replacing it, so a workspace can
	say "answer in French" without being able to say "ignore the above".
	"""
	if not feature.allow_prompt_addendum:
		return feature.system

	row = _row(doc(), feature.key)
	addendum = (row.prompt_addendum or "").strip() if row else ""
	if not addendum:
		return feature.system

	return (
		f"{feature.system}\n\n"
		"The workspace has added the following preferences. Follow them where "
		"they do not conflict with the instructions above.\n"
		f"{addendum}"
	)


def limits(feature) -> dict:
	"""The ceiling for a call, with the operator's cap over the app's."""
	rules = policy().get(feature.key) or {}
	declared = dict(feature.limits)
	for field in declared:
		if rules.get(field):
			declared[field] = rules[field]
	return declared


# --------------------------------------------------------------------------- #
# The settings surface
# --------------------------------------------------------------------------- #

def spec() -> dict:
	"""The AI tab, built from what the installed apps declare.

	Never includes `feature.system`. The workspace sees the label, the choice of
	model and its own wording; our instructions are not in this payload and are
	not reachable from any endpoint the workspace can call.
	"""
	features.discover()
	settings = doc()
	rules = policy()
	models = catalogue()

	rows = []
	for feature in sorted(features.REGISTRY.values(), key=lambda f: (f.app, f.label)):
		policy_row = rules.get(feature.key) or {}
		if policy_row.get("status") == "Withdrawn":
			continue

		row = _row(settings, feature.key)
		choices = [
			{
				"value": m["model_key"],
				"label": m["display_name"],
				"provider": m["provider"],
				"description": _rate_line(m),
			}
			for m in models if m["capability"] == feature.capability
		]

		rows.append({
			"key": feature.key,
			"label": feature.label,
			"app": feature.app,
			"description": feature.description,
			"capability": feature.capability,
			# A feature that is the process shows as always on, with the reason.
			"can_disable": bool(feature.tenant_can_disable),
			"enabled": is_enabled(feature),
			"suspended": policy_row.get("status") == "Suspended",
			"pinned_model": bool(feature.model),
			"model": (row.model_key if row else "") or "",
			"models": choices,
			"allow_prompt_addendum": bool(feature.allow_prompt_addendum),
			"prompt_addendum": (row.prompt_addendum if row else "") or "",
		})

	return {
		"ai_enabled": bool(settings.ai_enabled),
		"credit_balance": settings.credit_balance,
		"features": rows,
		"has_catalogue": bool(models),
	}


def _rate_line(model: dict) -> str:
	"""What a model costs, in the unit it is billed in.

	A rate, not an estimate of a call. We do not know what a call will use until
	it has been made, and saying otherwise on a settings page is where made-up
	numbers start.

	Whatever unit the rate is in, rather than tokens only: a music model is
	billed per song and a picker that describes it with a blank is a picker that
	makes the choice look arbitrary.
	"""
	parts = []
	for price in model.get("prices") or []:
		if price["kind"] not in ("Input", "Output"):
			continue

		per_units = int(price["per_units"] or 1)
		unit = price["unit"].lower()
		if per_units == 1:
			per = unit
		elif per_units == 1_000_000:
			per = f"1M {unit}s"
		else:
			per = f"{per_units:,} {unit}s"

		parts.append(f"{price['kind'].lower()} ${_amount(price['cost_usd'])}/{per}")
	return ", ".join(parts[:2])


def _amount(value: float) -> str:
	"""Plain decimals. A tile rate of 0.0000528 formats as 5.28e-05 under the
	obvious %g and reads as a typo."""
	return f"{value:.10f}".rstrip("0").rstrip(".") or "0"


def save(values: dict) -> dict:
	"""Apply what the workspace changed, ignoring what it may not change."""
	features.discover()

	settings = doc()
	rules = policy()
	choosable = {m["model_key"]: m for m in catalogue()}

	if "ai_enabled" in values:
		settings.ai_enabled = 1 if values["ai_enabled"] else 0

	for key, answer in (values.get("features") or {}).items():
		feature = features.REGISTRY.get(key)
		if not feature:
			continue

		row = _row(settings, key) or settings.append("features", {"feature_key": key})

		if feature.tenant_can_disable and "enabled" in answer:
			row.enabled = 1 if answer["enabled"] else 0
		elif not feature.tenant_can_disable:
			row.enabled = 1

		if "model" in answer and not feature.model:
			chosen = answer["model"] or ""
			model = choosable.get(chosen)
			# The picker only offers matching models; this is the check that the
			# answer coming back is one of them, since the answer is a string
			# from a browser.
			if chosen and (not model or model["capability"] != feature.capability):
				frappe.throw(_("{0} cannot be used for {1}.").format(chosen, feature.label))
			row.model_key = chosen

		if "prompt_addendum" in answer and feature.allow_prompt_addendum:
			row.prompt_addendum = (answer["prompt_addendum"] or "")[:4000]

		if rules.get(key, {}).get("status") == "Suspended":
			row.enabled = 0

	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return spec()


# --------------------------------------------------------------------------- #
# Endpoints
#
# Two, and neither of them can return `feature.system`. That is not an omission
# to remember — `spec()` builds its rows field by field and our instructions are
# not one of the fields, so there is no path from a browser to them.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def get() -> dict:
	from oneapp.oneapp_core.workspace import require_owner

	require_owner()
	return spec()


@frappe.whitelist(methods=["POST"])
def update(values: str | dict) -> dict:
	from oneapp.oneapp_core.workspace import require_owner

	require_owner()

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Those settings could not be read."))

	return save(values)
