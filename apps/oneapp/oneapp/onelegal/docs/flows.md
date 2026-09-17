# Flows

## Declaring a clause

A module says what is true about itself, in its own `legal.py`, beside the code
the clause is about:

    clause(document="terms", section="modules", key="code-execution",
           module="OneCode", body="...")

`registry.py` holds them. Nothing is written to the database. The whole point
is that adding a subprocessor is a line in the module that uses it, and the
privacy policy and the subprocessor list say so on the next read.

The alternative — a terms-of-service document written once, by hand — is a
document that is wrong the first time OneMail changes mail providers and stays
wrong until somebody remembers.

## Assembling a document — `assemble.py`

1. `documents.py` supplies the part that is true of the product as a whole:
   who the contract is with, what the service is, what we promise, what we do
   not, and which law decides an argument. It would still be true if every
   module were deleted.
2. The modules' clauses are slotted into the sections `documents.py` names.
3. The text is rendered and hashed. The version is `revision.hash`.
4. If no `Legal Document Version` exists for that version, one is written and
   frozen.

## Being asked — `gate.py`

`outstanding()` answers what this reader still owes, and it is two questions
because there are two parties:

* **The workspace.** Terms, DPA, Subprocessors and the AI Addendum are a
  contract with the organisation. The person who creates the workspace accepts
  them and that binds everybody in it. One acceptance covers the workspace.
* **The person.** Privacy and Cookies describe the handling of *their* personal
  data. Every person who signs in accepts those for themselves, once, and again
  whenever the version changes.

The Acceptable Use Policy has audience `both`, so it is asked twice — of the
organisation as a promise, and of each person as a rule they are bound by.

`accept(document, version)` writes a `Legal Acceptance` with the address and
the agent.

## Reading — `reading.py`

Read-only and open to anybody signed in, which follows from what a gate is for:
a person being asked to agree to something has to be able to read it first.
`catalogue()` lists, `document(key)` renders the current version, and
`history(key)` fetches a stored version by name — because somebody who agreed
in March has to be able to read what they agreed to, not what it says now.

## When a version changes

Bump `revision` in `documents.py`. Every workspace and every person whose last
acceptance names an older version is asked again, on their next request,
through the same gate.
