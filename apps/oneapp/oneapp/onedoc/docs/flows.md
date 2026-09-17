# Flows

The layers, in import order:

    body          opening one and saving one, and the store contract versions read
    text          the plain-text files beside them, read and written in place
    export        one self-contained HTML file, which is also the file_url
    templates     one to start from, which is a flag on a file
    fields        a record's field inside the prose
    typography    how a document is set, in the one place both renderings read
    writing       making one, copying one, throwing one away
    intelligence  what a document asks a model for
    actions       the one thing a model may ask a document to be, and its tool

## Making one — `writing.py`

`make` writes a `File` of kind `Doc` and a `Doc Body` beside it. `make_text`
makes a plain-text file with its own object. `duplicate` copies both.

`templates.set_template` marks a file as one to start from — a flag on a file
rather than a table, so a template is a document somebody decided to reuse.

## Opening and saving — `body.py`

`get_doc` returns the `content`, the `html` and the `settings`. `save_doc`
takes all three back. `head_seq` is what the version contract reads.

**The body is ProseMirror JSON saved whole, not a CRDT update.**
`frappe/writer` saves a base64 Yjs update because their editing model is
peer-to-peer over a signalling server they host; a shard here runs one
GIL-bound Python process, and a signalling server per shard is a second
runtime. The same argument `docs/SHEETS.md` makes, and the same answer.

What live editing did get built runs Yjs in the *browsers*, over a relay inside
the socketio the bench already starts — `docs/COLLABORATION.md`. Convergence
happens between the people in the room; the thing on disk is the thing anybody
else reads.

## A field in the prose — `fields.py`

Typing a quotation's total into its covering letter makes a second copy that
goes stale the first time the quotation changes, and the person who finds out
is the customer holding a letter whose total disagrees with the schedule
stapled behind it.

So a token stores `source.field` **and carries the last answer with it** — the
name so `refresh` can ask again, the answer so a reader with no permission on
the record still sees a document rather than a row of blanks. A block stores
`source.table` and renders as a real table.

**`settle` freezes what the tokens say now.** A sent document stops asking,
because a quotation the customer received is a fact about a day rather than a
view onto a record that has moved on. One press, not automatic — only a person
knows which day that was.

## Exporting — `export.py`

`download` produces one self-contained HTML file, and **that exporter is also
the `file_url`**. `File.validate` refuses a row whose `file_url` names nothing,
and the framework's own escape hatch for a produced file is a `/api/method/`
URL — so following a document's URL gets you the file the row claims to be,
which is true rather than merely convenient.

The large reason is that a document has to leave. Somebody mails the scope of
works to a client who has never heard of this workspace, and what should land
in their inbox is a document, not a link to a login.

`printable` is the print engine's input; `download_markdown` and `as_markdown`
are the other direction.

## Setting the type — `typography.py`

Two renderings of every document: the editor laying prose out in a page-width
column so somebody can see where pages break, and the print engine's, where
they actually break. Set in different type they break in different places, and
a paged document that repaginates the moment you print it is worse than one
that never claimed to be paged.

So the numbers are written once, as **plain CSS rather than Tailwind classes**,
because the exported file is opened where no stylesheet of ours exists.

## Editing a plain-text file — `text.py`

`get_text` reads the object; `save_text` writes it back under the same key. No
`Doc Body`, no export step, no second copy.

## Asking a model — `intelligence.py`

See `ai.md`.
