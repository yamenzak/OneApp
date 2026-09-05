"""Addresses, suppression and the records a customer has to publish.

The parts of the mail feature that are ordinary Python and are the parts that go
wrong quietly: what a local part may be, which SMTP failures mean "never again",
and whether the DNS a customer is told to publish is the DNS we then look for.

The wiring — that an Email Account is created, that a User Email row grants
access — is Frappe's own and belongs in a runner with a database. What is here
is the reasoning around it.
"""

import types

import pytest


def code_of(thing) -> str:
	"""Source with the prose taken out.

	Several of these guards assert that a piece of code does *not* do
	something — and the docstring right above it is usually the sentence
	explaining why not, which names the very thing being searched for. A plain
	text search over the source therefore fails on correct code.
	"""
	import inspect
	import pathlib
	import re as regex

	# A package's own source is its `__init__`, which here is re-exports and
	# nothing else — so `code_of(mailbox)` would search a list of names for
	# code that lives in the modules beside it.
	if getattr(thing, "__path__", None):
		whole = "\n".join(
			p.read_text()
			for p in sorted(pathlib.Path(thing.__path__[0]).glob("*.py"))
			if p.name != "__init__.py"
		)
	else:
		whole = inspect.getsource(thing)
	source = regex.sub(r'"""(?:.|\n)*?"""', "", whole)
	return "\n".join(
		line for line in source.splitlines() if not line.strip().startswith("#")
	)



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


# --------------------------------------------------------------------------- #
# Reading: what a person is allowed to see
# --------------------------------------------------------------------------- #
#
# The one genuinely dangerous thing in the mail feature. Every list, thread and
# count is `Communication` — the site's whole correspondence, including the mail
# of people who are not this person — narrowed by a filter. There is no second
# gate behind it, so the filter is the gate.


@pytest.fixture
def mailbox():
	from oneapp.oneapp_core.email import mailbox as module

	return module


@pytest.fixture
def holding(mailbox, monkeypatch, stub_mailbox):
	"""Say which addresses the caller holds."""

	def set(*addresses):
		stub_mailbox("_held", lambda: list(addresses))

	return set


@pytest.mark.parametrize(
	"subject,expected",
	[
		("Quote for Al Reem", "quote for al reem"),
		("Re: Quote for Al Reem", "quote for al reem"),
		("RE: Quote for Al Reem", "quote for al reem"),
		("Fwd: Re: Quote for Al Reem", "quote for al reem"),
		("Re: Fwd: RE: Quote for Al Reem", "quote for al reem"),
		("Re[2]: Quote for Al Reem", "quote for al reem"),
		("  Re:   Quote for Al Reem  ", "quote for al reem"),
		("AW: Quote for Al Reem", "quote for al reem"),  # a German mail client
		("", "(no subject)"),
		("Re:", "(no subject)"),
	],
)
def test_a_conversation_is_its_subject_without_the_ceremony(mailbox, subject, expected):
	assert mailbox.normalise(subject) == expected


def test_the_conversation_keeps_its_own_name_and_its_own_case(mailbox):
	"""Rows arrive newest first, so a conversation titled from `row.subject`
	would be called "Re: …" the moment somebody answered it."""
	assert mailbox.strip_prefixes("Re: Quotation for the Al Reem tower") == (
		"Quotation for the Al Reem tower"
	)
	assert mailbox.strip_prefixes("") == ""


def test_a_subject_that_merely_starts_with_those_letters_is_not_a_reply(mailbox):
	"""`Reminder` begins with `re` and is not `Re:`. The colon is the prefix."""
	assert mailbox.normalise("Reminder: site visit") == "reminder: site visit"
	assert mailbox.normalise("Fwding the drawings") == "fwding the drawings"


def test_a_wildcard_in_a_subject_is_a_character_and_not_a_wildcard(mailbox):
	"""`50% off` is one conversation, not every conversation starting `50`."""
	assert mailbox._like("50% off") == r"50\% off"
	assert mailbox._like("first_last@x.com") == r"first\_last@x.com"
	assert mailbox._like(r"a\b") == "a\\\\b"


def test_somebody_with_no_address_gets_a_filter_nothing_matches(mailbox, holding):
	"""Not an empty filter. An empty one reads as "every Communication"."""
	holding()
	filters, or_filters = mailbox._filters("all")
	assert filters == {"name": ("=", "")}
	assert or_filters is None


def test_the_two_halves_of_the_filter_are_returned_together(mailbox, holding):
	"""The union of two addresses lives in `or_filters`, because `recipients` is
	a comma-joined string and two of them is a LIKE each. A caller that took the
	`filters` half alone would be asking for every received email on the site,
	so there is no way to take it alone."""
	holding("sales@acme.4dl.app", "ap@acme.4dl.app")
	filters, or_filters = mailbox._filters("all")
	assert "recipients" not in filters
	assert or_filters == [
		["recipients", "like", "%sales@acme.4dl.app%"],
		["recipients", "like", "%ap@acme.4dl.app%"],
	]


def test_every_query_takes_both_halves(mailbox):
	"""The guard for the bug above, read off the source rather than exercised:
	each `_filters` call unpacks the pair, and each `get_all` under it passes
	`or_filters`. A query that forgets is the leak."""
	import re as regex

	source = code_of(mailbox)
	body = source.split("def _filters", 1)[1].split("\n\n\n", 1)[1]

	lonely = regex.search(r"^\s*\w+ = _filters\(", body, regex.M)
	assert not lonely, f"a caller took only the filters half: {lonely.group().strip()}"
	assert body.count("_filters(") == body.count("or_filters = _filters(")

	# Two queries are deliberately unscoped, and both are exempted by *name*
	# rather than by shape — `unread` also plucks names and is scoped, and an
	# exemption written as "queries that pluck names" would have stopped
	# guarding it. What makes these two safe is asserted separately below.
	# Cut with `code_of` too: `body` has had its prose stripped, and raw source
	# would no longer match a word of it.
	for unscoped in (mailbox._matching, mailbox._in_thread):
		body = body.replace(code_of(unscoped), "")

	for call in regex.findall(r"frappe\.get_all\(\s*\n\s*\"Communication\".*?\n\t\)", body,
	                          regex.S):
		assert "or_filters=or_filters" in call, call


@pytest.mark.parametrize("which", ["_matching", "_in_thread"])
def test_an_unscoped_query_can_only_answer_ids(mailbox, which):
	"""Both run before the gate rather than behind it — two OR groups cannot go
	in one `get_all`, and the address scope already owns the one they need. So
	what makes them safe is that nothing but names comes out: the real query
	then filters those names by who may see them. A `fields=` here is the leak.
	"""
	import inspect

	source = inspect.getsource(getattr(mailbox, which))
	assert 'pluck="name"' in source
	assert "fields=" not in source
	assert "or [\"\"]" in source, "an empty `in` matches everything in some engines"


def test_one_address_needs_no_or_filter(mailbox, holding):
	holding("sales@acme.4dl.app")
	filters, or_filters = mailbox._filters("all")
	assert filters["recipients"] == ("like", "%sales@acme.4dl.app%")
	assert or_filters is None


