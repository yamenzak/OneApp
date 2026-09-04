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
def holding(mailbox, monkeypatch):
	"""Say which addresses the caller holds."""

	def set(*addresses):
		monkeypatch.setattr(mailbox, "_held", lambda: list(addresses))

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
	import inspect
	import re as regex

	source = inspect.getsource(mailbox)
	body = source.split("def _filters", 1)[1].split("\n\n\n", 1)[1]

	lonely = regex.search(r"^\s*\w+ = _filters\(", body, regex.M)
	assert not lonely, f"a caller took only the filters half: {lonely.group().strip()}"
	assert body.count("_filters(") == body.count("or_filters = _filters(")

	for call in regex.findall(r"frappe\.get_all\(\s*\n\s*\"Communication\".*?\n\t\)", body,
	                          regex.S):
		assert "or_filters=or_filters" in call, call


def test_one_address_needs_no_or_filter(mailbox, holding):
	holding("sales@acme.4dl.app")
	filters, or_filters = mailbox._filters("all")
	assert filters["recipients"] == ("like", "%sales@acme.4dl.app%")
	assert or_filters is None


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


def test_the_seen_list_is_bounded(mailbox, monkeypatch):
	"""It is a user default, which every request loads. Unbounded it becomes a
	string megabytes long that the whole session pays for."""
	monkeypatch.setattr(mailbox, "_seen_set", lambda: set())
	result = mailbox.mark_read([f"m{n}" for n in range(mailbox.SEEN_LIMIT + 500)])
	assert result["seen"] == mailbox.SEEN_LIMIT
	written = mailbox.frappe.defaults.get_user_default(mailbox.SEEN_KEY, "Administrator")
	# The oldest fall off, not the newest — a recent message must not come back
	# as unread the moment somebody has a busy month.
	assert written.split(",")[-1] == f"m{mailbox.SEEN_LIMIT + 499}"


def test_read_receipts_are_stored_under_the_person_they_belong_to(mailbox):
	"""Not in the global defaults, which every session on the site loads whole."""
	import inspect

	code = "\n".join(
		line for line in inspect.getsource(mailbox).splitlines()
		if not line.strip().startswith("#")
	)
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
	import inspect
	import re as regex

	source = inspect.getsource(people)
	# Prose out, code only — the docstrings here *name* the thing they refuse
	# to do, which is the point of them and would fail a plain text search.
	code = regex.sub(r'"""(?:.|\n)*?"""', "", source)
	code = "\n".join(
		line for line in code.splitlines() if not line.strip().startswith("#")
	).lower()
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


def test_filing_a_conversation_files_every_message_in_it(mailbox, holding, monkeypatch):
	"""The conversation and not the message: filing the reply and leaving the
	original in the inbox is what every mail client got complained about."""
	holding("me@gmail.com")
	monkeypatch.setattr(
		mailbox.frappe.db, "get_value", lambda *a, **k: "Gmail"
	)
	monkeypatch.setattr(mailbox.frappe, "get_doc", lambda *a, **k: types.SimpleNamespace(name="Gmail"))
	monkeypatch.setattr(
		mailbox, "thread",
		lambda key, folder: [
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
