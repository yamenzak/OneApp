"""The workspace assistant: what it may read, and how a thread is stored.

Two claims are worth a test and neither is about the model.

The first is that the assistant is not privileged. Every tool goes through the
endpoint the browser calls — `spaceview.records.rows`, `drive.reading.listing`,
`docs.body` — so a question about a space nobody may open is refused by the same
code that refuses a click. Tested by proving the call reaches those functions
with the arguments the model chose, rather than a query of its own.

The second is that a stored transcript can be handed back to a provider. A
window that opens on a tool result — an answer to a question that is no longer
in the transcript — is rejected by Gemini, so trimming forward past one is not a
nicety.
"""

import json
import sys
import types

import pytest


@pytest.fixture
def chat(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	stub_frappe.log_error = lambda **kw: None
	stub_frappe.get_traceback = lambda: ""

	from oneapp.oneapp_core.chat import session, toolbox

	return types.SimpleNamespace(
		session=session, toolbox=toolbox, frappe=stub_frappe, monkeypatch=monkeypatch,
	)


# --------------------------------------------------------------------------- #
# The tools are the product's own endpoints
# --------------------------------------------------------------------------- #

def test_finding_records_goes_through_the_screen_the_browser_uses(chat):
	"""Not a query of its own — `records.rows`, with the same override shape.

	That is what makes the assistant unprivileged: `rows` resolves the space
	against the reader's roles, checks each filter against the screen's own
	columns, and fetches through `get_list` under User Permissions. A tool that
	built its own query would have none of that.
	"""
	asked = {}

	def rows(space_code, screen, limit, overrides):
		asked.update(space=space_code, screen=screen, limit=limit, overrides=overrides)
		return {"rows": [{"name": "Q-1", "status": "Open", "_liked_by": "[]"}],
		        "has_more": False}

	module = types.ModuleType("oneapp.oneapp_core.spaceview.records")
	module.rows = rows
	chat.monkeypatch.setitem(sys.modules, "oneapp.oneapp_core.spaceview.records", module)

	found = chat.toolbox.find_records(
		space="sales", screen="quotations",
		filters=[["status", "=", "Open"]], limit=5,
	)

	assert asked["space"] == "sales"
	assert asked["overrides"] == {"filters": [["status", "=", "Open"]]}
	assert found["records"] == [{"name": "Q-1", "status": "Open"}]


def test_a_tool_cannot_ask_for_more_rows_than_the_cap(chat):
	"""Every row is input tokens on every turn after it. The cap is not advice."""
	asked = {}
	module = types.ModuleType("oneapp.oneapp_core.spaceview.records")
	module.rows = lambda space_code, screen, limit, overrides: (
		asked.update(limit=limit) or {"rows": [], "has_more": False}
	)
	chat.monkeypatch.setitem(sys.modules, "oneapp.oneapp_core.spaceview.records", module)

	chat.toolbox.find_records(space="sales", screen="quotations", limit=5_000)
	assert asked["limit"] == chat.toolbox.MAX_ROWS


def test_browser_chrome_never_reaches_the_model(chat):
	"""What a screen returns is shaped for a browser. None of it helps here."""
	slim = chat.toolbox._slim({
		"name": "Q-1", "grand_total": 1200,
		"_liked_by": '["a@b.com"]', "_comment_count": 3, "owner_person": {"x": 1},
		"modified_pretty": "2 days ago", "__islocal": 0,
		"_meta": {"modified": "2026-09-01 10:00:00", "likes": 3, "comments": 2},
	})
	# When it last changed survives; the likes and comments beside it do not.
	assert slim == {"name": "Q-1", "grand_total": 1200,
	                "modified": "2026-09-01 10:00:00"}


def test_child_rows_come_back_only_when_a_record_was_asked_for(chat):
	"""A list of twenty records, each with its line items, is not an answer."""
	row = {"name": "Q-1", "items": [{"item": "Concrete", "qty": 4}]}
	assert "items" not in chat.toolbox._slim(row)
	assert chat.toolbox._slim(row, keep_children=True)["items"] == [
		{"item": "Concrete", "qty": 4}
	]


def test_a_long_document_is_clipped_and_says_so(chat):
	"""Truncating in silence is how an assistant summarises half a contract."""
	clipped = chat.toolbox._clipped("x" * (chat.toolbox.MAX_TEXT + 10))
	assert clipped["truncated"] is True
	assert len(clipped["text"]) == chat.toolbox.MAX_TEXT
	assert not chat.toolbox._clipped("short")["truncated"]


def test_every_tool_is_read_only(chat):
	"""The claim in `chat/toolbox.py`'s docstring, checked rather than asserted.

	A write needs a confirmation step and a confirmation step needs somewhere to
	appear. Until that exists, a verb in this list is a change made on a model's
	say-so.
	"""
	writes = ("make", "create", "save", "delete", "remove", "send", "update",
	          "set", "write", "add")
	named = [one.name for one in chat.toolbox.TOOLBOX]
	assert not [
		one for one in named if any(one.startswith(f"{verb}_") for verb in writes)
	], named


def test_the_tools_describe_their_arguments(chat):
	"""A model given `filters` with no description guesses at the shape.

	`find_records` is the one that matters: its filters are `[field, op, value]`
	and a model that sends a dict gets nothing back with no error to read.
	"""
	one = next(t for t in chat.toolbox.TOOLBOX if t.name == "find_records")
	described = one.parameters["properties"]["filters"].get("description") or ""
	assert "fieldname" in described and "operator" in described


# --------------------------------------------------------------------------- #
# A stored thread, read back as a transcript
# --------------------------------------------------------------------------- #

def stored(chat, rows):
	chat.monkeypatch.setattr(chat.session, "mine", lambda *a, **k: None)
	chat.frappe.get_list = lambda *a, **k: rows


def test_a_transcript_never_opens_on_an_orphaned_tool_result(chat):
	"""The window cut mid-exchange, which every provider rejects.

	Sending an answer to a question that is not in the transcript is a 400 from
	Gemini, so the trim goes forward until the first turn somebody said.
	"""
	chat.monkeypatch.setattr(chat.session, "WINDOW", 2)
	stored(chat, [
		{"role": "user", "content": "old", "tool_calls": "", "tool_call_id": "",
		 "tool_name": ""},
		{"role": "assistant", "content": "", "tool_call_id": "", "tool_name": "",
		 "tool_calls": json.dumps([{"id": "c0", "name": "count_records",
		                            "arguments": {"screen": "q"}}])},
		{"role": "tool", "content": '{"count": 4}', "tool_calls": "",
		 "tool_call_id": "c0", "tool_name": "count_records"},
		{"role": "assistant", "content": "Four.", "tool_calls": "",
		 "tool_call_id": "", "tool_name": ""},
	])

	spoken = chat.session.transcript("CHAT-1")
	assert [turn["role"] for turn in spoken] == ["assistant"]
	assert spoken[0]["content"] == "Four."


def test_a_stored_tool_call_reads_back_as_a_dict(chat):
	"""Stored as JSON, handed back as the shape `ai/transcript.py` speaks."""
	stored(chat, [
		{"role": "assistant", "content": "", "tool_call_id": "", "tool_name": "",
		 "tool_calls": json.dumps([{"id": "c0", "name": "count_records",
		                            "arguments": {"screen": "q"}}])},
		{"role": "tool", "content": '{"count": 4}', "tool_calls": "",
		 "tool_call_id": "c0", "tool_name": "count_records"},
	])

	spoken = chat.session.transcript("CHAT-1")
	assert spoken[0]["tool_calls"][0]["arguments"] == {"screen": "q"}
	assert spoken[1] == {"role": "tool", "tool_call_id": "c0",
	                     "name": "count_records", "content": '{"count": 4}'}


def test_a_thread_is_named_after_what_was_asked(chat):
	"""Not by the model: naming a thread would be a second call, and billed."""
	written = {}

	class Doc(dict):
		name = "CHAT-1"

		def insert(self):
			written.update(self)

	chat.frappe.get_doc = lambda values: Doc(values)
	chat.session.start("  How many quotations are open   this month?  ")
	assert written["title"] == "How many quotations are open this month?"


def test_a_very_long_first_question_is_trimmed_to_a_title(chat):
	class Doc(dict):
		name = "CHAT-1"

		def insert(self):
			pass

	held = {}
	chat.frappe.get_doc = lambda values: (held.update(values) or Doc(values))
	chat.session.start("word " * 200)
	assert len(held["title"]) <= chat.session.TITLE_LENGTH
