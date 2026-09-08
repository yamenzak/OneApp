"""The legal system, and the one guard that makes it a system.

Three claims are worth holding here.

**A document is assembled, not written once.** Every module declares the
clauses that follow from what it does, beside the code that does it, and
OneLegal puts them together. So a subprocessor added to OneMail turns up in the
privacy policy and in the subprocessor list without anybody editing either.

**A version is `revision.hash`, and both halves matter.** The revision is bumped
by a person when a change is material; the hash is taken over the assembled
text and cannot be bumped by hand. `test_no_document_has_drifted_without_saying`
is the whole point of the design: it holds a copy of every document's hash, so a
change to any clause anywhere fails the suite until somebody decides whether it
is a typo (record the new hash) or material (bump the revision, and every
workspace agrees again).

**Two parties, and only one of them can be signed for by somebody else.** A
contract binds the organisation and the person who creates the workspace can
accept it. A privacy notice describes the handling of one person's personal
data, and their employer cannot agree to that for them.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT / "apps/oneapp/oneapp/onelegal"

#: Every document's assembled text, hashed. Change one deliberately and this
#: line changes with it — which is the point: the diff says a legal document
#: moved, in a review that would otherwise show a paragraph in a module.
#:
#: To update: run `python3 -m pytest tests/test_legal.py -k hashes -q` and paste
#: what it prints, *after* deciding whether the revision should go up too.
HASHES = {
    "terms": "48dad46f",
    "aup": "6a531fe5",
    "privacy": "d5e7bc06",
    "cookies": "8266af8b",
    "dpa": "7fbb62c6",
    "subprocessors": "db9adfef",
    "ai": "5a2cefb5",
    "licences": "c5d062c1",
}


@pytest.fixture
def legal(stub_frappe):
	"""The package, and everything reached *through* it.

	Never `from oneapp.onelegal.registry import SUBPROCESSORS` in a test: the
	stub purges `oneapp.*` between tests but the `oneapp` package object
	survives with its attributes, so a second import can hand back a fresh
	empty registry beside the populated one the package is still holding. One
	handle, one registry.
	"""
	from oneapp import onelegal as module

	module.documents()  # loads every module's declarations
	return module


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def test_every_document_renders(legal):
	for one in legal.documents():
		rendered = legal.render(one["key"])
		assert rendered["html"].startswith("<h1>")
		assert rendered["version"] == one["version"]


def test_a_module_clause_reaches_the_document(legal):
	"""OneMail says Cloudflare carries the mail; the privacy policy says it."""
	privacy = legal.render("privacy")["html"]
	assert "Cloudflare Email Routing" in privacy


def test_a_module_subprocessor_reaches_the_list(legal):
	rows = legal.render("subprocessors")["html"]
	for company in ("Cloudflare, Inc.", "Stripe, Inc.", "Google LLC",
	                "Hetzner Online GmbH", "Frappe Technologies Pvt. Ltd."):
		assert company in rows, f"{company} is used and not listed"


def test_one_company_is_one_row(legal):
	"""Cloudflare is three modules' supplier and one row with three purposes."""
	cloudflare = legal.SUBPROCESSORS["Cloudflare, Inc."]
	modules = {use["module"] for use in cloudflare["uses"]}
	assert {"OneStorage", "OneMail", "OneSpace"} <= modules


def test_the_company_appears_where_it_must(legal):
	terms = legal.render("terms")["html"]
	assert "Four Degree Labs" in terms
	assert "legal@fourdegreelabs.com" in terms
	assert "Abu Dhabi" in terms


def test_the_text_is_escaped(legal):
	"""Every clause goes through `_esc`, so a `<` in one is a `<` and not a tag."""
	assert legal.assemble._esc('a <b> & "c"') == "a &lt;b&gt; &amp; &quot;c&quot;"


# --------------------------------------------------------------------------- #
# Versioning
# --------------------------------------------------------------------------- #

def test_a_version_is_a_revision_and_a_hash(legal):
	for key in HASHES:
		version = legal.version_of(key)
		assert re.fullmatch(r"\d+\.[0-9a-f]{8}", version), f"{key}: {version}"


