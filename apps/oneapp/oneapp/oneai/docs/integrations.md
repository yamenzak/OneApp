# Integrations

## The rule this module is built on

**The spine imports no module.** `oneai/gateway.py` knowing about mail would be
a gateway mail could break, and the sixth surface would find half of it already
shaped around a mailbox. `tests/test_ai_layering.py` holds every file beside
`chat/` to it, statically, over the import statements.

**The assistant may**, and must: answering "what is in my drive" means reading
the drive. That line used to come free from the directories — the spine was
`onespace/ai/` and the assistant `onespace/chat/` — and since stage 3b both are
OneAI's, so the guard names `oneai/chat/` as the surface.

**`kinds.py` is the one exception in the spine**, named one file at a time, and
its own docstring carries the argument: it holds the suggestion kinds for the
framework's own nouns, and a diary entry is OneCalendar's.

## The direction every module goes

A module declares its own features and its own tools and **knows nothing about
the gateway**. A module calling `gateway.call` would be a module spending
credits nobody priced, so `GATEWAY_SURFACE` in the layering test is the small
set a module may touch and `@ai_feature` is everything else.

| Module | What it declares |
| --- | --- |
| `onedoc` | Writing a document from its headings, and the editor's verbs |
| `onesheet` | A plan of changes to a workbook |
| `onemobility`, `onehr` | Assistant tools of their own, through `toolbox` |

## The control plane

**The model catalogue and the money.** `AI Model`, `AI Model Price`,
`AI Feature` and `AI Usage Record` are `oneapp_control`'s. A tenant caches the
catalogue and the registry in `OneAI Settings` rather than fetching per request:
choosing a model must work while the control plane is unreachable, and pricing a
call must not depend on a network hop in the middle of one.

`oneapp_control/ai/model_options.py` derives what else a model takes, from
Cloudflare's input schema and Google's published voice table. The workspace's
answers sit on its feature row, and the two only ever meet through
`options.resolved`.

## Cloudflare

**AI Gateway sits in front of every provider**, so a tenant site never holds a
provider key — the keys live in the gateway itself and a site holds only a
gateway token.

Three files here are **adapted from `frappe/flow_client`** and each carries the
notice, the origin and the licence in its header: `tools.py` (a Python
signature described to a model as JSON Schema), `transcript.py` (one message
shape and the two provider shapes it becomes) and `conversation.py` (ask, run
what came back, ask again). The model they call is ours, because Flow's own is
a provider row a tenant could edit. `tests/test_vendoring.py` holds the three
obligations that came with them.

## Frappe

**`doc_events["*"]`** twice: `index.on_save`/`on_delete` to keep the search
index in step, and `written.forget_changed`/`forget_deleted` to take the mark
off a value a person rewrote. Both are on `*` because the nouns they are about
belong to apps we do not own.

**The socket the bench already runs** carries a streaming run. No second
runtime.

## The engine (`onespace`)

`spaceview.records.save` is what an Apply goes through — the same function the
record form posts to, so a suggestion cannot reach a field a person could not.
`spaceview.resolve` is what the assistant's context and its tools resolve
through, so it sees exactly what its asker could click to.

## OneLegal

The AI Addendum's content is this module's clauses plus the product-level text.
A new provider is a line in `oneai/legal.py`, which changes the document hash,
which fails `tests/test_legal.py`, which makes telling customers a step
somebody takes.

## ERPNext and HRMS

Nothing directly. What the assistant reads of them it reads through their
spaces' screens.
