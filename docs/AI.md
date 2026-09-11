# AI, everywhere, on one spine

Mail, the document editor and the spreadsheet each want the same six or seven
things — summarise this, improve this, proofread this, change its tone, write
this for me, and here are three things you could do about it. Building those
three times gives three prompts to tune, three settings pages, three ways of
showing that something is being written, and three arguments about what a model
is allowed to change. This is the map for building them once.

It is deliberately not a list of features. The features are the easy half and
are named at the end; what decides whether this scales is the five pieces under
them, and four of the five already exist.

---

## 1. What is already built, and is not a prototype

The AI layer went in during Phase 5 and has been carrying the workspace
assistant since. Everything below is in the code today.

**`@ai_feature` is the whole declaration.** An app says what it wants once —
capability, system prompt, ceilings, whether the workspace may switch it off,
optionally a pinned model, optionally tools and a turn limit — and gets a row
in the workspace's AI settings with a model picker filtered to models that can
do the job, a credit hold before every call and a settlement after it, the
customer's own wording appended to the prompt and never replacing it, and an
entry in the operator's registry. `onespace/ai/features.py`.

**The gateway meters rather than estimates.** Hold a ceiling, make the call,
settle the units the model itself reported. Provider keys live in Cloudflare AI
Gateway, so a tenant site never holds one. `onespace/ai/gateway.py`.

**Tools are a Python signature.** `@tool` reads type hints into JSON Schema;
`Tool.bind()` fills in what the *caller* knows — the asking user, the space, the
session — and takes those arguments out of the schema, so the model has no word
for them and cannot be talked into changing one. `onespace/ai/tools.py`.

**A loop exists.** `conversation.run` asks, executes what came back, appends the
results and asks again, every turn a whole metered call, bounded by `max_turns`
and `max_run_credits`. `onespace/ai/conversation.py`.

**A model may ask for a write and may not perform one.** `chat/changes.py`: the
two `propose_` tools record what *would* be written — with the current values
captured beside it — and the write happens later, in a request a person made by
pressing Apply, through the same endpoint the form posts to. A record that moved
in between is refused rather than overwritten.

**What a model wrote is marked.** `onespace/ai/written.py` holds a row per
value, carrying the feature, the model and who asked; the mark expires the
moment a person rewrites that value.

That is a great deal of the hard part. The five pieces this arc adds are what
sits on top.

---

## 2. The five pieces

### 2.1 Streaming, which the gateway cannot do

`gateway._execute` is one `requests.post` and one JSON body. That is right for
a summary nobody is watching and wrong for every feature in this arc: a
paragraph being written into a document, a reply being drafted, a column being
filled. Waiting eleven seconds at a spinner and then having the answer appear
whole is a worse product than watching it arrive, and it is a worse product for
a reason that is not taste — a person can stop a bad answer three words in.

Three things have to be true and each is smaller than it sounds.

**The provider half.** Google's `:streamGenerateContent?alt=sse` returns the
same payload shape in frames, and the last frame carries `usageMetadata`. So
metering does not change at all: accumulate the frames, meter the final one,
settle exactly as now. `requests` already streams with `stream=True`.

**The transport half.** There is no new infrastructure to build. A tenant site
publishes with `frappe.publish_realtime(event, message, user=...)`, which goes
to redis, which the bench's socketio process is already subscribed to, which
emits into the room that user's browser is already in. The collaboration relay
(`apps/oneapp/realtime/handlers.js`) is not the right vehicle — it is for
peer-to-peer traffic inside a document room, and this is the server talking to
one person.

**The worker half.** An HTTP request that holds a gunicorn worker open for the
length of a generation is the thing to avoid, and it is exactly what the chat
endpoint already refuses to do for the same reason. So a streamed feature is
enqueued: the browser posts, gets a run id back immediately, and subscribes.
The job publishes deltas and one final frame.

### 2.2 The verbs, declared once

Summarise, improve, proofread, shorten, expand, change tone, and write-this.
Making them shared is what stops mail, the writer and the sheet drifting into
three voices: one place a workspace's own wording is appended, one place the
prompt is tuned when it turns out to be too chatty.