@pytest.fixture
def filed(mailbox, stub_mailbox, holding):
	"""One address whose server has the four folders that mean "put away"."""

	def set(**kinds):
		holding("sales@acme.4dl.app")
		stub_mailbox(
			"_accounts",
			lambda: {
				"sales@acme.4dl.app": {
					"account": "ACC",
					"folders": list(kinds),
					"kinds": kinds,
				}
			},
		)

	return set


def test_an_inbox_does_not_hold_what_has_been_put_away(mailbox, filed):
	"""The bug this exists for: Archive filed the conversation and left it in the
	list, because the inbox view is every *received* message on an address and it
	did not care what folder the message was in. Which is worse than not having
	the button — the mail is gone from where somebody would look for it and still
	in front of them."""
	filed(**{"Archive": "archive", "Deleted Items": "trash", "Junk": "junk", "Drafts": "drafts"})

	filters, _ = mailbox._filters("all")
	# Sorted, so the query is the same query run to run and a cache of it means
	# something.
	assert filters["custom_imap_folder"] == (
		"not in",
		["Archive", "Deleted Items", "Drafts", "Junk"],
	)


def test_the_same_holds_for_one_address_as_for_all_of_them(mailbox, filed):
	filed(**{"Archive": "archive"})
	assert mailbox._filters("sales@acme.4dl.app")[0]["custom_imap_folder"] == (
		"not in",
		["Archive"],
	)


def test_an_ordinary_folder_is_not_put_away(mailbox, filed):
	"""`Applicants` is somebody's own filing and belongs in their inbox view as
	much as anything else does."""
	filed(**{"Applicants": "", "Archive": "archive"})
	assert mailbox._filters("all")[0]["custom_imap_folder"] == ("not in", ["Archive"])


def test_opening_the_archive_shows_the_archive(mailbox, filed):
	"""The exclusion is what an inbox means, not what a query means. A folder
	asked for by name is asked for."""
	filed(**{"Archive": "archive"})
	filters, _ = mailbox._filters(f"sales@acme.4dl.app{mailbox.SPLIT}Archive")
	assert filters["custom_imap_folder"] == "Archive"


def test_sent_is_not_an_inbox_and_is_not_narrowed(mailbox, filed):
	filed(**{"Archive": "archive"})
	assert "custom_imap_folder" not in mailbox._filters("sent")[0]


def test_a_mailbox_with_no_folders_gets_no_clause_at_all(mailbox, filed):
	"""A routed address has no server and so no folders. An empty `not in` is a
	condition that matches nothing in some engines, and this is one of the two
	places where that would mean "no mail at all"."""
	filed()
	assert "custom_imap_folder" not in mailbox._filters("all")[0]


def test_the_exclusion_survives_a_message_with_no_folder(mailbox):
	"""Routed mail arrives in no folder, and `NULL NOT IN (…)` is NULL — which
	is to say the whole inbox would have been empty. Frappe writes the condition
	as `IFNULL(field, '')`, and this is the assertion that says we are relying
	on that."""
	import inspect

	source = inspect.getsource(mailbox._filters)
	assert '("not in", away)' in source
	assert "IFNULL" in source or "no folder at all" in source


def test_a_folder_is_refused_unless_it_is_one_of_yours(mailbox, holding):
	holding("sales@acme.4dl.app")
	mailbox._filters("sales@acme.4dl.app")  # fine
	with pytest.raises(Exception):
		mailbox._filters("ceo@acme.4dl.app")


def test_sent_is_scoped_by_who_sent_it(mailbox, holding):
	holding("sales@acme.4dl.app", "ap@acme.4dl.app")
	filters, or_filters = mailbox._filters("sent")
	assert filters["sent_or_received"] == "Sent"
	assert filters["sender"] == ("in", ["sales@acme.4dl.app", "ap@acme.4dl.app"])
	assert or_filters is None


def test_one_folder_of_one_mailbox(mailbox, holding):
	"""Scoped by the address as well as the folder name. Folder names are not
	unique across mailboxes — two people on this site can both have an
	`Applicants` — so a filter on the name alone hands one of them the other's.
	"""
	holding("me@gmail.com")

	filters, or_filters = mailbox._filters("me@gmail.com::Applicants")
	assert filters[mailbox.FOLDER_FIELD] == "Applicants"
	assert or_filters == [
		["recipients", "like", "%me@gmail.com%"],
		["sender", "=", "me@gmail.com"],
	]


def test_a_folder_is_scoped_by_address_and_not_by_account(mailbox, holding):
	"""`email_account` is set on mail that came through an account and is not
	set on the mail our own Worker delivers — there is no account to name. A
	folder scoped on it therefore hid exactly the mail this product is built
	around: filed, and then in no folder anybody could open."""
	holding("sales@acme.4dl.app")
	filters, _ = mailbox._filters("sales@acme.4dl.app::Applicants")
	assert "email_account" not in filters


def test_a_folder_of_an_address_you_do_not_hold_is_refused(mailbox, holding):
	holding("me@gmail.com")
	with pytest.raises(Exception):
		mailbox._filters("someone-else@gmail.com::Applicants")


def test_a_folder_is_not_forced_to_be_received(mailbox, holding):
	"""A Sent folder holds sent mail. A folder filter that also said
	"Received" would mirror the folder and then show it empty."""
	holding("me@gmail.com")
	filters, _ = mailbox._filters("me@gmail.com::Applicants")
	assert "sent_or_received" not in filters


def test_an_address_has_one_outbox(mailbox, holding):
	"""A reply written here and whatever the mailbox's own Sent folder already
	held are the same outbox. The sender is what they have in common; the
	folder is not, so the filter is on the sender."""
	holding("me@gmail.com")
	filters, or_filters = mailbox._filters(f"me@gmail.com::{mailbox.SENT}")
	assert filters["sent_or_received"] == "Sent"
	assert filters["sender"] == "me@gmail.com"
	assert mailbox.FOLDER_FIELD not in filters
	assert or_filters is None


def test_the_sent_key_cannot_be_a_real_folder(mailbox):
	"""IMAP names are ordinary text and somebody may genuinely have a folder
	called `Sent` — which is exactly the one this replaces."""
	assert mailbox.SENT.startswith("__")


def test_a_preview_is_text_and_is_bounded(mailbox):
	assert mailbox._preview("<p>Hello <b>there</b></p>") == "Hello there"
	assert mailbox._preview(None) == ""
	assert len(mailbox._preview("<p>" + "x" * 500 + "</p>")) == 160


def test_you_cannot_send_as_an_address_you_do_not_hold(mailbox, holding):
	holding("sales@acme.4dl.app")
	with pytest.raises(Exception):
		mailbox.send(to="x@y.com", subject="hi", content="hi", sender="ceo@acme.4dl.app")


def test_holding_nothing_means_sending_nothing(mailbox, holding):
	holding()
	with pytest.raises(Exception):
		mailbox.send(to="x@y.com", subject="hi", content="hi")


