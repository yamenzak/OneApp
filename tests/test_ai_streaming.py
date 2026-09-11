"""A run: an AI answer a browser watches arrive.

What can go wrong here is not the happy path. It is the four cases where a
stream is different from a call — a frame that is not JSON, a run nobody is
listening to any more, a cancel, and a browser that missed the end — and each
of those is silent when it breaks: the glow never stops and nobody is told
why. So they are the tests.
"""

import json

import pytest


@pytest.fixture
def gateway(stub_frappe):
	from oneapp.onespace.ai import gateway as module

	return module


@pytest.fixture
def streaming(stub_frappe):
	from oneapp.onespace.ai import streaming as module

	return module


class FakeResponse:
	"""Enough of `requests.Response` for the SSE reader."""

	def __init__(self, lines, status=200, headers=None):
		self._lines = lines
		self.status_code = status
		self.headers = headers or {}
		self.text = ""
		self.closed = False

	def iter_lines(self, decode_unicode=False):
		yield from self._lines

	def __enter__(self):
		return self

	def __exit__(self, *a):
		self.closed = True
		return False


def frame(text=None, usage=None, finish=None, call=None):
	parts = []
	if text is not None:
		parts.append({"text": text})
	if call is not None:
		parts.append({"functionCall": call})
	body = {"candidates": [{"content": {"parts": parts}}]}
	if finish:
		body["candidates"][0]["finishReason"] = finish
	if usage:
		body["usageMetadata"] = usage
	return "data: " + json.dumps(body)


# --------------------------------------------------------------------------- #
# Reading the frames
# --------------------------------------------------------------------------- #

def test_only_data_lines_are_read(gateway):
	"""SSE allows comments and keep-alives, and one must not end a generation."""
	response = FakeResponse([
		": keep alive",
		"",
		"event: message",
		frame("Hello"),
		"data: not json at all",
		frame(" world"),
		"data: [DONE]",
	])
	assert [f["candidates"][0]["content"]["parts"][0]["text"]
	        for f in gateway._sse(response)] == ["Hello", " world"]


def test_the_reader_is_a_generator_rather_than_a_list(gateway):
	"""Materialising the frames would turn a stream back into a wait."""
	import types

	assert isinstance(gateway._sse(FakeResponse([])), types.GeneratorType)


# --------------------------------------------------------------------------- #
# Reassembling them
# --------------------------------------------------------------------------- #

@pytest.fixture
def streamed(gateway, monkeypatch):
	"""Run `_execute_in_frames` over a canned response, returning what it built."""

	def go(lines, on_delta=None, stop=None, status=200):
		monkeypatch.setattr(gateway, "config", lambda: {
			"account_id": "a", "gateway": "g", "gateway_token": "",
			"google_key": "", "cf_token": "", "tenant": "t",
		})
		monkeypatch.setattr(gateway.settings, "options_for", lambda f: {})
		monkeypatch.setattr(
			gateway.requests, "post",
			lambda *a, **k: FakeResponse(lines, status, {gateway.LOG_ID_HEADER: "log-1"}),
		)

		model = {"provider": "google-ai-studio", "model_id": "flash"}
		feature = type("F", (), {"key": "x.y", "label": "X", "capability": "Text Generation"})()
		request = {"stop": stop} if stop else {}
		return gateway._execute_in_frames(
			model, feature, gateway._google_stream, "ask", "be brief",
			{"max_output_tokens": 10}, request, on_delta,
		)

	return go


def test_the_frames_become_one_payload_the_ordinary_reader_understands(gateway, streamed):
	payload, log_id = streamed([
		frame("The "), frame("quote "),
		frame("holds.", finish="STOP", usage={"promptTokenCount": 9, "candidatesTokenCount": 3}),
	])

	assert log_id == "log-1"
	assert gateway._google_result(payload, "Text Generation")["text"] == "The quote holds."
	# The whole point of reassembling rather than inventing a shape: metering
	# reads this untouched.
	assert payload["usageMetadata"]["candidatesTokenCount"] == 3


def test_usage_from_the_last_frame_wins(streamed):
	"""Google reports it cumulatively, so the last one seen is the total."""
	payload, _ = streamed([
		frame("a", usage={"candidatesTokenCount": 1}),
		frame("b", usage={"candidatesTokenCount": 2}),
		frame("c", usage={"candidatesTokenCount": 3}),
	])
	assert payload["usageMetadata"]["candidatesTokenCount"] == 3


def test_every_text_frame_reaches_the_sink(streamed):
	said = []
	streamed([frame("one "), frame("two "), frame("three")], on_delta=said.append)
	assert said == ["one ", "two ", "three"]


def test_a_tool_call_is_collected_and_never_streamed(gateway, streamed):
	"""Half a tool call is not something to show anybody."""
	said = []
	payload, _ = streamed(
		[frame("thinking "), frame(call={"name": "find_records", "args": {"q": "x"}})],
		on_delta=said.append,
	)
	assert said == ["thinking "]
	parts = payload["candidates"][0]["content"]["parts"]
	assert any("functionCall" in part for part in parts)