Not one feature, though, and not seven. **One feature per cost shape.** A hold
is priced off the declared ceiling *before* the call is made, so a single
feature big enough to summarise a thirty-message thread would reserve a
thirty-message thread's worth of credits every time somebody asked it to fix a
comma — on a workspace near its balance, a rewrite refused for want of credits
it was never going to spend. So `text.rewrite` works on what is on screen and
`text.summarise` reads something long; the six verbs that differ only in
wording are one feature, and the one that differs in size is another.

The surface calls it with the text, the verb, and a sentence about where the
text came from — "this is an email to a customer", "this is a cell in a column
of unit prices" — which is what makes the same verb produce a business reply in
one place and three words in another. That sentence is written by the module,
never by the reader: it travels as the gateway's `note`, which lands after our
instructions and after the workspace's addendum.

Three rules hold across everything built on this. **The verb is a key, never a
sentence** — a browser sends `improve` and the wording behind it is
server-side, because an endpoint that took the instruction would be an endpoint
that took the prompt. **The tone is a closed list**, since it goes straight
into the instruction and an open one is a prompt with a hole in it. And **what
comes back is plain text** — no HTML, no Markdown — because every surface
downstream owns a document model of its own and markup from a model is markup
somebody has to sanitise before it goes near one.

### 2.3 A suggested action, which is not a record edit

`chat/changes.py` proposes one thing: a save to a record on a screen. What this
arc needs is the same shape with other verbs — put this in the calendar, make a
task of it, file this message against that quotation. The failure mode to avoid
is obvious once stated: three more tables, three more cards, three more Apply
endpoints, and no two of them agreeing about what "pending" means.

So `changes.py` generalised into **one proposal with a kind**
(`onespace/ai/actions.py`). A `Kind` is a small class with six methods — check
it, read what is there now, write the heading, write the rows, say whether it
has moved since, do it — and applying always runs as the person who pressed
the button, through the ordinary endpoint a human doing it by hand would have
gone through: a record through `spaceview.records.save`, an event through
`onecalendar.diary.save_event`. The record save became the first registered
kind rather than the only thing that exists.

Three kinds ship with the spine because none of them is about mail, documents
or sheets: `record.save`, `calendar.event`, `task`. A module registers its own
through an `ai_actions` hook, the same shape `ai_features` uses.

This is the piece that carries the arc past mail, docs and sheets. Every
future "AI noticed something and suggests you do X" is a handler and nothing
else — no second table, no second card, no second answer to what Proposed
means.

### 2.4 Retrieval, which is not a prompt

"Relate this to the right document, better than Frappe does" is not a prompting
problem and cannot be solved by a better system message.
`docs/DOCUMENT-MAIL.md` §6 already sets out the shape and it does not change
here: **retrieve deterministically, then rank with a model.** Never "here is an
email, which of our records is it about?" — that is a hallucinated foreign key
on a financial document.

The half that was missing is the retrieval. The catalogue already synced and
priced a `Text Embeddings` capability and nothing used it. `onespace/ai/index.py`
is an embedding per record, refreshed on save, and a top-k over it — useful to
search long before it is useful to linking.

`onemail/linking.py` already wrote `custom_linked_by` on every link — `thread`,
`text` or `manual` — and the column was given a fourth value in mind from the
start. `model` is that fourth value, and `onemail/filing.py` is what writes it.

Four things about the retrieval half are decisions rather than details, and
each is argued at length in the module's own docstring:

* **The scan is a capped full scan in pure Python.** MariaDB has no vector
  index and the honest way to get one is a vector database, which is a second
  runtime. Measured instead: 2,000 rows of 768 dimensions dot in about 60ms,
  because vectors are stored base64 float32 already normalised so cosine is a
  dot product. `MAX_SCAN` is that measurement.
* **A digest of the embedded text stops a re-embed.** Without it every save on
  the site is a metered call.
* **The corpus is `sync.granted_doctypes()`** — what a space exposes, not what
  the site holds. Embedding a workspace's `Version` rows is paying to index a
  log.
* **A vector belongs to the model that made it.** Two models' vectors are not
  comparable at all, so the scan filters on `model_key` and a workspace that
  changes model gets an index that rebuilds rather than one that ranks noise.

