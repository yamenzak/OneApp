"""Telling a person from a script, and writing back to one.

`docs/ONEFORMS.md` §14, stage 15 and half of 14. Until this, the whole of the
defence on a public form was `@rate_limit(key="route", limit=20, seconds=60)`,
which bounds how fast rubbish arrives and says nothing about whether it is
rubbish — twenty an hour of somebody else's SEO spam in OneCRM's leads is
twenty an hour a person deletes.

Neither check claims to stop somebody determined, and both are free. What is
worth guarding is the shape of them: a field a person never meets, a stamp the
sender cannot mint, and a refusal that says the same thing as a success so a
script cannot learn which one it tripped.
"""

import pathlib
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/oneforms/guarding.py"
PUBLIC = ROOT / "apps/oneapp/oneapp/oneforms/public.py"
INVITE = ROOT / "apps/oneapp/oneapp/oneforms/invite.py"
PAGE = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue"
BUILDER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/FormBuilder.vue"


@pytest.fixture
def guarding(stub_frappe):
	from oneapp.oneforms import guarding

	stub_frappe.conf = {"encryption_key": "zzsecret"}
	return guarding


# ------------------------------------------------------------------- the stamp

def test_a_stamp_from_a_moment_ago_is_refused_and_one_from_a_minute_ago_is_not(guarding):
	"""A form filled in under three seconds was not read."""
	with pytest.raises(Exception):
		guarding.check(guarding.issued())

	guarding.check(f"{int(time.time()) - 60}.{guarding._signed(int(time.time()) - 60)}")


def test_a_stamp_from_yesterday_is_a_replay(guarding):
	old = int(time.time()) - guarding.MOST - 1
	with pytest.raises(Exception):
		guarding.check(f"{old}.{guarding._signed(old)}")


def test_a_stamp_the_sender_wrote_is_refused(guarding):
	"""The whole reason it is signed: otherwise it is a number they choose."""
	when = int(time.time()) - 60
	for made_up in (f"{when}.0000000000000000", f"{when}.", str(when), "", "x.y"):
		with pytest.raises(Exception):
			guarding.check(made_up)


def test_a_stamp_from_another_site_is_not_a_stamp_here(guarding, stub_frappe):
	when = int(time.time()) - 60
	theirs = guarding._signed(when)

	stub_frappe.conf = {"encryption_key": "zzsomebody-else"}
	with pytest.raises(Exception):
		guarding.check(f"{when}.{theirs}")


def test_every_refusal_reads_the_same(guarding):
	"""Out here the difference between "too quick", "stale" and "not ours" is a
	fact about how this workspace is defended."""
	said = set()
	when = int(time.time())
	for bad in (guarding.issued(), f"{when - guarding.MOST - 1}.{guarding._signed(when - guarding.MOST - 1)}",
	            "nonsense"):
		with pytest.raises(Exception) as refused:
			guarding.check(bad)
		said.add(str(refused.value))
	assert len(said) == 1


# -------------------------------------------------------------------- the trap

def test_the_field_nobody_sees_is_named_so_it_can_never_be_a_real_one(guarding):
	"""A leading underscore is the whole of why it is safe: no Frappe fieldname
	starts with one, so it cannot shadow a question and cannot reach `accept`."""
	assert guarding.TRAP.startswith("_")


def test_it_is_taken_out_whether_or_not_it_was_filled_in(guarding):
	filled = {"name": "a", guarding.TRAP: "http://spam"}
	assert guarding.caught(filled) is True
	assert guarding.TRAP not in filled

	empty = {"name": "a", guarding.TRAP: ""}
	assert guarding.caught(empty) is False
	assert guarding.TRAP not in empty


def test_nothing_underscored_reaches_the_write(guarding):
	"""Checked rather than remembered at each call site."""
	assert guarding.cleaned({"a": 1, "_b": 2, "_": 3}) == {"a": 1}


def test_a_caught_submission_is_answered_like_a_successful_one():
	"""A script that learns which check it tripped is a script that stops
	tripping it."""
	sending = PUBLIC.read_text().split("def send")[1]
	caught = sending.split("guarding.caught")[1].split("asked = guarding.cleaned")[0]
	assert "success_message" in caught and "success_title" in caught
	# And nothing was written, which is the point of answering at all.
	assert "accept(" not in caught


def test_the_page_draws_it_off_screen_rather_than_hidden():
	"""A script that skips hidden inputs is a script that skips this one."""
	page = PAGE.read_text()
	assert 'class="sr-only"' in page and 'aria-hidden="true"' in page
	assert 'tabindex="-1"' in page
	assert "form.trap" in page and "form.value?.stamp" in page


def test_there_is_no_captcha():
	"""A cost on every honest person to inconvenience a dishonest one — and a
	third party watching a page this product promises fetches nothing from
	anywhere, which is §13's fonts reached from the other side."""
	for word in ("recaptcha", "hcaptcha", "turnstile", "captcha"):
		assert word not in SOURCE.read_text().lower().replace(
			"what this is not: a captcha. a captcha", "")
	assert "captcha" not in PAGE.read_text().lower()


# --------------------------------------------------------------- the letter back

def test_the_receipt_does_not_carry_what_they_told_you(guarding):
	"""A receipt listing what somebody just said in confidence is that
	confidence sent unencrypted to whatever mailbox they gave — and the one
	form in the fixture collects a covering letter."""
	confirming = INVITE.read_text().split("def confirm")[1]
	assert "values" in confirming  # it is given them, and uses them for one thing
	assert "success_message" in confirming
	# The only thing it reads out of the payload is where to write to.
	assert confirming.count("values") == confirming.count("address(doc, values)") + 1


def test_the_address_is_the_one_the_form_declared_before_the_one_it_guessed(guarding):
	"""A `Data` field with `options = "Email"` is Frappe saying so, and
	`validate_data_field_options` already holds the submission to it."""
	from oneapp.oneforms import invite

	class Row(dict):
		def __getattr__(self, name):
			return self.get(name)

	class Form:
		web_form_fields = [
			Row(fieldname="contact_email", fieldtype="Data", options=""),
			Row(fieldname="reply_to", fieldtype="Data", options="Email"),
		]

	assert invite.address(Form(), {"contact_email": "a@x", "reply_to": "b@x"}) == "b@x"
	assert invite.address(Form(), {"contact_email": "a@x"}) == "a@x"
	assert invite.address(Form(), {}) == ""


def test_it_is_off_unless_a_form_asks_for_it(guarding):
	"""An internal request filed through a keyed link has already been
	acknowledged by the page, and a second letter is noise."""
	from oneapp.oneforms import invite, service

	assert invite.REPLY == service.REPLY == "custom_onespace_reply"
	assert service.REPLY in service.SETTINGS and service.REPLY in service.SWITCHES
	assert 'data-slot="builder-confirm"' in BUILDER.read_text()


def test_a_letter_that_cannot_be_sent_does_not_lose_the_submission(guarding):
	"""The same rule as an invitation, learned the same way."""
	confirming = INVITE.read_text().split("def confirm")[1]
	assert "try:" in confirming and "except Exception:" in confirming
	assert "log_error" in confirming


# ------------------------------------------------------------------- the embed

def test_a_form_can_go_on_the_customers_own_site():
	"""`allowed_embedding_domains` is Frappe's own field and has been on this
	form since stage 1 with nothing to set it — a form that cannot be embedded
	is a form people link away to."""
	builder = BUILDER.read_text()
	assert 'data-slot="builder-embedding"' in builder
	assert 'data-slot="builder-embed"' in builder
	assert "<iframe" in builder
