# AI

## Two features declared here

| Key | Label | What it does |
| --- | --- | --- |
| `doc.compose` | Writing in a document | A passage at the cursor, from what is around it. |
| `doc.fill` | Filling in a document | A whole document written from its own headings. |

**Two rather than one**, and the reason is money: a credit hold is priced off
the declared ceiling, and holding a document's worth to write one paragraph
would make the cursor verb unusable.

## What is not declared here

**The writing verbs.** Improve, proofread, shorten, lengthen, change tone —
those are `oneai/text.py`'s, declared once for the whole product and shared
with mail and the spreadsheet. A document is text; it needs no verbs of its
own for text.

`intelligence.rewrite`, `write_into`, `fill_document` and `suggest_sources` are
the endpoints this module exposes over them.

## Where it lives on screen, and why there is no button

All of it is in the document's own menu, beside Print and Page setup.

It was a button of its own in the chrome — *"Write with OneAI"*, beside the
title — and it came out when OneAI stopped being something each app had its own
door to. The panel knows which window is in front, it can put a passage into
this document through `useAiInsert`, and a second branded button beside the
title was a second answer to "where is the AI". The workbook had already
settled it, and the words and their order are `shared/lib/ai/verbs.js` so the
three editors cannot drift.

## What a model may ask a document to be

`actions.py` declares one action kind and its tool: a document. So the
assistant can offer to *write one* — a card, with a title and an outline — and
the write happens when a person presses Apply, landing a `File` of kind `Doc`
and a `Doc Body` beside it. The same row a person typing would have made; there
is no AI-written store.

## Why the model reads `html` and not the JSON

`Doc Body` stores both. A model reading a document reads the rendered HTML,
along with search, the preview, print, export and a mail body — which is the
whole reason the second blob exists. The alternative is a ProseMirror
implementation in Python, six times.

## What a tenant configures

The two features above appear in `OneAI Settings` like any other: on or off, a
model, its options, and a `prompt_addendum` where the customer's own wording
is appended to ours. A workspace that writes in a particular house style says
so there, once, and both features carry it.

## Not built

**Reading a document into the search index.** `oneai/index.py` embeds a record,
and a document's prose is not a record. A `Doc Body` has `html` sitting right
there, which makes this module the easiest first step for the gap
`onestorage/docs/ai.md` names — and it has not been taken.
