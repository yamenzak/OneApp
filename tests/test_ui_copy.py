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
