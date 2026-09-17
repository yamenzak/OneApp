# AI

## Three features declared here

| Key | Label | What it does |
| --- | --- | --- |
| `mail.summarise` | Summarising a thread | Reads a conversation and says the short version. |
| `mail.reply` | Suggesting a reply | Drafts one, from the thread. |
| `mail.file` | Filing a message | **Ranks** candidate records for a message nothing else could place. |

The third is the interesting one in the whole product's AI story.

## Filing, and why ranking is not choosing

`linking.py` applies the workspace's rules: a message from this address, about
this reference, belongs to that record. When no rule can tell, `filing.py` asks
a model — and what it asks for is a **ranking of candidates with a reason**,
not an answer.

The candidates come from `oneai/index.py`'s embeddings, so the model is picking
among records that already look related rather than naming one from nothing.
What lands is a `Communication Link` with `custom_link_by` saying a model made
it, which is what lets the UI offer to undo exactly that class of link and
leave the ones a person made alone.

`docs/DOCUMENT-MAIL.md` is the argument for why this lane is worth its cost.

## There is one AI door, and it is not in the composer

**`Write with OneAI` used to sit in the composer's own row of controls**,
beside Attach a file. It went the way the writer's did: with OneAI a window
that opens over whatever you are doing, a branded button inside each surface is
a second answer to "where is the AI", and two answers is one too many.

What replaced it is the work.

**Mail says what it has open.** A conversation is a claim, the way a document
and a workbook are — `shared/lib/ai/context.js` on the way out,
`oneai/chat/context.py` resolving it back through `mailbox.thread` on the way
in, **so a claim cannot reach a message its claimant could not open**.

Unlike a file, the thread arrives as **text** rather than as an id with a tool
to fetch it. A conversation is a few thousand characters and every question
asked with one open is about what it says, so a round trip to find that out
would be a turn spent on something already known.

**What somebody is typing back goes with it** while the composer is open, which
is what makes "make my reply shorter" mean the reply.

**And the composer takes an answer.** It registers as the insert target
(`shared/lib/ai/insert.js`), so the panel draws **Insert** and the words land
above the signature and the quoted history — the same place a suggested reply
lands, with the same offer to undo.

## What is not declared here

The writing verbs. Improve, proofread, change tone — `oneai/text.py`'s, shared
with the document editor and the spreadsheet. `intelligence.rewrite` is this
module's door onto them.

## What a tenant configures

The three features above, in `OneAI Settings`: on or off, a model, options, and
a `prompt_addendum`. Filing is the one a cautious workspace switches off and
keeps the rules — which works, because `linking.py` is rules and `filing.py` is
the fallback, and the fallback is the feature.
