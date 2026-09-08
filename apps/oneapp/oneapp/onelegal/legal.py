"""OneLegal's own clauses: the part of each document that is about the whole.

Every other module's `legal.py` says something about that module. This one says
what is true of the product, the company and the contract, and it is the file to
read first if you want to know what a customer is actually agreeing to.

Written by us, from what the product does, and not by a lawyer. That is a
deliberate trade and `docs/LEGAL.md` says what somebody reviewing it should
look at first.
"""

from .documents import PARTY
from .registry import clause

M = "OneLegal"


def _(document, section, key, body, order=10, heading=""):
    clause(document=document, section=section, key=key, module=M,
           body=body, order=order, heading=heading)


# --------------------------------------------------------------------------- #
# Terms of Service
# --------------------------------------------------------------------------- #

_("terms", "about", "party", f"""
    {PARTY['legal_name']} ({PARTY['short_name']}, also written {PARTY['also']})
    is {PARTY['registration']}. These terms are between {PARTY['legal_name']}
    ("we", "us") and the organisation that creates a workspace ("you", "your
    organisation"). Where a person accepts these terms, they confirm they are
    authorised to bind that organisation. You can reach us at
    {PARTY['email']}, or at {PARTY['phone']}; {PARTY['representative']} is
    responsible for legal matters.
""")

_("terms", "service", "what", f"""
    The service is {PARTY['products']}, provided over the internet as a
    subscription. A workspace is a private instance: its own database, its own
    files and its own address. Applications inside it are called spaces, and
    which ones a workspace carries is a choice you make and can change.
""", order=10)

_("terms", "service", "always-on", """
    OneDoc, OneSheet, OneCode, OneStorage, OneMail and OneCalendar are part of
    every workspace and are not separately enabled. Anything else is a space you
    turn on, and turning one on may add processing this agreement describes —
    which is why enabling a space can ask you to agree to a newer version of
    these documents.
""", order=20)

_("terms", "account", "who", """
    You decide who may sign in to your workspace and what they may do. People
    you invite are your users; you are responsible for their use of the service
    and for keeping their access current. We may refuse or remove an account
    that is being used in breach of the Acceptable Use Policy.
""", order=10)

_("terms", "account", "credentials", """
    Keep sign-in credentials secret and tell us promptly at
""" + PARTY["email"] + """ if you believe an account has been compromised. We
    are not responsible for loss caused by credentials you or your users have
    disclosed.
""", order=20)

_("terms", "content", "ownership", """
    Everything you and your users put into the workspace — documents,
    spreadsheets, files, messages, records — is yours. We claim no ownership of
    it and acquire no licence to it beyond what is needed to run the service
    for you: to store it, transmit it, back it up, index it so you can search
    it, render it so you can read it, and show it to the people you have shared
    it with.
""", order=10)

_("terms", "content", "responsibility", """
    You are responsible for what your organisation puts into the workspace,
    including having the right to put it there and to have us process it. We do
    not review your content and do not act as an editor of it.
""", order=20)

_("terms", "content", "export", """
    Your content is exportable while your workspace is live: files download as
    themselves, documents as HTML, sheets as CSV, and a full backup of the
    workspace can be taken from the settings. Do not rely on us to hold the only
    copy of anything you cannot lose.
""", order=30)

_("terms", "content", "software", """
    The software is ours, or our suppliers'. Nothing in these terms transfers it
    to you. Where a component is open source, its own licence governs it and
    those licences are published with the product — see the Open Source and
    Third-Party Notices.
""", order=40)

_("terms", "acceptable", "aup", """
    Use of the service is subject to the Acceptable Use Policy, which forms part
    of these terms.
""")

_("terms", "fees", "subscription", """
    A workspace runs on a plan. The plan's price, what it includes and the
    quotas that go with it are shown before you subscribe and in the workspace's
    billing settings. Fees are charged in advance for each billing period and
    are not refundable except where the law requires it.
""", order=10)

_("terms", "fees", "payment", """
    Payments are taken by Stripe. We do not see or hold your card details. You
    are responsible for keeping a working payment method on file and for any
    taxes due on the fees, other than taxes on our income.
""", order=20)

_("terms", "fees", "credits", """
    Some features are metered rather than included — AI in particular — and are
    paid for with credits. Credits are bought in advance, are consumed as the
    metered feature is used, and are not exchangeable for money. What a
    particular feature costs is shown before it runs and recorded afterwards in
    the workspace's own usage records.
""", order=30)

