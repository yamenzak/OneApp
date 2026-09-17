# AI

**OneCloud declares no `@ai_feature` of its own**, and it is the module OneAI
reaches into most.

## What OneAI does here

**The assistant reads the Drive.** `oneai/chat/toolbox.py` wraps
`onestorage.query` and `onestorage.reading` — the same functions the browser
calls — so "what did we send them last month" is answerable, as the asker,
through the asker's own permissions. This is the largest single use of the rule
in `permissions.md`: the assistant sees exactly what its asker could click to,
and it holds here without this module knowing the assistant exists.

**A file is a suggestion kind.** `oneai/kinds.py` can propose making one,
renaming one, moving one — the framework's own nouns — and the write happens
when a person presses Apply.

**Pictures are read.** `oneai/vision.read` is an `Image Understanding` feature
and what it reads is a `File`: a photograph, a scan, a screenshot.

**A written document lands here.** When the assistant writes a document, the
result is a `File` with `custom_kind` of Document and a `Doc Body` beside it —
the same row a person typing would have made. There is no AI-written store.

## The seam, stated the way the layering test states it

The spine may not import a module, so **none of the above is in this module's
direction**. `onestorage` imports nothing from `oneai`. What crosses is
`toolbox` reaching in, and `kinds` reaching in, and both are on OneAI's side of
the line where `tests/test_ai_layering.py` can see them.

## What a tenant configures

Nothing here. Every dial is OneAI's — the model, the per-feature switch, the
ceiling. A workspace that switches off text generation loses the assistant's
ability to talk about files along with everything else, which is the correct
blast radius for one switch.

## Not built

**Searching a file's contents.** `oneai/index.py` embeds a *record* — a title
and its fields — and a file's bytes are not a record. So "which document
mentions the retention clause" is not answerable, and the answer is per kind:
a Document has a `Doc Body` that could be embedded today, a PDF needs
extraction first, and a workbook is a question about cells rather than prose.
It is the biggest thing missing from this module's AI story and the one with
the clearest first step.
