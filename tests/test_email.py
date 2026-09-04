"""Addresses, suppression and the records a customer has to publish.

The parts of the mail feature that are ordinary Python and are the parts that go
wrong quietly: what a local part may be, which SMTP failures mean "never again",
and whether the DNS a customer is told to publish is the DNS we then look for.

The wiring — that an Email Account is created, that a User Email row grants
access — is Frappe's own and belongs in a runner with a database. What is here
is the reasoning around it.
"""

import pytest


# Imported inside fixtures, not at module scope: `frappe` is stubbed by an
# autouse fixture in conftest, so a module-level import runs before the stub
# exists and fails on the real package being absent.
@pytest.fixture
def addresses():
	from oneapp.oneapp_core.email import addresses as module

	return module


@pytest.fixture
def suppression():
	from oneapp.oneapp_core.email import suppression as module

	return module


@pytest.fixture
def verify():
	from oneapp.oneapp_core.email import verify as module

	return module


# --------------------------------------------------------------------------- #
# What a workspace may call an address
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
	"local_part",
	["sales", "accounts-payable", "a", "ap", "first.last", "a_b", "x1", "team.eu-west"],
)
def test_an_ordinary_local_part_is_allowed(addresses, local_part):
	assert addresses.LOCAL_PART.match(local_part)


@pytest.mark.parametrize(
	"local_part",
	[
		"",            # nothing
		".sales",      # leading dot — legal in RFC 5321, rejected by half the internet
		"sales.",      # trailing dot, same
		"-sales",
		"sales-",
		"Sales",       # upper case: addresses are lowercased before this runs
		"a b",         # a space
		"a@b",         # already an address
		"a+tag",       # plus addressing is a *recipient* trick, not a mailbox name
		"a" * 65,      # past the 64-octet limit on a local part
		"…",
	],
)
def test_anything_else_is_not(addresses, local_part):
	assert not addresses.LOCAL_PART.match(local_part)


def test_the_length_limit_is_the_one_the_rfc_sets(addresses):
	"""64 octets, and the boundary is worth pinning in both directions.

	Written the other way round first — asserting 64 was too long — which is the
	off-by-one this catches: a workspace refused a legal address and the message
	would have said nothing about why.
	"""
	assert addresses.LOCAL_PART.match("a" * 64)
	assert not addresses.LOCAL_PART.match("a" * 65)


def test_the_names_a_workspace_may_not_take(addresses):
	"""Two kinds, and both matter.

	`postmaster` and `abuse` are required by RFC 2142 to reach a human and are
	ours to answer. `noreply` and `admin` are the ones a phisher would want and
	the ones our own machinery already uses — a workspace that took `noreply@`
	would be receiving replies to password resets.
	"""
	assert {"postmaster", "abuse"} <= addresses.RESERVED
	assert {"noreply", "no-reply", "mailer-daemon", "bounce"} <= addresses.RESERVED
	assert {"admin", "administrator", "root", "system"} <= addresses.RESERVED
	# And the ones that are not reserved, because a workspace wanting them is
	# the ordinary case this feature exists for.
	assert not {"sales", "support", "accounts", "info", "hello"} & addresses.RESERVED


def test_every_reserved_name_is_a_name_that_could_be_asked_for(addresses):
	"""A reserved word that could never pass validation is dead weight.

	Reserving `not a local part` would look like a rule and enforce nothing —
	the pattern refuses it first — and the next person would add three more.
	"""
	for one in addresses.RESERVED:
		assert addresses.LOCAL_PART.match(one), f"{one} could never be typed anyway"


# --------------------------------------------------------------------------- #
# Whose domain it is
# --------------------------------------------------------------------------- #

def test_ours_is_decided_by_the_whole_domain(addresses, monkeypatch):
	"""Not by a suffix, because a suffix is how somebody else becomes us.

	`evil-acme.4dl.app` ends with `4dl.app`. What decides is the whole domain
	matching the workspace's own, which carries its slug.
	"""
	monkeypatch.setattr(addresses, "domain", lambda: "acme.4dl.app")

	assert addresses.is_ours("sales@acme.4dl.app")
	assert not addresses.is_ours("sales@globex.4dl.app")
	assert not addresses.is_ours("sales@notacme.4dl.app")
	assert not addresses.is_ours("sales@acme.4dl.app.evil.com")
	assert not addresses.is_ours("billing@theircompany.com")
	assert not addresses.is_ours("")


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #

def test_only_permanent_failures_suppress(suppression):
	"""A full mailbox is not a dead address.

	Suppressing on a soft failure means one bad afternoon costs a customer an
	address for good, and Frappe's queue already retries those.
	"""
	assert "5.1.1" in suppression.PERMANENT
	for soft in ("4.2.2", "4.4.1", "4.7.0", "2.0.0"):
		assert not any(soft.startswith(code) for code in suppression.PERMANENT)


def test_a_policy_rejection_does_not_suppress(suppression):
	"""5.7.1 is permanent and is about the *message*, not the recipient.

	Suppressing on it would take a live address off the list because one mail
	tripped a content rule.
	"""
	assert "5.7.1" not in suppression.PERMANENT