_("terms", "fees", "overage", """
    If your workspace exceeds the quotas its plan carries — storage in
    particular — we will tell you and give you a grace period, currently seven
    days, to come back within them or move to a plan that fits. After that we
    may stop accepting new data until you do.
""", order=40)

_("terms", "availability", "effort", """
    We aim to keep the service available and to keep the data in it safe. We do
    not promise a particular level of availability, and there is no service
    credit scheme. Planned maintenance is announced in the workspace where
    practicable.
""", order=10)

_("terms", "availability", "backups", """
    Workspaces are backed up daily and backups are kept for a period we
    publish, currently seven days. Backups are for our recovery from a failure
    on our side; they are not a substitute for your own export.
""", order=20)

_("terms", "availability", "support", f"""
    Support is by email to {PARTY['email']} and through the workspace. We answer
    in business hours in the United Arab Emirates and do not promise a response
    time.
""", order=30)

_("terms", "suspension", "you", """
    You may cancel at any time from the workspace's billing settings. Cancelling
    stops the next renewal; it does not refund the current period. Export what
    you need before the period ends.
""", order=10)

_("terms", "suspension", "nonpayment", """
    If a payment fails we will tell you and keep the workspace running for a
    grace period, currently seven days. After that the workspace is suspended
    and cannot be signed into, though the data is untouched, for a further
    period, currently fourteen days. After that it is moved to cold storage,
    where it is kept for a further period, currently sixty days, and can be
    restored on request. Before anything is destroyed we send a final warning,
    currently seven days ahead. The current windows are published in the
    workspace's billing settings, and we will not shorten them without notice.
""", order=20)

_("terms", "suspension", "breach", """
    We may suspend a workspace immediately, without the ladder above, where
    continuing to run it would break the law, endanger other customers or our
    infrastructure, or where the Acceptable Use Policy has been breached
    seriously. We will tell you why, and restore the workspace if the cause is
    fixed.
""", order=30)

_("terms", "suspension", "us", """
    We may stop offering the service, or a part of it, with at least sixty days'
    notice, and will refund the unused part of any period paid in advance.
""", order=40)

_("terms", "liability", "asis", """
    The service is provided as it is. To the extent the law allows, we exclude
    every implied warranty, including of merchantability, fitness for a
    particular purpose and non-infringement. We do not warrant that the service
    will be uninterrupted or free of error.
""", order=10)

_("terms", "liability", "cap", """
    To the extent the law allows, neither party is liable for indirect or
    consequential loss, for loss of profit, revenue, goodwill or anticipated
    savings, or for loss of data to the extent it could have been avoided by
    keeping your own export. Our total liability under this agreement in any
    twelve-month period is limited to the fees you paid us in that period.
""", order=20)

_("terms", "liability", "carveouts", """
    Nothing in this agreement limits liability for death or personal injury
    caused by negligence, for fraud, or for anything else that cannot lawfully
    be limited.
""", order=30)

_("terms", "changes", "how", f"""
    We may change these documents. When a change is material we will publish
    the new version and ask you to agree to it before you carry on using the
    service; you will see it the next time you sign in. Every version is kept
    and can be read from the workspace's legal settings, so you can always see
    what you agreed to and when. If you do not agree to a new version, you may
    cancel and export your data, and we will refund the unused part of the
    current period. Questions go to {PARTY['email']}.
""")

_("terms", "law", "governing", f"""
    This agreement is governed by the federal laws of the United Arab Emirates
    as applied in {PARTY['jurisdiction']}, and the courts of Abu Dhabi have
    exclusive jurisdiction over any dispute. Acceptance recorded electronically
    — a click, with the date, the version and the account that clicked it — is
    valid and admissible, as UAE law on electronic transactions provides.
""", order=10)

_("terms", "law", "entire", """
    These terms, together with the Acceptable Use Policy, the Data Processing
    Addendum, the Subprocessors list and the AI Addendum, are the whole
    agreement between us about the service. If any part is unenforceable the
    rest stands.
""", order=20)


# --------------------------------------------------------------------------- #
# Acceptable Use
# --------------------------------------------------------------------------- #

_("aup", "principle", "principle", """
    OneSpace is a workspace for doing legitimate work. This policy exists to
    keep it usable for everybody on it and to keep us on the right side of the
    law and of the suppliers we depend on. It binds your organisation and every
    person who signs in.
""")

