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

#: How the assistant speaks, as the panel offers it and the prompt says it.
#:
#: Here rather than read off the Select's own options: this is read on every
#: call that builds a prompt, a meta lookup for a fixed list of five words is a
#: query for nothing, and a site whose doctype has not been migrated yet would
#: have no vocabulary to validate against — which would refuse every tone
#: rather than none. `scripts/doctypes/ai.py` writes the same list into the
#: field, and `test_the_tones_offered_are_the_tones_stored` holds the two ends
#: together.
TONES = ("Neutral", "Friendly", "Formal", "Direct", "Warm")

from oneapp.oneapp_core.ai import features, options


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


def _resolved(feature) -> str:
	"""Which model this feature would run on right now, or nothing.

	`model_for` raises when the catalogue has nothing of the capability, which
	is a real answer to a call and the wrong answer to a settings page: a
	workspace with no model for one feature must still be able to read the tab
	and change the others.
	"""
	try:
		return model_for(feature)
	except features.AIError:
		return ""


def options_for(feature) -> dict:
	"""What to send this feature's call besides the ask itself.

	The model's own defaults with the workspace's answers over them, which is
	what a caller wants: an option nobody has touched is still sent, and is
	still sent as the model said. A feature that runs on a model declaring
	nothing gets an empty dict and passes it along, which costs nothing.
	"""
	model = {m["model_key"]: m for m in catalogue()}.get(model_for(feature))
	return options.resolved(_row(doc(), feature.key), model)


def identity() -> dict:
	"""Who the assistant is, to this workspace.

	One answer for the whole product. The chat panel, a drafted reply and
	anything else it speaks through are the same character, and a name that
	changed between them would read as two different products.

	The name and the picture are what surfaces show; the tone and the
	personality are what the model is told. Kept together because they are one
	decision — `assistant_name` is in the prompt too, since an assistant that
	is called Rua on screen and calls itself "the assistant" in its own answers
	is the same inconsistency from the other side.
	"""
	# `get` rather than attribute access: this is read on every call that
	# builds a prompt, and a site running new code against a database that has
	# not been migrated yet would otherwise raise here rather than fall back to
	# the default. A missing field is an assistant with no character, which is
	# what it had before there were fields.
	settings = doc()
	said = lambda name: (settings.get(name) or "").strip()  # noqa: E731

	return {
		"name": said("assistant_name") or _("Assistant"),
		"avatar": settings.get("assistant_avatar") or "",
		"tone": said("assistant_tone"),
		"personality": said("assistant_personality"),
	}


def _character() -> str:
	"""The identity as a paragraph, or nothing at all.

	Nothing where the workspace has said nothing beyond the default: an empty
	instruction is still a sentence the model reads and weighs, and "You are
	called Assistant" is not worth what it costs.
	"""
	who = identity()
	said = []
	if who["name"] and who["name"] != _("Assistant"):
		said.append(f"You are called {who['name']}.")
	if who["tone"] and who["tone"] != "Neutral":
		said.append(f"Your tone is {who['tone'].lower()}.")
	if who["personality"]:
		said.append(who["personality"])
	return " ".join(said)


def system_prompt(feature) -> str:
	"""Ours, then who it is, then theirs.

	Concatenated in that order deliberately: instructions later in a system
	prompt qualify what came before rather than replacing it, so a workspace can
	say "answer in French" without being able to say "ignore the above". The
	identity sits in the middle for the same reason — it shapes how the answer
	reads, and must not be able to reach what the feature is for.
	"""
	if not feature.allow_prompt_addendum:
		return feature.system

	parts = [feature.system]

	if character := _character():
		parts.append(
			"You have been given a character by the workspace. Keep it in how "
			"you write, not in what you do.\n"
			f"{character}"
		)

	row = _row(doc(), feature.key)
	if addendum := ((row.prompt_addendum or "").strip() if row else ""):
		parts.append(
			"The workspace has added the following preferences. Follow them "
			"where they do not conflict with the instructions above.\n"
			f"{addendum}"
		)

	return "\n\n".join(parts)


def limits(feature) -> dict:
	"""The ceiling for a call, with the operator's cap over the app's."""
	return _capped(feature, feature.limits)