def test_the_reasons_are_closed(suppression):
	assert set(suppression.REASONS) == {
		suppression.COMPLAINT, suppression.HARD_BOUNCE, suppression.MANUAL
	}


@pytest.mark.parametrize(
	"text,expected",
	[
		("Final-Recipient: rfc822; gone@example.com\nStatus: 5.1.1", "gone@example.com"),
		("final-recipient: RFC822; <Gone@Example.com>\nstatus: 5.1.1", "Gone@Example.com"),
	],
)
def test_a_delivery_report_names_the_address_that_failed(suppression, text, expected, monkeypatch):
	seen = {}
	monkeypatch.setattr(
		suppression, "suppress",
		lambda email, reason=None, detail="": seen.update(email=email, reason=reason),
	)
	suppression.handle_bounce({"text": text, "html": ""})
	assert seen["email"] == expected
	assert seen["reason"] == suppression.HARD_BOUNCE


def test_a_soft_delivery_report_suppresses_nothing(suppression, monkeypatch):
	monkeypatch.setattr(
		suppression, "suppress",
		lambda *a, **k: pytest.fail("a temporary failure must not suppress"),
	)
	result = suppression.handle_bounce(
		{"text": "Final-Recipient: rfc822; busy@example.com\nStatus: 4.2.2"}
	)
	assert result["suppressed"] is False


def test_a_report_we_do_not_understand_suppresses_nothing(suppression, monkeypatch):
	monkeypatch.setattr(
		suppression, "suppress", lambda *a, **k: pytest.fail("guessed a suppression")
	)
	assert suppression.handle_bounce({"text": "something went wrong"})["suppressed"] is False


# --------------------------------------------------------------------------- #
# The DNS a customer publishes
# --------------------------------------------------------------------------- #

def test_the_three_records_are_the_three_that_matter(verify, monkeypatch):
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": "KEY"}
	)
	rows = verify.records("theircompany.com")
	assert [row["kind"] for row in rows] == ["SPF", "DKIM", "DMARC"]
	assert all(row["type"] == "TXT" for row in rows)


def test_each_record_goes_on_the_host_the_check_reads(verify, monkeypatch):
	"""The bug this prevents: telling somebody to publish one name and looking
	for another. It cannot be caught by hand because both halves look right."""
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": "KEY"}
	)
	rows = {row["kind"]: row for row in verify.records("theircompany.com")}
	assert rows["SPF"]["host"] == "theircompany.com"
	assert rows["DKIM"]["host"] == f"{verify.SELECTOR}._domainkey.theircompany.com"
	assert rows["DMARC"]["host"] == "_dmarc.theircompany.com"

	asked = []
	monkeypatch.setattr(verify, "_txt", lambda host: asked.append(host) or [])
	verify.check("theircompany.com")
	assert asked == [
		"theircompany.com",
		f"{verify.SELECTOR}._domainkey.theircompany.com",
		"_dmarc.theircompany.com",
	]


def test_spf_names_the_platform_and_does_not_hard_fail(verify, monkeypatch):
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": "KEY"}
	)
	spf = verify.records("x.com")[0]["value"]
	assert "include:mail.4dl.app" in spf
	# `~all` and not `-all`: we are one sender among however many a customer
	# already has, and telling the world to reject everything else is not ours
	# to say on their domain.
	assert spf.endswith("~all")


def test_dkim_is_offered_blank_rather_than_hidden(verify, monkeypatch):
	"""A screen showing two of three records because a bench setting is missing
	sends somebody hunting for a DNS problem they do not have."""
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": ""}
	)
	dkim = verify.records("x.com")[1]
	assert dkim["value"] == ""
	assert dkim["note"]


def test_verification_needs_spf_and_dkim_but_not_dmarc(verify, monkeypatch):
	"""DMARC is advice to receivers and costs us nothing to send without.
	SPF and DKIM are what make the mail ours to send."""
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": "KEY"}
	)

	def answer(host):
		if host == "x.com":
			return ["v=spf1 include:mail.4dl.app ~all"]
		if host.startswith(verify.SELECTOR):
			return ["v=DKIM1; k=rsa; p=KEY"]
		return []

	monkeypatch.setattr(verify, "_txt", answer)
	result = verify.check("x.com")
	assert result["verified"] is True
	assert result["dmarc"] is False


def test_an_spf_that_does_not_include_us_is_not_verification(verify, monkeypatch):
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": "KEY"}
	)
	monkeypatch.setattr(
		verify, "_txt",
		lambda host: ["v=spf1 include:someone-else.com ~all"] if host == "x.com" else [],
	)
	assert verify.check("x.com")["verified"] is False


def test_dns_that_will_not_answer_reads_as_unpublished(verify, monkeypatch):
	"""Indistinguishable on purpose: the only action either supports is
	"publish it and try again", and naming a resolver timeout invites somebody
	to believe the record is fine."""
	monkeypatch.setattr(
		verify, "_platform", lambda: {"mail_domain": "mail.4dl.app", "dkim_public_key": "KEY"}
	)
	monkeypatch.setattr(verify, "_txt", lambda host: [])
	result = verify.check("x.com")
	assert result == {
		"domain": "x.com", "spf": False, "dkim": False, "dmarc": False, "verified": False
	}
