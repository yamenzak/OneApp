# AI

**OneLegal declares no `@ai_feature`, and this is one of the two modules where
that is a rule rather than an absence.**

Nothing in this module is generated, summarised or drafted by a model. The
documents are assembled from clauses that people wrote, the version is a hash
of that text, and the acceptance is a fact. A model anywhere in that chain
would mean a customer agreeing to text nobody wrote and nobody can reproduce.

## What OneAI does have here

**The AI Addendum is one of the eight documents** — `documents.DOCUMENTS["ai"]`
— and its content comes from the product-level text plus `oneai`'s own clauses:
which models run, what happens to what you type into the assistant, where a
prompt goes. It is a document *about* AI, assembled the way every other
document is.

That is the seam worth knowing: when OneAI gains a provider, the line that says
so goes in `oneai/legal.py`, the hash changes, `tests/test_legal.py` fails, and
somebody has to decide whether it is material enough to bump `revision`. The
test is what makes "we told customers" a step somebody takes rather than a step
somebody meant to.

## What a tenant configures

Nothing. There is no dial here and there should not be: a workspace cannot
switch off the clause describing what happens to its data.