def test_the_seen_list_is_bounded(mailbox, monkeypatch, stub_mailbox):
	"""It is a user default, which every request loads. Unbounded it becomes a
	string megabytes long that the whole session pays for."""
	stub_mailbox("_seen_set", lambda: set())
	result = mailbox.mark_read([f"m{n}" for n in range(mailbox.SEEN_LIMIT + 500)])
	assert result["seen"] == mailbox.SEEN_LIMIT
	written = mailbox.frappe.defaults.get_user_default(mailbox.SEEN_KEY, "Administrator")
	# The oldest fall off, not the newest — a recent message must not come back
	# as unread the moment somebody has a busy month.
	assert written.split(",")[-1] == f"m{mailbox.SEEN_LIMIT + 499}"


def test_read_receipts_are_stored_under_the_person_they_belong_to(mailbox):
	"""Not in the global defaults, which every session on the site loads whole."""
	import inspect

	code = code_of(mailbox)
	assert "frappe.db.get_default" not in code
	assert "frappe.db.set_default" not in code
	assert "frappe.defaults.get_user_default" in code


# --------------------------------------------------------------------------- #
# Connecting a mailbox somebody already has
# --------------------------------------------------------------------------- #

@pytest.fixture
def connect():
	from oneapp.oneapp_core.email import connect as module

	return module


@pytest.mark.parametrize(
	"email_id,server",
	[
		("someone@gmail.com", "imap.gmail.com"),
		("someone@googlemail.com", "imap.gmail.com"),
		("someone@outlook.com", "outlook.office365.com"),
		("someone@hotmail.com", "outlook.office365.com"),
		("someone@icloud.com", "imap.mail.me.com"),
	],
)
def test_a_host_we_know_is_not_a_question_we_ask(connect, email_id, server):
	guess = connect.suggest(email_id)
	assert guess["known"] is True
	assert guess["email_server"] == server


def test_a_host_we_do_not_know_gets_a_guess_that_says_it_is_one(connect):
	guess = connect.suggest("someone@mail.rua.ae")
	assert guess["known"] is False
	assert guess["email_server"] == "imap.mail.rua.ae"
	assert guess["smtp_server"] == "smtp.mail.rua.ae"
	assert "guessed" in guess["note"]


def test_every_known_host_answers_both_halves(connect):
	"""A host with an IMAP server and no SMTP server connects, syncs, and fails
	at the first reply — the worst shape a mailbox can be in."""
	for domain, known in connect.KNOWN.items():
		assert known["email_server"], domain
		assert known["smtp_server"], domain
		assert known["label"], domain


def test_a_refused_password_is_explained_as_the_thing_it_usually_is(connect):
	"""`AUTHENTICATIONFAILED` is true and useless to somebody who typed the
	right password and does not know Google stopped accepting it."""
	reason = connect._reason(
		Exception("b'[AUTHENTICATIONFAILED] Invalid credentials'"),
		connect.suggest("someone@gmail.com"),
	)
	assert "app password" in reason


def test_a_hostname_that_does_not_resolve_names_the_hostname(connect):
	guess = connect.suggest("someone@typo.example")
	reason = connect._reason(Exception("[Errno -2] Name or service not known"), guess)
	assert "imap.typo.example" in reason


def test_a_connected_mailbox_names_a_folder(connect):
	"""Frappe refuses an IMAP account with no folder row, and the row everybody
	has is added by the desk's JavaScript — which this product never runs. So an
	account made from here without it fails at insert, not at first sync."""
	import inspect

	source = inspect.getsource(connect.connect)
	assert '"imap_folder"' in source
	assert '"INBOX"' in source


def test_the_first_sync_is_bounded(connect):
	"""Nine years of somebody's mail pulled into a workspace their colleagues
	can be granted access to is a privacy incident, not a slow first sync.

	`ALL` rather than `UNSEEN` is what makes the folder mirror worth having —
	an Applicants folder somebody read years ago is empty under `UNSEEN` — and
	it is only safe because `initial_sync_count` bounds the first pass, per
	folder, off that folder's own UIDNEXT."""
	import inspect

	source = inspect.getsource(connect.connect)
	assert '"email_sync_option": "ALL"' in source
	assert '"initial_sync_count": 100' in source


# --------------------------------------------------------------------------- #
# The folders somebody already has
# --------------------------------------------------------------------------- #

@pytest.fixture
def folders():
	from oneapp.oneapp_core.email import folders as module

	return module


# Real `LIST` lines. Gmail, Outlook, a Dovecot server with a dotted hierarchy,
# and a German one — transcribed rather than invented, because the whole point
# of parsing this is that every server writes it slightly differently.
LIST_ROWS = [
	rb'(\HasNoChildren) "/" "INBOX"',
	rb'(\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"',
	rb'(\HasNoChildren \Junk) "/" "[Gmail]/Spam"',
	rb'(\Noselect \HasChildren) "/" "[Gmail]"',
	rb'(\HasNoChildren) "/" "Applicants"',
	rb'(\HasNoChildren) "." "INBOX.Clients.Rua"',
	rb'(\HasNoChildren \Sent) "/" "Gesendete Elemente"',
	rb'(\HasNoChildren) "/" Unquoted',
]


def test_a_container_is_not_a_folder(folders):
	"""`[Gmail]` holds folders and is not one — selecting it fails, so it is
	dropped here rather than discovered later as a sync error."""
	names = [one["name"] for one in folders.parse_list(LIST_ROWS)]
	assert "[Gmail]" not in names
	assert "[Gmail]/Sent Mail" in names


def test_a_name_without_quotes_is_still_a_name(folders):
	assert "Unquoted" in [one["name"] for one in folders.parse_list(LIST_ROWS)]


def test_a_hierarchy_separator_can_be_a_dot(folders):
	assert "INBOX.Clients.Rua" in [one["name"] for one in folders.parse_list(LIST_ROWS)]


def test_the_server_says_which_folder_is_sent(folders):
	"""RFC 6154, and the reason this needs no table of every language's word
	for Sent: `Gesendete Elemente` is flagged, so it is not guessed at."""
	found = {one["name"]: one["kind"] for one in folders.parse_list(LIST_ROWS)}
	assert found["[Gmail]/Sent Mail"] == "sent"
	assert found["Gesendete Elemente"] == "sent"
	assert found["[Gmail]/Spam"] == "junk"
	assert found["Applicants"] == ""


@pytest.mark.parametrize(
	"name,kind",
	[
		("Sent Items", "sent"),
		("INBOX.Sent", "sent"),
		("Deleted Items", "trash"),
		("Junk E-mail", "junk"),
		("Archive", "archive"),
		("Applicants", ""),
		("Documents", ""),
	],
)
def test_a_server_that_flags_nothing_is_guessed_at_by_name(folders, name, kind):
	assert folders.classify(name, "") == kind


def test_a_folder_named_like_a_special_one_is_still_flagged_first(folders):
	"""Flags beat names. A folder somebody called `Archive` that the server
	flags `\\Junk` is junk, whatever it says on it."""
	assert folders.classify("Archive", r"\HasNoChildren \Junk") == "junk"


