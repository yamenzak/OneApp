"""A run: one AI call a browser watches arrive, rather than waits out.

Three decisions, and each of them is a thing that was tried the other way
somewhere and is worse.

**It is a background job, not a long request.** A generation takes between two
and forty seconds. A gunicorn worker held open for that is a worker not
answering anything else, and a shard has four of them — a page with three
summaries on it would stop the site. `chat/assistant.send` already refuses to
stream for exactly this reason. So the browser posts, is handed a run id back
immediately, and subscribes.

**The transport is the one the bench already runs.** `frappe.publish_realtime`
writes to redis; the socketio process the bench already starts is already
subscribed to it and already has this person's browser in a room of their own.
There is nothing to deploy, nothing to configure and nothing new for an
operator to watch. The collaboration relay in `apps/oneapp/realtime/` is not
the right vehicle and was considered: it carries peer-to-peer traffic inside a
document room, and this is the server talking to one person.

**Realtime is best-effort, so the text is also written down.** A browser whose
wifi blinked mid-run has missed frames it can never get back. Every flush
updates a cached copy of the answer so far, and `result()` hands it over — so
a reconnect is a fetch rather than a lost generation. It is a cache and not a
doctype because a run is over in a minute and nobody will ever want yesterday's.

What is deliberately not here is an endpoint that starts an arbitrary feature.
`begin` takes a *function*, which only server code can hand it, and each module
exposes its own narrow endpoint over it. An endpoint taking a feature key and
a bag of arguments would be an endpoint taking a prompt, which is the thing
this whole layer exists not to have.
"""

import time

import frappe
from frappe import _

from oneapp.onespace.ai import features, gateway

#: One realtime event for every run on the site. The run id is in the message
#: rather than in the event name so a browser subscribes once and filters,
#: instead of subscribing and unsubscribing around every summary it asks for.
CHANNEL = "oneapp_ai"

#: How long a finished run stays readable. Long enough for a tab that was
#: asleep when it finished; short enough that this is a cache and not storage.
TTL = 15 * 60

KEY = "oneapp_ai_run"

#: Coalescing. A model returns frames several times a second and each publish
#: is a redis write and a websocket frame; flushing every one of them to draw
#: text a person reads at 250 words a minute is work nobody sees. These two are
#: the "it looks live" threshold rather than a tuned number: under about a
#: sixth of a second, prose reads as typing.
FLUSH_MS = 160
FLUSH_CHARS = 240

RUNNING, DONE, FAILED, CANCELLED = "running", "done", "failed", "cancelled"


def _key(run: str) -> str:
	return f"{KEY}:{run}"


def _read(run: str) -> dict:
	return frappe.cache.get_value(_key(run)) or {}

def _write(run: str, state: dict) -> None:
	frappe.cache.set_value(_key(run), state, expires_in_sec=TTL)


def _mine(run: str) -> dict:
	"""The run, if it is this person's.

	The only check there is, and it is enough because a run id is a 24-character
	hash nobody else is told. What it stops is the case that actually happens:
	a stale tab, signed in as somebody else since, polling a run id it still
	holds.
	"""
	state = _read(run)
	if not state:
		frappe.throw(_("That answer is no longer available."), frappe.DoesNotExistError)
	if state.get("by") != frappe.session.user:
		frappe.throw(_("That answer is not yours."), frappe.PermissionError)
	return state


# --------------------------------------------------------------------------- #
# Starting one
# --------------------------------------------------------------------------- #

def begin(fn, label: str = "", **arguments) -> dict:
	"""Run `fn` in the background, streaming what it writes. Returns the run.

	`fn` is a function this module was handed by the module that owns it —
	an `@ai_feature`, or something that calls one. The dotted path is worked
	out here from the object, never taken from a caller, so there is no way to
	name a function from a browser.

	Refused early where it would fail late: a feature the workspace switched
	off, or a gateway nobody configured, is an answer now rather than a job
	that fails in a worker where the person asking cannot see it.
	"""
	feature = getattr(fn, "feature", None)
	if feature is not None:
		if not gateway.is_configured():
			return {"ok": False, "reason": "unconfigured",
			        "message": _("AI is not set up on this site.")}
		if not features.is_enabled(feature.key):
			return {"ok": False, "reason": "disabled",
			        "message": _("{0} is switched off for this workspace.").format(feature.label)}

	run = frappe.generate_hash(length=24)
	_write(run, {
		"state": RUNNING,
		"by": frappe.session.user,
		"label": label,
		"text": "",
		"credits": 0,
	})

	frappe.enqueue(
		"oneapp.onespace.ai.streaming.perform",
		# `short` because a generation is a minute at the outside, and the long
		# queue is where backups and imports live. A summary queued behind a
		# site backup is a summary nobody waits for.
		queue="short",
		run=run,
		path=f"{fn.__module__}.{fn.__name__}",
		arguments=arguments,
	)
	return {"ok": True, "run": run, "label": label}


