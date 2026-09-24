# Integrations

## Every module in this app

That is the integration, and the direction is the design. **Each module
declares its own clauses, in its own `legal.py`, and this one assembles them.**

    onecode/legal.py      "OneCode is an editor. It does not run your code."
    onestorage/legal.py   R2, the region the customer chose, retention
    onecalendar/legal.py  a negative: nothing syncs to Google or Exchange
    onedoc, onesheet, onemobility, onehr, onecrm, onetask, onespace…

`registry.clause` is the one seam and it takes a document, a section, a key, a
module and a body. Nothing else crosses: this module imports no other module,
and the modules import nothing from here except `clause`.

That inversion is what makes the documents true. A module changing what it does
changes its own clause in its own commit; a lawyer's file written once is wrong
the first time anything moves and stays wrong until somebody remembers.

## Frappe

`User` and the session, for who is being asked. `Legal Acceptance` records the
request's address and agent from the framework's own request object. Nothing
else — this module writes no override and hooks no document event.

## ERPNext and HRMS

Nothing.

## The engine (`onespace`)

**The gate runs in front of everything.** `gate.outstanding` is what the shell
asks on boot, and a workspace or a person with something outstanding is shown
it before the product. `onespace/legal.py` carries the platform's own clauses —
what the *platform* adds, as opposed to what a module does.

## The control plane

**The operator's side is separate and stays separate.** A tenant site assembles
and stores its own versions; the control plane knows about acceptance as a fact
about a tenant, not as a text to serve. `docs/LEGAL.md` is the argument.

## OneAI

The AI Addendum is a document like any other, and its content comes from
`oneai`'s clauses plus the product-level text in `documents.py`. See `ai.md`.

## Who reads this module

`gate.outstanding` and `gate.accept` from the shell; `reading.*` from the
documents page and from the marketing site. Nothing imports `assemble` or
`registry` except the modules registering into it.