def test_the_bookmarks_survive_a_refresh(folders):
	"""`uidvalidity` and `uidnext` are where the sync left off in that folder.
	Dropping them on a refresh re-downloads the mailbox."""
	rows = [
		types.SimpleNamespace(folder_name="INBOX", uidvalidity="9", uidnext="450"),
		types.SimpleNamespace(folder_name="Gone", uidvalidity="1", uidnext="2"),
	]
	account = _FakeAccount(rows)
	folders.apply(account, [{"name": "INBOX", "kind": "inbox"}, {"name": "New", "kind": ""}])

	written = {row["folder_name"]: row for row in account.imap_folder}
	assert written["INBOX"]["uidvalidity"] == "9"
	assert written["INBOX"]["uidnext"] == "450"
	# A folder somebody deleted on the server goes; a new one starts with no
	# bookmark, which is what makes its first sync the bounded backfill.
	assert "Gone" not in written
	assert written["New"]["uidvalidity"] is None


def test_every_mirrored_folder_files_into_communication(folders):
	"""Turning Applicants into Job Applicant documents is an `append_to` away
	and is a rule somebody has to choose. A mirror must not invent one."""
	account = _FakeAccount([])
	folders.apply(account, [{"name": "Applicants", "kind": ""}])
	assert account.imap_folder[0]["append_to"] == "Communication"


class _FakeAccount:
	"""Enough of an Email Account for `apply` — a child table and `append`."""

	def __init__(self, rows):
		self.imap_folder = list(rows)

	def set(self, field, value):
		setattr(self, field, value)

	def append(self, field, row):
		getattr(self, field).append(row)


def test_sent_mail_in_a_sent_folder_is_sent(folders):
	"""Frappe stores everything it pulls as Received, and refuses outright to
	import a message whose sender is the account itself — right for an inbox,
	and it empties the Sent folder."""
	mail = folders.OneSpaceInboundMail(
		"raw", object(), "12", None, "Communication", folder="Sent Items", sent=True
	)
	assert mail.is_sender_same_as_receiver() is False

	data = mail.as_dict()
	assert data["sent_or_received"] == "Sent"
	assert data[folders.FOLDER_FIELD] == "Sent Items"
	# Sent mail is not unread mail. Without this every count is wrong the
	# moment somebody connects a mailbox with a Sent folder in it.
	assert data["seen"] == 1


def test_the_guard_still_holds_in_an_inbox(folders):
	"""It exists for a reason: an inbox that imported your own copies would
	double every conversation."""
	mail = folders.OneSpaceInboundMail(
		"raw", object(), "12", None, "Communication", folder="INBOX", sent=False
	)
	assert mail.is_sender_same_as_receiver() is True
	assert mail.as_dict()["sent_or_received"] == "Received"


def test_every_message_remembers_where_it_was_filed(folders):
	mail = folders.OneSpaceInboundMail(
		"raw", object(), "12", None, "Communication", folder="Applicants"
	)
	assert mail.as_dict()[folders.FOLDER_FIELD] == "Applicants"


# --------------------------------------------------------------------------- #
# Who wrote this
# --------------------------------------------------------------------------- #

@pytest.fixture
def people():
	from oneapp.oneapp_core.email import people as module

	return module


@pytest.mark.parametrize(
	"name,expected",
	[
		("Hala Nasser", "HN"),
		("hala", "HA"),
		("Hala bint Ahmed Nasser", "HN"),
		("h.nasser@alreem.ae", "HN"),
		("accounts@alreem.ae", "AC"),
		("first_last@x.com", "FL"),
		("", "?"),
	],
)
def test_two_letters_for_a_face_we_do_not_have(people, name, expected):
	"""Most senders are not Contacts and never will be. Their initials come off
	the address, using its own separators as word boundaries — `h.nasser` is HN
	and not HN-the-first-two-characters-of-h."""
	assert people.initials(name) == expected


def test_a_sender_we_do_not_know_still_has_a_name(people, monkeypatch):
	"""A page that made a Contact for everyone who wrote in would turn an inbox
	into a directory of strangers."""
	monkeypatch.setattr(people, "_contacts", lambda addresses: {})
	found = people.profiles([("hala@client.test", "Hala Nasser")])
	assert found["hala@client.test"]["label"] == "Hala Nasser"
	assert found["hala@client.test"]["initials"] == "HN"
	assert found["hala@client.test"]["contact"] == ""


def test_a_contact_beats_the_header(people, monkeypatch):
	"""The header is whatever the sender's own client put there. A Contact is
	what this workspace decided the person is called."""
	monkeypatch.setattr(
		people, "_contacts",
		lambda addresses: {"hala@client.test": {
			"name": "CT-001", "full_name": "Hala Nasser", "image": "/files/h.png",
			"company_name": "Al Reem Consultants", "designation": "Project Manager",
			"mobile_no": "+971 50 000 0000", "phone": "",
		}},
	)
	one = people.profiles([("hala@client.test", "h.nasser")])["hala@client.test"]
	assert one["label"] == "Hala Nasser"
	assert one["company"] == "Al Reem Consultants"
	assert one["image"] == "/files/h.png"


def test_the_same_sender_is_resolved_once(people, monkeypatch):
	asked = []
	monkeypatch.setattr(
		people, "_contacts", lambda addresses: asked.append(addresses) or {}
	)
	people.profiles([("a@x.com", "A"), ("a@x.com", "A"), ("b@x.com", "B")])
	# Deduplicated before the query, not after: a page of fifty rows from one
	# busy sender must not be fifty entries in an `in` clause.
	assert asked == [["a@x.com", "a@x.com", "b@x.com"]]


def test_nothing_about_a_sender_leaves_the_site(people):
	"""Avatar services work by sending a hash of every correspondent's address
	to a third party, once per message in the list."""
	code = code_of(people).lower()
	assert "gravatar" not in code
	assert "http" not in code


# --------------------------------------------------------------------------- #
# Folders somebody makes
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
	"name,quoted",
	[
		("Applicants", '"Applicants"'),
		("Al Reem 2026", '"Al Reem 2026"'),
		('He said "no"', '"He said \\"no\\""'),
		("back\\slash", '"back\\\\slash"'),
	],
)
def test_a_folder_name_is_quoted_for_imap(folders, name, quoted):
	"""Folder names have spaces in them, which is the whole reason IMAP quotes
	them — and a quote inside one has to be escaped or the command ends early."""
	assert folders._quote(name) == quoted


def test_removing_a_folder_moves_its_mail_out_first(folders):
	"""IMAP `DELETE` removes the folder *and* everything in it, which is not
	what "remove this folder" means to anybody who has used a mail client."""
	import inspect

	source = inspect.getsource(folders.remove)
	assert "_empty(server" in source
	assert source.index("_empty(server") < source.index("server.imap.delete")


def test_the_folder_is_made_on_the_server_before_the_row(folders):
	"""A row written before a CREATE that failed is a folder in our rail that
	exists nowhere else, and the next sync skips it forever."""
	import inspect

	source = inspect.getsource(folders.create)
	assert source.index("server.imap.create") < source.index('account.append("imap_folder"')


def test_a_new_folder_is_subscribed_as_well_as_created(folders):
	"""An unsubscribed folder exists and is hidden by most clients — which is a
	folder somebody made here and cannot find in Outlook."""
	assert "subscribe" in inspect_source(folders.create)