def perform(run: str, path: str, arguments: dict) -> None:
	"""The job. Runs as whoever enqueued it — `frappe.enqueue` carries the user.

	Every exit publishes. A run that fails silently is a glow that never stops,
	which is worse than an error: the person cannot tell whether to wait.
	"""
	sink = _Sink(run)

	try:
		with gateway.deltas_to(sink, stop=lambda: _cancelled(run)):
			answer = frappe.get_attr(path)(**(arguments or {}))
	except gateway.OutOfCredits as e:
		return _finish(run, FAILED, sink, reason="insufficient_credits", message=str(e))
	except features.FeatureDisabled as e:
		return _finish(run, FAILED, sink, reason="disabled", message=str(e))
	except Exception:
		frappe.log_error(title=f"AI run {path} failed", message=frappe.get_traceback())
		return _finish(run, FAILED, sink, reason="error",
		               message=_("That did not work. Nothing was changed."))

	# What the feature returned wins over what was streamed. A feature that
	# post-processes its own answer — trims a preamble, pulls JSON out of it —
	# has the right text and the sink has the raw one.
	said = answer if isinstance(answer, dict) else {"text": answer or ""}
	_finish(
		run,
		CANCELLED if _cancelled(run) else DONE,
		sink,
		text=said.get("text") or sink.whole,
		credits=said.get("credits") or 0,
		extra={k: v for k, v in said.items() if k not in ("text", "credits")},
	)


class _Sink:
	"""Collects deltas and publishes them in readable pieces.

	Holds the whole answer as well as the pending piece, because the cached
	copy is what a reconnecting browser reads and it has to be the text so far
	rather than the last fragment.
	"""

	def __init__(self, run: str):
		self.run = run
		self.whole = ""
		self._pending = ""
		# Zero rather than "now", so the first piece goes out the moment it
		# arrives however small it is. The wait before the first word is the
		# one a person actually feels; every wait after it is covered by the
		# words already on screen.
		self._last = 0.0

	def __call__(self, text: str) -> None:
		if not text:
			return
		self.whole += text
		self._pending += text
		now = time.monotonic() * 1000
		if len(self._pending) >= FLUSH_CHARS or now - self._last >= FLUSH_MS:
			self.flush()

	def flush(self) -> None:
		if not self._pending:
			return
		piece, self._pending = self._pending, ""
		self._last = time.monotonic() * 1000

		state = _read(self.run)
		state["text"] = self.whole
		_write(self.run, state)
		_publish(self.run, {"delta": piece})


def _finish(run: str, state_name: str, sink: "_Sink", *, text: str = "",
            credits: float = 0, reason: str = "", message: str = "",
            extra: dict | None = None) -> None:
	sink.flush()

	state = _read(run)
	state.update({
		"state": state_name,
		"text": text or state.get("text") or "",
		"credits": credits or state.get("credits") or 0,
		"reason": reason,
		"message": message,
		# Under one key rather than spread, so `result` can hand back exactly
		# what the final frame carried without guessing which of the stored
		# keys were the feature's and which were the run's.
		"extra": extra or {},
	})
	_write(run, state)

	# The whole text on the final frame, not only the deltas. A browser that
	# joined late, or dropped a frame, is then correct at the end rather than
	# holding a sentence with a hole in it — and the one that saw every delta
	# throws away an identical string.
	_publish(run, {
		"done": True,
		"state": state_name,
		"text": state["text"],
		"credits": state["credits"],
		"reason": reason,
		"message": message,
		**(extra or {}),
	})


def _publish(run: str, message: dict) -> None:
	frappe.publish_realtime(
		CHANNEL, {"run": run, **message}, user=_read(run).get("by") or frappe.session.user
	)


# --------------------------------------------------------------------------- #
# Stopping one, and catching up with one
# --------------------------------------------------------------------------- #

def _cancelled(run: str) -> bool:
	return bool(frappe.cache.get_value(f"{_key(run)}:stop"))


@frappe.whitelist(methods=["POST"])
def stop(run: str) -> dict:
	"""Stop a run where it is. What was written stays written.

	A flag rather than killing the job: the job is inside a socket read in
	another process, and the useful thing is for it to finish the frame it is
	on, settle what it spent and publish a final message. Killing it would
	leave a credit hold nobody releases.
	"""
	_mine(run)
	frappe.cache.set_value(f"{_key(run)}:stop", 1, expires_in_sec=TTL)
	return {"ok": True}


@frappe.whitelist(methods=["GET"])
def result(run: str) -> dict:
	"""Where a run has got to. What a browser calls when it missed frames."""
	state = _mine(run)
	return {
		"run": run,
		"state": state.get("state") or RUNNING,
		"text": state.get("text") or "",
		"credits": state.get("credits") or 0,
		"reason": state.get("reason") or "",
		"message": state.get("message") or "",
		# Whatever the feature returned beyond text — the records it filed, the
		# cards it offered. Spread, because the catch-up path hands this
		# straight to the same handler the final frame goes through.
		**(state.get("extra") or {}),
	}