def test_a_cancel_ends_it_and_says_so(streamed):
	said = []
	# True from the start: the first frame is delivered, then the loop stops.
	payload, _ = streamed([frame("one "), frame("two "), frame("three")],
	                      on_delta=said.append, stop=lambda: True)
	assert said == ["one "]
	assert payload["candidates"][0]["finishReason"] == "CANCELLED"


def test_a_refusal_is_raised_rather_than_streamed_as_nothing(gateway, streamed):
	with pytest.raises(gateway.AIError):
		streamed([], status=429)


# --------------------------------------------------------------------------- #
# The seam: a feature that streams on a provider that cannot
# --------------------------------------------------------------------------- #

def test_only_google_text_streams(gateway):
	"""Workers AI is absent on purpose — its usage block is not reliably on the
	last frame, and a call we cannot meter is a hold we have to eat."""
	assert ("google-ai-studio", "Text Generation") in gateway.STREAMERS
	assert not any(provider == "workers-ai" for provider, _ in gateway.STREAMERS)


def test_a_provider_with_no_streamer_still_answers_the_sink(gateway, monkeypatch):
	"""The seam that lets a surface be written against streaming without asking
	which model the workspace picked."""
	feature = type("F", (), {
		"key": "x.y", "label": "X", "capability": "Text Generation",
	})()

	monkeypatch.setattr(gateway, "is_configured", lambda: True)
	monkeypatch.setattr(gateway.settings, "is_enabled", lambda f: True)
	monkeypatch.setattr(gateway.settings, "model_for", lambda f: "workers-ai:llama")
	monkeypatch.setattr(gateway.settings, "catalogue", lambda: [
		{"model_key": "workers-ai:llama", "provider": "workers-ai"},
	])
	monkeypatch.setattr(gateway.settings, "limits", lambda f: {})
	monkeypatch.setattr(gateway.settings, "system_prompt", lambda f: "")
	monkeypatch.setattr(gateway.control_client, "call",
	                    lambda name, payload: {"ok": True, "reservation": "r1", "credits": 1})
	monkeypatch.setattr(gateway, "_execute",
	                    lambda *a: ({"result": {"response": "whole answer"}}, "log"))
	monkeypatch.setattr(gateway, "_meter", lambda *a: [])

	said = []
	result = gateway.call(feature, "ask", on_delta=said.append)

	assert result["streamed"] is False
	assert said == ["whole answer"]


def test_the_sink_is_ambient_so_a_feature_need_not_know(gateway):
	"""A feature writes `ai(prompt)` and streams if it is inside a run."""
	assert gateway._sink() == (None, None)
	with gateway.deltas_to(print, stop=bool):
		assert gateway._sink() == (print, bool)
		# Nested — a tool loop inside a run — restores rather than clears.
		with gateway.deltas_to(len):
			assert gateway._sink()[0] is len
		assert gateway._sink()[0] is print
	assert gateway._sink() == (None, None)


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #

def test_a_run_is_enqueued_with_a_path_the_caller_never_named(streaming, stub_frappe):
	def summarise(thread):
		return {"text": "..."}

	summarise.__module__ = "oneapp.onemail.intelligence"

	started = streaming.begin(summarise, label="Summary", thread="abc")

	assert started["ok"] and started["run"]
	method, kwargs = stub_frappe.enqueued[-1]
	assert method == "oneapp.onespace.ai.streaming.perform"
	assert kwargs["path"] == "oneapp.onemail.intelligence.summarise"
	assert kwargs["arguments"] == {"thread": "abc"}
	# `short`, because the long queue is where backups live and a summary
	# queued behind one is a summary nobody waits for.
	assert kwargs["queue"] == "short"


def test_a_switched_off_feature_is_refused_now_rather_than_in_a_worker(
	streaming, gateway, monkeypatch, stub_frappe
):
	monkeypatch.setattr(gateway, "is_configured", lambda: True)
	monkeypatch.setattr(streaming.features, "is_enabled", lambda key: False)

	def write():
		return ""

	write.feature = type("F", (), {"key": "x.y", "label": "Writing"})()

	before = len(stub_frappe.enqueued)
	answer = streaming.begin(write)

	assert answer["ok"] is False and answer["reason"] == "disabled"
	assert len(stub_frappe.enqueued) == before


def test_an_unconfigured_site_says_so_before_enqueueing(streaming, gateway, monkeypatch, stub_frappe):
	monkeypatch.setattr(gateway, "is_configured", lambda: False)

	def write():
		return ""

	write.feature = type("F", (), {"key": "x.y", "label": "Writing"})()

	before = len(stub_frappe.enqueued)
	assert streaming.begin(write)["reason"] == "unconfigured"
	assert len(stub_frappe.enqueued) == before