def test_you_cannot_remove_the_inbox_or_the_sent_folder(folders, monkeypatch):
	monkeypatch.setattr(folders, "kinds", lambda name: {"INBOX": "inbox"})
	account = _FakeAccount([types.SimpleNamespace(folder_name="INBOX", uidvalidity=None,
	                                              uidnext=None)])
	account.name = "Gmail"
	with pytest.raises(Exception):
		folders.remove(account, "INBOX")


def test_a_filed_message_forgets_its_uid(folders):
	"""A UID belongs to a folder. After a MOVE the same number means a
	different message, so keeping it points the next sync at the wrong mail."""
	import inspect

	source = inspect.getsource(folders.file)
	assert 'db_set("uid", -1' in source


def test_an_address_we_route_still_gets_folders(folders):
	"""No server to make it on, and nothing to disagree with either: there is no
	Outlook showing `sales@acme.4dl.app`. Refusing to organise the mail we own
	outright would be the worse answer."""
	import inspect

	source = inspect.getsource(folders.create)
	# The IMAP half is conditional; the row is not.
	assert "if server:" in source
	assert source.rindex('account.append("imap_folder"') > source.index("if server:")


def inspect_source(fn):
	import inspect

	return inspect.getsource(fn)


def test_the_folder_module_is_not_shadowed_by_the_folder_endpoint(mailbox):
	"""`mailbox.folders()` is the rail endpoint and `folders` is the module that
	does the IMAP. Imported under its own name the function wins, Python says
	nothing, and the first call reaching for `folders.file` dies at runtime with
	"'function' object has no attribute 'file'" — which is exactly what
	happened, and only in a browser."""
	import types as typemod

	assert isinstance(mailbox.folder_ops, typemod.ModuleType)
	assert callable(mailbox.folders)
	for name in ("create", "remove", "file"):
		assert hasattr(mailbox.folder_ops, name), name


def test_filing_a_conversation_files_every_message_in_it(mailbox, holding, monkeypatch, stub_mailbox):
	"""The conversation and not the message: filing the reply and leaving the
	original in the inbox is what every mail client got complained about."""
	holding("me@gmail.com")
	monkeypatch.setattr(
		mailbox.frappe.db, "get_value", lambda *a, **k: "Gmail"
	)
	monkeypatch.setattr(mailbox.frappe, "get_doc", lambda *a, **k: types.SimpleNamespace(name="Gmail"))
	stub_mailbox("thread", lambda key, folder: [
			{"name": "C-1", "email_account": "Gmail"},
			{"name": "C-2", "email_account": "Gmail"},
			# A conversation can span two addresses. The other mailbox's half is
			# not this server's to move.
			{"name": "C-3", "email_account": "Outlook"},
		],
	)
	moved = []
	monkeypatch.setattr(
		mailbox.folder_ops, "file",
		lambda account, message, name: moved.append((message, name)),
	)

	result = mailbox.file_thread("a quote", "me@gmail.com", "Applicants")
	assert result["filed"] == 2
	assert moved == [("C-1", "Applicants"), ("C-2", "Applicants")]


# --------------------------------------------------------------------------- #
# Answering and passing on
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
	"header,expected",
	[
		("hala@x.test", ["hala@x.test"]),
		("a@x.test, b@y.test", ["a@x.test", "b@y.test"]),
		('"Nasser, Hala" <hala@x.test>', ["hala@x.test"]),
		('"Nasser, Hala" <hala@x.test>, ap@y.test', ["hala@x.test", "ap@y.test"]),
		("Hala Nasser <hala@x.test>", ["hala@x.test"]),
		("", []),
	],
)
def test_a_header_is_addresses_not_commas(mailbox, header, expected):
	"""`"Nasser, Hala" <hala@x.test>` is one address with a comma inside the
	display name, which is why this is not `value.split(",")`."""
	assert mailbox._addresses(header) == expected


def test_replying_to_all_does_not_reply_to_yourself(mailbox, holding, monkeypatch):
	"""The oldest bug in mail. Every other recipient goes on the Cc; the
	addresses this person holds do not, and neither does the sender, who is
	already on the To."""
	holding("sales@acme.4dl.app")
	monkeypatch.setattr(
		mailbox.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(
			name="C-1", subject="Re: Quote", sender="hala@client.test",
			sender_full_name="Hala Nasser", content="<p>body</p>",
			recipients="sales@acme.4dl.app, ops@client.test",
			cc="hala@client.test, boss@client.test", communication_date="2026-09-04",
		),
	)
	opening = mailbox.draft("C-1", "reply_all")
	assert opening["to"] == "hala@client.test"
	assert "sales@acme.4dl.app" not in opening["cc"]
	assert "hala@client.test" not in opening["cc"]
	assert opening["cc"] == "ops@client.test, boss@client.test"


def test_a_reply_answers_from_the_address_it_reached(mailbox, holding, monkeypatch):
	"""Answering mail that came to `sales@` from a personal address is how a
	customer finds out a shared mailbox is not shared."""
	holding("sales@acme.4dl.app", "me@acme.4dl.app")
	monkeypatch.setattr(
		mailbox.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(
			name="C-1", subject="Quote", sender="hala@client.test", sender_full_name="",
			content="", recipients="sales@acme.4dl.app", cc="",
			communication_date="2026-09-04",
		),
	)
	assert mailbox.draft("C-1", "reply")["sender"] == "sales@acme.4dl.app"


def test_a_forward_carries_the_files_and_a_reply_does_not(mailbox, holding, monkeypatch):
	"""A forwarded invoice without the invoice is why people go back to
	Outlook. A reply does not need them: the person being replied to sent them.
	"""
	holding("sales@acme.4dl.app")
	monkeypatch.setattr(
		mailbox.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(
			name="C-1", subject="Quote", sender="hala@client.test", sender_full_name="",
			content="", recipients="sales@acme.4dl.app", cc="",
			communication_date="2026-09-04",
		),
	)
	monkeypatch.setattr(
		mailbox.frappe, "get_all",
		lambda *a, **k: [
			mailbox.frappe._dict({"name": "F-1", "file_name": "quote.pdf", "file_size": 10})
		],
	)
	assert mailbox.draft("C-1", "forward")["attachments"] == [
		{"name": "F-1", "file_name": "quote.pdf", "file_size": 10}
	]
	assert mailbox.draft("C-1", "reply")["attachments"] == []


def test_a_forward_starts_with_nobody_on_it(mailbox, holding, monkeypatch):
	holding("sales@acme.4dl.app")
	monkeypatch.setattr(
		mailbox.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(
			name="C-1", subject="Quote", sender="hala@client.test", sender_full_name="",
			content="", recipients="sales@acme.4dl.app", cc="boss@client.test",
			communication_date="2026-09-04",
		),
	)
	opening = mailbox.draft("C-1", "forward")
	assert opening["to"] == ""
	assert opening["cc"] == ""
	assert opening["subject"] == "Fwd: Quote"


def test_a_subject_does_not_collect_prefixes(mailbox, holding, monkeypatch):
	"""`Re: Re: Re: Quote` is what a client that appends rather than replaces
	produces after three rounds."""
	holding("sales@acme.4dl.app")
	monkeypatch.setattr(
		mailbox.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(
			name="C-1", subject="Re: Fwd: Quote", sender="a@x.test", sender_full_name="",
			content="", recipients="sales@acme.4dl.app", cc="",
			communication_date="2026-09-04",
		),
	)
	assert mailbox.draft("C-1", "reply")["subject"] == "Re: Quote"