_("aup", "prohibited", "law", """
    Do not use the service to do anything unlawful under the laws of the United
    Arab Emirates or of any country where you or the people you deal with are.
""", order=10)

_("aup", "prohibited", "harm", """
    Do not use it to harass, threaten, defame or impersonate anybody, to
    distribute malware, to attack any system, to circumvent any security
    measure, or to store or distribute material that sexually exploits
    children.
""", order=20)

_("aup", "prohibited", "infringe", """
    Do not use it to infringe somebody else's intellectual property, or to
    store material you have no right to store.
""", order=30)

_("aup", "prohibited", "capacity", """
    Do not use the service in a way that degrades it for others: no
    load-testing without asking us, no automated traffic beyond what an ordinary
    person's use would generate, no reselling capacity, no mining
    cryptocurrency.
""", order=40)

_("aup", "prohibited", "security", """
    Do not probe, scan or test the security of the service without our written
    permission. If you find a vulnerability, tell us at """ + PARTY["email"] +
  """ and give us a reasonable chance to fix it before telling anybody else.
""", order=50)

_("aup", "enforcement", "how", """
    Where we can, we will tell you and give you a chance to put it right. Where
    the breach is serious, ongoing, or exposes other customers, we may remove
    content or suspend access first and explain afterwards. We report to the
    authorities what the law requires us to report.
""")


# --------------------------------------------------------------------------- #
# Privacy
# --------------------------------------------------------------------------- #

_("privacy", "who", "roles", f"""
    There are two kinds of personal data here and it matters which is which.
    For the personal data your organisation puts *into* its workspace — a
    customer's name in a record, a colleague's address in a message — your
    organisation decides what is collected and why, and we handle it on their
    instructions. In data-protection language they are the controller and we are
    the processor; the Data Processing Addendum is the terms for that. For the
    data we need to run the service and the account — who signed in, from where,
    what was billed — {PARTY['legal_name']} is the controller and this policy is
    ours.
""")

_("privacy", "what", "account", """
    To give you an account we hold your name, your email address, the workspace
    you belong to and what you are allowed to do in it, your language and time
    zone, and any picture you choose to upload.
""", order=10)

_("privacy", "what", "usage", """
    To keep the service running and secure we hold sign-in records with the time
    and the network address, a log of errors, the requests a workspace made to
    metered features, and the quantity of storage and mail a workspace is using.
""", order=20)

_("privacy", "what", "billing", """
    To bill you we hold the plan, the invoices, and an identifier from our
    payment processor. We do not hold card numbers.
""", order=30)

_("privacy", "why", "contract", """
    Most of this is processed because it is necessary to provide the service you
    or your organisation asked for. Sign-in and error records are processed
    because we have a legitimate interest in keeping the service secure and
    working. Billing records are processed because the law requires us to keep
    them.
""", order=10)

_("privacy", "why", "nosale", """
    We do not sell personal data. We do not use your content or your usage to
    build advertising profiles, and we do not share it with anybody for their
    own purposes.
""", order=20)

_("privacy", "sharing", "who", """
    We share personal data with the suppliers who make the service work, and
    with nobody else, except where the law requires it or where you ask us to.
    Every one of those suppliers is listed in the Subprocessors document, with
    what they receive and where they hold it, and each is bound by terms no less
    protective than these.
""")

_("privacy", "where", "region", """
    Your workspace's data is held in the region chosen when it was created, and
    files in the object-storage location that goes with it. Some of our
    suppliers operate globally; where data leaves the United Arab Emirates or
    the European Economic Area, it does so under the transfer terms described in
    the Data Processing Addendum.
""")

_("privacy", "keeping", "howlong", """
    Content stays until you delete it. Deleted files sit in the workspace's bin
    and are recoverable for a limited period before they are destroyed. Version
    history is thinned over time and forgotten after ninety days. Sign-in and
    error records are kept for a rolling period and then discarded. Billing
    records are kept for as long as the law requires. When a workspace ends, the
    lifecycle in the Terms of Service applies.
""")

_("privacy", "rights", "what", f"""
    Under UAE Federal Decree-Law No. 45 of 2021 on the Protection of Personal
    Data, and under the GDPR where it applies to you, you may ask for a copy of
    your personal data, ask us to correct it, ask us to delete it, object to
    some processing, and ask us to restrict it. Write to {PARTY['email']} and we
    will answer within thirty days. If the data is in your organisation's
    workspace rather than in your account with us, we will pass the request to
    them, because it is their decision to make.
""", order=10)

