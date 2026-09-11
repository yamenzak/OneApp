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
These are not seven features; they are one feature with a verb argument, and
making them one is what stops mail, the writer and the sheet from drifting into
three voices. One settings row, one model picker, one place a workspace's own
wording is appended, one place the prompt is tuned when it turns out to be too
chatty.

The surface calls it with the text, the verb, and a sentence about where the
text came from — "this is an email to a customer", "this is a cell in a column
of unit prices" — which is what makes the same verb produce a business reply in
one place and three words in another.

### 2.3 A suggested action, which is not a record edit

`chat/changes.py` proposes one thing: a save to a record on a screen. What this
arc needs is the same shape with other verbs — put this in the calendar, make a
task of it, file this message against that quotation. The failure mode to avoid
is obvious once stated: three more tables, three more cards, three more Apply
endpoints, and no two of them agreeing about what "pending" means.

So `changes.py` generalises into **one proposal with a kind**. A kind declares
how to preview itself and how to apply itself, and applying always runs as the
person who pressed the button, through the ordinary endpoint that a human doing
it by hand would have gone through. The existing record save becomes the first
registered kind rather than the only thing that exists.

This is the piece that carries the arc past mail, docs and sheets, because
every future "AI noticed something and suggests you do X" is a new kind and
nothing else.

### 2.4 Retrieval, which is not a prompt

"Relate this to the right document, better than Frappe does" is not a prompting
problem and cannot be solved by a better system message.
`docs/DOCUMENT-MAIL.md` §6 already sets out the shape and it does not change
here: **retrieve deterministically, then rank with a model.** Never "here is an
email, which of our records is it about?" — that is a hallucinated foreign key
on a financial document.

The half that is missing is the retrieval. The catalogue already syncs and
prices a `Text Embeddings` capability and nothing uses it. An embedding per
record and per document turns "which of four thousand projects" into a top-k,
and it is useful to search long before it is useful to linking.

`onemail/linking.py` already writes `custom_linked_by` on every link — `thread`,
`text` or `manual` today — and the column was given a fourth value in mind from
the start. This is that fourth value.

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
is not negotiable and it is not a placeholder for a later "auto-apply" setting.

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
| A suggested action | `onespace/ai/actions.py`, kinds registered by each module |
| Retrieval | `onespace/ai/index.py` |
| The glow | `shared/components/AiGlow.vue` |
| The verb menu | `shared/components/AiMenu.vue` |
| Mail's own features | `onemail/intelligence.py` |
| The writer's own tools | `onedoc/writing.py` |
| The sheet's own tools | `onesheet/writing.py` |

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
   reader's thread summary.
3. **Suggested actions.** `changes.py` generalised into `ai/actions.py` with a
   kind registry; the record save becomes a kind; `calendar.event`, `todo` and
   `link.record` join it. Mail proposes them off a thread.
4. **Retrieval, then linking.** An embedding per record and per document, a
   top-k, then `mail.link` ranking over a candidate set built by rules —
   `docs/DOCUMENT-MAIL.md` §6 B1, with `custom_linked_by='model'`.
5. **The writer.** Tools that write into the document where the cursor is,
   streamed; fill-out-this-document; associating documents.
6. **The sheet.** Tools that write cells, formulas, formats and new sheets;
   the glow on a range while it fills; associating documents to a workbook.
7. **Docs, guards, suites and a browser pass.**

The order is not negotiable in one place: **1 and 2 before anything else**.
Every stage after them is a consumer of the same run, the same glow and the
same verb menu, and building a consumer first is how three of them end up
different.

---

## 6. What this does not do

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