def test_you_cannot_draft_from_somebody_elses_message(mailbox, holding, monkeypatch):
	"""A draft is a way of reading a message — it hands back the whole body —
	so it has to be one this person could already open."""
	holding("sales@acme.4dl.app")
	monkeypatch.setattr(
		mailbox.frappe, "get_doc",
		lambda *a, **k: types.SimpleNamespace(
			name="C-1", subject="Private", sender="a@x.test", sender_full_name="",
			content="", recipients="someone-else@acme.4dl.app", cc="",
			communication_date="2026-09-04",
		),
	)
	with pytest.raises(Exception):
		mailbox.draft("C-1", "reply")


def test_an_unknown_kind_is_refused(mailbox):
	with pytest.raises(Exception):
		mailbox.draft("C-1", "delete-everything")


def test_the_quote_is_a_blockquote_and_the_name_is_escaped(mailbox):
	"""A `>` prefix on lines of HTML produces neither quoted text nor valid
	markup. And a display name is somebody else's text."""
	quoted = mailbox._quote(
		types.SimpleNamespace(
			communication_date="2026-09-04",
			sender_full_name='Hala <script>alert(1)</script>',
			sender="hala@x.test",
			content="<p>the original</p>",
		)
	)
	assert "<blockquote" in quoted
	assert "<p>the original</p>" in quoted
	assert "<script>" not in quoted
	assert "&lt;script&gt;" in quoted


def test_the_quoted_body_is_the_stored_one(mailbox):
	"""Not the copy the reader is looking at, which has had its remote images
	held back — quoting that sends somebody a reply full of empty `<img>`."""
	import inspect

	source = inspect.getsource(mailbox.draft)
	assert "_quote(original)" in source


# --------------------------------------------------------------------------- #
# Sending with something attached
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
	"sent,expected",
	[
		('["F-1", "F-2"]', ["F-1", "F-2"]),
		("F-1", ["F-1"]),
		("", []),
		([], []),
		(["F-1", "", None], ["F-1"]),
	],
)
def test_attachment_names_out_of_whatever_the_request_sent(mailbox, sent, expected):
	assert mailbox._names(sent) == expected


def test_you_cannot_attach_a_file_you_cannot_read(mailbox, monkeypatch):
	"""The names come from the browser. Without this the endpoint would attach
	any file on the site to a message going anywhere."""
	monkeypatch.setattr(mailbox.frappe, "has_permission", lambda *a, **k: False)
	with pytest.raises(Exception):
		mailbox._carry("C-1", ["F-1"])


def test_an_attachment_is_carried_by_reference(mailbox):
	"""A new File row pointing at the same `file_url`. A forward of a 40 MB
	drawing set copies a row, not the drawings."""
	import inspect

	source = inspect.getsource(mailbox._carry)
	assert '"file_url": source.file_url' in source
	assert "content" not in source.split('"doctype": "File"')[1].split("}")[0]


def test_attachments_are_on_the_message_before_it_is_sent(mailbox):
	"""`send_email` reads the File rows off the document to build the message.
	Attaching afterwards produces a sent message with nothing on it."""
	import inspect

	source = inspect.getsource(mailbox.send)
	assert source.index("_carry(doc.name") < source.index("doc.send_email()")


# --------------------------------------------------------------------------- #
# A list that does not stop at fifty
# --------------------------------------------------------------------------- #

def test_the_next_page_starts_where_the_messages_ended(mailbox, holding, monkeypatch, stub_mailbox):
	"""Messages consumed, not conversations returned. Fifty messages can be
	twelve conversations, and paging by what came back re-reads the same rows
	forever."""
	holding("me@x.test")
	rows = [
		mailbox.frappe._dict({
			"name": f"C-{n}", "subject": "One conversation", "sender": "a@x.test",
			"sender_full_name": "A", "recipients": "me@x.test",
			"communication_date": "2026-09-04", "sent_or_received": "Received",
			"seen": 0, "reference_doctype": None, "reference_name": None,
			"content": "<p>hi</p>",
		})
		for n in range(10)
	]
	monkeypatch.setattr(mailbox.frappe, "get_all", lambda *a, **k: rows)
	stub_mailbox("_seen_set", lambda: set())
	monkeypatch.setattr(mailbox.people, "profiles", lambda senders: {})

	page = mailbox.threads("all", start=0)
	assert len(page["threads"]) == 1
	assert page["next"] == 10


def test_a_search_is_names_first_and_the_gate_second(mailbox):
	"""Two OR groups cannot go in one `get_all`: the address scope is already
	an `or_filters`, and a second would replace it rather than add to it —
	which is the mistake that turns a search into everybody's mail."""
	import inspect

	source = inspect.getsource(mailbox.threads)
	assert 'filters["name"] = ("in", _matching(search))' in source
	# And the scope is still the one every other query uses.
	assert "filters, or_filters = _filters(folder)" in source


def test_a_search_matches_the_body_too(mailbox):
	import inspect

	source = inspect.getsource(mailbox._matching)
	assert '["subject", "like", like]' in source
	assert '["content", "like", like]' in source


def test_a_search_that_finds_nothing_matches_nothing(mailbox, monkeypatch):
	"""An `in` on an empty list matches nothing in some engines and everything
	in others, and this one stands in front of the whole site."""
	monkeypatch.setattr(mailbox.frappe, "get_all", lambda *a, **k: [])
	assert mailbox._matching("nothing at all") == [""]


def test_a_search_is_bounded(mailbox):
	"""A search for "the" on a busy site should not build a list of every
	message ever written."""
	import inspect

	assert "limit_page_length=SEARCH_CEILING" in inspect.getsource(mailbox._matching)


# --------------------------------------------------------------------------- #
# Acting on a conversation
# --------------------------------------------------------------------------- #

def test_deleting_is_a_move_to_trash_and_not_a_deletion(mailbox):
	"""Removing the document would take the message off the record it is filed
	against and away from everybody else who holds the address, permanently, on
	a click every mail client has taught people is reversible."""
	source = code_of(mailbox.bin)
	assert "delete_doc" not in source
	assert '"trash"' in source


def test_trash_and_archive_use_the_mailbox_own_name_for_them(mailbox):
	"""`[Gmail]/Bin`, `Deleted Items`, `Papierkorb`. The server said which
	folder plays the role — see `folders.classify` — so nothing here guesses at
	a name."""
	import inspect

	source = inspect.getsource(mailbox._into)
	assert "folder_ops.kinds(account.name)" in source
	assert "role == kind" in source


def test_a_mailbox_with_no_trash_gets_one(mailbox):
	"""A routed address has no server and so no Trash, and refusing to delete
	on the addresses we own outright would be the wrong way round."""
	import inspect

	source = inspect.getsource(mailbox._into)
	assert "folder_ops.create(account, name)" in source


def test_a_star_belongs_to_a_person(mailbox):
	"""Two people on `sales@` star different things, for the same reason they
	have different ideas of what they have read."""
	source = code_of(mailbox)
	assert "STARRED_KEY" in source
	assert "frappe.defaults.set_user_default(\n\t\tSTARRED_KEY" in source


