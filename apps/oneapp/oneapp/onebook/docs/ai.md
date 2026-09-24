# AI

**OneAI does nothing in this space yet, and a tenant configures nothing.**

There is no `ai.py`, no tool registered with `oneai`, and no per-action setting
in the AI config manager that names OneBook. What a reader gets here is what
every space gets from the engine: the assistant can open a screen, narrow a
list and read a record through the same endpoints a person does, checked by the
same permissions. Nothing is trained on the ledger and nothing is suggested
about it.

That is deliberate for one stage and should not survive many. The two things
worth building, in the order they are worth building:

**Reading a bill.** A purchase invoice arrives as a PDF in an inbox and is
retyped by a person — supplier, date, number, net, tax, total. It is the single
most mechanical job in this space, the source document is already a `File`
because OneCloud put it there, and every field it fills is one somebody can
check at a glance before submitting. Mail, which is OneDesk's `one_mail` now,
is the lane it would arrive down.

**Suggesting the account.** Which expense account a bill belongs in is a
judgement made the same way four hundred times, and the evidence — every
previous bill from that supplier and what it was coded to — is in the ledger
this space already draws. A suggestion with the three previous codings beside it
is useful; a silent auto-coding is a set of books nobody can explain.

Both are suggestions a person accepts, never a posting. The rule this space
would keep if it had an AI lane at all is the one `docs/CLEANUP.md` §7 states
for the whole product: OneAI proposes and a seat decides. A document that posts
itself is one nobody reviewed.
