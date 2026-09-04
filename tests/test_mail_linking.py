"""Which record a message is about, and the rules that decide it.

Every one of these is a case the framework gets wrong or does not attempt.
Frappe's own linking resolves a reply it can trace, a name somebody typed
inside `#(...)`, or the contact the sender is — and never reads the message. So
the two mechanisms here are the ones that matter and the ones nothing else
tests.

The permission rule is tested from the source rather than by calling: a link
must not grant read, and the difference between that being true and false is
one word — `get_list` against `get_all` — in one line.
"""

import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def linking(monkeypatch):
	"""The module, with the site's granted doctypes and series stubbed.

	Imported inside the fixture, not at module scope: `frappe` is stubbed by an
	autouse fixture in conftest, and a module-level import would run before it.
	"""
	from oneapp.oneapp_core.email import linking as module

	monkeypatch.setattr(
		module.sync, "granted_doctypes",
		lambda: {"Purchase Invoice", "Project", "Correspondence"},
	)
	monkeypatch.setattr(module, "prefixes", lambda: {
		"PINV-": ["Purchase Invoice"],
		"PROJ-": ["Project"],
		"LTR-": ["Correspondence"],
	})
	return module


def message(**values):
	"""A Communication as the hook sees it: a bag with `append`."""
	doc = types.SimpleNamespace(links=[], **values)
	doc.get = lambda key, default=None: (
		doc.links if key == "timeline_links" else getattr(doc, key, default)
	)
	doc.set = lambda key, value: setattr(doc, key, value)
	doc.append = lambda key, row: doc.links.append(types.SimpleNamespace(
		link_doctype=row["link_doctype"], link_name=row["link_name"],
		get=lambda k, d=None: row.get(k, d),
	))
	doc.reference_doctype = values.get("reference_doctype")
	doc.reference_name = values.get("reference_name")
	return doc


# --------------------------------------------------------------------------- #
# A series prefix is the fixed head of the template
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("series,expected", [
	("PINV-.YYYY.-", "PINV-"),
	("ACC-JV-.YYYY.-", "ACC-JV-"),
	("MR-{#####}", "MR-"),
	("EV.#####", "EV"),
	("LTR-.YY.-", "LTR-"),
	# The scheme in front of a series is not part of any document's name.
	("format:CD-{#####}", "CD-"),
	# And these are not series at all. `naming.options` reports a doctype's raw
	# `autoname` where it has no `naming_series` field, so they arrive here
	# looking like templates — and `hash` as a prefix would match the word in
	# any message anybody sent.
	("hash", ""),
	("field:title", ""),
	("prompt", ""),
	("autoincrement", ""),
	# One character would match a word. Two is the floor.
	("X.#####", ""),
	("", ""),
])
def test_a_prefix_is_the_part_that_does_not_vary(linking, series, expected):
	assert linking._literal(series) == expected


# --------------------------------------------------------------------------- #
# An id written in the message
# --------------------------------------------------------------------------- #

def test_an_id_in_the_subject_is_found(linking, monkeypatch):
	"""The case the framework files nowhere: a first contact naming a record.

	No `in_reply_to`, no `#(...)`, and a sender we may never have seen. This is
	the commonest inbound shape for an accounts address and Frappe's own subject
	scan cannot reach it, because the token it looks for is one we put there.
	"""
	monkeypatch.setattr(
		linking.frappe.db, "exists",
		lambda doctype, name=None: doctype == "Purchase Invoice" and name == "PINV-2025-0041",
	)
	doc = message(subject="Re: your invoice PINV-2025-0041", content="")

	assert linking.from_text(doc) is True
	assert linking.links_of(doc) == [
		{"doctype": "Purchase Invoice", "name": "PINV-2025-0041", "by": "text"}
	]


def test_an_id_that_is_not_a_record_is_not_a_link(linking, monkeypatch):
	"""A prefix match is a guess; the database is the answer.

	Somebody quoting a number that looks like ours must not staple their message
	to a document that does not exist, or worse to one that does under a
	different id.
	"""
	monkeypatch.setattr(linking.frappe.db, "exists", lambda *a, **k: False)
	doc = message(subject="About PINV-9999-9999", content="")

	assert linking.from_text(doc) is False
	assert linking.links_of(doc) == []


