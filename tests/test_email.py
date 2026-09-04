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


def test_one_folder_of_one_mailbox(mailbox, holding, monkeypatch):
	"""Scoped by the address as well as the folder name. Folder names are not
	unique across mailboxes — two people on this site can both have an
	`Applicants` — so a filter on the name alone hands one of them the other's.
	"""
	holding("me@gmail.com")
	monkeypatch.setattr(mailbox, "_accounts_for", lambda address: ["Gmail"])

	filters, or_filters = mailbox._filters("me@gmail.com::Applicants")
	assert filters[mailbox.FOLDER_FIELD] == "Applicants"
	assert filters["email_account"] == ("in", ["Gmail"])
	assert or_filters is None


def test_a_folder_of_an_address_you_do_not_hold_is_refused(mailbox, holding):
	holding("me@gmail.com")
	with pytest.raises(Exception):
		mailbox._filters("someone-else@gmail.com::Applicants")


def test_a_folder_query_never_gets_an_empty_account_list(mailbox, monkeypatch):
	"""An empty `in` matches nothing in some engines and everything in others,
	and this is the filter standing between one person and the site's mail."""
	monkeypatch.setattr(mailbox.frappe, "get_all", lambda *a, **k: [])
	assert mailbox._accounts_for("me@gmail.com") == [""]


def test_a_folder_is_not_forced_to_be_received(mailbox, holding, monkeypatch):
	"""A Sent folder holds sent mail. A folder filter that also said
	"Received" would mirror the folder and then show it empty."""
	holding("me@gmail.com")
	monkeypatch.setattr(mailbox, "_accounts_for", lambda address: ["Gmail"])
	filters, _ = mailbox._filters("me@gmail.com::Sent Items")
	assert "sent_or_received" not in filters


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
