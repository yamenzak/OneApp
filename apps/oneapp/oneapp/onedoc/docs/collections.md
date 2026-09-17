# Collections

**A document is a `File`.** That one decision is what makes the rest cheap: it
lands in a folder, is shared with a colleague, is handed to a stranger on an
expiring link, goes in the bin and comes back, hangs off a quotation through
`attached_to_doctype`, and counts in the storage meter — and none of that is
written here. What is here is the only thing a `File` cannot hold, which is
what the document says.

## Owned

| Doctype | What it is |
| --- | --- |
| `Doc Body` | What the document says. `doc` (the File), `content` (ProseMirror JSON), `html` (what the editor rendered it to), `settings` (the page setup), `byte_size`, `head_seq`. |

One doctype. Everything else is borrowed, and that is the shape the module is
arguing for.

## Two blobs, and only one is authoritative

`content` is the JSON the editor reads back. `html` is what the editor rendered
it to, sent alongside on the same save.

The second exists so that search, the preview, print, export, a mail body and —
since the AI arc — a model reading the document do not each need a ProseMirror
implementation in Python. It is derived and it is stored, which is a
duplication taken deliberately and worth knowing about: if they ever disagree,
`content` is the document.

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `File` (kind `Doc`) | Frappe core, via OneCloud | The document's identity. No bytes — they are produced on export. |
| `File Version` | OneCloud | An earlier draft. Shared with workbooks, because a version of a document and a version of a workbook turned out to be the same five columns. |
| `Bound Record` | The engine | A record this document reads. Keyed, so the prose names `quotation.grand_total` and the record behind the key can be swapped without touching a word. |
| `DocShare`, `File Link` | OneCloud | Sharing, unchanged. |

## Three things open in this editor and only two are documents

    Doc kind            prose in a `Doc Body` row, no object, bytes on export
    .txt / .md / .csv   a real object in R2, edited in place — text.py
    anything else       downloaded, not opened

**A plain-text file has no second store.** A `.md` in the Drive is a real
object, and editing one reads that object and writes it back under the same
key: somebody who writes a README here expects the thing they download to *be*
that README, not an export of it.

`own_object` is the one line without which none of that works. Every empty file
starts as the same single newline, so Frappe hands them all one object and the
first edit to any of them would rewrite all of them.
