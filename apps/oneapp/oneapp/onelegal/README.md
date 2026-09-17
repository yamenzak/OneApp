# OneLegal

The agreements a workspace runs under, assembled from the modules that make
them true.

Every other module in this app knows something the lawyer's file does not: that
OneMail hands a message to Cloudflare, that OneCloud keeps objects in R2 in a
region the customer chose, that the assistant sends a prompt to a model we
picked. A terms-of-service document written once, by hand, is a document that
is wrong the first time any of those changes and stays wrong until somebody
remembers.

So it is not written once. Each module declares the clauses it needs — in its
own `legal.py`, beside the code the clause is about — and this module assembles
them into the documents a person is shown. Adding a subprocessor is a line in
the module that uses it; the privacy policy and the subprocessor list both
change, and every workspace is asked to agree again.

    registry      what a module declares: clauses and subprocessors
    documents     the documents themselves — the parts we write, and the
                  audience each one binds
    assemble      declarations plus documents into rendered HTML, and the
                  version that identifies it
    gate          who has agreed to what, and who may not proceed until they do
    reading       the read side, open to anybody signed in

`docs/LEGAL.md` is the argument and what a person reviewing this should look at
first. This file is about the decisions in it that cost something.

## The decisions that cost something

**A version is `revision.hash`, and the hash is not typed.** `revision` is a
number a person bumps when a change is material; `hash` is a SHA-256 over the
assembled text and changes the moment any clause anywhere does.
`tests/test_legal.py` carries the hash of every document and fails when the
text has moved without a bump. That is the whole mechanism: an accidental
change to a subprocessor list becomes a decision somebody takes rather than a
deployment nobody noticed.

The cost is real — a typo fails the suite and somebody has to look at the diff
and say "not material". That is the intended cost. The alternative is a hash
nobody reads, which is the same as no hash.

**Two parties, and one of them cannot be spoken for.** Terms, the DPA, the
Subprocessor list and the AI Addendum are a contract with the *organisation*,
accepted once by whoever created the workspace. Privacy and Cookies describe
the handling of a *person's* own data, and an employer cannot agree to that on
their behalf — so every person accepts those for themselves, and again
whenever the version changes. The Acceptable Use Policy is `both`, and is
asked twice, because it is a promise the organisation makes and a rule each
person is bound by.

Rejected: one acceptance per workspace covering everything, which is simpler,
is what most products do, and is wrong about the half that is personal data.

**A stored version is frozen, and nothing edits it.** `Legal Document Version`
is written when a version is first needed and never again. Somebody who agreed
in March has to be able to read what they agreed to, not what it says now — so
`reading.history` fetches by version, and an editable record of an agreement
would not be a record of one.

**An acceptance carries the address and the agent.** Without them the row says
somebody agreed and cannot say who from where, which is exactly the half that
matters in an argument.

**Written by us, from what the product does, and not by a lawyer.** A
deliberate trade, stated plainly rather than implied. What it buys is documents
that are true; what it costs is that nobody has checked them against a
jurisdiction. `docs/LEGAL.md` says what a reviewer should look at first.

## What is not built

1. **Telling a workspace owner before a revision lands.** An organisation with
   a review process gets no warning: the gate raises on the next request and
   that is the first they hear of it. It is a mail from the control plane about
   a tenant, not a rule on a tenant site, which is why it is not an alert here.
2. **A jurisdiction per customer.** One governing law, named in `documents.py`,
   for everybody. A customer who needs their own is a conversation and not a
   field.
3. **Countersigning.** An acceptance is a click. A customer who wants a signed
   copy of the Terms gets the text and does it outside the product.