def run_budget(feature) -> dict:
	"""How far one ask may go: turns, and credits across all of them.

	The same override rule as `limits`, and separate from it because the
	gateway holds against one call and knows nothing about the loop around it.
	An operator who suspects a feature is looping shortens the run rather than
	the call.
	"""
	return _capped(feature, feature.run)


def _capped(feature, declared: dict) -> dict:
	rules = policy().get(feature.key) or {}
	settled = dict(declared)
	for field in settled:
		if rules.get(field):
			settled[field] = rules[field]
	return settled


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
				# What else this one takes. On every choice rather than only on
				# the one in use, so picking a model that speaks draws its
				# language and its pace straight away instead of after a save.
				"options": options.declared(m),
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
			# Which model an empty choice comes out as, so the panel can find
			# the declaration for "Recommended" without repeating the rule that
			# decides it. See `model_for`.
			"resolved_model": _resolved(feature),
			# And what this workspace has answered. Every answer it has, not
			# only the ones the model in use declares: the panel narrows them as
			# the picker moves, and dropping them here would lose an answer the
			# moment somebody looked at another model. `options.answered` is
			# what narrows them for a call.
			"model_options": options.stored(row),
			"allow_prompt_addendum": bool(feature.allow_prompt_addendum),
			"prompt_addendum": (row.prompt_addendum if row else "") or "",
		})

	return {
		"ai_enabled": bool(settings.ai_enabled),
		"credit_balance": settings.credit_balance,
		"assistant": identity(),
		"tones": _tones(),
		"features": rows,
		"has_catalogue": bool(models),
	}


def _tones() -> list[str]:
	"""The tones offered. See `TONES`."""
	return list(TONES)


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


def _identity(settings, who: dict) -> None:
	"""Write the assistant's identity, bounded.

	The tone is checked against the field's own options rather than taken as
	given: it reaches the model as a word in an instruction, and a Select whose
	value came from the browser is not a Select.
	"""
	if "name" in who:
		settings.assistant_name = (who["name"] or "").strip()[:60]
	if "avatar" in who:
		settings.assistant_avatar = (who["avatar"] or "").strip()
	if "tone" in who:
		tone = (who["tone"] or "").strip()
		if tone and tone not in _tones():
			frappe.throw(_("{0} is not a tone this can use.").format(tone))
		settings.assistant_tone = tone
	if "personality" in who:
		# Bounded like the addendum, and for the same reason: this is prose that
		# goes in front of a model on every call, and the cost of it is paid by
		# the workspace on each one.
		settings.assistant_personality = (who["personality"] or "")[:1000]


def save(values: dict) -> dict:
	"""Apply what the workspace changed, ignoring what it may not change."""
	features.discover()

	settings = doc()
	rules = policy()
	choosable = {m["model_key"]: m for m in catalogue()}

	if "ai_enabled" in values:
		settings.ai_enabled = 1 if values["ai_enabled"] else 0

	if who := values.get("assistant"):
		_identity(settings, who)

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

		# After the model, and on purpose: an answer is only meaningful against
		# the model it is for, and a save that changes both has to be checked
		# against the new one. `model_for` is what the call will use, which is
		# not always what the row says — a feature can pin one, and an empty
		# choice means whatever is recommended.
		if "model_options" in answer:
			chosen = {m["model_key"]: m for m in catalogue()}.get(_resolved(feature))
			# This model's answers are replaced wholesale and every other
			# model's are left alone. Replaced, because an option cleared back
			# to the model's default has to stop being stored or it can never be
			# cleared; left alone, because a workspace that tries a second model
			# and goes back should find what it typed still there.
			kept = {
				key: value for key, value in options.stored(row).items()
				if key not in options.keys(chosen)
			}
			row.model_options = json.dumps(
				{**kept, **options.checked(answer["model_options"], chosen)}
			)

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
	"""What the workspace's AI tab renders: the feature registry, as rows."""
	from oneapp.oneapp_core.workspace import require_owner

	require_owner()
	return spec()


@frappe.whitelist(methods=["POST"])
def update(values: str | dict) -> dict:
	"""Write the workspace's own AI settings. Owners only, like the rest of the tab."""
	from oneapp.oneapp_core.workspace import require_owner

	require_owner()

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Those settings could not be read."))

	return save(values)
