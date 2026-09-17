# Integrations

## OneCloud (`onestorage`)

**The whole of the way in, and most of the model.** A document is a `File`, so
folders, sharing, links, the bin, quota and the WebDAV mount all belong to
OneCloud and this module restates none of them. OneWriter is the Drive landed
on `place=documents` — not a second application over a second store.

`File Version` is shared with OneWorkbook. A `Writer Version` table of its own
would have been five columns that already existed. What made it easy is that
both stores answer the same three questions — what is the head, read it, put
this back — so `shared/versions.py` asks through a small contract and neither
module knows about the other.

## Frappe

**`File`**, through OneCloud's override. **`on_trash`** is hooked so a binned
document takes its `Doc Body` with it.

**The `/api/method/` URL** is the framework's own escape hatch for a produced
file, and it is what makes a document's `file_url` its exporter.

## ERPNext and HRMS

**Through `Bound Record`, and only by key.** A covering letter reads
`quotation.grand_total` without this module knowing what a Quotation is: the
prose names a *key*, the binding says which record that key points at, and the
record behind a key can be swapped without touching a word.

That indirection is the integration. A document that hard-named a doctype would
be a document that only works in one space.

## OneWorkbook (`onesheet`)

Two editors, one chrome, one version store, and one argument: the person who
prices the job in the sheet is the person who writes the letter, and that
adjacency is most of the reason both exist here rather than in Word and Excel.

`EditorChrome` is shared with OneCode as well;
`tests/test_frontend_guards.py` parameterises over all three so a fourth
editor cannot grow its own bar.

## OneMail

A document is what a scope of works is, and mail is how it leaves. The export
being a self-contained HTML file rather than a link is that requirement
written down: what lands in a stranger's inbox should be a document.

## The engine (`onespace`)

* **`printing.py`** takes `export.printable`.
* **The desk** — OneWriter is a window with its own dock tile, its own mark
  colour and its own corner. There are no tabs inside it: this product's tab
  bar is the dock, and it already draws a face per thing.
* **The record shell** — a record's Files tab reaches a document through
  `onestorage/linked.py`.
* **`collab.py` and the socketio relay** — `docs/COLLABORATION.md`.

## OneLegal

Nothing of its own. What a document is and where its bytes live are OneCloud's
clauses.

## OneAI

`ai.md`. Two features declared here; the verbs are the spine's.