_("privacy", "rights", "complain", f"""
    If you think we have got this wrong, tell us first at {PARTY['email']}. You
    may also complain to the UAE Data Office, or to the supervisory authority in
    your country if you are in the European Economic Area or the United Kingdom.
""", order=20)

_("privacy", "children", "age", """
    OneSpace is a product for work and is not directed at children. Do not
    create an account for anybody under eighteen.
""")

_("privacy", "contact", "how", f"""
    Privacy questions, requests and complaints go to {PARTY['email']}, marked
    for the attention of {PARTY['representative']}. We are in
    {PARTY['jurisdiction']}.
""")


# --------------------------------------------------------------------------- #
# Cookies
# --------------------------------------------------------------------------- #

_("cookies", "what", "kinds", """
    OneSpace stores a small amount of data on your device. Some of it is
    cookies; some of it is local storage, which works the same way for our
    purposes. This document covers both.
""")

_("cookies", "ours", "session", """
    A session cookie identifies you to your workspace after you sign in. It is
    strictly necessary — without it there is no way to know who is asking — and
    it cannot be turned off while you are signed in. It is cleared when you
    sign out.
""", order=10)

_("cookies", "ours", "preferences", """
    Local storage remembers what you chose: light or dark, which sidebar
    sections are open, the last view you used on a screen, an unsent draft.
    None of it leaves your device and none of it identifies you to us.
""", order=20)

_("cookies", "ours", "noads", """
    There are no advertising cookies, no third-party analytics and no tracking
    pixels in OneSpace. We do not use Google Analytics or anything like it.
""", order=30)

_("cookies", "choices", "how", """
    You can clear this data in your browser at any time; you will be signed out
    and your preferences will return to their defaults. Blocking the session
    cookie means you cannot sign in.
""")


# --------------------------------------------------------------------------- #
# Data Processing Addendum
# --------------------------------------------------------------------------- #

_("dpa", "scope", "roles", """
    This addendum applies where we process personal data on your behalf, and
    forms part of the Terms of Service. For that data you are the controller and
    we are the processor. Where the GDPR applies, this addendum is the Article
    28 contract between us; where the UAE Personal Data Protection Law applies,
    it is the equivalent.
""", order=10)

_("dpa", "scope", "subject", """
    The subject matter is the provision of OneSpace. The duration is the term of
    the Terms of Service. The nature and purpose is hosting, storing,
    transmitting and displaying the content your organisation puts into its
    workspace, and the features it enables. The categories of data subject and
    of personal data are whatever your organisation chooses to put in — we do
    not restrict them, and we do not inspect them.
""", order=20)

_("dpa", "instructions", "only", """
    We process personal data only on your documented instructions, which the
    Terms of Service and your use of the product's features are. If we are
    required by law to process it otherwise, we will tell you first unless the
    law forbids that.
""")

_("dpa", "confidentiality", "staff", """
    Everybody at Four Degree Labs with access to customer data is bound by
    confidentiality obligations, and access is limited to those who need it to
    run the service or to answer a support request you have raised.
""")

_("dpa", "security", "measures", """
    We keep appropriate technical and organisational measures: transport
    encryption everywhere, encryption at rest for stored objects and backups,
    per-workspace isolation with a separate database per workspace, access
    control inside the product that follows the framework's own permission
    model, credentials held as secrets and never written into a workspace,
    daily backups held in a second location, and audit records of administrative
    action.
""")

_("dpa", "subprocessing", "authorised", """
    You give general authorisation for us to use subprocessors. Every current
    one is listed in the Subprocessors document, which is part of this
    addendum, and each is engaged under terms no less protective than these. We
    remain responsible to you for what they do.
""")

_("dpa", "assistance", "requests", """
    The product gives you the means to find, export, correct and delete the
    personal data in your workspace yourself. Where you cannot, and where a data
    subject exercises a right against you, we will help you answer them, at our
    cost for anything reasonable.
""", order=10)

_("dpa", "assistance", "impact", """
    We will give you the information you reasonably need for a data protection
    impact assessment or a consultation with a supervisory authority, so far as
    it concerns our processing.
""", order=20)

_("dpa", "breach", "notify", """
    If we become aware of a personal data breach affecting your data we will
    tell you without undue delay, and in any event within seventy-two hours, and
    give you what we know: what happened, which data, how many people, what we
    are doing about it, and who to talk to.
""")

