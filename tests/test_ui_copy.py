"""One voice, everywhere the reader can see it.

A product speaks to the person using it about *their* work. The framework
underneath has its own vocabulary — doctypes, fieldnames, permlevels, syncs,
transactions — and every one of those words is a fact about our plumbing rather
than about anything the reader asked for. They leak the same way every time:
somebody writes the sentence while holding the code in their head, and the
sentence comes out true and useless.

So this refuses the vocabulary, over every string the browser can show in
either SPA and every message the server throws back. Which strings those are is
`copy_reader`'s question and not a second answer here — the rule is about the
English sentence, so it applies to one inside `__()` exactly as it did the day
before it was wrapped. It is a spelling test, not a style test: it cannot tell
whether a sentence is good, only whether it is about the wrong thing.

The operator console is exempt from the *vendor* nouns and nothing else.
Frappe Cloud, bench groups and Stripe subscriptions are what an operator
actually works with — the names are on the invoices — and renaming them there
would be the same mistake in the other direction.
"""

import re

import pytest
from copy_reader import thrown, visible

# What a sentence must not be about. Each maps to the thing to say instead —
# the failure prints it, because "don't say doctype" without "say record" is a
# rule somebody works around rather than follows.
BANNED = {
	"doctype": "the kind of record, or nothing at all",
	"docname": "the record",
	"fieldname": "the field",
	"permlevel": "who may see it",
	"enqueue": "what the reader waits for, not how we queue it",
	"transaction": "what still works afterwards",
	"payload": "the thing being sent",
	"hmac": "nothing — this is not the reader's problem",
	"manifest": "the app, or the space",
	"webhook": "the thing that calls us",
	"child table": "the rows, or the table's own label",
	"whitelisted": "nothing — this is not the reader's problem",
}

# The two places a message is written *for an operator*: the console's own API
# and the billing webhooks it replays from. "This event was recorded without a
# payload to replay" is the sentence an operator needs — the payload is the
# thing they are deciding whether to send again — and softening it there would
# make the console vaguer without making anything friendlier.
OPERATOR = (
	"apps/oneapp_control/oneapp_control/api/admin",
	"apps/oneapp_control/oneapp_control/billing/",
	"modules/onespace/screens/ops/",
)


def for_an_operator(where: str) -> bool:
	return any(one in where for one in OPERATOR)


# Words that are fine for an operator and wrong for a customer. Frappe Cloud
# is a supplier we buy from and Stripe takes the payments; an operator's screen
# names them because that is where they will go to look.
VENDOR = ("frappe", "stripe", "bench", "site plan", "press")


def test_the_reader_found_the_copy():
	"""A scan that matches nothing passes for the wrong reason."""
	assert len(visible()) > 150, "the copy scan matched almost nothing"
	assert len(thrown()) > 20, "the server-message scan matched almost nothing"


@pytest.mark.parametrize("word", sorted(BANNED))
def test_no_customer_sentence_is_about_the_plumbing(word):
	guilty = [
		f"{where}: {text!r} — say {BANNED[word]}"
		for where, text in visible() + thrown()
		if re.search(rf"\b{re.escape(word)}s?\b", text, re.I)
		and not for_an_operator(where)
	]
	assert not guilty, "\n".join(guilty)


def test_a_customer_screen_does_not_name_our_suppliers():
	"""Who we buy from is ours to know. An operator's screen may say it."""
	guilty = [
		f"{where}: {text!r}"
		for where, text in visible()
		if not for_an_operator(where)
		and any(re.search(rf"\b{word}\b", text, re.I) for word in VENDOR)
		# Billing names Stripe on purpose: somebody about to type a card
		# number is entitled to know who is taking it.
		and "Billing.vue" not in where
	]
	assert not guilty, "\n".join(guilty)


