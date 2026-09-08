"""OneLegal — the agreements a workspace runs under, assembled from the modules.

Every other module in this app knows something the lawyer's file does not: that
OneMail hands a message to Cloudflare, that OneStorage keeps objects in R2 in a
region the customer chose, that the assistant sends a prompt to a model we
picked. A terms-of-service document written once, by hand, is a document that is
wrong the first time any of those changes and stays wrong until somebody
remembers.

So it is not written once. Each module declares the clauses it needs — in its
own `legal.py`, beside the code the clause is about — and this module assembles
them into the documents a person is actually shown. Adding a subprocessor is a
line in the module that uses it; the privacy policy and the subprocessor list
both change, and every workspace is asked to agree again.

    registry      what a module declares: clauses and subprocessors
    documents     the documents themselves — the parts we write, and the
                  audience each one binds
    assemble      declarations plus documents into rendered HTML, and the
                  version that identifies it
    gate          who has agreed to what, and who may not proceed until they do

The versioning rule is the point of the whole thing. A document's version is
`revision.hash` — a number a person bumps when the change is material, and a
hash of the assembled text that nobody bumps by hand. A change with no bump
fails `tests/test_legal.py`, which is how an accidental change to a subprocessor
list becomes a decision rather than a deployment.

Not legal advice, and it does not pretend to be: it is our own drafting of what
this product actually does, kept honest by being generated from the code that
does it. `docs/LEGAL.md` says what a person reviewing it should look at.
"""

from . import assemble, documents as documents_module, gate, registry
from .assemble import documents, render, text_of, version_of
from .gate import accept, keys_for, outstanding, record, require, standing
from .reading import catalogue, document, history
from .registry import CLAUSES, SUBPROCESSORS, clause, subprocessor

__all__ = [
    "accept",
    "catalogue",
    "clause",
    "CLAUSES",
    "document",
    "assemble",
    "documents",
    "documents_module",
    "gate",
    "registry",
    "history",
    "keys_for",
    "outstanding",
    "record",
    "render",
    "require",
    "standing",
    "subprocessor",
    "SUBPROCESSORS",
    "text_of",
    "version_of",
]
