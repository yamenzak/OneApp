# Legal

Every other document in this directory describes something the product does.
This one describes something the product *says* — the agreements a workspace
runs under — and the reason it is a system rather than a page.

> **This is our own drafting, not a lawyer's.** It is written from what the
> product actually does, and it is kept honest by being generated from the code
> that does it. If you take one thing to a lawyer, take
> `apps/oneapp/oneapp/onelegal/legal.py` and the assembled Terms of Service; the
> machinery around them is engineering and needs no advice.

---

## The problem this solves

A terms-of-service document is written once, by somebody who understood the
product on the day they wrote it. Then OneMail starts handing messages to
Cloudflare, OneStorage puts files in a region the customer chose, the assistant
sends a prompt to a model we picked — and the document is wrong, and stays wrong
until somebody remembers it exists.

So it is not written once. **Each module declares the clauses that follow from
what it does, in its own `legal.py`, beside the code the clause is about.**
OneLegal assembles those into the documents a person is shown. Adding a
subprocessor is a line in the module that uses it; the privacy policy and the
subprocessor list both change, and every workspace is asked to agree again.

---

## The pieces

| | |
|---|---|
| `onelegal/registry.py` | what a module declares: `clause()` and `subprocessor()` |
| `onelegal/documents.py` | the catalogue: who we are, what each document is for, its sections and its revision |
| `onelegal/legal.py` | our own half of the text — the part true of the product as a whole |
| `<module>/legal.py` | that module's clauses and suppliers |
| `onelegal/assemble.py` | declarations plus documents into HTML, and the version |
| `onelegal/gate.py` | who has agreed to what, and who may not proceed |
| `onelegal/reading.py` | what the browser asks for |
| `Legal Document Version` | the exact text of every version anybody agreed to |
| `Legal Acceptance` | who agreed, to which version, when, from where |

A clause names the document and the section it belongs in. The sections are
listed in `documents.py`, and a clause aimed at a section that does not exist is
an error rather than a paragraph that silently never appears.

---

## Versions, and the one guard that matters

A version is **`revision.hash`**.

* `revision` is a number in `documents.py`. A person bumps it when a change is
  material. Bumping it is what makes every workspace agree again.
* `hash` is eight hex characters of a SHA-256 over the assembled **plain text**.
  Nobody types it. It changes the moment any clause anywhere changes.

The hash is taken over the text and not the HTML on purpose: changing a heading
level should not invalidate every acceptance in the fleet. What is agreed to is
the words.

`tests/test_legal.py` carries the current hash of all eight documents. Change a
clause and the suite fails, with two ways out and no third:

* **material** — bump `revision` in `documents.py`, and every workspace is
  asked again the next time somebody signs in;
* **a typo** — record the new hash in the test.

That is the whole design. An accidental change to a subprocessor list becomes a
decision rather than a deployment.

---

## Who agrees, and why it is asked twice

**The workspace owner accepts the contract.** Terms of Service, the Data
Processing Addendum, the Subprocessors list and the AI Addendum are an agreement
with the *organisation*. The person who creates the workspace is the one
entering into it, and their acceptance binds everybody in it. One acceptance
covers the workspace.

**Every person accepts the notices.** The Privacy Policy and the Cookie Policy
describe the handling of *their* personal data. An employer cannot consent to
that on their behalf — that is not a nicety, it is what makes the consent worth
anything — so each person who signs in accepts them for themselves.

**The Acceptable Use Policy is both.** The organisation promises it; each person
acknowledges it. It is the one document that describes what an *individual* may
not do.

An invited user who signs in to a workspace whose own contract is outstanding is
told whose signature is missing, rather than shown a button that would refuse
them.

### Where it is enforced

`LegalGate.vue` asks once when the shell boots and puts up a dialog that cannot
be dismissed. That is the surface. The two places where carrying on would mean
carrying on *under* an agreement nobody made call `gate.require()` on the
server: creating a workspace, and enabling a space. Not every request — a check
on every read is a check on every read.

---

## The documents

| Key | Title | Who agrees |
|---|---|---|
| `terms` | Terms of Service | the organisation |
| `aup` | Acceptable Use Policy | both |
| `privacy` | Privacy Policy | each person |
| `cookies` | Cookie Policy | each person |
| `dpa` | Data Processing Addendum | the organisation |
| `subprocessors` | Subprocessors | the organisation |
| `ai` | AI Addendum | the organisation |
| `licences` | Open Source and Third-Party Notices | published, not agreed to |

## The party

Four Degree Labs (4° Labs, 4DL), a company established on the UAE mainland in
Abu Dhabi. Legal contact `legal@fourdegreelabs.com`, Yamen Zakhour,
+971 56 331 5633. Governing law is the federal law of the UAE as applied in Abu
Dhabi, and the courts of Abu Dhabi have exclusive jurisdiction. One place —
`documents.PARTY` — because an address that is right in seven documents and
wrong in the eighth is worse than one that is wrong in all of them.

## The subprocessors, and why the list is complete

Generated. Cloudflare (R2, Email Routing and Sending, Workers AI), Stripe
(payments), Frappe Technologies (the managed platform), Hetzner (the machines
underneath it in Europe) and Google (the Gemini models) are in the list because
the modules that use them say so. A supplier used by a module that does not
declare it is a bug the same way a missing permission check is a bug — and
`test_legal.py` is where that is caught, because a new `subprocessor()` call
changes the document hash.

One company is one row with several uses. What a company does varies by use and
so does where it does it, so `where` belongs to the use; the safeguard is the
contract we have with the company, so that belongs to the company.

## What is deliberately not here

**No cookie banner.** There is nothing to consent to: a session cookie is
strictly necessary and everything else is local storage that never leaves the
device. A banner asking permission for something that needs none teaches people
to click through banners.

**No consent management platform, no analytics, no advertising identifiers.**

**No per-space legal text yet.** Enabling a space can change a document — it
adds module clauses and sometimes a subprocessor — and that is handled by the
version bump. A space that needs its *own* agreement, separate from the
workspace's, is a thing this design can carry and does not yet.