def test_nothing_tells_a_customer_to_wait_for_a_sync():
	"""`sync` is our word for the control plane's pull, and it means nothing to
	somebody who just pressed Save. Say how long, or say nothing."""
	guilty = [
		f"{where}: {text!r} — say how long it takes, not what runs"
		for where, text in visible() + thrown()
		if re.search(r"\bre-?sync|\bsyncs?\b|\bsynced\b|\bsyncing\b", text, re.I)
		and not for_an_operator(where)
	]
	assert not guilty, "\n".join(guilty)


# --------------------------------------------------------------------------- #
# The prose budget
#
# 2,608 visible strings and only 44 ran past twenty words, so there was never
# an epidemic of long sentences. What there was, was *stacking*: 200 words in
# twelve explanatory strings down one settings panel, every one of which
# passes review on its own and which together are a manual somebody has to
# read to find the control they came for. `docs/UNIFICATION.md` §A3.
# --------------------------------------------------------------------------- #

import re as _re  # noqa: E402

from copy_reader import ROOT as _ROOT, visible as _visible  # noqa: E402

_WORD = _re.compile(r"[A-Za-z][A-Za-z'-]*")

#: One line of help per control. Past this it is not help, it is a paragraph,
#: and a paragraph belongs behind an info affordance or in the docs.
CEILING = 20

#: Below this a string is a label rather than prose.
PROSE_FROM = 9

BUDGET = _ROOT / "tests/prose_budget.txt"


def _budgets() -> dict[str, int]:
	found = {}
	for line in BUDGET.read_text().splitlines():
		if line.startswith("#") or not line.strip():
			continue
		words, where = line.split("\t", 1)
		found[where] = int(words)
	return found


def test_no_help_line_runs_past_twenty_words():
	offenders = [
		f"{where.split('/src/')[-1]} ({len(_WORD.findall(text))} words): {text[:70]}…"
		for where, text in _visible()
		if len(_WORD.findall(text)) > CEILING
	]
	assert not offenders, (
		"these are paragraphs rather than help lines:\n  "
		+ "\n  ".join(sorted(offenders))
		+ "\n\nAnything past twenty words is not deleted, it moves: behind an "
		"info affordance on the control it explains, or into the docs. The "
		"sentence that explains what a restore does to files is a good "
		"sentence in a popover and a bad one as the fifth paragraph of a panel."
	)


def test_the_ceiling_scan_would_catch_one():
	long = "one two three four five six seven eight nine ten " * 3
	assert len(_WORD.findall(long)) > CEILING
	assert len(_WORD.findall("Copies of this workspace, and going back to one.")) <= CEILING


def test_a_screen_carries_no_more_prose_than_it_did():
	"""A ratchet, not a cap — see the header of `prose_budget.txt` for why.

	A cap would push somebody to split a file rather than shorten a screen,
	and several of the files listed hold mutually exclusive branches of one
	message where no reader sees more than one. What a ratchet catches is the
	thing that actually happened: a sentence added to a screen that already
	had eleven, each addition right on its own.
	"""
	import collections

	allowed = _budgets()
	per: collections.Counter = collections.Counter()
	for where, text in _visible():
		words = len(_WORD.findall(text))
		if words >= PROSE_FROM:
			per[where] += words

	grown = [
		f"{where.split('/src/')[-1]}: {words} words, budget {allowed.get(where, 60)}"
		for where, words in sorted(per.items())
		if words > allowed.get(where, 60)
	]
	assert not grown, (
		"these screens carry more prose than they did:\n  "
		+ "\n  ".join(grown)
		+ "\n\nCut something else on the screen, move it behind an info "
		"affordance, or put it in the docs. `scripts/prose_budget.py` "
		"re-measures — after cutting, never after adding."
	)


def test_the_budget_file_describes_the_screens_that_exist():
	"""A ratchet with a stale entry is a budget somebody can spend twice."""
	for where in _budgets():
		assert (_ROOT / where).exists(), (
			f"{where} is in the prose budget and not on disk — re-run "
			f"scripts/prose_budget.py"
		)