def test_a_star_reaches_the_server_too(mailbox):
	"""So it is the same star in Outlook."""
	import inspect

	assert "folder_ops.flag(names" in inspect.getsource(mailbox.star)


def test_a_starred_list_is_bounded_like_the_seen_one(mailbox):
	import inspect

	assert "SEEN_LIMIT" in inspect.getsource(mailbox.star)


def test_flagging_groups_by_mailbox_and_folder(folders):
	"""IMAP is stateful: a STORE applies to whichever folder is selected, and
	one connection per message would be one login per star."""
	import inspect

	source = inspect.getsource(folders.flag)
	assert "by_account.setdefault" in source
	assert "select_imap_folder(folder_name)" in source


def test_a_star_that_cannot_reach_the_server_is_still_a_star(folders):
	"""The next sync corrects it. A star that threw is a button that looks
	broken."""
	import inspect

	source = inspect.getsource(folders.flag)
	assert "except Exception:" in source
	assert "frappe.log_error" in source


def test_a_conversation_is_starred_if_any_message_in_it_is(mailbox):
	"""Somebody stars the thread. Which message they had open when they did is
	not something they should have to remember."""
	import inspect

	source = inspect.getsource(mailbox.threads)
	assert 'thread["starred"] = True' in source


# --------------------------------------------------------------------------- #
# Which conversation a message belongs to
# --------------------------------------------------------------------------- #

@pytest.fixture
def threading():
	from oneapp.oneapp_core.email import threading as module

	return module


def test_a_message_that_answers_nothing_starts_a_conversation(threading):
	doc = {"subject": "Re: Quotation for the tower", "in_reply_to": None}
	assert threading.key_for(doc) == "quotation for the tower"


def test_a_reply_takes_its_parent_key_however_the_subject_drifts(threading, monkeypatch):
	"""Which is the whole point: a thread that wanders onto another topic and
	gets renamed is still the same thread."""
	monkeypatch.setattr(
		threading.frappe.db, "get_value",
		lambda *a, **k: {threading.THREAD_FIELD: "the original", "in_reply_to": None},
	)
	doc = {"subject": "Completely different now", "in_reply_to": "C-1"}
	assert threading.key_for(doc) == "the original"


def test_two_strangers_writing_invoice_are_two_conversations(threading):
	"""The subject grouping's other failure, and the commoner one. `Invoice` is
	the most-written subject line there is."""
	one = threading.key_for({"subject": "Invoice", "in_reply_to": None})
	assert one == "invoice"
	# Nothing here merges them — they are only one conversation if one answers
	# the other, which is what `in_reply_to` says and a subject cannot.


def test_a_chain_gives_up_rather_than_looping(threading, monkeypatch):
	"""`In-Reply-To` is a header the sender writes, so a cycle is something
	somebody can send us rather than something that cannot happen."""
	monkeypatch.setattr(
		threading.frappe.db, "get_value",
		lambda *a, **k: {threading.THREAD_FIELD: "", "in_reply_to": "C-1"},
	)
	# Terminates, and falls back to the subject rather than hanging.
	assert threading.key_for({"subject": "Loop", "in_reply_to": "C-1"}) == "loop"


def test_only_email_gets_a_conversation_key(threading):
	"""A Comment and a phone call are Communications too, and neither threads."""
	doc = types.SimpleNamespace(
		_values={}, get=lambda key, default=None: {"communication_medium": "Phone"}.get(key),
		set=lambda key, value: doc._values.__setitem__(key, value),
	)
	threading.on_insert(doc)
	assert doc._values == {}


# --------------------------------------------------------------------------- #
# Rules, and the out-of-office
# --------------------------------------------------------------------------- #

@pytest.fixture
def rules():
	from oneapp.oneapp_core.email import rules as module

	return module


@pytest.mark.parametrize(
	"operator,haystack,needle,hit",
	[
		("Contains", "Hala Nasser <hala@x.test>", "hala@x.test", True),
		("Contains", "somebody@y.test", "hala@x.test", False),
		("Is", " hala@x.test ", "HALA@X.TEST", True),
		("Is", "hala@x.test extra", "hala@x.test", False),
		("Starts with", "LPO 4432 for Al Reem", "lpo", True),
		("Ends with", "quote.pdf", ".PDF", True),
		# An empty needle would match everything, which is a rule that files
		# the whole mailbox somewhere.
		("Contains", "anything", "", False),
	],
)
def test_a_condition_ignores_case_and_never_matches_nothing(
	rules, operator, haystack, needle, hit
):
	assert rules._hit(operator, haystack, needle) is hit


def test_the_first_matching_rule_wins(rules):
	"""Ordered, and the first match acts. Two rules that both matched and both
	acted would be a coin toss dressed as a feature."""
	import inspect

	source = inspect.getsource(rules.matching)
	assert 'order_by="priority asc, creation asc"' in source
	assert "return rule" in source


def test_rules_run_after_the_message_is_stored(rules):
	"""A rule that threw while the message was half-written would lose the
	message, and losing mail to a filing rule is the worst trade there is."""
	from oneapp.oneapp_core.email import inbound

	source = code_of(inbound.handle_address)
	assert source.index("_communication(payload") < source.index("rules.apply_to")
	assert "except Exception:" in source


def test_a_rule_that_says_star_actually_stars(rules, monkeypatch, stub_frappe):
	"""Stored, listed, fetched — and acted on nowhere, from the day rules shipped.

	`star` was in the doctype, in the settings form's field list and in the row
	`matching()` returns, and `apply_to` handled only `into` and `mark_read`. A
	rule with Star ticked filed the message and left it unstarred, which is the
	failure nobody reports because it looks like forgetting to tick the box.
	"""
	from oneapp.oneapp_core.email import folders as folder_ops

	monkeypatch.setattr(
		rules, "matching",
		lambda doc, address: stub_frappe._dict({
			"name": "R1", "into": "", "mark_read": 0, "star": 1,
		}),
	)

	# Two people share `sales@`, which is the case the per-person star exists
	# for: a rule is the *address* saying these matter, so both get it.
	monkeypatch.setattr(
		stub_frappe, "get_all", lambda *a, **k: ["hala@x.test", "omar@x.test"]
	)

	flagged = []
	monkeypatch.setattr(
		folder_ops, "flag", lambda names, on: flagged.append((tuple(names), on))
	)

	doc = stub_frappe._dict({"name": "COMM-1"})
	doc.db_set = lambda *a, **k: None

	assert rules.apply_to(doc, "sales@x.test")["filed"] is True

	# Both holders, each under their own key.
	starred = {
		person: stub_frappe.defaults.get_user_default("oneapp_mail_starred", person)
		for person in ("hala@x.test", "omar@x.test")
	}
	assert starred == {"hala@x.test": "COMM-1", "omar@x.test": "COMM-1"}
	# And the IMAP flag, so the star is the same star in Outlook.
	assert flagged == [(("COMM-1",), True)]