And one about the ranking half. `DOCUMENT-MAIL.md` §6 describes this running
on arrival; it runs when somebody presses a button on a thread instead, for
three reasons that are all about *who is asking*: `OneSpace Suggestion` is
`if_owner`, so a card the system user made on inbound mail would be invisible
to everybody; running as the asker is what makes "records this reader may
open" the permission filter rather than a rule this module implements; and a
filing pass over a morning's inbox is a bill nobody agreed to. The
deterministic half — `from_thread`, `from_text` — still runs on every message,
automatically and free.

### 2.5 The glow

One component, not one per surface. A streamed answer has exactly three shapes
on screen and every surface in the product is one of them:

* **a block** — a paragraph arriving where a summary goes;
* **an inline span** — a cell, a subject line, a field;
* **an overlay** — a pane whose whole contents are being rewritten.

So: one component, three modes, one animation, one set of tokens, and it
respects `prefers-reduced-motion` because a shimmer that cannot be turned off
is an accessibility bug rather than a flourish.

---

## 3. What a model may and may not do

Four rules, and they are the same four everywhere in this arc.

**A tool runs as the person asking.** Every tool wraps an endpoint the SPA
already calls, so what a model can read is what its asker could have opened.
There is no second permission implementation, because a second implementation
is a second set of bugs and only one of them is the one anybody tests.

**A model never writes to a record.** It proposes, and a person applies. This
is not negotiable and it is not a placeholder for a later "auto-apply"
setting. The property that keeps it true is asserted rather than remembered:
`tests/test_ai_actions.py` reads the source of every tool in the toolbox and
fails if one of them ever calls an apply.

**A model writes to a document or a sheet only where a person put the cursor.**
This is the one place the rule bends, and it bends because a document is not a
financial record: a paragraph that arrives where you asked for one is undoable
in one keystroke and is visible while it happens. Everything a model writes
there is marked by `ai/written.py` and the mark expires when the text is edited.

**Nothing is sent anywhere a workspace did not agree to.** Every call goes
through the declared feature, the declared capability and the workspace's own
model choice. There is no endpoint that takes a model name.

---

## 4. Where each piece lives

| Piece | Where |
|---|---|
| Streaming a call | `onespace/ai/gateway.py` (`stream=`), `onespace/ai/streaming.py` |
| The run, over realtime | `onespace/ai/streaming.py`, `shared/lib/ai/stream.js` |
| The verbs | `onespace/ai/text.py` |
| A suggested action | `onespace/ai/actions.py`, `ai/kinds.py`, `ai/proposing.py` |
| Retrieval | `onespace/ai/index.py` |
| Ranking a shortlist into a link | `onemail/filing.py` |
| The glow | `shared/components/AiGlow.vue` |
| The verb menu | `shared/components/AiMenu.vue` |
| Mail's own feature | `onemail/intelligence.py` |
| The writer's own features | `onedoc/intelligence.py` |
| The sheet's own features | `onesheet/intelligence.py` |

The rule the table encodes: **the spine is in `onespace/ai/` and knows nothing
about mail, documents or sheets; a module declares its own features and its own
tools and knows nothing about the gateway.** A module that has to import the
gateway to do its job means the spine is missing something.

---

## 5. The stages

1. **The spine streams.** Streaming in the gateway, `ai/streaming.py`, the
   realtime channel, `onEvent` on the SPA socket, `useAiRun`, `AiGlow.vue`.
   Nothing a customer can see: the first thing to use it is stage 2, and a
   probe feature shipped only to exercise the suite would be a row in every
   workspace's AI settings that nothing in the product calls.
2. **The verbs.** `ai/text.py`, `AiMenu.vue`. Wired first into the mail
   composer — help me write, improve, proofread, change tone — and the mail
   reader's thread summary and suggested reply.
3. **Suggested actions.** `changes.py` generalised into `ai/actions.py` with a
   kind registry, `ai/kinds.py` holding the three the spine ships, and
   `ai/proposing.py` holding the four tools that ask. Mail's `mail.notice`
   reads a thread and offers what is waiting in it. Linking a message to a
   record is deliberately not among them — that is stage 4, because it is a
   retrieval problem and offering it here would be offering a guess.
