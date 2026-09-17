# Collections

## Owned

| Doctype | What it is |
| --- | --- |
| `Legal Document Version` | The assembled text of one document at one version, frozen. `document`, `title`, `version`, `revision`, `audience`, `html`, `text`. Written when a version is first needed and never edited — somebody who agreed in March has to be able to read what they agreed to. |
| `Legal Acceptance` | One person or one workspace agreeing to one version. `document`, `version`, `stored_version` (the link to the frozen text), `party`, `user`, `accepted_on`, `address`, `agent`. |

The address and the agent are on the acceptance because an acceptance is
evidence. Without them the row says somebody agreed and cannot say who from
where, which is the half of it that matters in an argument.

## The version, which is the whole point

A version is `revision.hash`:

* **`revision`** is a number in `documents.py` that a person bumps when a
  change is material — a new subprocessor, a changed retention period, anything
  that alters what somebody agreed to. Bumping it is what makes every workspace
  agree again.
* **`hash`** is the first eight hex characters of a SHA-256 over the assembled
  text. Nobody types it. It changes the moment any clause anywhere changes.

That pair is what lets `tests/test_legal.py` tell a typo from a new
subprocessor and insist somebody says which. A document whose text drifted
without a bump fails the suite.

## The eight documents

`documents.DOCUMENTS`, each with a title, an audience and a revision:

| Key | Title | Audience |
| --- | --- | --- |
| `terms` | Terms of Service | customer |
| `aup` | Acceptable Use Policy | both |
| `privacy` | Privacy Policy | user |
| `cookies` | Cookie Policy | user |
| `dpa` | Data Processing Addendum | customer |
| `subprocessors` | Subprocessors | customer |
| `ai` | AI Addendum | customer |
| `licences` | Open Source and Third-Party Notices | — |

**Audience is what decides who is asked**, and it is a real distinction rather
than a label: `customer` binds the organisation and is accepted once by
whoever created the workspace; `user` is about a person's own data and cannot
be agreed to on their behalf by an employer.

## Not a doctype: the clauses

A clause is a `registry.clause(...)` call in a module's own `legal.py`, held in
memory and assembled on read. There is no `Legal Clause` row, deliberately —
a clause is code that ships with the code it describes, so a subprocessor
arrives in the same commit as the call to it.
