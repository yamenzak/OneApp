"""The documents themselves: who we are, what each one is for, and our half of
the text.

The other half comes from the modules — `registry.py` — and is slotted into the
sections named here. What is in this file is the part that is true of the
product as a whole and would still be true if every module were deleted: who
the contract is with, what the service is, what we promise, what we do not, and
which law decides an argument.

**Revisions.** Each document carries a `revision`. Bump it when the change is
material — a new subprocessor, a changed retention period, anything that alters
what somebody agreed to. Do not bump it for a typo. `tests/test_legal.py`
carries the hash of every document's assembled text and fails when the text
moves without a bump, so the choice is always deliberate: either say "this is
material, everyone re-agrees" or "this is a typo, record the new hash".

**Audience.** Two, and the split is the reason this product asks twice.

* `customer` — the organisation. Accepted by the person who creates the
  workspace, because they are the one entering into the contract, and it binds
  the organisation and everyone in it.
* `user` — the individual. Accepted by every person who signs in, because a
  privacy notice describes the handling of *their* personal data and an
  employer cannot consent to that on their behalf.

The acceptable-use policy is in both: the organisation promises it, and each
person acknowledges it.
"""

#: Us. One place, because it appears in eight documents and an address that is
#: right in seven of them is worse than one that is wrong in all eight.
PARTY = {
    "legal_name": "Four Degree Labs",
    "short_name": "4° Labs",
    "also": "4DL",
    "jurisdiction": "the Emirate of Abu Dhabi, United Arab Emirates",
    "registration": "a company established on the UAE mainland in Abu Dhabi",
    "email": "legal@fourdegreelabs.com",
    "representative": "Yamen Zakhour",
    "phone": "+971 56 331 5633",
    "products": "OneSpace and the applications within it — OneDoc, OneSheet, "
                "OneCode, OneStorage, OneMail and OneCalendar — together with "
                "OneAdmin, the operator console",
}

#: Where a document's clauses go. Each is `(id, heading)`; modules declare into
#: these ids and nowhere else, so a typo in a module is an error rather than a
#: paragraph that silently never appears.
SECTIONS = {
    "terms": [
        ("about", "Who we are"),
        ("service", "What the service is"),
        ("account", "Your account and your workspace"),
        ("content", "Your content"),
        ("modules", "The applications in your workspace"),
        ("acceptable", "Acceptable use"),
        ("fees", "Fees, credits and payment"),
        ("availability", "Availability and support"),
        ("suspension", "Suspension and termination"),
        ("liability", "Warranties and liability"),
        ("changes", "Changes to these terms"),
        ("law", "Governing law"),
    ],
    "aup": [
        ("principle", "The principle"),
        ("prohibited", "What you may not do"),
        ("modules", "Rules for particular applications"),
        ("enforcement", "How we enforce this"),
    ],
    "privacy": [
        ("who", "Who is responsible"),
        ("what", "What we collect"),
        ("why", "Why we process it"),
        ("modules", "What each application processes"),
        ("sharing", "Who else sees it"),
        ("where", "Where it is kept"),
        ("keeping", "How long we keep it"),
        ("rights", "Your rights"),
        ("children", "Children"),
        ("contact", "Contacting us"),
    ],
    "cookies": [
        ("what", "What we store on your device"),
        ("ours", "What we use"),
        ("modules", "What particular applications store"),
        ("choices", "Your choices"),
    ],
    "dpa": [
        ("scope", "Scope and roles"),
        ("instructions", "Our instructions"),
        ("confidentiality", "Confidentiality"),
        ("security", "Security"),
        ("subprocessing", "Subprocessors"),
        ("assistance", "Assistance to you"),
        ("breach", "Personal data breaches"),
        ("transfers", "International transfers"),
        ("deletion", "Return and deletion"),
        ("audit", "Audits"),
        ("modules", "Processing by application"),
    ],
    "subprocessors": [
        ("about", "About this list"),
        ("list", "The list"),
        ("changes", "Changes to the list"),
    ],
    "ai": [
        ("what", "What the assistant is"),
        ("models", "Which models run"),
        ("training", "Training"),
        ("provenance", "Marking what a model wrote"),
        ("modules", "AI in particular applications"),
        ("limits", "What it will get wrong"),
    ],
    "licences": [
        ("ours", "Our source"),
        ("theirs", "What we build on"),
        ("modules", "Notices from particular applications"),
    ],
}

#: The catalogue. `needs` is who must agree before using the product; a document
#: with no audience is published and not agreed to.
DOCUMENTS = {
    "terms": {
        "title": "Terms of Service",
        "audience": "customer",
        "revision": 2,
        "summary": "The agreement between your organisation and Four Degree "
                   "Labs for the use of OneSpace.",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "audience": "both",
        "revision": 1,
        "summary": "What OneSpace may not be used for. It binds your "
                   "organisation and everybody who signs in.",
    },
    "privacy": {
        "title": "Privacy Policy",
        "audience": "user",
        "revision": 4,
        "summary": "What we do with personal data — yours, and the personal "
                   "data your organisation puts into the product.",
    },
    "cookies": {
        "title": "Cookie Policy",
        "audience": "user",
        "revision": 1,
        "summary": "What OneSpace stores on your device and why.",
    },
    "dpa": {
        "title": "Data Processing Addendum",
        "audience": "customer",
        "revision": 1,
        "summary": "How we handle personal data your organisation is "
                   "responsible for. Part of the Terms of Service.",
    },
    "subprocessors": {
        "title": "Subprocessors",
        "audience": "customer",
        "revision": 4,
        "summary": "Every third party that receives customer data, what for, "
                   "and where it sits.",
    },
    "ai": {
        "title": "AI Addendum",
        "audience": "customer",
        "revision": 1,
        "summary": "How the assistant works, which models run, and what "
                   "happens to what you type into it.",
    },
    "licences": {
        "title": "Open Source and Third-Party Notices",
        "audience": None,
        "revision": 1,
        "summary": "The software OneSpace is built from, and the licences it "
                   "carries.",
    },
}