4. **Retrieval, then linking.** `ai/index.py` — an embedding per record,
   refreshed on save, a capped scan, a top-k. Then `onemail/filing.py`:
   `mail.link` ranking over a shortlist built by rules (what this
   correspondent's mail is already about, plus the nearest vectors), writing
   through `linking.add` with `custom_linked_by='model'` above its confidence
   threshold and a `mail.link` suggestion card below it —
   `docs/DOCUMENT-MAIL.md` §6 B1.
5. **The writer.** `onedoc/intelligence.py`. The shared verbs on a selection,
   `doc.compose` for a passage at the cursor, and `doc.fill` for a whole
   document written from its own headings — three shapes, and three features
   for the two that are the document's own, because a hold is priced off the
   declared ceiling. All three stream into the prose rather than into a
   panel, which is also what makes replacing a document safe: it arrives as
   ProseMirror transactions, one Undo puts it back, and nothing is saved
   until the person leaves it there. The material a model is given is the
   document's prose plus the records it reads, described by `index.describe`
   — the same description the search index embeds, because "what this record
   is about, as text" is one question. And associating documents is
   retrieval without ranking: `suggest_sources` embeds the prose, and the
   nearest records this reader can open appear in the record panel for them
   to pick.
6. **The sheet.** `onesheet/intelligence.py`, and the one surface where the
   answer is not text. The browser evaluates formulas and the server stores
   what it computed (`docs/SHEETS.md` §1), so a server that wrote
   `=SUM(D2:D20)` would be writing a workbook whose stored values disagree
   with it. `sheet.plan` therefore answers with a **plan** — `tab`, `set`,
   `format`, `name`, a closed four — which is validated here against the
   workbook that exists (a tab that is not there, a reference that does not
   parse, a style key nothing declares, a rectangle bigger than the store
   holds) and applied in the browser through `setCell`, `applyToRange` and
   `_pushEditOp`: the same calls the toolbar uses, so one Undo takes the whole
   plan back and a colleague in the workbook watches it arrive. The material
   is a *sample* of the workbook as values rather than formulas — a model
   reading `=C2*D2` cannot tell a broken reference from a working one. The
   writing verbs are deliberately not here: improve and proofread are about
   prose, and the useful thing in a grid is "write this formula", which is
   what `set` is.
7. **Docs, guards, suites and a browser pass.**
   `onespace/ai/README.md` is the spine's own document — its layers, the
   decisions that cost something, and what is not built.
   `tests/test_ai_layering.py` is the part that does not go stale: the spine
   imports no module (`kinds.py` is the one exception and has to say why), a
   module uses the gateway only for what the decorator cannot do, every
   module declaring a feature is in the `ai_features` hook and every module
   registering a kind is in `ai_actions`, every feature declares the ceiling
   it is held against, a feature with tools bounds the whole run, and no
   whitelisted endpoint runs a feature inline — `chat/assistant.send` is the
   one exception, named in the guard, and the first thing in §6.

The order is not negotiable in one place: **1 and 2 before anything else**.
Every stage after them is a consumer of the same run, the same glow and the
same verb menu, and building a consumer first is how three of them end up
different.

---

## 6. What this does not do

**The assistant still answers inside the request.** `chat/assistant.send`
predates the run spine: it refuses to stream and holds a gunicorn worker for
the length of a generation, which is the thing `streaming.py` exists to stop.
Moving it onto `begin` is the first thing owed here, and
`tests/test_ai_layering.py` names it as the single exception so a second one
cannot appear quietly.

**There is no structured output.** The gateway sends no `responseSchema`, so
the two features whose answer is JSON — `mail.link` and `sheet.plan` — find
it in whatever the model wrote and parse it tolerantly. That works and is
tested; it is not the same as being told by the provider that the shape is
guaranteed.

**It does not agentically act.** Nothing in this arc runs on a schedule,
watches an inbox, or does anything nobody asked for. Every call in it starts
with a person pressing something. That is a decision rather than a limitation,
and the thing that would change it is a queue somebody can inspect and stop,
which does not exist yet.

**It does not train on anything.** There is no fine-tuning, no memory across
sessions beyond a stored chat transcript, and no workspace's data in any
prompt but its own.

**It does not replace the assistant.** `chat/assistant.py` stays what it is —
the one conversational feature, with the whole workspace in reach. What this
arc adds is the opposite shape: small, local, one-shot verbs on the thing
already on screen, which is what people actually reach for while working.
