# Integrations

## Frappe

**`File`, and nothing else.** Every code file and every project folder is a
core `File` row. OneCode adds no override of its own — `onestorage/file.py`
already carries the one that moves an uploaded file to R2 — so a `.js` in the
Drive takes the same path an attachment does.

**`Web Page`**, not yet. It is where a served project will land, and its
`context_script` is the field this module exists to avoid handing to a tenant:
Python that runs with the framework in scope before the template renders.
`manifest.context` is the answer — a declaration the server reads, not a script
the server runs.

## ERPNext and HRMS

Nothing. A code file has no accounting or personnel meaning.

## OneCloud (`onestorage`)

The whole of the way in. There is no OneCode route: a file is opened from the
Drive, and `Code` is one of its places. That place is the exception in
`onestorage`'s `PLACE_FOR` — every other place is a *kind* somebody declares by
making a file there, and this one is derived from filenames, because a person
looking for what they are building is looking for a folder.

Sharing, versions, the bin, quota and the WebDAV mount all belong to OneCloud
and OneCode inherits every one of them rather than restating any.

## OneWriter (`onedoc`)

They share `Doc.vue` and the `EditorChrome` around it. OneCode had its own bar
for one stage — a mark, a title input, a save state, four buttons — and every
one of those already existed in the chrome the document and the workbook wear.
`tests/test_frontend_guards.py` parameterises over all three so a fourth editor
cannot grow its own.

## OneLegal (`onelegal`)

Two clauses, in `legal.py`: one in the terms saying this is an editor and not
an execution environment, and one in the acceptable-use policy about secrets in
files shared by link. Registered through `onelegal.registry.clause`, which is
how every module writes into the agreements.

## OneAI

See `ai.md`. The short version is that OneCode declares no feature of its own.

## Reached by

Nothing imports this module. `languages.is_code` is read by OneCloud when it
decides what a file is, and that is the only call across the seam.
