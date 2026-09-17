# Flows

## Declaring a feature

    @ai_feature("text.summarise", label="Summaries",
                capability="Text Generation", system=SUMMARY_SYSTEM,
                description="Reads something long and says the short version.")
    def summarise(...): ...

`features.py` turns the declaration into a callable with the workspace's policy
already applied. What follows from it and nobody writes six times: a row in the
workspace's settings with a model picker filtered to models that can do the job,
a credit hold before the call and a settlement after it, the customer's own
wording appended to the prompt, and an entry in the operator's registry.

The five declared here: `chat.workspace`, `index.embed`, `text.rewrite`,
`text.summarise`, `ai.vision.read`. Modules declare their own — mail's three,
the document editor's two, the spreadsheet's one — and know nothing about the
gateway.

## Asking — the spine, in order

1. **`features`** resolves the workspace's answers: is it on, which model, what
   options, what wording to append.
2. **`meter`** holds credits before the call. A call nobody can pay for does
   not start.
3. **`gateway`** makes the request. Cloudflare's AI Gateway sits in front, so a
   tenant site never holds a provider key.
4. **`conversation`** loops where a feature is a loop, bounded by a turn count
   and a credit budget.
5. **`meter`** settles afterwards against what was actually used.

## Watching it arrive — `streaming.py`

**A run is a background job a browser watches**, and the reason is arithmetic:
a generation is two to forty seconds, a shard has four gunicorn workers, and a
page with three summaries on it would stop the site.

`begin(fn, …)` enqueues and hands back an id. What arrives is published over
the socket the bench already runs, and cached, so a dropped frame is not a lost
generation. `stop(id)` ends one; `result(id)` fetches what a browser missed.

## Proposing, and applying — `proposing.py`, `kinds.py`, `actions.py`

**No tool writes.** The `propose_` tools record what would change and return
"waiting"; a `OneAI Suggestion` row is what sits between the asking and the
doing.

`kinds.py` is a small class per kind with six methods — check, describe, apply
and the rest — over the framework's own nouns: a record, a date in a diary, a
task, a file. It is the single file in the spine allowed to import a module,
and `tests/test_ai_layering.py` names it.

`actions.apply_suggestion` is a request a **person** makes by pressing Apply.
It runs as them, through `spaceview.records.save` — the same function the record
form posts to, with the same field allowlist and the same validation.
`actions.discard_suggestion` is the other half.

## Marking — `written.py`

Hooked on `doc_events["*"]`. After a model writes a value, a `OneAI Written
Value` row marks it and the sparkle appears beside the field's label. When a
person changes that value, `forget_changed` drops the mark.

`_marked_doctypes` is cached, because the hook is on `*` and without it every
save on the site would pay a query to learn that nothing on that doctype was
ever marked. The cache is *not* written when the table is missing — that state
is real during a migrate, and a cached empty set would outlive it.

## Retrieval — `index.py`

`embed` is an `@ai_feature` like any other: declared, priced and switchable.
Retrieval is not a special case with its own plumbing. `on_save` and `on_delete`
keep the index in step; `rebuild` and `coverage` are the operator's view of it.

## The assistant — `chat/`

One `@ai_feature` that loops:

`toolbox` (what it may read — every tool a wrapper over an endpoint the SPA
already calls, so the assistant sees exactly what its asker could click to) →
`context` (where the question was asked from: the space bound onto the tools and
out of their schemas, the screen and record said once in the system prompt, both
resolved through the same checks a click goes through) → `session` (a
conversation on disk, and as the transcript a provider is sent) → `assistant`
(the declaration, the system prompt, and the endpoints).