def test_the_first_piece_goes_out_at_once_and_the_rest_are_coalesced(streaming, stub_frappe):
	"""The wait before the first word is the one a person feels. After it, a
	redis write per token to draw text somebody reads at 250 words a minute is
	work nobody sees."""
	streaming._write("run-1", {"by": "ada@example.com", "state": streaming.RUNNING})
	sink = streaming._Sink("run-1")
	before = len(stub_frappe.published)

	for _ in range(5):
		sink("tiny ")

	assert len(stub_frappe.published) == before + 1
	assert stub_frappe.published[-1][1]["delta"] == "tiny "
	# The four after it are held, and nothing is lost: the whole answer is
	# intact and the pending piece goes on the next flush or on the last frame.
	assert sink.whole == "tiny " * 5
	assert sink._pending == "tiny " * 4


def test_a_big_piece_flushes_immediately(streaming, stub_frappe):
	streaming._write("run-2", {"by": "ada@example.com", "state": streaming.RUNNING})
	sink = streaming._Sink("run-2")
	sink("x" * (streaming.FLUSH_CHARS + 1))

	event, message, kwargs = stub_frappe.published[-1]
	assert event == streaming.CHANNEL
	assert message["run"] == "run-2"
	assert len(message["delta"]) == streaming.FLUSH_CHARS + 1
	# To one person, never to the site.
	assert kwargs["user"] == "ada@example.com"


def test_the_cached_copy_is_the_whole_text_so_far(streaming):
	"""A browser that missed frames reads this, not the last fragment."""
	streaming._write("run-3", {"by": "ada@example.com", "state": streaming.RUNNING})
	sink = streaming._Sink("run-3")
	sink("a" * streaming.FLUSH_CHARS)
	sink("b" * streaming.FLUSH_CHARS)

	assert streaming._read("run-3")["text"] == "a" * streaming.FLUSH_CHARS + "b" * streaming.FLUSH_CHARS


def test_the_final_message_carries_the_whole_answer(streaming, stub_frappe):
	streaming._write("run-4", {"by": "ada@example.com", "state": streaming.RUNNING})
	sink = streaming._Sink("run-4")
	sink("half ")
	streaming._finish("run-4", streaming.DONE, sink, text="half and half", credits=3)

	_, message, _ = stub_frappe.published[-1]
	assert message["done"] is True
	assert message["text"] == "half and half"
	assert message["credits"] == 3
	assert message["state"] == streaming.DONE


def test_a_failure_publishes_too(streaming, stub_frappe, monkeypatch):
	"""A run that fails silently is a glow that never stops, which is worse
	than an error: nobody can tell whether to wait."""
	streaming._write("run-5", {"by": "ada@example.com", "state": streaming.RUNNING})

	def explode():
		raise RuntimeError("the provider fell over")

	monkeypatch.setattr(stub_frappe, "get_attr", lambda path: explode)
	streaming.perform("run-5", "somewhere.explode", {})

	_, message, _ = stub_frappe.published[-1]
	assert message["done"] is True
	assert message["state"] == streaming.FAILED
	# And never the exception's own words, which are the provider's.
	assert "fell over" not in message["message"]


def test_what_the_feature_returned_wins_over_what_was_streamed(
	streaming, stub_frappe, monkeypatch
):
	"""A feature that trims its own preamble has the right text; the sink has
	the raw one."""
	streaming._write("run-6", {"by": "ada@example.com", "state": streaming.RUNNING})

	def tidy():
		return {"text": "Tidied.", "credits": 2, "actions": [{"kind": "todo"}]}

	monkeypatch.setattr(stub_frappe, "get_attr", lambda path: tidy)
	streaming.perform("run-6", "somewhere.tidy", {})

	_, message, _ = stub_frappe.published[-1]
	assert message["text"] == "Tidied."
	assert message["credits"] == 2
	# Anything else the feature returned rides along, so a surface that asked
	# for actions gets them on the frame that says it finished.
	assert message["actions"] == [{"kind": "todo"}]


def test_a_run_is_only_readable_by_whoever_started_it(streaming, stub_frappe):
	streaming._write("run-7", {"by": "ada@example.com", "state": streaming.DONE, "text": "x"})
	stub_frappe.session.user = "grace@example.com"

	with pytest.raises(Exception) as refused:
		streaming.result("run-7")
	assert "not yours" in str(refused.value)


def test_a_run_nobody_started_is_gone_rather_than_empty(streaming):
	with pytest.raises(Exception) as missing:
		streaming.result("never-existed")
	assert "no longer available" in str(missing.value)


def test_stopping_sets_a_flag_the_job_reads(streaming):
	"""A flag rather than killing the job: killing it would leave a credit hold
	nobody releases."""
	streaming._write("run-8", {"by": "Administrator", "state": streaming.RUNNING})
	assert streaming._cancelled("run-8") is False
	streaming.stop("run-8")
	assert streaming._cancelled("run-8") is True


def test_catching_up_returns_what_there_is(streaming):
	streaming._write("run-9", {
		"by": "Administrator", "state": streaming.RUNNING, "text": "so far",
	})
	caught = streaming.result("run-9")
	assert caught["state"] == streaming.RUNNING
	assert caught["text"] == "so far"