def test_one_message_can_be_about_several_records(linking, monkeypatch):
	"""A supplier statement names eleven invoices, and `reference_name` holds one.

	This is why the child table is the storage: the pair keeps the first, and
	every one after it would otherwise be lost.
	"""
	real = {("Purchase Invoice", "PINV-2025-0041"), ("Project", "PROJ-0088")}
	monkeypatch.setattr(
		linking.frappe.db, "exists", lambda doctype, name=None: (doctype, name) in real
	)
	doc = message(subject="PINV-2025-0041 against PROJ-0088", content="")

	assert linking.from_text(doc) is True
	assert [one["name"] for one in linking.links_of(doc)] == ["PINV-2025-0041", "PROJ-0088"]
	# The first is also the primary, because that is the one the framework reads.
	assert doc.reference_doctype == "Purchase Invoice"
	assert doc.reference_name == "PINV-2025-0041"


def test_the_quoted_history_is_not_scanned(linking, monkeypatch):
	"""A reply carries every earlier message inside it.

	Their ids were found when those messages arrived. Reading them again links a
	one-line reply to everything the conversation ever mentioned.
	"""
	body = (
		"<p>Yes, go ahead.</p>"
		"<blockquote>Please see PINV-2025-0041 and PROJ-0088</blockquote>"
	)
	assert "PINV" not in linking._words(body)


def test_an_ungranted_doctype_is_never_linked(linking, monkeypatch):
	"""The manifest is the allowlist here too.

	Without this a stranger could write a plausible id in a subject line and
	have their message filed against the platform's own bookkeeping.
	"""
	monkeypatch.setattr(linking, "prefixes", lambda: {})
	monkeypatch.setattr(linking.frappe.db, "exists", lambda *a, **k: True)
	doc = message(subject="ERR-0001 and TOK-0002", content="")

	assert linking.from_text(doc) is False


# --------------------------------------------------------------------------- #
# A conversation carries its answer
# --------------------------------------------------------------------------- #

def test_a_reply_inherits_what_the_conversation_is_about(linking, monkeypatch):
	"""The cheapest correct link there is: one query, exact, no guessing.

	It reads `custom_thread` rather than `in_reply_to`, so it still finds the
	answer where the reply arrived with its headers stripped and was threaded on
	the subject instead.
	"""
	monkeypatch.setattr(linking.frappe, "get_all", lambda *a, **k: [
		types.SimpleNamespace(
			reference_doctype="Project", reference_name="PROJ-0088",
			get=lambda key, default=None: default,
		)
	])
	doc = message(subject="Re: the tower", custom_thread="abc", content="")

	assert linking.from_thread(doc) is True
	assert doc.reference_name == "PROJ-0088"
	assert linking.links_of(doc)[0]["by"] == "thread"


def test_a_message_that_already_knows_is_left_alone(linking):
	"""`append_to` and the framework's own resolution both run before this."""
	doc = message(custom_thread="abc", reference_doctype="Project",
	              reference_name="PROJ-0001", subject="x", content="")
	assert linking.from_thread(doc) is False


def test_a_conversation_about_nothing_stays_about_nothing(linking, monkeypatch):
	"""The honest empty answer, and the queue a model would later be given."""
	monkeypatch.setattr(linking.frappe, "get_all", lambda *a, **k: [])
	doc = message(custom_thread="abc", subject="hello", content="")
	assert linking.from_thread(doc) is False


# --------------------------------------------------------------------------- #
# The same record twice is one link
# --------------------------------------------------------------------------- #

def test_a_record_named_twice_is_linked_once(linking):
	doc = message(subject="x", content="")
	assert linking.add(doc, "Project", "PROJ-0088", "text") is True
	assert linking.add(doc, "Project", "PROJ-0088", "manual") is False
	assert len(linking.links_of(doc)) == 1


