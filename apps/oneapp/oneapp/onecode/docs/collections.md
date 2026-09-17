# Collections

**OneCode owns no doctypes.** That is the whole design and not an omission:
a code file is a `File`, and a project is a folder of them with an
`onecode.json` inside it. There is no `Project` row to keep in step with the
folder, no second place a rename has to land, and no migration when somebody
moves a project into another folder.

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `File` | Frappe core, extended by OneCloud | Every `.py`, `.js`, `.yaml` and every project folder. Versions, sharing, the bin and the WebDAV mount come with it. |
| `File Version` | OneCloud | A code file's history, the same one a document has. |
| `Drive Access` | OneCloud | Who a file or a project folder is shared with. |
| `Web Page` | Frappe core | Not used yet. It is where a served project will land — see the README's "what is not built", item 1. |

## The declaration

`onecode.json` is the only OneCode-specific data on disk, and it is a file
rather than a row. `manifest.KEYS` is its whole vocabulary:

    name     what the project is called
    route    the path it claims, checked by routes.validate
    engine   a key in engines.ENGINES, resolved to a pinned import map
    entry    the module the page loads first
    reads    doctypes the page may read
    calls    whitelisted methods the page may call

Six keys, closed. A key not in `KEYS` is refused rather than ignored, because
a manifest that silently drops what it does not understand is a manifest that
lies about what a page can do.
