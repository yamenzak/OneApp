# OneDoc

Documents — the prose half of what a workspace writes. A scope of works, a
covering letter, a method statement, a README. Opened from the Drive, from a
record's Files tab, or from a link somebody sent to a person with no account.

Who opens it: whoever writes the letter. Which in a small contractor is the
same person who priced the job in the sheet next door, and that adjacency is
most of the argument for this module existing rather than the customer using
Word.

`docs/WRITER.md` is why this is built at all, what `frappe/writer` gave us and
what its collaboration would have cost. `docs/COLLABORATION.md` is the live
half. This file is the module.

---

## 1. The model

**A document is a `File`.** That one decision is what makes the rest cheap: it
lands in a folder, is shared with a colleague, is handed to a stranger on an
expiring link, goes in the bin and comes back, hangs off a quotation through
`attached_to_doctype`, and counts in the storage meter — and none of that is
written here. What is here is the only thing a `File` cannot hold, which is
what the document says.

| | |
|---|---|
| **File** (kind `Doc`) | The document's identity. No bytes; they are produced on export. |
| **Doc Body** | What it says: ProseMirror JSON, the HTML the editor rendered it to, and the page setup. |
| **File Version** | An earlier draft. Shared with sheets, because a version of a document and a version of a workbook turned out to be the same five columns. |
| **Bound Record** | A record this document reads. Keyed, so the prose names `quotation.grand_total` and the record behind the key can be swapped without touching a word. |

**Two blobs go in on every save and only one is authoritative.** `content` is
the JSON the editor reads back; `html` is what the editor rendered it to, sent
alongside. The second exists so that search, the preview, print, export, a mail
body and — since the AI arc — a model reading the document do not each need a
ProseMirror implementation in Python.

Three things open in the same editor and only two of them are documents:

    Doc kind            prose in a `Doc Body` row, no object, bytes on export
    .txt / .md / .csv   a real object in R2, edited in place — `text.py`
    anything else       downloaded, not opened

---

## 2. The layers

Server, in import order:

    body          opening one and saving one, and the store contract versions read
    text          the plain-text files beside them, read and written in place
    export        one self-contained HTML file, which is also the `file_url`
    templates     one to start from, which is a flag on a file
    fields        a record's field inside the prose — live in a draft, frozen when sent
    typography    how a document is set, in the one place both renderings read
    writing       making one, copying one, throwing one away
    intelligence  what a document asks a model for

Browser, at `frontend/src/modules/onedoc/`: `Doc.vue` is the page and
`DocEditor.vue` the editor, with the outline, the settings dialog, the
long-text dialog, the toolbar declaration, and `lib/` — the record-field nodes,
the live-document wiring, and the plain-text-to-blocks conversion a model's
answer goes through.

---

## 3. The decisions that cost something

### The body is ProseMirror JSON saved whole, not a CRDT update

`frappe/writer` saves a base64 Yjs update, because their editing model is
peer-to-peer over a signalling server they host. Ours saves the document. A
shard runs one GIL-bound Python process and a signalling server per shard is a
second runtime — the same argument `docs/SHEETS.md` makes and the same answer.

What that costs is spelled out in `docs/COLLABORATION.md`: the live editing
that did get built runs Yjs in the *browsers* over a relay inside the
socketio the bench already starts, and the stored form is still HTML and JSON.
Convergence happens between the people in the room; the thing on disk is the
thing anybody else reads.

### Versions are `File Version`, shared with sheets

A `Writer Version` table of its own would have been five columns that already
existed. What made this easy is that both stores answer the same three
questions — what is the head, read it, put this back — so `shared/versions.py`
asks them through a small contract and neither module knows about the other.

### A field in the prose is a name, not a number

Typing a quotation's total into its covering letter makes a second copy that
goes stale the first time the quotation changes, and the person who finds out
is the customer holding a letter whose total disagrees with the schedule
stapled behind it.

So a token stores `source.field` and carries the last answer with it — the
name so it can be refreshed, the answer so a reader with no permission on the
record still sees a document rather than a row of blanks. A block stores
`source.table` and renders as a real table.

And **a sent document stops asking.** `settle` freezes what the tokens say
now, because a quotation the customer received is a fact about a day rather
than a view onto a record that has moved on. That is one press and it is not
automatic, because only a person knows which day that was.

### The type is written down once, in CSS both renderings read

There are two renderings of every document: the editor laying prose out in a
page-width column so somebody can see where pages break, and the print
engine's, where they actually break. Set in different type they break in
different places — and a paged document that repaginates the moment you print
it is worse than one that never claimed to be paged. `typography.py` is those
numbers, once, as plain CSS rather than Tailwind classes, because the exported
file is opened where no stylesheet of ours exists.

### Export is HTML, self-contained, and is also the `file_url`

`File.validate` refuses a row whose `file_url` names nothing, and the
framework's own escape hatch for a produced file is a `/api/method/` URL. So a
document's `file_url` is its exporter — true rather than convenient, since
following it gets you the file the row claims to be.

The large reason is that a document has to leave. Somebody mails the scope of
works to a client who has never heard of this workspace, and what should land
in their inbox is a document, not a link to a login.

### A plain-text file has no second store

A `.md` in the Drive is a real object, and editing one reads that object and
writes it back under the same key. Somebody who writes a README here expects
the thing they download to *be* that README, not an export of it. `own_object`
is the one line without which none of it works — every empty file starts as
the same single newline, so Frappe hands them all one object and the first edit
to any of them rewrites all of them.

### What a model may do here, and where it lands

The writing verbs are `onespace/ai/text.py`'s, shared with mail and everything
else. What this module owns is writing something that was not there:
`doc.compose` for a passage at the cursor, `doc.fill` for a whole document
written from its own headings. Two features rather than one because a credit
hold is priced off the declared ceiling, and holding a document's worth to
write one paragraph would make the cursor verb unusable.

All of it arrives **in the prose**, as ordinary ProseMirror transactions — not
into a panel with a Use button. That is what makes replacing a whole document
safe to offer: the editor's own history has it, one Undo puts it back, and
nothing is saved until the person leaves it there. Fill is still the one action
that asks first, and it sits in the document menu rather than beside Improve,
because putting "replace everything" one item under "Improve" is how somebody
loses an afternoon.

The material a model is given is the document's prose — read from the stored
HTML, not the JSON — plus the records it reads, described by
`ai/index.describe`. The same description the search index embeds, because
"this record as the text that says what it is about" is one question.

---

## 4. What is not built

In the order it blocks.

1. **Comments on a selection.** `FileChat` is a conversation about the *file*;
   a note pinned to a paragraph is the thing people ask for next and it needs
   an anchor that survives an edit, which is the hard half.
2. **Export to `.docx`.** HTML is what leaves today. A customer who wants to
   edit it in Word gets a file Word opens and reflows, which is worse than a
   real one and better than a PDF.
3. **Suggesting mode.** Track-changes over a CRDT-less store is its own
   design, and the live editing built in `docs/COLLABORATION.md` stage 3 is
   the piece it would build on.
4. **Headers and footers per page.** The letter head is drawn on every sheet;
   anything else — a page number, a running title — is not.
