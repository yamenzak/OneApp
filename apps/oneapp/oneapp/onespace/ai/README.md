# The AI spine

Everything in this product that asks a model something goes through this
directory. Mail's summary, the writing verbs in a composer, a card offering to
put a date in somebody's diary, the search index behind "which record is this
email about", a document written from its own headings, a plan of changes to a
spreadsheet — six surfaces, one spine, and the surfaces know almost nothing
about each other.

`docs/AI.md` is the map of the whole arc and the argument for its order. This
file is about the spine itself: what it is made of, and the decisions in it
that cost something.

## The model

**A feature is a declaration, not a call site.** `@ai_feature` says what a
piece of code wants — a capability, a system prompt, the most it may spend —
and gets back a callable with the workspace's policy already applied. What
follows from the declaration is everything nobody wants to write six times: a
row in the workspace's settings with a model picker filtered to models that
can do the job, a credit hold before the call and a settlement after it, the
customer's own wording appended to the prompt, and an entry in the operator's
registry. A module that wanted to pick a model, price a call or hold credits
would be a module that has to be kept in step with five others.

**A run is a background job a browser watches.** `begin(fn, …)` enqueues,
hands back an id, and publishes what arrives over the socket the bench already
runs. It is not a held-open request, and the reason is arithmetic: a
generation is two to forty seconds, a shard has four gunicorn workers, and a
page with three summaries on it would stop the site.

**A suggestion is a kind.** A model cannot write. What it can do is put a card
in front of somebody — this record, these fields, that value — and the doing
happens later, in a request a person made by pressing Apply, through the same
path they would have gone through by hand.

**An embedding is a feature like any other.** Retrieval is not a special case
with its own plumbing: `index.embed` is declared, priced and switched off the
same way the writing verbs are.

## The layers, in import order

    features     declaring one, and the registry the settings page reads
    settings     which model, whose ceiling, whether it is switched on
    meter        what a call actually consumed, in the provider's own units
    gateway      one metered call, whole or in frames
    tools        a Python function as a tool a model may call
    conversation ask, execute, append, ask — bounded by turns and credits
    streaming    a run: enqueued, published, cached, cancellable
    text         the writing verbs, declared once for the whole product
    index        an embedding per record, and a top-k over them
    actions      a suggestion, and the moment a person says yes
    kinds        the three suggestions that belong to no module
    proposing    the tools a model asks for one with
    written      which values a model wrote, and when they stopped being its

A layer may use the ones above it and never the ones below.
`tests/test_ai_layering.py` keeps that honest, along with the two rules below.

## The decisions that cost something

**The spine knows nothing about a module.** Not mail, not documents, not
sheets. A module declares its own features and its own tools, and reaches the
spine through the decorator and `streaming.begin`. `kinds.py` is the single
exception — a diary entry is `onecalendar`'s and there is nowhere else for the
handler to live — and the guard names it one file at a time. The alternative
was tried in miniature and lost: the assistant's record edit lived in
`chat/changes.py` under a doctype called Chat Change, and the moment mail
wanted to offer a diary entry that would have meant three more tables, three
more cards and three more Apply endpoints, no two agreeing what Proposed
means.

**A module never calls `gateway.call`.** The hold, the model choice and the
ceiling are applied by the callable the decorator injects; a module reaching
past it would be a module spending credits nobody priced. The three things a
module *may* use the gateway for — `unstreamed`, `deltas_to` and its two
exception classes — are a closed list in the guard.

**Streaming is ambient, not an argument.** `gateway.deltas_to(sink)` stores
the sink on `frappe.local`, and `gateway.call` reads it. The alternative was
threading a sink through every feature signature, which would have meant every
feature choosing whether it can stream — and a tool loop threading it through
each turn as well, so the feature written before streaming existed is the one
that silently does not.

**Realtime is best-effort, so the text is also written down.** Every flush
updates a cached copy and the final frame carries the whole answer, because a
browser whose wifi blinked has missed frames it can never get back. A dropped
frame would otherwise be a sentence with a hole in it that nothing ever fixes.

**Two ceilings, kept apart.** `limits` prices one call and is what the control
plane holds against; `run` bounds how many calls one ask may become. A turn is
a whole call with its own hold, so `max_credits` bounds one turn and nothing
bounds ten — `max_run_credits` is the figure that actually bounds an ask.

**No scheduler drains anything.** Nothing here runs on a timer, watches an
inbox or acts on its own. A proposal nobody answered is a question nobody
answered, and the only two things that resolve one are a person pressing Apply
and a person pressing Discard. That is a decision rather than a limitation,
and what would change it is a queue somebody can inspect and stop.

## What is not built

In the order it blocks.

1. **The assistant still answers inside the request.** `chat/assistant.send`
   predates the run spine and holds a gunicorn worker for the length of a
   generation. It is the one exception the layering guard names.
2. **No structured output.** The gateway has no `responseSchema`, so the two
   features that need JSON — `mail.link` and `sheet.plan` — parse it out of
   whatever the model wrote, tolerantly.
3. **An embedding index no scheduler maintains.** A build starts because
   somebody switched the feature on or pressed Rebuild, chains until it has
   caught up, and stops. A record saved while the feature was off stays
   unindexed until the next build.
4. **Module documents.** `onemail/`, `onedoc/` and `onesheet/` have no
   `README.md` yet, so the half of each module that is AI is documented here
   and in `docs/AI.md` rather than beside it — see `docs/ARCHITECTURE.md`,
   "Where a document goes".