_("dpa", "transfers", "how", """
    Where personal data is transferred out of the United Arab Emirates, we rely
    on the transfer mechanisms the UAE Personal Data Protection Law provides —
    an adequate jurisdiction, or contractual safeguards. Where it is transferred
    out of the European Economic Area or the United Kingdom, we rely on the
    European Commission's Standard Contractual Clauses and the UK Addendum, and
    our subprocessors are engaged on the same basis.
""")

_("dpa", "deletion", "end", """
    When the agreement ends you can export your data, and the lifecycle in the
    Terms of Service says how long the workspace remains restorable. After that
    we delete it, including from backups as those backups expire on their normal
    schedule. We will confirm deletion in writing if you ask.
""")

_("dpa", "audit", "how", """
    We will answer reasonable questions about our processing and provide the
    information you need to show compliance. Where an audit is legally required,
    we will agree its scope and timing with you first, once in any twelve-month
    period unless a supervisory authority requires otherwise, and at your cost.
""")


# --------------------------------------------------------------------------- #
# Subprocessors
# --------------------------------------------------------------------------- #

_("subprocessors", "about", "what", """
    A subprocessor is a company we use that may handle personal data from your
    workspace. This list is generated from the product itself — each part of
    OneSpace declares the suppliers it uses, beside the code that uses them — so
    it is complete by construction rather than by somebody remembering to
    update it.
""")

_("subprocessors", "changes", "notice", f"""
    When we add a subprocessor, this document changes, its version changes, and
    you are asked to agree to it before carrying on. If you object to a new
    subprocessor on reasonable data-protection grounds, tell us at
    {PARTY['email']} within thirty days and we will either find another way or
    let you terminate the affected part of the service and refund the unused
    period.
""")


# --------------------------------------------------------------------------- #
# AI
# --------------------------------------------------------------------------- #

_("ai", "what", "assistant", """
    OneSpace includes an assistant and a number of features that use large
    language models: writing a field's value, summarising a record, answering a
    question about a screen. They are optional; a workspace can turn every one
    of them off, and they do nothing until somebody asks.
""")

_("ai", "models", "ours", """
    The models are ours to choose and we run them through our own gateway. A
    workspace cannot bring its own key or point the product at another provider,
    which is deliberate: it is the only way we can promise what happens to the
    text you send, meter what it costs and keep the audit trail complete.
""", order=10)

_("ai", "models", "where", """
    Today the catalogue is Cloudflare Workers AI, which runs open-weight models
    on Cloudflare's network, and Google's Gemini models through Google's API.
    Which model a feature uses is shown in the workspace's AI settings before
    you enable it. Adding a provider changes this document and asks you to agree
    again.
""", order=20)

_("ai", "training", "never", """
    Nothing you send to a model is used to train it. We do not train models
    ourselves, and we use the providers' APIs on terms that exclude training on
    customer input. Prompts and completions are retained only as long as needed
    to produce the answer and to keep the usage record that bills it.
""")

_("ai", "provenance", "marked", """
    Anything a model wrote is marked as such where it lands: a value written by
    the assistant is recorded with the model that wrote it and the person who
    asked, and the record shows it. A person can accept it, edit it or throw it
    away, and what they did is recorded too. Nothing is written to a record
    without somebody asking for it.
""")

_("ai", "limits", "wrong", """
    Language models get things wrong confidently. The assistant is a drafting
    tool and nothing it produces is advice — legal, financial, medical or
    otherwise. Check what it writes before you rely on it, and do not use it to
    make a decision about a person that has a legal or similarly significant
    effect on them.
""")


# --------------------------------------------------------------------------- #
# Notices
# --------------------------------------------------------------------------- #

_("licences", "ours", "agpl", """
    OneSpace is released under the GNU Affero General Public License, version 3.
    You may read its source, and if you run a modified version as a network
    service you must offer that modified source to its users on the same terms.
""")

_("licences", "theirs", "frappe", """
    The product is built on the Frappe Framework and parts of ERPNext, Frappe
    CRM, Frappe Drive, Frappe Sheets and Frappe Writer, all © Frappe
    Technologies Pvt. Ltd. and contributors and all under the GNU Affero General
    Public License, version 3. Where we have taken code from them, the file says
    so at the top and keeps their notice.
""", order=10)

_("licences", "theirs", "ui", """
    The interface uses frappe-ui, Tailwind CSS, Vue and TipTap under the MIT
    licence, and Lucide icons under the ISC licence.
""", order=20)