def test_a_second_record_does_not_move_the_primary(linking):
	"""The primary is the first link. A later one is a row and nothing more."""
	doc = message(subject="x", content="")
	linking.add(doc, "Project", "PROJ-0088", "text")
	linking.add(doc, "Purchase Invoice", "PINV-2025-0041", "text")
	assert doc.reference_name == "PROJ-0088"


# --------------------------------------------------------------------------- #
# A link is not a grant
# --------------------------------------------------------------------------- #

def test_the_record_reader_applies_the_readers_own_permission():
	"""One word decides whether this feature is a disclosure.

	`get_all` ignores permissions. If the record's correspondence were read with
	it, filing a message against a project would publish that message to
	everybody who can open the project — including mail that arrived on an
	address they were never granted. `get_list` is what stops it, and it is not
	something a reviewer would notice going missing.
	"""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview/mail.py").read_text()
	body = source[source.index("def correspondence("):source.index("def write(")]

	assert 'frappe.get_list(\n\t\t"Communication"' in body, (
		"the record's mail is read with something other than get_list"
	)
	assert "ignore_permissions" not in body


def test_nothing_in_the_record_reader_shares_a_message():
	"""Sharing is how a person gets access to mail, and this is not that path.

	`inbound._share` grants the holders of an address; a link says what a message
	is about. Anything here calling `frappe.share` would be turning the second
	into the first.
	"""
	# The call, not the name: both files argue about sharing in their prose,
	# and a guard that cannot tell an explanation from an instruction is a guard
	# that has to be worked around.
	for path in (
		"apps/oneapp/oneapp/oneapp_core/spaceview/mail.py",
		"apps/oneapp/oneapp/oneapp_core/email/linking.py",
	):
		assert "frappe.share.add" not in (ROOT / path).read_text(), path


# --------------------------------------------------------------------------- #
# Filing must never lose a message
# --------------------------------------------------------------------------- #

def test_a_failure_while_filing_does_not_lose_the_message(linking, monkeypatch):
	"""Losing mail to a filing rule is the worst trade there is."""
	def boom(doc):
		raise RuntimeError("no")

	monkeypatch.setattr(linking, "place", boom)
	logged = []
	monkeypatch.setattr(linking.frappe, "log_error", lambda **k: logged.append(k))

	linking.on_insert(message(communication_medium="Email", subject="x", content=""))
	assert logged


def test_only_email_is_placed(linking, monkeypatch):
	"""A phone call logged as a Communication has no subject to read."""
	monkeypatch.setattr(linking, "place", lambda doc: pytest.fail("ran on a call"))
	linking.on_insert(message(communication_medium="Phone", subject="x", content=""))


# --------------------------------------------------------------------------- #
# The framework rewrites the rows we wrote
# --------------------------------------------------------------------------- #

def test_provenance_is_written_after_the_framework_has_finished(linking, monkeypatch):
	"""`deduplicate_timeline_links` rebuilds every link row from its doctype and
	name alone — it iterates a set of those pairs and calls `add_link` for each,
	dropping anything else the row carried. It runs in `validate`, after
	`before_insert`.

	So provenance written with the link is written and then silently thrown
	away, with the link itself intact — which is the worst shape a bug can have.
	It goes on afterwards instead, straight onto the rows.
	"""
	written = []
	monkeypatch.setattr(
		linking.frappe.db, "set_value",
		lambda doctype, filters, field, value, **k: written.append((filters["link_name"], value)),
	)
	doc = message(subject="x", content="")
	doc.name = "COMM-0001"
	doc._onespace_links = [{"doctype": "Project", "name": "PROJ-0088", "by": "text"}]

	linking.stamp(doc)
	assert written == [("PROJ-0088", "text")]


def test_a_message_this_did_not_place_is_not_stamped(linking, monkeypatch):
	"""The contact links the framework adds are the framework's, not ours."""
	monkeypatch.setattr(
		linking.frappe.db, "set_value",
		lambda *a, **k: pytest.fail("stamped a link we did not make"),
	)
	doc = message(subject="x", content="")
	doc.name = "COMM-0002"
	linking.stamp(doc)
