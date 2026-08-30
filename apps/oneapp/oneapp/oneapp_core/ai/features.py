"""Declaring an AI feature, and everything that follows from declaring it.

An app says what it wants once:

    @ai_feature(
        "invoice.summary",
        label="Invoice summary",
        capability="Text Generation",
        system="You summarise invoices for a small business owner...",
        max_output_tokens=400,
    )
    def summarise(ai, invoice):
        return ai(f"Summarise this invoice:\\n{invoice.as_text()}").text

and gets, without writing any of it:

  * a row in the workspace's settings, with a model picker filtered to models
    that can actually do the job;
  * a credit hold before the call and a charge after it, both priced by the
    control plane against the synced catalogue;
  * the customer's own wording appended to the prompt, never replacing it;
  * an entry in the operator's feature registry.

The decorator injects `ai` as the first argument. Everything the feature
declares — which model, what it may spend, whether a workspace may switch it
off — is policy the injected callable applies, so a feature cannot accidentally
call a model the workspace did not agree to pay for.

`tenant_can_disable=False` is the flag for a feature where AI *is* the process
rather than an assistant beside it. Those keep running when a workspace turns
AI off, because the alternative is a broken workflow with no error to point at.
"""

import functools

import frappe

# feature_key -> Feature. Populated by import, which is why discover() exists.
REGISTRY: dict[str, "Feature"] = {}


class AIError(Exception):
	pass


class FeatureDisabled(AIError):
	"""The workspace switched this off, and was allowed to."""


class Feature:
	def __init__(self, key, label, capability, system, description,
	             tenant_can_disable, allow_prompt_addendum, app,
	             max_input_tokens, max_output_tokens, max_images, max_outputs,
	             max_audio_seconds, max_credits, model):
		self.key = key
		self.label = label
		self.capability = capability
		# Ours. Never sent to a workspace, never rendered in a settings page,
		# never returned by an endpoint — see settings.py, which reads
		# `prompt_addendum` and never this.
		self.system = system
		self.description = description
		self.tenant_can_disable = tenant_can_disable
		self.allow_prompt_addendum = allow_prompt_addendum
		self.app = app
		self.model = model
		self.limits = {
			"max_input_tokens": max_input_tokens,
			"max_output_tokens": max_output_tokens,
			"max_images": max_images,
			"max_outputs": max_outputs,
			"max_audio_seconds": max_audio_seconds,
			"max_credits": max_credits,
		}

	def as_report(self) -> dict:
		"""What the control plane is told. Deliberately without `system`."""
		return {
			"key": self.key,
			"label": self.label,
			"app": self.app,
			"capability": self.capability,
			"description": self.description,
			"tenant_can_disable": 1 if self.tenant_can_disable else 0,
			"allow_prompt_addendum": 1 if self.allow_prompt_addendum else 0,
			**self.limits,
		}


def ai_feature(
	name: str,
	label: str = "",
	capability: str = "Text Generation",
	system: str = "",
	description: str = "",
	tenant_can_disable: bool = True,
	allow_prompt_addendum: bool = True,
	max_input_tokens: int = 0,
	max_output_tokens: int = 0,
	max_images: int = 0,
	max_outputs: int = 0,
	max_audio_seconds: int = 0,
	max_credits: float = 0,
	model: str = "",
):
	"""Register a feature and hand its function a configured AI callable.

	`max_*` are a ceiling, not a guess: they are the most this call may consume,
	and the credits that much would cost are what gets held. Nothing here
	predicts what the answer will actually cost, because the answer does not
	exist yet and a prediction would end up on an invoice.

	`model` pins a model in code, for the rare feature that only works with one.
	Leave it empty and the workspace chooses, from models that match
	`capability`.
	"""

	def decorate(fn):
		app = fn.__module__.split(".")[0]
		key = name if name.startswith(f"{app}.") else f"{app}.{name}"

		feature = Feature(
			key=key,
			label=label or name.replace(".", " ").replace("_", " ").capitalize(),
			capability=capability,
			system=system,
			description=description or (fn.__doc__ or "").strip().split("\n")[0],
			tenant_can_disable=tenant_can_disable,
			allow_prompt_addendum=allow_prompt_addendum,
			app=app,
			max_input_tokens=max_input_tokens,
			max_output_tokens=max_output_tokens,
			max_images=max_images,
			max_outputs=max_outputs,
			max_audio_seconds=max_audio_seconds,
			max_credits=max_credits,
			model=model,
		)
		REGISTRY[key] = feature

		@functools.wraps(fn)
		def wrapper(*args, **kwargs):
			from oneapp.oneapp_core.ai import gateway

			return fn(gateway.caller(feature), *args, **kwargs)

		wrapper.feature = feature
		wrapper.enabled = lambda: is_enabled(key)
		return wrapper

	return decorate


def discover() -> dict[str, Feature]:
	"""Import every module an installed app declared under `ai_features`.

	Frappe's hooks rather than a filesystem walk: a feature that only registers
	when something happens to import its module is a feature that is missing
	from the settings page on a cold worker.
	"""
	for path in frappe.get_hooks("ai_features") or []:
		try:
			frappe.get_module(path)
		except Exception:
			frappe.log_error(
				title=f"AI feature module {path} failed to import",
				message=frappe.get_traceback(),
			)
	return REGISTRY


def get(key: str) -> Feature | None:
	if key not in REGISTRY:
		discover()
	return REGISTRY.get(key)


def is_enabled(key: str) -> bool:
	from oneapp.oneapp_core.ai import settings

	feature = get(key)
	return bool(feature) and settings.is_enabled(feature)


def report():
	"""Tell the control plane what this site declares. Called from sync."""
	from oneapp.oneapp_core import control_client

	discover()
	if not REGISTRY:
		return

	control_client.call("report_ai_features", {
		"features": [f.as_report() for f in REGISTRY.values()],
	})
