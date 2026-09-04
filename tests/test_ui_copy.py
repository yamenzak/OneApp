"""One voice, everywhere the reader can see it.

A product speaks to the person using it about *their* work. The framework
underneath has its own vocabulary — doctypes, fieldnames, permlevels, syncs,
transactions — and every one of those words is a fact about our plumbing rather
than about anything the reader asked for. They leak the same way every time:
somebody writes the sentence while holding the code in their head, and the
sentence comes out true and useless.

So this reads every string the browser can show, in both SPAs and in the
messages the server throws back, and refuses the vocabulary. It is a spelling
test, not a style test: it cannot tell whether a sentence is good, only whether
it is about the wrong thing.

The operator console is exempt from the *vendor* nouns and nothing else.
Frappe Cloud, bench groups and Stripe subscriptions are what an operator
actually works with — the names are on the invoices — and renaming them there
would be the same mistake in the other direction.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Where a customer reads. Everything under `screens/ops/` is the operator
# console; everything else in these trees is a workspace member's.
SPAS = ("apps/oneapp/frontend/src", "apps/oneapp_control/frontend/src")

# The attributes and calls that put a string in front of somebody.
ATTRS = ("label", "title", "description", "placeholder", "tooltip", "message",
         "successMessage", "empty", "header", "subtitle", "text")

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
	"screens/ops/",
)


def for_an_operator(where: str) -> bool:
	return any(one in where for one in OPERATOR)


# Words that are fine for an operator and wrong for a customer. Frappe Cloud
# is a supplier we buy from and Stripe takes the payments; an operator's screen
# names them because that is where they will go to look.
VENDOR = ("frappe", "stripe", "bench", "site plan", "press")


def strip_comments(text: str) -> str:
	text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
	text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
	return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def visible() -> list[tuple[str, str]]:
	"""Every string the reader can see, as (where, what)."""
	found = []
	for spa in SPAS:
		base = ROOT / spa
		for path in sorted(base.rglob("*.vue")) + sorted(base.rglob("*.js")):
			raw = strip_comments(path.read_text())
			where = f"{spa}/{path.relative_to(base)}"
			for attr in ATTRS:
				pattern = rf'(?<![\w:.-]){attr}\s*[=:]\s*["\']([^"\']{{3,}})["\']'
				for m in re.finditer(pattern, raw):
					found.append((where, m.group(1)))
			for m in re.finditer(r">\s*([A-Z][^<>{}\n]{12,})\s*<", raw):
				found.append((where, m.group(1).strip()))
	return found


def thrown() -> list[tuple[str, str]]:
	"""Every message the server hands back to a browser."""
	found = []
	for path in sorted((ROOT / "apps").rglob("*.py")):
		if "node_modules" in str(path):
			continue
		where = str(path.relative_to(ROOT))
		for m in re.finditer(r'_\(\s*"([^"]{8,})"', path.read_text()):
			found.append((where, m.group(1)))
	return found


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