def test_a_rule_only_touches_an_address_you_hold(rules, monkeypatch):
	monkeypatch.setattr(
		"oneapp.oneapp_core.email.mailbox._held", lambda: ["mine@x.test"]
	)
	assert rules._mine("MINE@x.test") == "mine@x.test"
	with pytest.raises(Exception):
		rules._mine("someone-else@x.test")


def test_an_away_message_needs_something_to_say(rules, monkeypatch):
	monkeypatch.setattr(rules, "_account_of", lambda address: None, raising=False)
	monkeypatch.setattr(
		"oneapp.oneapp_core.email.mailbox._account_of",
		lambda address: types.SimpleNamespace(db_set=lambda *a, **k: None),
	)
	with pytest.raises(Exception):
		rules.set_away("mine@x.test", enabled=1, message="   ")


def test_an_away_message_switches_itself_off(rules):
	"""The part Frappe does not have and the part that matters: one somebody
	forgot to turn off answers their mail for a month, telling everybody they
	are away when they are back."""
	import inspect

	source = inspect.getsource(rules.expire_away)
	assert '"custom_away_until": ("<", nowdate())' in source
	assert '"enable_auto_reply", 0' in source


# --------------------------------------------------------------------------- #
#
# A selection, and the way back from one.
#
# Bulk is where somebody loses a morning: a mis-shift-click takes forty
# conversations rather than four, and "Archived 40" with no way back is not an
# outcome anybody chose. So what `bulk` records on the way past is as much the
# feature as what it moves.


@pytest.fixture
def selection(mailbox, stub_mailbox):
	"""`bulk`, with everything under it replaced by a note of what was asked."""
	# By path: `selections` is the module, `bulk` is the whitelisted function it
	# exports, and the two cannot share a name — see the module's own docstring.
	import importlib

	module = importlib.import_module("oneapp.oneapp_core.email.mailbox.selections")

	log = []
	rows = {
		"one": [{"name": "C1", "custom_imap_folder": "INBOX"}],
		# Two messages, in two folders — so which one the note takes is a
		# decision this can see rather than a coincidence.
		"two": [
			{"name": "C2", "custom_imap_folder": "Applicants"},
			{"name": "C3", "custom_imap_folder": "INBOX"},
		],
		# A conversation this person cannot read comes back empty, exactly as a
		# missing one does.
		"gone": [],
	}

	stub_mailbox("thread", lambda key, folder="all": rows.get(key, []))
	for name in ("archive", "bin", "file_thread"):
		stub_mailbox(name, (lambda name: lambda *a, **k: log.append((name, a)))(name))
	stub_mailbox("mark_read", lambda names: log.append(("read", tuple(names))))
	stub_mailbox("mark_unread", lambda key, folder="all": log.append(("unread", (key,))))
	stub_mailbox("star", lambda key, folder, on: log.append(("star", (key, on))))

	# The column the note is read off, spelled out in the rows above: if it is
	# ever renamed, this is where that shows.
	assert module.FOLDER_FIELD == "custom_imap_folder"
	return module, log


@pytest.mark.parametrize(
	"action,expected",
	[
		("archive", ["archive", "archive"]),
		("bin", ["bin", "bin"]),
		("read", ["read", "read"]),
		("unread", ["unread", "unread"]),
		("star", ["star", "star"]),
		("unstar", ["star", "star"]),
	],
)
def test_a_selection_does_one_thing_to_every_conversation_in_it(selection, action, expected):
	module, log = selection
	done = module.bulk(action, ["one", "two"], address="me@x.test")

	assert [entry[0] for entry in log] == expected
	assert done["done"] == 2


def test_starring_and_unstarring_are_the_same_call_with_a_different_answer(selection):
	module, log = selection
	module.bulk("unstar", ["one"], address="me@x.test")
	assert log == [("star", ("one", 0))]


def test_a_selection_cannot_be_told_to_do_something_that_is_not_a_thing(selection):
	module, _ = selection
	with pytest.raises(Exception):
		module.bulk("shred", ["one"], address="me@x.test")


def test_the_keys_arrive_as_json_because_that_is_how_a_post_sends_a_list(selection):
	module, log = selection
	module.bulk("archive", '["one", "two"]', address="me@x.test")
	assert len(log) == 2


def test_a_conversation_that_is_not_there_is_skipped_rather_than_counted(selection):
	module, log = selection
	done = module.bulk("archive", ["one", "gone"], address="me@x.test")
	assert done["done"] == 1
	assert len(log) == 1


def test_archiving_records_where_each_conversation_was(selection):
	"""The note undo reads. Without it, Undo has nowhere to put anything."""
	module, _ = selection
	done = module.bulk("archive", ["one", "two"], address="me@x.test")

	# The newest message's folder, which is the last row: a conversation whose
	# messages sit in two folders goes back to one place, and the place it goes
	# is where the person was looking at it.
	assert done["was"] == [
		{"key": "one", "folder": "INBOX"},
		{"key": "two", "folder": "INBOX"},
	]


def test_a_flag_records_nothing_to_undo_because_pressing_it_again_is_the_undo(selection):
	module, _ = selection
	assert module.bulk("unread", ["one"], address="me@x.test")["was"] == []


def test_undo_files_every_conversation_back_where_it_was(selection):
	module, log = selection
	was = module.bulk("archive", ["one", "two"], address="me@x.test")["was"]
	log.clear()

	assert module.restore(was, address="me@x.test")["restored"] == 2
	# `everywhere` rather than the folder somebody was looking at: an archived
	# conversation is not in any inbox scope, so looking for it through one
	# found nothing and put nothing back — which is how Undo silently did not.
	assert log == [
		("file_thread", ("one", "me@x.test", "INBOX", "everywhere")),
		("file_thread", ("two", "me@x.test", "INBOX", "everywhere")),
	]


def test_undo_takes_the_note_back_as_json_too(selection):
	module, log = selection
	module.restore('[{"key": "one", "folder": "INBOX"}]', address="me@x.test")
	assert len(log) == 1


def test_a_conversation_with_no_folder_recorded_is_left_alone(selection):
	"""A routed address has no folders, so there is nowhere to put it back to —
	and inventing an INBOX it never had would file mail somewhere new under the
	word Undo."""
	module, log = selection
	assert module.restore([{"key": "one", "folder": ""}], address="me@x.test")["restored"] == 0
	assert log == []


def test_everywhere_is_every_folder_and_still_only_your_mail(mailbox, filed):
	"""The scope that moves mail rather than lists it. It drops the inbox's
	exclusion and keeps every part of the gate: this is one word away from being
	the query that hands somebody the site's whole correspondence."""
	filed(**{"Archive": "archive"})

	filters, _ = mailbox._filters(mailbox.EVERYWHERE)
	assert "custom_imap_folder" not in filters
	assert filters["recipients"] == ("like", "%sales@acme.4dl.app%")
	assert filters["sent_or_received"] == "Received"


def test_everywhere_is_not_a_folder_somebody_can_ask_for(mailbox, filed):
	"""It reads as a folder name in the URL, and a folder name is checked
	against the addresses somebody holds — so if this ever stopped being handled
	before that check it would be a refusal, not a leak."""
	filed(**{"Archive": "archive"})
	assert mailbox.EVERYWHERE not in mailbox._held()
