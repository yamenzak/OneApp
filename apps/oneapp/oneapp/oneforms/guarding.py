"""Telling a person from a script, cheaply.

`docs/ONEFORMS.md` §14, stage 15. Until this, the whole of the defence on a
public form was `@rate_limit(key="route", limit=20, seconds=60)` — which is a
rate limit. It bounds how fast rubbish arrives and says nothing about whether
what arrived is rubbish, and twenty an hour of somebody else's SEO spam in
OneCRM's leads is twenty an hour a person has to delete.

Two checks, both free, neither of them a claim to stop somebody determined:

* **A field no person sees.** The page draws it off-screen with no label a
  reader meets; a script that fills every input fills it too. Named with a
  leading underscore, which is a thing no doctype fieldname is, so it can never
  collide with a real one and never reaches `accept`.
* **How long it took.** `page` hands out a stamp and `send` reads it back. A
  form filled in under three seconds was not read, and one submitted against a
  stamp from yesterday is a replay.

**The stamp is signed**, because the alternative is a number the sender chooses.
Keyed on the site's own secret, so a stamp from one site is not a stamp on
another, and truncated because this is a nonce rather than a credential.

What this is not: a captcha. A captcha is a cost on every honest person to
inconvenience a dishonest one, and it is also a third party watching a page this
product promises fetches nothing from anywhere — §13's fonts are the same
argument. If a form ever needs more than this, the answer is a key, and the key
already exists.
"""

import hashlib
import time

import frappe
from frappe import _

#: The field nobody sees. A leading underscore is the whole of why it is safe:
#: no Frappe fieldname starts with one, so it cannot shadow a real question and
#: `send` strips it before anything else looks at the payload.
TRAP = "_website"

#: Under this and it was not read. Three seconds is the shortest a person takes
#: to find one field and press a button; anything quicker did not look.
LEAST = 3

#: And over this it is a replay. A day, because somebody who opened a form,
#: went to lunch and came back should still be able to send it.
MOST = 24 * 60 * 60

#: How much of the digest travels. A nonce rather than a credential — the
#: timestamp beside it is the thing being protected, and it is not a secret.
SHORT = 16


def issued() -> str:
	"""`<seconds>.<signature>` — handed out with the page.

	Not `stamp`, because `counting.stamp` is in the same three lines of `send`
	and means something else entirely: that one marks a record, this one mints
	a nonce.
	"""
	now = int(time.time())
	return f"{now}.{_signed(now)}"


def check(said: str) -> None:
	"""Refuse a submission that was not read, or that is a replay.

	One sentence for all three failures, like `_form`'s: out here the difference
	between "you were too quick", "that is stale" and "that is not ours" is a
	fact about how this workspace is defended.
	"""
	said = str(said or "")
	when, _dot, signature = said.partition(".")

	try:
		when = int(when)
	except ValueError:
		_refuse()

	if signature != _signed(when):
		_refuse()

	spent = int(time.time()) - when
	if spent < LEAST or spent > MOST:
		_refuse()


def caught(values: dict) -> bool:
	"""Whether the field nobody sees was filled in. Removes it either way."""
	return bool(str(values.pop(TRAP, "") or "").strip())


def cleaned(values: dict) -> dict:
	"""The payload with everything this module put in it taken out.

	A leading underscore is the marker and it is checked here rather than
	remembered at each call site: nothing starting with one is a field on a
	doctype, so nothing starting with one has any business reaching `accept`.
	"""
	return {key: value for key, value in (values or {}).items()
	        if not str(key).startswith("_")}


def _signed(when: int) -> str:
	"""A digest of the moment, keyed on this site.

	`frappe.conf` rather than a constant, so a stamp minted on one site is not
	a stamp on another — and `get` rather than `[]` because a test site has no
	key and the check should still be a check, just not a secret one.
	"""
	secret = str((frappe.conf or {}).get("encryption_key") or "oneforms")
	return hashlib.sha256(f"{when}:{secret}".encode()).hexdigest()[:SHORT]


def _refuse():
	frappe.throw(_("That did not go through. Open the form again and resend it."))
