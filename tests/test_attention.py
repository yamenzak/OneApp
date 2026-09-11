"""The one screen that speaks without being asked.

Each check is a query, and a query is easy to write and easy to get subtly
wrong in the direction that matters: a check that never fires is worse than no
check, because it reads as "nothing is wrong". So these assert the *shape* of
every check — that it is registered, that it names a screen a person can open,
and that it says nothing when there is nothing to say — plus the two rules the
module turns on.
"""

import sys

import pytest


@pytest.fixture
def attention(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp_control.attention"):
			del sys.modules[name]
	from oneapp_control import attention as module

	return module


def test_every_check_is_registered(attention):
	"""A function nobody calls is a check that never fires."""
	registered = {check for _name, check in attention.CHECKS}
	written = {
		value
		for key, value in vars(attention).items()
		if callable(value)
		and getattr(value, "__module__", "") == attention.__name__
		and not key.startswith("_")
		and key not in ("rows", "board", "digest")
	}
	assert written == registered, (
		"these are written and never run: "
		+ ", ".join(sorted(f.__name__ for f in written - registered))
	)


def test_the_keys_are_unique(attention):
	keys = [name for name, _check in attention.CHECKS]
	assert len(keys) == len(set(keys))


def test_every_severity_is_one_of_three(attention):
	"""A fourth severity is a row that sorts last and reads as unranked."""
	assert set(attention.RANK) == {"blocking", "warning", "notice"}


def test_a_row_carries_somewhere_to_go_or_says_why_not(attention):
	row = attention._row("k", "warning", "Title", "Detail", screen="tenants")
	assert set(row) == {"key", "severity", "title", "detail", "screen", "record", "count"}
	assert row["screen"] == "tenants"
	# Without one, the row is still valid — a broken check has nowhere to send
	# anybody, and must not be dropped for it.
	assert attention._row("k", "notice", "T", "D")["screen"] == ""


def test_a_check_that_raises_becomes_a_row(attention, monkeypatch):
	"""A console that goes blank because Frappe Cloud is down has told you
	nothing. "The press check is broken" is itself worth reading."""
	def explode():
		raise RuntimeError("press is unreachable")

	monkeypatch.setattr(attention, "CHECKS", (("press", explode),))
	found = attention.rows()
	assert len(found) == 1
	assert found[0]["key"] == "check:press"
	assert found[0]["severity"] == "notice"


def test_rows_are_worst_first(attention, monkeypatch):
	monkeypatch.setattr(attention, "CHECKS", (
		("a", lambda: [attention._row("a", "notice", "n", "")]),
		("b", lambda: [attention._row("b", "blocking", "b", "")]),
		("c", lambda: [attention._row("c", "warning", "w", "")]),
	))
	assert [row["severity"] for row in attention.rows()] == [
		"blocking", "warning", "notice",
	]


def test_a_quiet_day_sends_nothing(attention, monkeypatch):
	"""The whole reason the digest is worth having. An email that arrives every
	morning saying nothing is wrong is an email that gets filtered."""
	monkeypatch.setattr(attention, "CHECKS", ())
	sent = []
	monkeypatch.setattr(attention.frappe, "sendmail", lambda **kw: sent.append(kw), raising=False)
	assert attention.digest() == {"sent": 0, "rows": 0}
	assert not sent


def test_the_digest_names_the_worst_it_found(attention, monkeypatch):
	monkeypatch.setattr(attention, "CHECKS", (
		("a", lambda: [attention._row("a", "notice", "Something", "worth knowing")]),
		("b", lambda: [attention._row("b", "blocking", "Nothing works", "at all")]),
	))
	monkeypatch.setattr(attention, "_recipients", lambda: ["ops@example.com"])
	sent = []
	monkeypatch.setattr(attention.frappe, "sendmail", lambda **kw: sent.append(kw), raising=False)

	out = attention.digest()
	assert out == {"sent": 1, "rows": 2}
	assert "blocking" in sent[0]["subject"]
	assert "Nothing works" in sent[0]["message"]


def test_nobody_to_tell_is_not_a_crash(attention, monkeypatch):
	monkeypatch.setattr(attention, "CHECKS", (
		("a", lambda: [attention._row("a", "warning", "T", "D")]),
	))
	monkeypatch.setattr(attention, "_recipients", lambda: [])
	sent = []
	monkeypatch.setattr(attention.frappe, "sendmail", lambda **kw: sent.append(kw), raising=False)
	assert attention.digest()["sent"] == 0
	assert not sent


# --------------------------------------------------------------------------- #
# And the console knows about it
# --------------------------------------------------------------------------- #

def test_attention_leads_the_rail(stub_frappe):
	"""First, or it is one more screen to remember to open."""
	from oneapp_control.entitlements import operator

	assert operator.LEADING[0][0] == "attention"
	shape = operator.manifest()
	assert shape["screens"][0]["screen"] == "attention"
	assert shape["screens"][0]["component"] == "onespace-ops/attention"


def test_the_digest_runs_after_the_sweeps(stub_frappe):
	"""It reads what they write. Before them it reports yesterday."""
	import pathlib
	import re

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp_control/oneapp_control/hooks.py"
	).read_text()
	daily = source.split('"daily": [')[1].split("]")[0]
	jobs = re.findall(r'"([\w.]+)"', daily)
	assert jobs[-1] == "oneapp_control.attention.digest"
	assert "oneapp_control.lifecycle.sweep.run" in jobs


def test_the_screen_is_registered_in_the_spa(stub_frappe):
	import pathlib

	source = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
	).read_text()
	assert "'onespace-ops/attention'" in source