def test_the_hash_follows_the_words_and_not_the_markup(legal):
	"""What is agreed to is the text. Changing a heading level should not
	invalidate every acceptance in the fleet, and the hash is taken over the
	plain text for exactly that reason."""
	assert "<" not in legal.text_of("terms")


def test_no_document_has_drifted_without_saying(legal):
	"""The guard this whole module exists for. See the docstring at the top."""
	import hashlib

	drifted = []
	current = {}
	for key, known in HASHES.items():
		digest = hashlib.sha256(legal.text_of(key).encode("utf-8")).hexdigest()[:8]
		current[key] = digest
		if known and known != digest:
			drifted.append(f"{key}: was {known}, is {digest}")

	if any(one is None for one in HASHES.values()):
		pytest.skip("hashes not recorded yet: " + repr(current))

	assert not drifted, (
		"a legal document changed. Decide which it is:\n"
		"  material — bump `revision` in onelegal/documents.py, and every "
		"workspace agrees again;\n"
		"  a typo   — record the new hash in tests/test_legal.py.\n"
		+ "\n".join(drifted)
	)


def test_hashes(legal):
	"""Prints what to paste into `HASHES`. Never fails."""
	import hashlib

	for key in HASHES:
		digest = hashlib.sha256(legal.text_of(key).encode("utf-8")).hexdigest()[:8]
		print(f'    "{key}": "{digest}",')


# --------------------------------------------------------------------------- #
# Who agrees to what
# --------------------------------------------------------------------------- #

def test_the_contract_binds_the_workspace_and_the_notice_binds_the_person(legal):
	WORKSPACE, USER = legal.gate.WORKSPACE, legal.gate.USER

	assert "terms" in legal.keys_for(WORKSPACE)
	assert "dpa" in legal.keys_for(WORKSPACE)
	assert "terms" not in legal.keys_for(USER)
	assert "privacy" in legal.keys_for(USER)
	assert "cookies" in legal.keys_for(USER)
	# Both: the organisation promises it and each person acknowledges it.
	assert "aup" in legal.keys_for(WORKSPACE) and "aup" in legal.keys_for(USER)


def test_a_document_with_no_audience_is_published_and_not_agreed_to(legal):
	assert "licences" not in legal.keys_for(legal.gate.WORKSPACE)
	assert "licences" not in legal.keys_for(legal.gate.USER)


def test_every_document_has_a_summary_and_a_revision(legal):
	for key, one in legal.documents_module.DOCUMENTS.items():
		assert one["summary"], key
		assert one["revision"] >= 1, key
		assert one["audience"] in (None, "customer", "user", "both"), key


# --------------------------------------------------------------------------- #
# The declarations themselves
# --------------------------------------------------------------------------- #

def test_every_clause_lands_in_a_section_that_exists(legal):
	SECTIONS = legal.documents_module.SECTIONS
	for document, section in legal.CLAUSES:
		assert document in SECTIONS, f"clause for unknown document {document}"
		assert section in {one for one, _ in SECTIONS[document]}, (
			f"clause for unknown section {document}/{section}"
		)


def test_a_module_that_declares_anything_declares_it_in_legal_py():
	"""One file per module, and its name is the convention.

	A clause hidden in a module's business logic is a clause nobody reviewing
	the agreements would find.
	"""
	stray = []
	for path in (ROOT / "apps/oneapp/oneapp").rglob("*.py"):
		if path.name == "legal.py" or "onelegal" in path.parts:
			continue
		body = path.read_text()
		if re.search(r"^\s*(clause|subprocessor)\(", body, re.M):
			stray.append(str(path.relative_to(ROOT)))
	assert not stray, "declared outside a module's legal.py: " + ", ".join(stray)


def test_the_subprocessor_rows_say_everything_a_reader_needs(legal):
	for row in legal.registry.subprocessor_rows():
		assert row["safeguard"], f"{row['name']} does not say what makes it lawful"
		for use in row["uses"]:
			assert use["purpose"] and use["data"], row["name"]
			assert use["where"], f"{row['name']} does not say where {use['purpose']}"
